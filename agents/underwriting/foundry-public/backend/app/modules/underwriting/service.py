from __future__ import annotations

import uuid
from typing import Any

from app.core.config import Settings
from app.infrastructure.db.engine import get_runtime_db_engine, init_db, reset_db
from app.infrastructure.persistence.teams_card_action_repository import (
    TeamsCardActionRepository,
)
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.factory import create_workflow_engine
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.models import (
    CardActionClaim,
    OriginChannel,
    ReviewerOutcome,
    ReviewerType,
    UnderwritingApplication,
)
from app.modules.underwriting.ports import (
    TeamsCardActionRepositoryPort,
    UnderwritingHostedWorkflowPort,
    UnderwritingRunRepositoryPort,
    UnderwritingWorkflowEngine,
)
from app.modules.underwriting.projections import project_workflow_run


class LocalReviewDisabledError(RuntimeError):
    pass


class LocalUnderwritingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = get_runtime_db_engine(settings)
        init_db(
            self.engine,
            schema_managed_externally=settings.db_schema_managed_externally,
        )
        self.repository = WorkflowRunRepository(self.engine)
        self.card_actions = TeamsCardActionRepository(self.engine)
        self.workflow = create_workflow_engine(repository=self.repository, settings=settings)

    async def run_workflow(
        self,
        *,
        workflow_run_id: str | None = None,
        application: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
        origin_channel: OriginChannel | None = None,
    ) -> tuple[str, list[Any]]:
        return await self.workflow.start(
            workflow_run_id=workflow_run_id,
            application=application,
            fail_risk_once=fail_risk_once,
            fail_credit_randomly=fail_credit_randomly,
            crash_after_executor=crash_after_executor,
            origin_channel=origin_channel
            or (
                OriginChannel.RESPONSES
                if self.settings.execution_mode == "hosted"
                and self.settings.db_schema_managed_externally
                else OriginChannel.API
            ),
        )

    async def resume_workflow(self, workflow_run_id: str) -> list[Any]:
        return await self.workflow.resume(workflow_run_id)

    def reset_database(self) -> None:
        reset_db(self.engine)

    def default_application(self) -> UnderwritingApplication:
        return UnderwritingApplication(
            application_id=f"app-{uuid.uuid4().hex[:8]}",
            applicant_name="Ada Lovelace",
            age=38,
            income=145000,
            requested_coverage=500000,
            health_disclosures="none",
            driving_history="clean",
            credit_score=760,
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.repository.get_workflow_run(run_id)

    def list_runs(
        self, *, search: str | None, status: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict[str, Any]]]:
        return self.repository.list_workflow_runs(
            search=search, status=status, limit=limit, offset=offset
        )

    def get_state(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_business_state(run_id)

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_events(run_id)

    def get_checkpoints(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_checkpoints(run_id)

    def create_pending_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return self.repository.create_pending_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            request_id=request_id,
        )

    def get_pending_review(self, checkpoint_id: str) -> dict[str, Any] | None:
        return self.repository.get_pending_approval(checkpoint_id)

    def complete_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> bool:
        return self.repository.complete_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=reviewer_id,
            reviewer_type=reviewer_type,
        )

    async def decide_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        origin_channel: OriginChannel,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> list[Any]:
        return await self.workflow.decide_review(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=reviewer_id,
            origin_channel=origin_channel,
            reviewer_type=reviewer_type,
        )

    def get_review(self, workflow_run_id: str) -> dict[str, Any] | None:
        return self.repository.get_review_projection(workflow_run_id)

    def issue_teams_review_actions(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        conversation_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> dict[ReviewerOutcome, str]:
        return self.card_actions.issue_actions(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ttl_seconds=ttl_seconds,
        )

    def claim_teams_review_action(
        self,
        *,
        token: str,
        decision: ReviewerOutcome,
        conversation_id: str,
        user_id: str,
    ) -> CardActionClaim:
        return self.card_actions.claim_action(
            token=token,
            decision=decision,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def complete_teams_review_action(self, batch_id: str) -> bool:
        return self.card_actions.complete_action(batch_id)

    def release_teams_review_action(self, batch_id: str) -> bool:
        return self.card_actions.release_action(batch_id)


class UnderwritingService:
    def __init__(
        self,
        *,
        settings: Settings,
        workflow: UnderwritingWorkflowEngine | None,
        workflow_run_repository: UnderwritingRunRepositoryPort,
        card_action_repository: TeamsCardActionRepositoryPort | None = None,
        responses_client: UnderwritingHostedWorkflowPort | None = None,
    ) -> None:
        if workflow is None and responses_client is None:
            raise ValueError("UnderwritingService requires a workflow engine or responses client.")

        self.settings = settings
        self.workflow = workflow
        self.repository = workflow_run_repository
        self.card_actions = card_action_repository
        self.engine = getattr(workflow_run_repository, "engine", None)
        self.responses_client = responses_client

    async def start_run(
        self,
        *,
        workflow_run_id: str,
        application: UnderwritingApplication,
        fail_risk_once: bool,
        fail_credit_randomly: bool,
        crash_after_executor: str | None,
    ) -> dict[str, Any]:
        existing = self.repository.get_workflow_run(workflow_run_id)
        if existing is not None:
            return project_workflow_run(
                self.repository,
                workflow_run_id,
                fallback_status=str(existing.get("status", "SUBMITTED")),
            )

        if self.responses_client is not None:
            response = await self.responses_client.invoke(
                HostedWorkflowEnvelope(
                    workflow_run_id=workflow_run_id,
                    action="start",
                    application=application,
                    fail_risk_once=fail_risk_once,
                    fail_credit_randomly=fail_credit_randomly,
                    crash_after_executor=crash_after_executor,
                )
            )
            return project_workflow_run(
                self.repository,
                workflow_run_id,
                fallback_status=str(response.get("status", "SUBMITTED")),
            )

        if self.workflow is None:
            raise RuntimeError("Local underwriting workflow engine is not configured.")

        _, outputs = await self.workflow.start(
            workflow_run_id=workflow_run_id,
            application=application,
            fail_risk_once=fail_risk_once,
            fail_credit_randomly=fail_credit_randomly,
            crash_after_executor=crash_after_executor,
            origin_channel=OriginChannel.API,
        )
        return project_workflow_run(
            self.repository,
            workflow_run_id,
            fallback_status="COMPLETED",
            outputs=outputs,
        )

    async def resume_run(self, workflow_run_id: str) -> dict[str, Any]:
        existing = self.repository.get_workflow_run(workflow_run_id)
        if existing is not None and existing.get("status") == "COMPLETED":
            return project_workflow_run(
                self.repository,
                workflow_run_id,
                fallback_status=str(existing.get("status", "COMPLETED")),
            )

        if self.responses_client is not None:
            response = await self.responses_client.invoke(
                HostedWorkflowEnvelope(workflow_run_id=workflow_run_id, action="resume")
            )
            return project_workflow_run(
                self.repository,
                workflow_run_id,
                fallback_status=str(response.get("status", "SUBMITTED")),
            )

        if self.workflow is None:
            raise RuntimeError("Local underwriting workflow engine is not configured.")

        outputs = await self.workflow.resume(workflow_run_id)
        return project_workflow_run(
            self.repository,
            workflow_run_id,
            fallback_status="COMPLETED",
            outputs=outputs,
        )

    async def decide_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
    ) -> dict[str, Any]:
        existing = self.repository.get_workflow_run(workflow_run_id)
        if existing is None:
            raise ValueError(f"run not found: {workflow_run_id}")

        if self.responses_client is not None:
            raise LocalReviewDisabledError(
                "Web review decisions are disabled in hosted mode; use the bound Teams review card"
            )
        if (
            self.settings.execution_mode != "local"
            or self.settings.db_schema_managed_externally
            or not self.settings.local_review_mutation_enabled
            or not self.settings.local_review_actor_id
        ):
            raise LocalReviewDisabledError(
                "Web review decisions are disabled; use the bound Teams review card"
            )

        if self.workflow is None:
            raise RuntimeError("Local underwriting workflow engine is not configured.")
        outputs = await self.workflow.decide_review(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=self.settings.local_review_actor_id,
            origin_channel=OriginChannel.API,
            reviewer_type=ReviewerType.ADMINISTRATIVE,
        )
        return project_workflow_run(
            self.repository,
            workflow_run_id,
            fallback_status="COMPLETED",
            outputs=outputs,
        )

    def get_review(self, workflow_run_id: str) -> dict[str, Any] | None:
        return self.repository.get_review_projection(workflow_run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.repository.get_workflow_run(run_id)

    def list_runs(
        self, *, search: str | None, status: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict[str, Any]]]:
        return self.repository.list_workflow_runs(
            search=search, status=status, limit=limit, offset=offset
        )

    def get_state(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_business_state(run_id)

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_events(run_id)

    def get_checkpoints(self, run_id: str) -> list[dict[str, Any]]:
        return self.repository.list_checkpoints(run_id)

    def create_pending_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return self.repository.create_pending_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            request_id=request_id,
        )

    def get_pending_review(self, checkpoint_id: str) -> dict[str, Any] | None:
        return self.repository.get_pending_approval(checkpoint_id)

    def complete_review(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> bool:
        return self.repository.complete_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=reviewer_id,
            reviewer_type=reviewer_type,
        )

    def issue_teams_review_actions(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        conversation_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> dict[ReviewerOutcome, str]:
        if self.card_actions is None:
            raise RuntimeError("Teams card action persistence is not configured")
        return self.card_actions.issue_actions(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ttl_seconds=ttl_seconds,
        )

    def claim_teams_review_action(
        self,
        *,
        token: str,
        decision: ReviewerOutcome,
        conversation_id: str,
        user_id: str,
    ) -> CardActionClaim:
        if self.card_actions is None:
            raise RuntimeError("Teams card action persistence is not configured")
        return self.card_actions.claim_action(
            token=token,
            decision=decision,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def complete_teams_review_action(self, batch_id: str) -> bool:
        if self.card_actions is None:
            raise RuntimeError("Teams card action persistence is not configured")
        return self.card_actions.complete_action(batch_id)

    def release_teams_review_action(self, batch_id: str) -> bool:
        if self.card_actions is None:
            raise RuntimeError("Teams card action persistence is not configured")
        return self.card_actions.release_action(batch_id)
