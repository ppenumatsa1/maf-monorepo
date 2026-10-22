from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from evals.foundry_eval_runner import (
    _TERMINAL_EVAL_STATUSES,
    _build_conversation_data_source,
    _build_conversation_trace_testing_criteria,
    _is_transient_eval_poll_error,
    _load_hosted_e2e_evidence,
    _parse_hosted_e2e_evidence,
    _release_mode,
    _resolve_input_path,
    _should_retry_empty_evaluation,
    _validate_result_counts,
    _validate_testing_criteria_results,
)

_NOW = datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc)


def _valid_evidence() -> dict[str, object]:
    return {
        "release_id": "release-1",
        "release_started_at": "2026-07-23T14:40:00Z",
        "started_at": "2026-07-23T14:45:00Z",
        "generated_at": "2026-07-23T14:50:00Z",
        "conversation_ids": ["conv-low", "conv-high", "conv-damaged"],
        "low_risk_thread_id": "conv-low",
        "high_risk_thread_id": "conv-high",
        "damaged_item_thread_id": "conv-damaged",
    }


def test_parse_hosted_e2e_evidence_returns_release_conversations() -> None:
    release_started_at, started_at, generated_at, conversation_ids, release_id = (
        _parse_hosted_e2e_evidence(
            _valid_evidence(),
            max_age_seconds=3600,
            now=_NOW,
        )
    )

    assert release_started_at == datetime(2026, 7, 23, 14, 40, tzinfo=timezone.utc)
    assert started_at == datetime(2026, 7, 23, 14, 45, tzinfo=timezone.utc)
    assert generated_at == datetime(2026, 7, 23, 14, 50, tzinfo=timezone.utc)
    assert conversation_ids == ["conv-low", "conv-high", "conv-damaged"]
    assert release_id == "release-1"


def test_parse_hosted_e2e_evidence_accepts_named_scenario_ids() -> None:
    evidence = _valid_evidence()
    del evidence["conversation_ids"]

    conversation_ids = _parse_hosted_e2e_evidence(
        evidence,
        max_age_seconds=3600,
        now=_NOW,
    )[3]
    assert conversation_ids == ["conv-low", "conv-high", "conv-damaged"]


def test_parse_hosted_e2e_evidence_rejects_duplicate_scenario_ids() -> None:
    evidence = _valid_evidence()
    evidence["conversation_ids"] = ["conv-low", "conv-high", "conv-high"]

    with pytest.raises(ValueError, match="three unique conversation IDs"):
        _parse_hosted_e2e_evidence(
            evidence,
            max_age_seconds=3600,
            now=_NOW,
        )


def test_parse_hosted_e2e_evidence_rejects_non_utc_timestamps() -> None:
    evidence = _valid_evidence()
    evidence["generated_at"] = "2026-07-23T09:50:00-05:00"

    with pytest.raises(ValueError, match="generated_at must be UTC"):
        _parse_hosted_e2e_evidence(
            evidence,
            max_age_seconds=3600,
            now=_NOW,
        )


def test_parse_hosted_e2e_evidence_rejects_predating_release_window() -> None:
    evidence = _valid_evidence()
    evidence["started_at"] = "2026-07-23T14:39:59Z"

    with pytest.raises(ValueError, match="predates the release window"):
        _parse_hosted_e2e_evidence(
            evidence,
            max_age_seconds=3600,
            now=_NOW,
        )


def test_parse_hosted_e2e_evidence_rejects_stale_evidence() -> None:
    evidence = _valid_evidence()
    evidence["release_started_at"] = "2026-07-23T11:55:00Z"
    evidence["started_at"] = "2026-07-23T12:00:00Z"

    with pytest.raises(ValueError, match="is stale"):
        _parse_hosted_e2e_evidence(
            evidence,
            max_age_seconds=3600,
            now=_NOW,
        )


def test_load_hosted_e2e_evidence_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Hosted E2E evidence is required"):
        _load_hosted_e2e_evidence(
            tmp_path / "does-not-exist.json",
            max_age_seconds=3600,
            now=_NOW,
        )


def test_load_hosted_e2e_evidence_rejects_malformed_json(tmp_path: Path) -> None:
    evidence_path = tmp_path / "hosted-e2e-evidence.json"
    evidence_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="must be valid JSON"):
        _load_hosted_e2e_evidence(
            evidence_path,
            max_age_seconds=3600,
            now=_NOW,
        )


def test_resolve_input_path_prefers_release_evidence_environment(
    tmp_path: Path,
) -> None:
    configured = tmp_path / "release" / "hosted-e2e-evidence.json"

    with patch.dict(
        os.environ,
        {"HOSTED_E2E_EVIDENCE_FILE": str(configured)},
        clear=False,
    ):
        assert (
            _resolve_input_path(
                tmp_path,
                "HOSTED_E2E_EVIDENCE_FILE",
                ".foundry/results/hosted-e2e-evidence.json",
            )
            == configured
        )


def test_empty_evaluation_without_service_error_is_retryable() -> None:
    assert _should_retry_empty_evaluation(
        status="failed",
        result_counts={"total": 0},
        error=None,
    )


def test_evaluation_with_results_is_not_retried() -> None:
    assert not _should_retry_empty_evaluation(
        status="completed",
        result_counts={"total": 3, "failed": 1},
        error=None,
    )


def test_evaluation_service_error_is_not_retried() -> None:
    assert not _should_retry_empty_evaluation(
        status="failed",
        result_counts={"total": 0},
        error={"message": "authorization failed"},
    )


def test_only_json_decode_poll_errors_are_transient() -> None:
    assert _is_transient_eval_poll_error(json.JSONDecodeError("empty response", "", 0))
    assert not _is_transient_eval_poll_error(RuntimeError("service failure"))


def test_conversation_trace_criteria_use_current_model_parameters() -> None:
    criteria = _build_conversation_trace_testing_criteria(
        ["task_completion", "coherence"],
        "gpt-4o-mini",
    )

    assert criteria == [
        {
            "type": "azure_ai_evaluator",
            "name": "task_completion",
            "evaluator_name": "builtin.task_completion",
            "initialization_parameters": {"deployment_name": "gpt-4o-mini"},
            "data_mapping": {"messages": "{{item.messages}}"},
        },
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            "initialization_parameters": {"model": "gpt-4o-mini"},
            "data_mapping": {"messages": "{{item.messages}}"},
        },
    ]


def test_trace_data_source_uses_exact_e2e_conversation_ids() -> None:
    conversation_ids = ["conv-low", "conv-high", "conv-damaged"]

    assert _build_conversation_data_source(conversation_ids) == {
        "type": "azure_ai_trace_data_source_preview",
        "trace_source": {
            "type": "conversation_id_source",
            "conversation_ids": conversation_ids,
        },
    }


def test_terminal_eval_statuses_use_openai_canceled_spelling() -> None:
    assert "canceled" in _TERMINAL_EVAL_STATUSES
    assert "cancelled" not in _TERMINAL_EVAL_STATUSES


def test_release_context_enables_strict_mode_by_default() -> None:
    with patch.dict(os.environ, {"FOUNDRY_RELEASE_ID": "release-1"}, clear=True):
        assert _release_mode()


def test_release_context_cannot_disable_strict_mode() -> None:
    with patch.dict(
        os.environ,
        {
            "FOUNDRY_RELEASE_ID": "release-1",
            "FOUNDRY_EVAL_ENFORCE_PASS": "false",
        },
        clear=True,
    ):
        assert _release_mode()


def test_standalone_report_only_mode_is_preserved() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert not _release_mode()


def test_enforced_result_counts_require_every_conversation_to_pass() -> None:
    with pytest.raises(RuntimeError, match="did not pass every selected E2E conversation"):
        _validate_result_counts(
            {
                "passed": 2,
                "failed": 1,
                "errored": 0,
                "skipped": 0,
                "total": 3,
            },
            expected_total=3,
            enforce_pass=True,
            max_errored=0,
        )


def test_enforced_result_counts_accept_complete_pass() -> None:
    _validate_result_counts(
        {
            "passed": 3,
            "failed": 0,
            "errored": 0,
            "skipped": 0,
            "total": 3,
        },
        expected_total=3,
        enforce_pass=True,
        max_errored=0,
    )


def test_enforced_result_counts_reject_expected_only_items() -> None:
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
            enforce_pass=True,
            max_errored=0,
        )


def test_enforced_testing_criteria_rejects_masked_evaluator_errors() -> None:
    with pytest.raises(RuntimeError, match="coherence produced 2 errored results"):
        _validate_testing_criteria_results(
            [
                {
                    "testing_criteria": "task_completion",
                    "passed": 3,
                    "failed": 0,
                    "errored": 0,
                    "skipped": 0,
                },
                {
                    "testing_criteria": "coherence",
                    "passed": 1,
                    "failed": 0,
                    "errored": 2,
                    "skipped": 0,
                },
            ],
            expected_evaluators=["task_completion", "coherence"],
            expected_total=3,
            enforce_pass=True,
            max_errored=0,
        )


def test_enforced_testing_criteria_accepts_every_evaluator_pass() -> None:
    _validate_testing_criteria_results(
        [
            {
                "testing_criteria": "task_completion",
                "passed": 3,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
            },
            {
                "testing_criteria": "coherence",
                "passed": 3,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
            },
        ],
        expected_evaluators=["task_completion", "coherence"],
        expected_total=3,
        enforce_pass=True,
        max_errored=0,
    )
