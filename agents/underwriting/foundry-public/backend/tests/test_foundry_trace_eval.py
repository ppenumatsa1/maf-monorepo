from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL, HostedWorkflowEnvelope
from evals.foundry_trace_eval import _criteria, _load_evidence


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
            "initialization_parameters": {"model": "underwriting-gpt-4-1-mini"},
            "data_mapping": {"messages": "{{item.messages}}"},
        }
    ]


def test_eval_config_references_existing_dataset_and_trace_evidence() -> None:
    root = _backend_root()
    config = yaml.safe_load((root / "eval.yaml").read_text(encoding="utf-8"))

    assert config["name"] == "underwriting-public-smoke"
    assert config["dataset"]["local_uri"] == ".foundry/datasets/underwriting-smoke.jsonl"
    assert (root / config["dataset"]["local_uri"]).is_file()
    assert (root / config["foundry"]["trace_evaluation"]["evidence_file"]).is_file()
    assert config["foundry"]["evaluators"] == [
        "task_adherence",
        "intent_resolution",
        "relevance",
    ]


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
