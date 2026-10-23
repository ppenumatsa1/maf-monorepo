from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UnderwritingApplicationRequest(BaseModel):
    application_id: str
    applicant_name: str
    age: int
    income: float
    requested_coverage: float
    health_disclosures: str
    driving_history: str
    credit_score: int


class StartRunRequest(BaseModel):
    application: UnderwritingApplicationRequest
    workflow_run_id: str | None = None
    fail_risk_once: bool = False
    fail_credit_randomly: bool = False
    crash_after_executor: str | None = None


class ResumeRunRequest(BaseModel):
    pass


class RunResponse(BaseModel):
    workflow_run_id: str
    status: str
    outputs: list[Any] = Field(default_factory=list)
    machine_recommendation: str | None = None
    reviewer_outcome: str | None = None
    review_checkpoint_id: str | None = None
    review_status: str | None = None


class ReviewDecisionRequest(BaseModel):
    outcome: Literal["APPROVED", "DECLINED"]


class ReviewProjectionResponse(BaseModel):
    workflow_run_id: str
    checkpoint_id: str
    status: str
    machine_recommendation: str
    reviewer_outcome: str | None = None
    requested_at: datetime
    resolved_at: datetime | None = None


class RunHistoryItem(BaseModel):
    workflow_run_id: str
    application_id: str
    applicant_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    final_decision: str | None = None
    machine_recommendation: str | None = None
    reviewer_outcome: str | None = None
    review_status: str | None = None
    review_checkpoint_id: str | None = None
    checkpoint_count: int
    latest_checkpoint_at: datetime | None = None
    resumable: bool
    reviewable: bool = False


class RunHistoryResponse(BaseModel):
    items: list[RunHistoryItem]
    total: int
    limit: int
    offset: int
