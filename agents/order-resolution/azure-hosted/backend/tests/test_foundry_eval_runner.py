from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.foundry_eval_runner import (
    _count_blocking_result_rows,
    _load_report_cases,
    _load_report_queries,
    _release_eval_passed,
)


def test_load_report_queries_selects_configured_canonical_cases(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps({"id": "low", "input": "Low-risk request"}),
                json.dumps({"id": "high", "input": "High-risk request"}),
            ]
        ),
        encoding="utf-8",
    )

    assert _load_report_queries(dataset, ["low", "high"]) == [
        "Low-risk request",
        "High-risk request",
    ]


def test_load_report_queries_rejects_missing_configured_case(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(json.dumps({"id": "low", "input": "Low-risk request"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing from"):
        _load_report_queries(dataset, ["high"])


def test_load_report_cases_preserves_case_id_order(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps({"id": "second", "input": "Second request"}),
                json.dumps({"id": "first", "input": "First request"}),
            ]
        ),
        encoding="utf-8",
    )

    assert _load_report_cases(dataset, ["first", "second"]) == [
        {"id": "first", "input": "First request"},
        {"id": "second", "input": "Second request"},
    ]


def test_count_blocking_result_rows_sums_failed_and_errored_counts() -> None:
    assert (
        _count_blocking_result_rows(
            {
                "completed": 3,
                "failed": 1,
                "errored": "2",
                "failed_rows": 4.0,
            }
        )
        == 7
    )


def test_release_eval_passed_requires_completed_status_zero_failures_and_completed_captures() -> (
    None
):
    captures = [
        {"scenario_id": "ord-1001-low-risk-late", "terminal_status": "completed"},
        {"scenario_id": "ord-1004-damaged-approve", "terminal_status": "completed"},
        {"scenario_id": "ord-1009-high-amount", "terminal_status": "completed"},
    ]

    assert (
        _release_eval_passed(
            run_status="completed",
            result_counts={"completed": 3, "failed": 0, "errored": 0},
            captures=captures,
        )
        is True
    )
    assert (
        _release_eval_passed(
            run_status="failed",
            result_counts={"completed": 3, "failed": 0, "errored": 0},
            captures=captures,
        )
        is False
    )
    assert (
        _release_eval_passed(
            run_status="completed",
            result_counts={"completed": 3, "failed": 1},
            captures=captures,
        )
        is False
    )
    assert (
        _release_eval_passed(
            run_status="completed",
            result_counts={"completed": 3, "failed": 0},
            captures=[
                *captures[:2],
                {"scenario_id": "ord-1009-high-amount", "terminal_status": "escalated"},
            ],
        )
        is False
    )
