from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.foundry_eval_runner import (
    _build_testing_criteria,
    _count_blocking_result_rows,
    _is_transient_eval_poll_error,
    _load_report_cases,
    _load_report_queries,
    _normalize_status,
    _release_eval_passed,
    _validate_result_counts,
    _validate_testing_criteria_results,
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
            result_counts={
                "passed": 3,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
                "expected": 0,
                "total": 3,
            },
            captures=captures,
            evaluators=["task_completion", "coherence"],
            run_details={
                "per_testing_criteria_results": [
                    {
                        "testing_criteria": evaluator,
                        "passed": 3,
                        "failed": 0,
                        "errored": 0,
                        "skipped": 0,
                        "expected": 0,
                    }
                    for evaluator in ("task_completion", "coherence")
                ]
            },
        )
        is True
    )
    assert (
        _release_eval_passed(
            run_status="failed",
            result_counts={"passed": 3, "failed": 0, "errored": 0, "total": 3},
            captures=captures,
            evaluators=["task_completion", "coherence"],
            run_details={},
        )
        is False
    )
    assert (
        _release_eval_passed(
            run_status="completed",
            result_counts={"passed": 2, "failed": 1, "errored": 0, "total": 3},
            captures=captures,
            evaluators=["task_completion", "coherence"],
            run_details={},
        )
        is False
    )
    assert (
        _release_eval_passed(
            run_status="completed",
            result_counts={"passed": 3, "failed": 0, "errored": 0, "total": 3},
            captures=[
                *captures[:2],
                {"scenario_id": "ord-1009-high-amount", "terminal_status": "escalated"},
            ],
            evaluators=["task_completion", "coherence"],
            run_details={},
        )
        is False
    )


def test_normalize_status_supports_current_canceled_spelling_and_enum_values() -> None:
    class Status:
        value = "Completed"

    assert _normalize_status(Status()) == "completed"
    assert _normalize_status("RunStatus.CANCELLED") == "canceled"
    assert _normalize_status("canceled") == "canceled"


def test_strict_overall_counts_reject_quality_failures_and_expected_rows() -> None:
    with pytest.raises(RuntimeError, match="failed=1"):
        _validate_result_counts(
            {
                "passed": 2,
                "failed": 1,
                "errored": 0,
                "skipped": 0,
                "expected": 0,
                "total": 3,
            },
            expected_total=3,
        )
    with pytest.raises(RuntimeError, match="expected=1"):
        _validate_result_counts(
            {
                "passed": 2,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
                "expected": 1,
                "total": 3,
            },
            expected_total=3,
        )


def test_strict_per_evaluator_counts_require_exact_evaluator_set() -> None:
    with pytest.raises(RuntimeError, match="do not match configured evaluators"):
        _validate_testing_criteria_results(
            [
                {
                    "testing_criteria": "task_completion",
                    "passed": 3,
                    "failed": 0,
                    "errored": 0,
                    "skipped": 0,
                    "expected": 0,
                }
            ],
            expected_evaluators=["task_completion", "coherence"],
            expected_total=3,
        )


def test_strict_per_evaluator_counts_reject_masked_evaluator_error() -> None:
    with pytest.raises(RuntimeError, match="coherence did not pass"):
        _validate_testing_criteria_results(
            [
                {
                    "testing_criteria": "task_completion",
                    "passed": 3,
                    "failed": 0,
                    "errored": 0,
                    "skipped": 0,
                    "expected": 0,
                },
                {
                    "testing_criteria": "coherence",
                    "passed": 2,
                    "failed": 0,
                    "errored": 1,
                    "skipped": 0,
                    "expected": 0,
                },
            ],
            expected_evaluators=["task_completion", "coherence"],
            expected_total=3,
        )


def test_testing_criteria_uses_current_evaluator_initialization_parameters() -> None:
    assert _build_testing_criteria(["task_completion", "coherence"], "gpt-evaluator") == [
        {
            "type": "azure_ai_evaluator",
            "name": "task_completion",
            "evaluator_name": "builtin.task_completion",
            "initialization_parameters": {"deployment_name": "gpt-evaluator"},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
            },
        },
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            "initialization_parameters": {"model": "gpt-evaluator"},
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
            },
        },
    ]


def test_malformed_json_poll_is_the_only_retryable_poll_failure() -> None:
    assert _is_transient_eval_poll_error(json.JSONDecodeError("bad", "", 0))
    assert not _is_transient_eval_poll_error(RuntimeError("service unavailable"))
