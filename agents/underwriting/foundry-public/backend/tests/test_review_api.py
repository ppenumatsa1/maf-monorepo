from __future__ import annotations

import asyncio
import inspect
from dataclasses import replace

import pytest
from app.api.v1.routers import underwriting
from app.api.v1.schemas.underwriting import ReviewDecisionRequest
from app.core.config import load_settings
from app.modules.underwriting.models import OriginChannel, ReviewerOutcome, ReviewerType
from app.modules.underwriting.service import LocalReviewDisabledError, UnderwritingService
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class _DisabledReviewService:
    async def decide_review(self, **_kwargs: object) -> dict[str, object]:
        raise LocalReviewDisabledError(
            "Web review decisions are disabled in hosted mode; use the bound Teams review card"
        )


class _Repository:
    engine = None

    def get_workflow_run(self, workflow_run_id: str) -> dict[str, object]:
        return {
            "id": workflow_run_id,
            "status": "PENDING_REVIEW",
            "machine_recommendation": "REFER_TO_HUMAN_UNDERWRITER",
        }

    def list_underwriting_results(self, _workflow_run_id: str) -> list[dict[str, object]]:
        return []

    def get_review_projection(self, workflow_run_id: str) -> dict[str, object]:
        return {
            "workflow_run_id": workflow_run_id,
            "checkpoint_id": "checkpoint-review-api",
            "status": "completed",
            "reviewer_outcome": "DECLINED",
        }


class _LocalWorkflow:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def decide_review(self, **kwargs: object) -> list[object]:
        self.calls.append(kwargs)
        return []


def test_review_api_fails_closed_and_has_no_caller_identity_header(monkeypatch) -> None:
    monkeypatch.setattr(underwriting, "service", _DisabledReviewService())

    with pytest.raises(HTTPException) as forbidden:
        asyncio.run(
            underwriting.decide_review(
                "run-review-api",
                "checkpoint-review-api",
                ReviewDecisionRequest(outcome="APPROVED"),
            )
        )

    assert forbidden.value.status_code == 403
    assert "Teams" in str(forbidden.value.detail)
    assert "reviewer_id" not in inspect.signature(underwriting.decide_review).parameters


def test_spoofed_client_principal_header_cannot_enable_hosted_review(monkeypatch) -> None:
    monkeypatch.setattr(underwriting, "service", _DisabledReviewService())
    app = FastAPI()
    app.include_router(underwriting.router)

    response = TestClient(app).post(
        "/api/v1/underwriting/runs/run-review-api/reviews/checkpoint-review-api",
        headers={"X-MS-CLIENT-PRINCIPAL-ID": "spoofed-reviewer"},
        json={"outcome": "APPROVED"},
    )

    assert response.status_code == 403
    assert "Teams" in response.json()["detail"]


def test_explicit_local_review_uses_server_authorized_administrative_actor(monkeypatch) -> None:
    workflow = _LocalWorkflow()
    service = UnderwritingService(
        settings=replace(
            load_settings(),
            execution_mode="local",
            local_review_mutation_enabled=True,
            local_review_actor_id="local-admin-operator",
        ),
        workflow=workflow,
        workflow_run_repository=_Repository(),
    )
    monkeypatch.setattr(underwriting, "service", service)

    response = asyncio.run(
        underwriting.decide_review(
            "run-review-api",
            "checkpoint-review-api",
            ReviewDecisionRequest(outcome="DECLINED"),
        )
    )

    assert response.machine_recommendation == "REFER_TO_HUMAN_UNDERWRITER"
    assert response.reviewer_outcome == "DECLINED"
    assert workflow.calls == [
        {
            "workflow_run_id": "run-review-api",
            "checkpoint_id": "checkpoint-review-api",
            "outcome": ReviewerOutcome.DECLINED,
            "reviewer_id": "local-admin-operator",
            "origin_channel": OriginChannel.API,
            "reviewer_type": ReviewerType.ADMINISTRATIVE,
        }
    ]


def test_local_review_setting_rejects_hosted_mode_and_missing_actor(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LOCAL_REVIEW_MUTATION", "true")
    monkeypatch.setenv("UNDERWRITING_EXECUTION_MODE", "hosted")
    monkeypatch.setenv("LOCAL_REVIEW_ACTOR_ID", "operator")
    with pytest.raises(RuntimeError, match="non-hosted local execution"):
        load_settings()

    monkeypatch.setenv("UNDERWRITING_EXECUTION_MODE", "local")
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    with pytest.raises(RuntimeError, match="non-hosted local execution"):
        load_settings()

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DB_SCHEMA_MANAGED_EXTERNALLY", raising=False)
    monkeypatch.delenv("LOCAL_REVIEW_ACTOR_ID")
    with pytest.raises(RuntimeError, match="LOCAL_REVIEW_ACTOR_ID"):
        load_settings()
