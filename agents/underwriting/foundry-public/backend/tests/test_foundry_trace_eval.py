from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL, HostedWorkflowEnvelope
from evals.foundry_trace_eval import (
    _criteria,
    _criterion_result_counts,
    _evidence_path,
    _is_trace_readiness_error,
    _is_transient_poll_error,
    _load_evidence,
    _load_release_evidence,
    _result_counts,
    _should_retry_empty_evaluation,
)


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
            "initialization_parameters": {"deployment_name": "underwriting-gpt-4-1-mini"},
            "data_mapping": {"messages": "{{item.messages}}"},
        }
    ]


def test_result_counts_normalizes_foundry_sdk_model() -> None:
    class Counts:
        errored = 0
        failed = 0
        passed = 1
        total = 1
        skipped = 0

    assert _result_counts(Counts()) == {
        "errored": 0,
        "failed": 0,
        "passed": 1,
        "total": 1,
        "skipped": 0,
    }


def test_criterion_result_counts_detects_nested_evaluator_errors() -> None:
    assert _criterion_result_counts(
        [
            {
                "results": [
                    {
                        "name": "task_completion",
                        "passed": True,
                        "status": "completed",
                        "sample": {"error": None},
                    },
                    {
                        "name": "coherence",
                        "passed": None,
                        "status": "error",
                        "sample": {
                            "error": {
                                "code": "FAILED_EXECUTION",
                                "message": "Principal does not have access.",
                            }
                        },
                    },
                ]
            }
        ]
    ) == {
        "errored": 1,
        "failed": 0,
        "passed": 1,
        "total": 2,
        "skipped": 0,
    }


def test_evidence_path_prefers_current_release_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "release-smoke.json"
    monkeypatch.setenv("FOUNDRY_SMOKE_EVIDENCE_FILE", str(current))

    assert _evidence_path(tmp_path, "tracked-sample.json") == current


def test_release_evidence_must_be_fresh_and_match_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = tmp_path / "hosted-smoke-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "release_id": "release-001",
                "release_started_at": "2026-08-04T16:00:00Z",
                "generated_at": "2026-08-04T16:01:00Z",
                "conversation_ids": ["conv-1"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RELEASE_ID", "release-001")
    monkeypatch.setenv("FOUNDRY_RELEASE_STARTED_AT", "2026-08-04T16:00:00Z")

    generated_at, ids, release_id, started_at = _load_release_evidence(
        evidence,
        max_age_seconds=600,
        now=datetime(2026, 8, 4, 16, 2, tzinfo=UTC),
    )

    assert generated_at == datetime(2026, 8, 4, 16, 1, tzinfo=UTC)
    assert ids == ["conv-1"]
    assert release_id == "release-001"
    assert started_at == datetime(2026, 8, 4, 16, 0, tzinfo=UTC)


def test_evaluation_retry_is_narrowly_limited_to_empty_or_malformed_polling() -> None:
    assert _should_retry_empty_evaluation(
        status="completed",
        result_counts={"total": 0},
        error=None,
    )
    assert not _should_retry_empty_evaluation(
        status="failed",
        result_counts={"total": 0},
        error={"code": "Unauthorized"},
    )
    trace_readiness_error = {
        "code": "UserError",
        "message": 'No trace data found for the provided conversation id(s) ["conv-1"].',
    }
    assert _is_trace_readiness_error(trace_readiness_error)
    assert _should_retry_empty_evaluation(
        status="failed",
        result_counts={"total": 0},
        error=trace_readiness_error,
    )
    assert not _is_trace_readiness_error(
        {"code": "UserError", "message": "The evaluation configuration is invalid."}
    )
    assert _is_transient_poll_error(json.JSONDecodeError("empty", "", 0))
    assert not _is_transient_poll_error(RuntimeError("service failure"))


def test_eval_config_references_existing_dataset_and_trace_evidence() -> None:
    root = _backend_root()
    config = yaml.safe_load((root / "eval.yaml").read_text(encoding="utf-8"))

    assert config["name"] == "underwriting-public-smoke"
    assert config["dataset"]["local_uri"] == ".foundry/datasets/underwriting-smoke.jsonl"
    assert (root / config["dataset"]["local_uri"]).is_file()
    assert (root / config["foundry"]["trace_evaluation"]["evidence_file"]).is_file()
    assert config["foundry"]["evaluators"] == ["task_completion", "coherence"]


def test_smoke_dataset_uses_hosted_workflow_start_envelopes_for_happy_and_retry_paths() -> None:
    dataset_path = _backend_root() / ".foundry" / "datasets" / "underwriting-smoke.jsonl"
    records = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(records) == 2

    retry_flags: list[bool] = []
    run_ids: list[str] = []
    for record in records:
        payload = json.loads(record["query"])
        assert payload["protocol"] == HOSTED_WORKFLOW_PROTOCOL
        envelope = HostedWorkflowEnvelope.from_dict(payload)
        assert envelope.action == "start"
        assert envelope.application is not None
        assert envelope.crash_after_executor is None
        assert "decision" in record["expected_behavior"].lower()
        retry_flags.append(envelope.fail_risk_once)
        run_ids.append(envelope.workflow_run_id)

    assert retry_flags == [False, True]
    assert len(set(run_ids)) == len(run_ids)


def test_hosted_smoke_evidence_sample_tracks_mode_and_conversation_ids() -> None:
    evidence_path = _backend_root() / ".foundry" / "results" / "hosted-smoke-evidence.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    generated_at, conversation_ids = _load_evidence(evidence_path)

    assert generated_at.tzinfo is UTC
    assert payload["mode"] in {"happy", "retry", "crash-resume"}
    assert payload["workflow_run_id"].startswith("run-")
    assert isinstance(payload["decision"], str) and payload["decision"]
    assert conversation_ids == payload["conversation_ids"]
