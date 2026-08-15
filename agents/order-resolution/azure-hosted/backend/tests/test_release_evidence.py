from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "release"
        / "aggregate-release-evidence.py"
    )
    spec = importlib.util.spec_from_file_location("aggregate_release_evidence", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_artifact(
    *,
    artifact_type: str,
    release_id: str,
    release_started_at: str,
    generated_at: str,
    target: dict[str, str],
    status: str = "passed",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "azure-hosted-release/v1",
        "lane": "azure-hosted",
        "artifact_type": artifact_type,
        "status": status,
        "release_id": release_id,
        "release_started_at": release_started_at,
        "generated_at": generated_at,
        "target": target,
    }


def _build_release_dir(tmp_path: Path) -> Path:
    release_id = "release-001"
    release_started_at = "2026-08-15T17:00:00Z"
    generated_at = "2026-08-15T17:05:00Z"
    subscription_id = "7df95e88-701c-4693-af77-3159f83b558d"
    resource_group = "rg-maf-ora-azure"
    location = "northcentralus"
    target = {
        "azd_env_name": "maf-ora-azure",
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
    }
    release_dir = tmp_path / "release-001"
    evidence_dir = release_dir / "evidence"
    (release_dir / "logs").mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "logs" / "browser-e2e.log").write_text(
        "Hosted browser E2E passed.\n",
        encoding="utf-8",
    )

    _write_json(
        evidence_dir / "release-context.json",
        {
            **_base_artifact(
                artifact_type="release_context",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target=target,
                status="ready",
            ),
            "artifact_files": {
                "source_validation": "source-validation.json",
                "images": "images.json",
                "deployment": "deployment.json",
                "smoke": "smoke.json",
                "domain_e2e": "domain-e2e.json",
                "evaluation": "evaluation.json",
                "telemetry": "telemetry.json",
                "release_evidence": "release-evidence.json",
            },
        },
    )

    _write_json(
        evidence_dir / "source-validation.json",
        {
            **_base_artifact(
                artifact_type="source_validation",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target=target,
            ),
            "checks": [
                {"name": "release-source-validation", "status": "passed"},
                {"name": "bicep-build", "status": "passed"},
            ],
        },
    )

    backend_resource_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        "/providers/Microsoft.App/containerApps/backend-app"
    )
    frontend_resource_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        "/providers/Microsoft.App/containerApps/frontend-app"
    )

    _write_json(
        evidence_dir / "images.json",
        {
            **_base_artifact(
                artifact_type="images",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target=target,
            ),
            "backend": {
                "container_app": "backend-app",
                "resource_id": backend_resource_id,
                "image": "registry.azurecr.io/backend@sha256:" + "a" * 64,
                "image_digest": "sha256:" + "a" * 64,
                "revision": "backend-rev-1",
            },
            "frontend": {
                "container_app": "frontend-app",
                "resource_id": frontend_resource_id,
                "image": "registry.azurecr.io/frontend@sha256:" + "b" * 64,
                "image_digest": "sha256:" + "b" * 64,
                "revision": "frontend-rev-1",
            },
        },
    )

    _write_json(
        evidence_dir / "deployment.json",
        {
            **_base_artifact(
                artifact_type="deployment",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target=target,
            ),
            "deploy_mode": "app_only",
            "api_url": "https://backend.example.com",
            "web_url": "https://frontend.example.com",
            "services": {
                "backend": {
                    "container_app": "backend-app",
                    "resource_id": backend_resource_id,
                    "image": "registry.azurecr.io/backend@sha256:" + "a" * 64,
                    "image_digest": "sha256:" + "a" * 64,
                    "revision": "backend-rev-1",
                    "active_revision": {
                        "name": "backend-rev-1",
                        "active": True,
                        "traffic_weight": 100,
                        "health_state": "Healthy",
                        "running_state": "Running",
                    },
                    "ingress": {"external": False, "fqdn": "backend.example.com"},
                    "target_identity": {
                        "resource_id": backend_resource_id,
                        "managed_identity_type": "SystemAssigned",
                    },
                },
                "frontend": {
                    "container_app": "frontend-app",
                    "resource_id": frontend_resource_id,
                    "image": "registry.azurecr.io/frontend@sha256:" + "b" * 64,
                    "image_digest": "sha256:" + "b" * 64,
                    "revision": "frontend-rev-1",
                    "active_revision": {
                        "name": "frontend-rev-1",
                        "active": True,
                        "traffic_weight": 100,
                        "health_state": "Healthy",
                        "running_state": "Running",
                    },
                    "ingress": {"external": True, "fqdn": "frontend.example.com"},
                    "target_identity": {
                        "resource_id": frontend_resource_id,
                        "managed_identity_type": "SystemAssigned",
                    },
                },
            },
        },
    )

    _write_json(
        evidence_dir / "smoke.json",
        {
            **_base_artifact(
                artifact_type="smoke",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target={
                    "api_url": "https://backend.example.com",
                    "web_url": "https://frontend.example.com",
                },
            ),
            "scenarios": [
                {
                    "scenario_id": "low-risk-no-hitl",
                    "status": "passed",
                    "thread_id": "smoke-apphosted-release-001-low",
                    "workflow_run_id": "smoke-low",
                    "terminal_status": "completed",
                },
                {
                    "scenario_id": "high-risk-hitl-request",
                    "status": "passed",
                    "thread_id": "smoke-apphosted-release-001-high",
                    "workflow_run_id": "smoke-high",
                    "terminal_status": "waiting_approval",
                },
            ],
            "correlations": [
                {"thread_id": "smoke-apphosted-release-001-low", "workflow_run_id": "smoke-low"},
                {"thread_id": "smoke-apphosted-release-001-high", "workflow_run_id": "smoke-high"},
            ],
        },
    )

    domain_scenarios = [
        {
            "scenario_id": "low-risk-no-hitl",
            "order_id": "ORD-1001",
            "transport": "http",
            "status": "passed",
            "thread_id": "domain-e2e-release-001-low-risk-no-hitl",
            "workflow_run_id": "domain-low",
            "terminal_status": "completed",
        },
        {
            "scenario_id": "high-risk-approval-resume",
            "order_id": "ORD-1009",
            "transport": "http",
            "status": "passed",
            "thread_id": "domain-e2e-release-001-high-risk-approval-resume",
            "workflow_run_id": "domain-high",
            "terminal_status": "completed",
        },
        {
            "scenario_id": "damaged-item-approval-resume",
            "order_id": "ORD-1001",
            "transport": "http",
            "status": "passed",
            "thread_id": "domain-e2e-release-001-damaged-item-approval-resume",
            "workflow_run_id": "domain-damaged",
            "terminal_status": "completed",
        },
    ]
    _write_json(
        evidence_dir / "domain-e2e.json",
        {
            **_base_artifact(
                artifact_type="domain_e2e",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target={**target, "api_url": "https://backend.example.com"},
            ),
            "scenarios": domain_scenarios,
            "correlations": [
                {
                    "thread_id": scenario["thread_id"],
                    "workflow_run_id": scenario["workflow_run_id"],
                }
                for scenario in domain_scenarios
            ],
        },
    )

    evaluation_case_ids = [
        "ord-1001-low-risk-late",
        "ord-1004-damaged-approve",
        "ord-1009-high-amount",
    ]
    evaluation_captures = [
        {
            "scenario_id": "ord-1001-low-risk-late",
            "thread_id": "foundry-eval-release-001-ord-1001-low-risk-late",
            "workflow_run_id": "eval-low",
            "terminal_status": "completed",
        },
        {
            "scenario_id": "ord-1004-damaged-approve",
            "thread_id": "foundry-eval-release-001-ord-1004-damaged-approve",
            "workflow_run_id": "eval-damaged",
            "terminal_status": "completed",
        },
        {
            "scenario_id": "ord-1009-high-amount",
            "thread_id": "foundry-eval-release-001-ord-1009-high-amount",
            "workflow_run_id": "eval-high",
            "terminal_status": "completed",
        },
    ]
    _write_json(
        evidence_dir / "evaluation.json",
        {
            **_base_artifact(
                artifact_type="evaluation",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target={**target, "api_url": "https://backend.example.com"},
            ),
            "provider": "foundry",
            "run_status": "completed",
            "provider_status": "completed",
            "case_ids": evaluation_case_ids,
            "evaluators": ["relevance"],
            "result_counts": {"completed": 3, "failed": 0, "errored": 0},
            "captures": evaluation_captures,
            "http_output_capture": "logs/evaluation-http-output.json",
        },
    )

    _write_json(
        evidence_dir / "telemetry.json",
        {
            **_base_artifact(
                artifact_type="telemetry",
                release_id=release_id,
                release_started_at=release_started_at,
                generated_at=generated_at,
                target={**target, "workspace_id": "workspace-123"},
            ),
            "required_scenarios": [
                "low-risk-no-hitl",
                "high-risk-approval-resume",
                "damaged-item-approval-resume",
            ],
            "validated_pairs": [
                {
                    "scenario_id": "low-risk-no-hitl",
                    "thread_id": "domain-e2e-release-001-low-risk-no-hitl",
                    "workflow_run_id": "domain-low",
                    "telemetry_count": 5,
                    "exception_count": 0,
                },
                {
                    "scenario_id": "high-risk-approval-resume",
                    "thread_id": "domain-e2e-release-001-high-risk-approval-resume",
                    "workflow_run_id": "domain-high",
                    "telemetry_count": 7,
                    "exception_count": 0,
                },
                {
                    "scenario_id": "damaged-item-approval-resume",
                    "thread_id": "domain-e2e-release-001-damaged-item-approval-resume",
                    "workflow_run_id": "domain-damaged",
                    "telemetry_count": 6,
                    "exception_count": 0,
                },
            ],
        },
    )

    return release_dir


def test_aggregate_accepts_app_only_release_without_infrastructure(tmp_path: Path) -> None:
    module = _load_module()
    release_dir = _build_release_dir(tmp_path)

    payload = module.aggregate(release_dir)

    assert payload["status"] == "passed"
    assert payload["summary"]["browser_e2e_log"] == "logs/browser-e2e.log"
    assert "infrastructure.json" not in payload["summary"]["validated_artifacts"]
    assert payload["summary"]["telemetry_pairs"] == 3


def test_aggregate_rejects_unexpected_domain_scenario(tmp_path: Path) -> None:
    module = _load_module()
    release_dir = _build_release_dir(tmp_path)
    domain_path = release_dir / "evidence" / "domain-e2e.json"
    payload = json.loads(domain_path.read_text(encoding="utf-8"))
    payload["scenarios"].append(
        {
            "scenario_id": "browser-e2e",
            "order_id": "ORD-1001",
            "transport": "browser",
            "status": "passed",
            "thread_id": "domain-e2e-release-001-browser-e2e",
            "workflow_run_id": "domain-browser",
            "terminal_status": "completed",
        }
    )
    _write_json(domain_path, payload)

    with pytest.raises(ValueError, match="unexpected scenario IDs"):
        module.aggregate(release_dir)


def test_aggregate_rejects_secret_bearing_artifact(tmp_path: Path) -> None:
    module = _load_module()
    release_dir = _build_release_dir(tmp_path)
    deployment_path = release_dir / "evidence" / "deployment.json"
    payload = json.loads(deployment_path.read_text(encoding="utf-8"))
    payload["runtime_connection"] = "AccountKey=super-secret"
    _write_json(deployment_path, payload)

    with pytest.raises(
        ValueError, match="Forbidden key|Forbidden value|Unexpected Foundry hosted-agent field"
    ):
        module.aggregate(release_dir)
