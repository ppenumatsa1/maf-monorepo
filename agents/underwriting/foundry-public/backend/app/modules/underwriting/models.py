from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class CheckType(StrEnum):
    RISK = "risk"
    CREDIT = "credit"
    MEDICAL = "medical"
    DRIVING = "driving"


class Decision(StrEnum):
    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    REFER_TO_HUMAN_UNDERWRITER = "REFER_TO_HUMAN_UNDERWRITER"
    DECLINED = "DECLINED"


class OriginChannel(StrEnum):
    API = "api"
    RESPONSES = "responses"
    TEAMS_ACTIVITY = "teams_activity"


class ReviewerOutcome(StrEnum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"


class ReviewerType(StrEnum):
    HUMAN = "human"
    ADMINISTRATIVE = "administrative"
    UNKNOWN_LEGACY = "unknown_legacy"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"


class CardActionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    RELEASED = "released"


@dataclass(slots=True)
class UnderwritingApplication:
    application_id: str
    applicant_name: str
    age: int
    income: float
    requested_coverage: float
    health_disclosures: str
    driving_history: str
    credit_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnderwritingRunRequest:
    workflow_run_id: str
    application: UnderwritingApplication


@dataclass(slots=True)
class CheckRequest:
    workflow_run_id: str
    application: UnderwritingApplication
    check_type: CheckType

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_type"] = self.check_type.value
        return payload


@dataclass(slots=True)
class CheckResult:
    workflow_run_id: str
    application_id: str
    check_type: CheckType
    score: float
    details: dict[str, Any]
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_type"] = self.check_type.value
        return payload


@dataclass(slots=True)
class AllChecksComplete:
    workflow_run_id: str
    application_id: str


@dataclass(slots=True)
class FinalDecisionResult:
    workflow_run_id: str
    application_id: str
    decision: Decision
    rationale: str
    score_breakdown: dict[str, Any]
    idempotency_key: str
    reviewer_outcome: ReviewerOutcome | None = None
    review_checkpoint_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        if self.reviewer_outcome is None:
            payload.pop("reviewer_outcome", None)
            payload.pop("review_checkpoint_id", None)
        else:
            payload["machine_recommendation"] = self.decision.value
            payload["reviewer_outcome"] = self.reviewer_outcome.value
        return payload


@dataclass(frozen=True, slots=True)
class HumanReviewRequest:
    workflow_run_id: str
    application_id: str
    machine_recommendation: Decision


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    workflow_run_id: str
    checkpoint_id: str
    outcome: ReviewerOutcome
    origin_channel: OriginChannel


@dataclass(frozen=True, slots=True)
class ApprovalClaim:
    workflow_run_id: str
    checkpoint_id: str
    request_id: str
    outcome: ReviewerOutcome
    origin_channel: OriginChannel
    reviewer_type: ReviewerType
    acquired: bool
    completed: bool


@dataclass(frozen=True, slots=True)
class CardActionClaim:
    workflow_run_id: str
    checkpoint_id: str
    decision: ReviewerOutcome
    batch_id: str
