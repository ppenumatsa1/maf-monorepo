from typing import Never

from agent_framework import Executor, WorkflowContext, handler, response_handler

from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting import events as event_types
from app.modules.underwriting.contracts import DecisionLLMClient
from app.modules.underwriting.decisions import build_final_rationale, compute_decision
from app.modules.underwriting.models import (
    AllChecksComplete,
    Decision,
    FinalDecisionResult,
    HumanReviewDecision,
    HumanReviewRequest,
    ReviewerOutcome,
)


class FinalDecisionExecutor(Executor):
    def __init__(self, repository: WorkflowRunRepository, llm_client: DecisionLLMClient | None):
        super().__init__(id="final_decision")
        self.repository = repository
        self.llm_client = llm_client

    @handler
    async def run(
        self, message: AllChecksComplete, ctx: WorkflowContext[Never, FinalDecisionResult]
    ) -> None:
        with workflow_stage_span("stage.final_decision", workflow_attributes(message, self.id)):
            child_results = ctx.get_state("child_results") or {}
            avg_score = sum(v["score"] for v in child_results.values()) / max(1, len(child_results))
            decision = compute_decision(
                avg_score, {k: v["score"] for k, v in child_results.items()}
            )
            idempotency_key = (
                f"underwriting:{message.workflow_run_id}:{message.application_id}:final-decision"
            )
            persisted_result = self.repository.get_underwriting_result_by_key(idempotency_key)

            existing = self.repository.get_idempotency(idempotency_key)
            if existing and existing.get("status") == "completed":
                payload = existing.get("result_json") or persisted_result
                if payload is None:
                    raise ValueError("idempotency completed without result payload")
                final = FinalDecisionResult(
                    workflow_run_id=payload["workflow_run_id"],
                    application_id=payload["application_id"],
                    decision=Decision(payload["decision"]),
                    rationale=payload["rationale"],
                    score_breakdown=payload["score_breakdown"],
                    idempotency_key=payload["idempotency_key"],
                    reviewer_outcome=(
                        ReviewerOutcome(payload["reviewer_outcome"])
                        if payload.get("reviewer_outcome") is not None
                        else None
                    ),
                    review_checkpoint_id=payload.get("review_checkpoint_id"),
                )
                self.repository.log_event(
                    message.workflow_run_id,
                    event_types.IDEMPOTENCY_SKIP,
                    self.id,
                    {"idempotency_key": idempotency_key},
                )
                await self._yield_or_request_review(final, ctx)
                return
            if persisted_result:
                self.repository.upsert_idempotency(
                    idempotency_key, "final_decision", "completed", persisted_result
                )
                self.repository.log_event(
                    message.workflow_run_id,
                    event_types.IDEMPOTENCY_SKIP,
                    self.id,
                    {"idempotency_key": idempotency_key, "source": "result_row"},
                )
                final = FinalDecisionResult(
                    workflow_run_id=persisted_result["workflow_run_id"],
                    application_id=persisted_result["application_id"],
                    decision=Decision(persisted_result["decision"]),
                    rationale=persisted_result["rationale"],
                    score_breakdown=persisted_result["score_breakdown"],
                    idempotency_key=persisted_result["idempotency_key"],
                    reviewer_outcome=(
                        ReviewerOutcome(persisted_result["reviewer_outcome"])
                        if persisted_result.get("reviewer_outcome") is not None
                        else None
                    ),
                    review_checkpoint_id=persisted_result.get("review_checkpoint_id"),
                )
                await self._yield_or_request_review(final, ctx)
                return

            score_breakdown = {k: v["score"] for k, v in child_results.items()}
            rationale = await build_final_rationale(
                decision=decision,
                average_score=avg_score,
                score_breakdown=score_breakdown,
                llm_client=self.llm_client,
            )
            final = FinalDecisionResult(
                workflow_run_id=message.workflow_run_id,
                application_id=message.application_id,
                decision=decision,
                rationale=rationale,
                score_breakdown=score_breakdown,
                idempotency_key=idempotency_key,
            )

            ctx.set_state("final_decision", final.to_dict())
            self.repository.save_underwriting_result(
                message.workflow_run_id,
                message.application_id,
                "final_decision",
                final.to_dict(),
                idempotency_key,
            )
            self.repository.upsert_idempotency(
                idempotency_key, "final_decision", "completed", final.to_dict()
            )
            self.repository.write_business_state(
                message.workflow_run_id,
                message.application_id,
                "final_decision",
                final.to_dict(),
            )
            self.repository.log_event(
                message.workflow_run_id,
                event_types.FINAL_DECISION,
                self.id,
                final.to_dict(),
            )
            await self._yield_or_request_review(final, ctx)

    async def _yield_or_request_review(
        self,
        final: FinalDecisionResult,
        ctx: WorkflowContext[Never, FinalDecisionResult],
    ) -> None:
        if final.decision == Decision.REFER_TO_HUMAN_UNDERWRITER:
            await ctx.request_info(
                HumanReviewRequest(
                    workflow_run_id=final.workflow_run_id,
                    application_id=final.application_id,
                    machine_recommendation=final.decision,
                ),
                HumanReviewDecision,
                request_id=f"underwriting-review:{final.workflow_run_id}",
            )
            return
        await ctx.yield_output(final)

    @response_handler
    async def handle_review_decision(
        self,
        original_request: HumanReviewRequest,
        response: HumanReviewDecision,
        ctx: WorkflowContext[Never, FinalDecisionResult],
    ) -> None:
        if response.workflow_run_id != original_request.workflow_run_id:
            raise ValueError("Review decision workflow run does not match the request")
        if original_request.machine_recommendation != Decision.REFER_TO_HUMAN_UNDERWRITER:
            raise ValueError("Only referred recommendations can be reviewed")

        idempotency_key = (
            f"underwriting:{original_request.workflow_run_id}:review:{response.checkpoint_id}"
        )
        existing = self.repository.get_idempotency(idempotency_key)
        if existing and existing.get("status") == "completed":
            payload = existing.get("result_json")
            if not isinstance(payload, dict):
                raise ValueError("Review idempotency record has no result payload")
            await ctx.yield_output(
                FinalDecisionResult(
                    workflow_run_id=payload["workflow_run_id"],
                    application_id=payload["application_id"],
                    decision=Decision(payload["decision"]),
                    rationale=payload["rationale"],
                    score_breakdown=payload["score_breakdown"],
                    idempotency_key=payload["idempotency_key"],
                    reviewer_outcome=response.outcome,
                    review_checkpoint_id=response.checkpoint_id,
                )
            )
            return

        final_result = self.repository.get_underwriting_result_by_key(
            f"underwriting:{original_request.workflow_run_id}:"
            f"{original_request.application_id}:final-decision"
        )
        if final_result is None:
            raise ValueError("Persisted machine recommendation was not found")
        if final_result.get("decision") != Decision.REFER_TO_HUMAN_UNDERWRITER.value:
            raise ValueError("Persisted machine recommendation is not reviewable")

        resolved = FinalDecisionResult(
            workflow_run_id=original_request.workflow_run_id,
            application_id=original_request.application_id,
            decision=Decision.REFER_TO_HUMAN_UNDERWRITER,
            rationale=str(final_result["rationale"]),
            score_breakdown=dict(final_result["score_breakdown"]),
            idempotency_key=str(final_result["idempotency_key"]),
            reviewer_outcome=response.outcome,
            review_checkpoint_id=response.checkpoint_id,
        )
        resolved_payload = resolved.to_dict()
        self.repository.upsert_idempotency(
            idempotency_key,
            "human_review_decision",
            "completed",
            resolved_payload,
        )
        self.repository.write_business_state(
            original_request.workflow_run_id,
            original_request.application_id,
            "human_review",
            {
                "machine_recommendation": Decision.REFER_TO_HUMAN_UNDERWRITER.value,
                "reviewer_outcome": response.outcome.value,
                "checkpoint_id": response.checkpoint_id,
            },
        )
        self.repository.log_event(
            original_request.workflow_run_id,
            event_types.REVIEW_RESOLVED,
            self.id,
            {
                "checkpoint_id": response.checkpoint_id,
                "machine_recommendation": Decision.REFER_TO_HUMAN_UNDERWRITER.value,
                "reviewer_outcome": response.outcome.value,
            },
        )
        await ctx.yield_output(resolved)
