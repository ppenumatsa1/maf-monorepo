from __future__ import annotations

import dataclasses
import logging
import uuid
from typing import Any

from app.core.config import Settings
from app.core.observability import log_with_context
from app.core.telemetry import workflow_stage_span
from app.infrastructure.persistence.checkpoint_store import PostgresCheckpointStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.clients.foundry_maf_client import create_foundry_maf_client
from app.maf.workflows.underwriting import build_underwriting_workflow
from app.modules.underwriting import events as event_types
from app.modules.underwriting.models import (
    HumanReviewDecision,
    HumanReviewRequest,
    OriginChannel,
    ReviewerOutcome,
    ReviewerType,
    UnderwritingApplication,
    UnderwritingRunRequest,
)


class UnderwritingMafRunner:
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        self.repository = repository
        self.base_settings = settings

    def _build_workflow_components(self, settings: Settings):
        checkpoint_storage = PostgresCheckpointStore(self.repository.engine)
        foundry_client = create_foundry_maf_client(settings)
        workflow = build_underwriting_workflow(
            repository=self.repository,
            settings=settings,
            checkpoint_storage=checkpoint_storage,
            foundry_client=foundry_client,
        )
        return workflow, checkpoint_storage, foundry_client

    def _build_workflow(self, settings: Settings):
        workflow, _, _ = self._build_workflow_components(settings)
        return workflow

    async def start(
        self,
        *,
        workflow_run_id: str | None = None,
        application: UnderwritingApplication,
        fail_risk_once: bool | None = None,
        fail_credit_randomly: bool | None = None,
        crash_after_executor: str | None = None,
        origin_channel: OriginChannel = OriginChannel.API,
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
                "underwriting.application_id": application.application_id,
            },
        ):
            workflow = self._build_workflow(effective_settings)
        existing_run = self.repository.get_workflow_run(run_id)
        if existing_run is not None:
            raise ValueError(f"workflow_run_id already exists: {run_id}")
        self.repository.create_workflow_run(
            run_id,
            workflow.id,
            "underwriting-parent",
            application.application_id,
            application.applicant_name,
            origin_channel=origin_channel,
        )
        self.repository.log_event(
            run_id,
            event_types.WORKFLOW_START,
            "main",
            {"application_id": application.application_id, "maf_workflow_id": workflow.id},
        )
        log_with_context(
            logging.getLogger("app.workflow"),
            "workflow_start",
            workflow_run_id=run_id,
            application_id=application.application_id,
            workflow_id=workflow.id,
        )
        try:
            with workflow_stage_span(
                "underwriting.run",
                {
                    "workflow.run_id": run_id,
                    "underwriting.application_id": application.application_id,
                },
            ):
                result = await workflow.run(
                    message=UnderwritingRunRequest(
                        workflow_run_id=run_id,
                        application=application,
                    )
                )
                outputs = result.get_outputs()
            review_requests = result.get_request_info_events()
            if review_requests:
                if len(review_requests) != 1 or not isinstance(
                    review_requests[0].data, HumanReviewRequest
                ):
                    raise RuntimeError("Workflow produced an unsupported external input request")
                checkpoint_id = self.repository.latest_checkpoint_id(run_id)
                if not checkpoint_id:
                    raise RuntimeError("Review request did not produce a durable checkpoint")
                request = review_requests[0]
                self.repository.create_pending_approval(
                    workflow_run_id=run_id,
                    checkpoint_id=checkpoint_id,
                    request_id=request.request_id,
                )
                self.repository.update_workflow_run_status(run_id, "PENDING_REVIEW")
                self.repository.log_event(
                    run_id,
                    event_types.REVIEW_REQUESTED,
                    "final_decision",
                    {
                        "checkpoint_id": checkpoint_id,
                        "machine_recommendation": (request.data.machine_recommendation.value),
                    },
                )
                return run_id, outputs

            self.repository.update_workflow_run_status(run_id, "COMPLETED")
            self.repository.log_event(
                run_id,
                event_types.WORKFLOW_COMPLETED,
                "main",
                {"output_count": len(outputs)},
            )
            return run_id, outputs
        except Exception as exc:
            self.repository.update_workflow_run_status(run_id, "CRASHED")
            self.repository.log_event(
                run_id,
                event_types.WORKFLOW_CRASHED,
                "main",
                {"error": str(exc)},
            )
            raise

    async def resume(self, workflow_run_id: str) -> list[Any]:
        run = self.repository.get_workflow_run(workflow_run_id)
        if run is None:
            raise ValueError(f"run not found: {workflow_run_id}")
        if run.get("status") == "COMPLETED":
            raise ValueError(f"run is already COMPLETED: {workflow_run_id}")
        if run.get("status") != "CRASHED":
            raise ValueError(f"run is not eligible for checkpoint recovery: {workflow_run_id}")

        checkpoint_id = self.repository.latest_checkpoint_id(workflow_run_id)
        if not checkpoint_id:
            raise ValueError(f"No checkpoints available for run {workflow_run_id}")

        self.repository.log_event(
            workflow_run_id,
            event_types.RESUME_REQUESTED,
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
            workflow_run_id,
            event_types.RESUME_COMPLETED,
            "main",
            {"output_count": len(outputs)},
        )
        self.repository.log_event(
            workflow_run_id,
            event_types.WORKFLOW_COMPLETED,
            "main",
            {"output_count": len(outputs), "recovered_from_checkpoint": checkpoint_id},
        )
        return outputs

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
        claim = self.repository.claim_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=reviewer_id,
            origin_channel=origin_channel,
            reviewer_type=reviewer_type,
        )
        if claim.completed:
            return []

        try:
            with workflow_stage_span(
                "underwriting.review_resume",
                {
                    "workflow.run_id": workflow_run_id,
                    "workflow.checkpoint_id": checkpoint_id,
                    "workflow.review.outcome": outcome.value,
                    "workflow.review.origin": origin_channel.value,
                },
            ):
                workflow, checkpoint_storage, _ = self._build_workflow_components(
                    self.base_settings
                )
                result = await workflow.run(
                    checkpoint_id=checkpoint_id,
                    checkpoint_storage=checkpoint_storage,
                    responses={
                        claim.request_id: HumanReviewDecision(
                            workflow_run_id=workflow_run_id,
                            checkpoint_id=checkpoint_id,
                            outcome=outcome,
                            origin_channel=origin_channel,
                        )
                    },
                )
                if result.get_request_info_events():
                    raise RuntimeError("Review decision did not resolve the pending request")
                outputs = result.get_outputs()
            if not self.repository.finish_approval(claim):
                raise RuntimeError("Review completion could not be persisted")
            self.repository.update_workflow_run_status(workflow_run_id, "COMPLETED")
            self.repository.log_event(
                workflow_run_id,
                event_types.WORKFLOW_COMPLETED,
                "main",
                {
                    "output_count": len(outputs),
                    "review_checkpoint_id": checkpoint_id,
                },
            )
            return outputs
        except Exception:
            self.repository.release_approval(claim)
            self.repository.update_workflow_run_status(workflow_run_id, "PENDING_REVIEW")
            raise
