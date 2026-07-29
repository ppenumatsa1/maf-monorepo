from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.verify_telemetry import (
    _build_telemetry_query,
    _build_trace_ids_query,
    _load_conversation_ids,
    _query_row,
    _trace_ids,
)


def _evidence() -> dict[str, str]:
    return {
        "started_at": "2026-07-29T16:00:00Z",
        "low_risk_thread_id": "conv-low",
        "high_risk_thread_id": "conv-high",
        "damaged_item_thread_id": "conv-damaged",
    }


def test_load_conversation_ids_requires_unique_safe_scenarios(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_evidence()), encoding="utf-8")

    assert _load_conversation_ids(path) == (
        "2026-07-29T16:00:00Z",
        ["conv-low", "conv-high", "conv-damaged"],
    )


def test_load_conversation_ids_rejects_unsafe_identifier(tmp_path: Path) -> None:
    evidence = _evidence()
    evidence["high_risk_thread_id"] = "conv'unsafe"
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="high_risk_thread_id"):
        _load_conversation_ids(path)


def test_telemetry_queries_filter_exact_agent_and_conversations() -> None:
    conversation_ids = ["conv-low", "conv-high", "conv-damaged"]

    telemetry_query = _build_telemetry_query(
        "2026-07-29T16:00:00Z", conversation_ids, "order-resolution-hosted:7"
    )
    trace_ids_query = _build_trace_ids_query(
        "2026-07-29T16:00:00Z", conversation_ids, "order-resolution-hosted:7"
    )

    for query in (telemetry_query, trace_ids_query):
        assert 'dynamic(["conv-low", "conv-high", "conv-damaged"])' in query
        assert 'dynamic(["order-resolution-hosted:7"])' in query
        assert "gen_ai.conversation.id" in query
        assert "gen_ai.agent.id" in query
    assert "arg_max(timestamp, operation_Id)" in trace_ids_query


def test_trace_ids_parses_a_dynamic_json_result() -> None:
    assert _trace_ids(
        {"evaluation_trace_ids": '["trace-damaged", "trace-low", "trace-low"]'}
    ) == ["trace-damaged", "trace-low"]


def test_query_row_accepts_string_columns_from_logs_query_client() -> None:
    class Response:
        status = "Success"
        tables = [
            type(
                "Table",
                (),
                {
                    "columns": ["matched_count", "telemetry_rows"],
                    "rows": [[3, 42]],
                },
            )()
        ]

    class Client:
        def query_resource(self, resource_id: str, query: str, timespan: None) -> Response:
            assert resource_id == "resource-id"
            assert query == "query"
            assert timespan is None
            return Response()

    assert _query_row(Client(), "resource-id", "query") == {
        "matched_count": 3,
        "telemetry_rows": 42,
    }
