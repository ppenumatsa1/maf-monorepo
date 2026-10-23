from __future__ import annotations

from typing import Any, Protocol

from app.modules.underwriting.copilot import SafeRunExplanationRequest
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.models import (
    ApprovalClaim,
    CardActionClaim,
    OriginChannel,
    ReviewerOutcome,
    ReviewerType,
    UnderwritingApplication,
)


class UnderwritingWorkflowEngine(Protocol):
    async def start(
        self,
        *,
        workflow_run_id: str | None = None,
        application: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
        origin_channel: OriginChannel = OriginChannel.API,
    ) -> tuple[str, list[Any]]: ...

    async def resume(self, workflow_run_id: str) -> list[Any]: ...

    async def decide_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        origin_channel: OriginChannel,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> list[Any]: ...


class UnderwritingHostedWorkflowPort(Protocol):
    async def invoke(
        self,
        request_envelope: HostedWorkflowEnvelope | SafeRunExplanationRequest,
    ) -> dict[str, Any]: ...


class UnderwritingRunRepositoryPort(Protocol):
    engine: Any

    def get_workflow_run(self, workflow_run_id: str) -> dict[str, Any] | None: ...

    def list_workflow_runs(
        self,
        *,
        search: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]: ...

    def list_business_state(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_events(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_checkpoints(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_underwriting_results(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def get_safe_run_status(self, workflow_run_id: str) -> str | None: ...

    def list_safe_event_summaries(
        self, workflow_run_id: str, *, limit: int
    ) -> list[dict[str, Any]]: ...

    def get_safe_checkpoint_summary(self, workflow_run_id: str) -> tuple[int, Any | None]: ...

    def get_safe_final_decision(self, workflow_run_id: str) -> str | None: ...

    def get_workflow_origin_channel(self, workflow_run_id: str) -> OriginChannel | None: ...

    def create_pending_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        request_id: str,
    ) -> dict[str, Any]: ...

    def get_pending_approval(self, checkpoint_id: str) -> dict[str, Any] | None: ...

    def get_approval(self, workflow_run_id: str, checkpoint_id: str) -> dict[str, Any] | None: ...

    def get_review_projection(self, workflow_run_id: str) -> dict[str, Any] | None: ...

    def claim_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        origin_channel: OriginChannel,
        reviewer_type: ReviewerType,
    ) -> ApprovalClaim: ...

    def finish_approval(self, claim: ApprovalClaim) -> bool: ...

    def release_approval(self, claim: ApprovalClaim) -> bool: ...

    def complete_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> bool: ...


class TeamsCardActionRepositoryPort(Protocol):
    def issue_actions(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        conversation_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> dict[ReviewerOutcome, str]: ...

    def claim_action(
        self,
        *,
        token: str,
        decision: ReviewerOutcome,
        conversation_id: str,
        user_id: str,
    ) -> CardActionClaim: ...

    def complete_action(self, batch_id: str) -> bool: ...

    def release_action(self, batch_id: str) -> bool: ...
