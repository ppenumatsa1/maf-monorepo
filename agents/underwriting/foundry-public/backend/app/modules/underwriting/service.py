from __future__ import annotations

import uuid
from typing import Any

from app.core.config import Settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.infrastructure.repositories.underwriting_repository import Repository
from app.maf.runner import UnderwritingMafRunner
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.models import UnderwritingApplication


class UnderwritingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_db_engine(settings)
        init_db(self.engine)
        self.repository = Repository(self.engine)
        self.runner = UnderwritingMafRunner(repository=self.repository, settings=settings)

    async def run_workflow(
        self,
        *,
        workflow_run_id: str | None = None,
        application: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
    ) -> tuple[str, list[Any]]:
        return await self.runner.run(
            workflow_run_id=workflow_run_id,
            app=application,
            fail_risk_once=fail_risk_once,
            fail_credit_randomly=fail_credit_randomly,
            crash_after_executor=crash_after_executor,
        )

    async def resume_workflow(self, workflow_run_id: str) -> list[Any]:
        return await self.runner.resume(workflow_run_id)

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


class UnderwritingHostedAdapter:
    """Browser-facing adapter that invokes and projects the hosted MAF workflow."""

    def __init__(
        self,
        settings: Settings,
        *,
        responses_client: UnderwritingResponsesClient | None = None,
    ):
        self.settings = settings
        self.engine = create_db_engine(settings)
        init_db(self.engine)
        self.repository = Repository(self.engine)
        self._responses_client = responses_client or UnderwritingResponsesClient(settings)
        if settings.execution_mode not in {"hosted", "local"}:
            raise ValueError("UNDERWRITING_EXECUTION_MODE must be 'hosted' or 'local'")
        self._local_service = (
            UnderwritingService(settings) if settings.execution_mode == "local" else None
        )

    async def start_workflow(
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
            return self._project_run(workflow_run_id, {})

        if self._local_service is not None:
            await self._local_service.run_workflow(
                workflow_run_id=workflow_run_id,
                application=application,
                fail_risk_once=fail_risk_once,
                fail_credit_randomly=fail_credit_randomly,
                crash_after_executor=crash_after_executor,
            )
            return self._project_run(workflow_run_id, {})

        response = await self._responses_client.invoke(
            HostedWorkflowEnvelope(
                workflow_run_id=workflow_run_id,
                action="start",
                application=application,
                fail_risk_once=fail_risk_once,
                fail_credit_randomly=fail_credit_randomly,
                crash_after_executor=crash_after_executor,
            )
        )
        return self._project_run(workflow_run_id, response)

    async def resume_workflow(self, workflow_run_id: str) -> dict[str, Any]:
        existing = self.repository.get_workflow_run(workflow_run_id)
        if existing is not None and existing.get("status") == "COMPLETED":
            return self._project_run(workflow_run_id, {})

        if self._local_service is not None:
            await self._local_service.resume_workflow(workflow_run_id)
            return self._project_run(workflow_run_id, {})

        response = await self._responses_client.invoke(
            HostedWorkflowEnvelope(workflow_run_id=workflow_run_id, action="resume")
        )
        return self._project_run(workflow_run_id, response)

    def _project_run(self, workflow_run_id: str, response: dict[str, Any]) -> dict[str, Any]:
        run = self.repository.get_workflow_run(workflow_run_id)
        outputs = [
            result["result_json"]
            for result in self.repository.list_underwriting_results(workflow_run_id)
            if result.get("check_type") == "final_decision"
            and isinstance(result.get("result_json"), dict)
        ]
        status = run.get("status") if run is not None else response.get("status", "SUBMITTED")
        return {
            "workflow_run_id": workflow_run_id,
            "status": str(status),
            "outputs": outputs,
        }

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
