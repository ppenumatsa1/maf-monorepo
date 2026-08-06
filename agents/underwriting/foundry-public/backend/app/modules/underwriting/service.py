from __future__ import annotations

import uuid
from typing import Any

from app.core.config import Settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.factory import create_workflow_engine
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.models import UnderwritingApplication
from app.modules.underwriting.ports import (
    UnderwritingHostedWorkflowPort,
    UnderwritingRunRepositoryPort,
    UnderwritingWorkflowEngine,
)
from app.modules.underwriting.projections import project_workflow_run


class LocalUnderwritingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_db_engine(settings)
        init_db(self.engine)
        self.repository = WorkflowRunRepository(self.engine)
        self.workflow = create_workflow_engine(repository=self.repository, settings=settings)

    async def run_workflow(
        self,
        *,
        workflow_run_id: str | None = None,
        application: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
    ) -> tuple[str, list[Any]]:
        return await self.workflow.start(
            workflow_run_id=workflow_run_id,
            application=application,
            fail_risk_once=fail_risk_once,
            fail_credit_randomly=fail_credit_randomly,
            crash_after_executor=crash_after_executor,
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


class UnderwritingService:
    def __init__(
        self,
        *,
        settings: Settings,
        workflow: UnderwritingWorkflowEngine | None,
        workflow_run_repository: UnderwritingRunRepositoryPort,
        responses_client: UnderwritingHostedWorkflowPort | None = None,
    ) -> None:
        if workflow is None and responses_client is None:
            raise ValueError("UnderwritingService requires a workflow engine or responses client.")

        self.settings = settings
        self.workflow = workflow
        self.repository = workflow_run_repository
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
