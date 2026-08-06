from agent_framework import Executor, WorkflowContext, handler

from app.core.config import Settings
from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.middleware.failures import maybe_crash_after_executor
from app.modules.underwriting import events as event_types
from app.modules.underwriting.models import AllChecksComplete, CheckResult


class FanInAggregatorExecutor(Executor):
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        super().__init__(id="fan_in_aggregator")
        self.repository = repository
        self.settings = settings

    @handler
    async def run(self, result: CheckResult, ctx: WorkflowContext[AllChecksComplete]) -> None:
        with workflow_stage_span("stage.fan_in", workflow_attributes(result, self.id)):
            expected_checks = ctx.get_state("expected_checks") or []
            completed_checks = ctx.get_state("completed_checks") or []
            child_results = ctx.get_state("child_results") or {}
            application_id = ctx.get_state("application_id")
            final_decision_emitted = ctx.get_state("final_decision_emitted") or False
            workflow_run_id = result.workflow_run_id

            maybe_crash_after_executor(
                self.settings, self.repository, workflow_run_id, f"{result.check_type.value}_check"
            )

            check_key = result.check_type.value
            child_results[check_key] = result.to_dict()
            if check_key not in completed_checks:
                completed_checks.append(check_key)

            ctx.set_state("child_results", child_results)
            ctx.set_state("completed_checks", completed_checks)

            self.repository.write_business_state(
                workflow_run_id,
                application_id,
                "aggregation_state",
                {
                    "expected_checks": expected_checks,
                    "completed_checks": completed_checks,
                    "child_results": child_results,
                },
            )
            self.repository.log_event(
                workflow_run_id,
                event_types.FAN_IN_RESULT_RECEIVED,
                self.id,
                {
                    "received_check": check_key,
                    "completed_checks": completed_checks,
                    "expected_checks": expected_checks,
                },
            )
            if sorted(expected_checks) == sorted(completed_checks) and not final_decision_emitted:
                ctx.set_state("final_decision_emitted", True)
                await ctx.send_message(
                    AllChecksComplete(
                        workflow_run_id=workflow_run_id, application_id=application_id
                    )
                )
