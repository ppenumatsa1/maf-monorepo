from typing import Never

from agent_framework import Executor, WorkflowContext, handler

from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.repositories.underwriting_repository import Repository
from app.modules.underwriting.contracts import DecisionLLMClient
from app.modules.underwriting.decisions import build_final_rationale, compute_decision
from app.modules.underwriting.models import AllChecksComplete, Decision, FinalDecisionResult


class FinalDecisionExecutor(Executor):
    def __init__(self, repository: Repository, llm_client: DecisionLLMClient | None):
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
            idempotency_key = f"underwriting:{message.application_id}:final-decision"
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
                )
                self.repository.log_event(
                    message.workflow_run_id,
                    "idempotency_skip",
                    self.id,
                    {"idempotency_key": idempotency_key},
                )
                await ctx.yield_output(final)
                return
            if persisted_result:
                self.repository.upsert_idempotency(
                    idempotency_key, "final_decision", "completed", persisted_result
                )
                self.repository.log_event(
                    message.workflow_run_id,
                    "idempotency_skip",
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
                )
                await ctx.yield_output(final)
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
                message.workflow_run_id, "final_decision", self.id, final.to_dict()
            )
            await ctx.yield_output(final)
