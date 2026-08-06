from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from evals.foundry_trace_eval import _criteria, _load_evidence


def test_load_evidence_returns_unique_conversation_ids(tmp_path: Path) -> None:
    evidence = tmp_path / "hosted-smoke-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-04T16:00:00Z",
                "conversation_ids": ["conv-1", "conv-1", "conv-2"],
            }
        ),
        encoding="utf-8",
    )

    generated_at, conversation_ids = _load_evidence(evidence)

    assert generated_at == datetime(2026, 8, 4, 16, 0, tzinfo=UTC)
    assert conversation_ids == ["conv-1", "conv-2"]


def test_load_evidence_rejects_missing_conversations(tmp_path: Path) -> None:
    evidence = tmp_path / "hosted-smoke-evidence.json"
    evidence.write_text(json.dumps({"generated_at": "2026-08-04T16:00:00Z"}), encoding="utf-8")

    with pytest.raises(ValueError, match="conversation_ids"):
        _load_evidence(evidence)


def test_criteria_uses_conversation_message_mapping() -> None:
    assert _criteria(["task_completion"], "underwriting-gpt-4-1-mini") == [
        {
            "type": "azure_ai_evaluator",
            "name": "task_completion",
            "evaluator_name": "builtin.task_completion",
            "initialization_parameters": {"model": "underwriting-gpt-4-1-mini"},
            "data_mapping": {"messages": "{{item.messages}}"},
        }
    ]
