from agent_framework import Executor, WorkflowContext, handler

from app.core.config import Settings
from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.middleware.failures import maybe_crash_after_executor
from app.maf.middleware.resilience import invoke_check_operation
from app.modules.underwriting import events as event_types
from app.modules.underwriting.models import CheckRequest, CheckResult, CheckType


class CreditCheckExecutor(Executor):
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        super().__init__(id="credit_check")
        self.repository = repository
        self.settings = settings

    @handler
    async def run(self, request: CheckRequest, ctx: WorkflowContext[CheckResult]) -> None:
        if request.check_type != CheckType.CREDIT:
            return

        async def external_call() -> dict:
            normalized = min(1.0, max(0.0, request.application.credit_score / 850.0))
            return {"score": round(normalized, 3), "details": {"bureau": "demo-credit-bureau"}}

        with workflow_stage_span("stage.credit_check", workflow_attributes(request, self.id)):
            invocation = await invoke_check_operation(
                repository=self.repository,
                settings=self.settings,
                workflow_run_id=request.workflow_run_id,
                application_id=request.application.application_id,
                check_type=CheckType.CREDIT,
                operation_name="credit_check",
                executor_name=self.id,
                operation=external_call,
            )
        payload = invocation.payload

        if invocation.from_idempotency:
            await ctx.send_message(
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
            check_type=CheckType.CREDIT,
            score=payload["score"],
            details=payload["details"],
            idempotency_key=invocation.idempotency_key,
        )
        self.repository.save_underwriting_result(
            request.workflow_run_id,
            request.application.application_id,
            CheckType.CREDIT.value,
            result.to_dict(),
            invocation.idempotency_key,
        )
        self.repository.upsert_idempotency(
            invocation.idempotency_key, "credit_check", "completed", result.to_dict()
        )
        self.repository.log_event(
            request.workflow_run_id,
            event_types.CHECK_COMPLETED,
            self.id,
            result.to_dict(),
        )
        maybe_crash_after_executor(
            self.settings, self.repository, request.workflow_run_id, "credit_check"
        )
        await ctx.send_message(result)
