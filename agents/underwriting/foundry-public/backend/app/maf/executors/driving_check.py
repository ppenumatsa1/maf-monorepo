from agent_framework import Executor, WorkflowContext, handler

from app.core.config import Settings
from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.middleware.failures import maybe_crash_after_executor
from app.maf.middleware.resilience import invoke_check_operation
from app.modules.underwriting import events as event_types
from app.modules.underwriting.models import CheckRequest, CheckResult, CheckType


class DrivingCheckExecutor(Executor):
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        super().__init__(id="driving_check")
        self.repository = repository
        self.settings = settings

    @handler
    async def run(self, request: CheckRequest, ctx: WorkflowContext[CheckResult]) -> None:
        if request.check_type != CheckType.DRIVING:
            return

        async def external_call() -> dict:
            history = request.application.driving_history.lower()
            score = 0.35 if "dui" in history or "accident" in history else 0.9
            return {"score": score, "details": {"history": request.application.driving_history}}

        with workflow_stage_span("stage.driving_check", workflow_attributes(request, self.id)):
            invocation = await invoke_check_operation(
                repository=self.repository,
                settings=self.settings,
                workflow_run_id=request.workflow_run_id,
                application_id=request.application.application_id,
                check_type=CheckType.DRIVING,
                operation_name="driving_check",
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
            check_type=CheckType.DRIVING,
            score=payload["score"],
            details=payload["details"],
            idempotency_key=invocation.idempotency_key,
        )
        self.repository.save_underwriting_result(
            request.workflow_run_id,
            request.application.application_id,
            CheckType.DRIVING.value,
            result.to_dict(),
            invocation.idempotency_key,
        )
        self.repository.upsert_idempotency(
            invocation.idempotency_key, "driving_check", "completed", result.to_dict()
        )
        self.repository.log_event(
            request.workflow_run_id,
            event_types.CHECK_COMPLETED,
            self.id,
            result.to_dict(),
        )
        maybe_crash_after_executor(
            self.settings, self.repository, request.workflow_run_id, "driving_check"
        )
        await ctx.send_message(result)
