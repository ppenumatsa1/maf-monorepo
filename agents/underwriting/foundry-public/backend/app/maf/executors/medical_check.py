from typing import Never

from agent_framework import Executor, WorkflowContext, handler

from app.core.config import Settings
from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.repositories.underwriting_repository import Repository
from app.maf.middleware.failures import maybe_crash_after_executor
from app.maf.middleware.resilience import invoke_check_operation
from app.modules.underwriting.models import CheckRequest, CheckResult, CheckType


class MedicalCheckExecutor(Executor):
    def __init__(self, repository: Repository, settings: Settings):
        super().__init__(id="medical_check")
        self.repository = repository
        self.settings = settings

    @handler
    async def run(self, request: CheckRequest, ctx: WorkflowContext[Never, CheckResult]) -> None:
        if request.check_type != CheckType.MEDICAL:
            return

        async def external_call() -> dict:
            disclosures = request.application.health_disclosures.lower()
            score = 0.4 if "chronic" in disclosures else 0.85
            return {
                "score": score,
                "details": {"disclosures": request.application.health_disclosures},
            }

        with workflow_stage_span("stage.medical_check", workflow_attributes(request, self.id)):
            invocation = await invoke_check_operation(
                repository=self.repository,
                settings=self.settings,
                workflow_run_id=request.workflow_run_id,
                application_id=request.application.application_id,
                check_type=CheckType.MEDICAL,
                operation_name="medical_check",
                executor_name=self.id,
                operation=external_call,
            )
        payload = invocation.payload

        if invocation.from_idempotency:
            await ctx.yield_output(
                CheckResult(
                    workflow_run_id=payload["workflow_run_id"],
                    application_id=payload["application_id"],
                    check_type=CheckType(payload["check_type"]),
                    score=payload["score"],
                    details=payload["details"],
                    idempotency_key=payload["idempotency_key"],
                )
            )
            return

        result = CheckResult(
            workflow_run_id=request.workflow_run_id,
            application_id=request.application.application_id,
            check_type=CheckType.MEDICAL,
            score=payload["score"],
            details=payload["details"],
            idempotency_key=invocation.idempotency_key,
        )
        self.repository.save_underwriting_result(
            request.workflow_run_id,
            request.application.application_id,
            CheckType.MEDICAL.value,
            result.to_dict(),
            invocation.idempotency_key,
        )
        self.repository.upsert_idempotency(
            invocation.idempotency_key, "medical_check", "completed", result.to_dict()
        )
        self.repository.log_event(
            request.workflow_run_id, "check_completed", self.id, result.to_dict()
        )
        maybe_crash_after_executor(
            self.settings, self.repository, request.workflow_run_id, "medical_check"
        )
        await ctx.yield_output(result)
