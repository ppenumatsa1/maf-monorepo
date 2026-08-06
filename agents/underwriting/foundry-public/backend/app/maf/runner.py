from __future__ import annotations

import dataclasses
import logging
import uuid
from typing import Any

from app.core.config import Settings
from app.core.observability import log_with_context
from app.core.telemetry import workflow_stage_span
from app.infrastructure.checkpointing.postgres_checkpoint_storage import PostgresCheckpointStorage
from app.infrastructure.repositories.underwriting_repository import Repository
from app.maf.clients.foundry_maf_client import create_foundry_maf_client
from app.maf.workflows.parent_underwriting_workflow import build_parent_underwriting_workflow
from app.modules.underwriting.models import UnderwritingApplication, UnderwritingRunRequest


class UnderwritingMafRunner:
    def __init__(self, repository: Repository, settings: Settings):
        self.repository = repository
        self.base_settings = settings

    def _build_workflow_components(self, settings: Settings):
        checkpoint_storage = PostgresCheckpointStorage(self.repository.engine)
        foundry_client = create_foundry_maf_client(settings)
        workflow = build_parent_underwriting_workflow(
            repository=self.repository,
            settings=settings,
            checkpoint_storage=checkpoint_storage,
            foundry_client=foundry_client,
        )
        return workflow, checkpoint_storage, foundry_client

    def _build_workflow(self, settings: Settings):
        workflow, _, _ = self._build_workflow_components(settings)
        return workflow

    async def run(
        self,
        *,
        workflow_run_id: str | None = None,
        app: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
    ) -> tuple[str, list[Any]]:
        effective_settings = dataclasses.replace(
            self.base_settings,
            fail_risk_once=self.base_settings.fail_risk_once
            if fail_risk_once is None
            else fail_risk_once,
            fail_credit_randomly=self.base_settings.fail_credit_randomly
            if fail_credit_randomly is None
            else fail_credit_randomly,
            crash_after_executor=self.base_settings.crash_after_executor
            if crash_after_executor is None
            else crash_after_executor,
        )
        run_id = workflow_run_id or f"run-{uuid.uuid4().hex[:10]}"
        with workflow_stage_span(
            "underwriting.initialize",
            {
                "workflow.run_id": run_id,
                "underwriting.application_id": app.application_id,
            },
        ):
            workflow = self._build_workflow(effective_settings)
        existing_run = self.repository.get_workflow_run(run_id)
        if existing_run is not None:
            raise ValueError(f"workflow_run_id already exists: {run_id}")
        self.repository.create_workflow_run(
            run_id, workflow.id, "underwriting-parent", app.application_id, app.applicant_name
        )
        self.repository.log_event(
            run_id,
            "workflow_start",
            "main",
            {"application_id": app.application_id, "maf_workflow_id": workflow.id},
        )
        log_with_context(
            logging.getLogger("app.workflow"),
            "workflow_start",
            workflow_run_id=run_id,
            application_id=app.application_id,
            workflow_id=workflow.id,
        )
        try:
            with workflow_stage_span(
                "underwriting.run",
                {
                    "workflow.run_id": run_id,
                    "underwriting.application_id": app.application_id,
                },
            ):
                result = await workflow.run(
                    message=UnderwritingRunRequest(workflow_run_id=run_id, application=app)
                )
                outputs = result.get_outputs()
            self.repository.update_workflow_run_status(run_id, "COMPLETED")
            self.repository.log_event(
                run_id, "workflow_completed", "main", {"output_count": len(outputs)}
            )
            return run_id, outputs
        except Exception as exc:
            self.repository.update_workflow_run_status(run_id, "CRASHED")
            self.repository.log_event(run_id, "workflow_crashed", "main", {"error": str(exc)})
            raise

    async def resume(self, workflow_run_id: str) -> list[Any]:
        run = self.repository.get_workflow_run(workflow_run_id)
        if run is None:
            raise ValueError(f"run not found: {workflow_run_id}")
        if run.get("status") == "COMPLETED":
            raise ValueError(f"run is already COMPLETED: {workflow_run_id}")

        checkpoint_id = self.repository.latest_checkpoint_id(workflow_run_id)
        if not checkpoint_id:
            raise ValueError(f"No checkpoints available for run {workflow_run_id}")

        self.repository.log_event(
            workflow_run_id,
            "resume_requested",
            "main",
            {"checkpoint_id": checkpoint_id, "note": "loading real MAF checkpoint from postgres"},
        )

        with workflow_stage_span(
            "underwriting.resume",
            {
                "workflow.run_id": workflow_run_id,
                "workflow.checkpoint_id": checkpoint_id,
            },
        ):
            workflow, checkpoint_storage, _ = self._build_workflow_components(self.base_settings)
            result = await workflow.run(
                checkpoint_id=checkpoint_id,
                checkpoint_storage=checkpoint_storage,
            )
            outputs = result.get_outputs()
        self.repository.update_workflow_run_status(workflow_run_id, "COMPLETED")
        self.repository.log_event(
            workflow_run_id, "resume_completed", "main", {"output_count": len(outputs)}
        )
        return outputs
