from agent_framework import Executor, WorkflowContext, handler

from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.repositories.underwriting_repository import Repository
from app.modules.underwriting.models import CheckRequest, CheckType, UnderwritingRunRequest


class InitContextExecutor(Executor):
    def __init__(self, repository: Repository):
        super().__init__(id="init_context")
        self.repository = repository

    @handler
    async def run(
        self, request: UnderwritingRunRequest, ctx: WorkflowContext[CheckRequest]
    ) -> None:
        workflow_run_id = request.workflow_run_id
        app = request.application
        attributes = workflow_attributes(request, self.id)
        with workflow_stage_span("stage.init_context", attributes):
            ctx.set_state("workflow_run_id", workflow_run_id)
            expected_checks = [check.value for check in CheckType]

            ctx.set_state("application_id", app.application_id)
            ctx.set_state("applicant_profile", app.to_dict())
            ctx.set_state("expected_checks", expected_checks)
            ctx.set_state("completed_checks", [])
            ctx.set_state("child_results", {})
            ctx.set_state("final_decision", None)
            ctx.set_state("final_decision_emitted", False)

            self.repository.write_business_state(
                workflow_run_id,
                app.application_id,
                "underwriting_context",
                {
                    "application_id": app.application_id,
                    "applicant_name": app.applicant_name,
                    "age": app.age,
                    "income": app.income,
                    "requested_coverage": app.requested_coverage,
                    "expected_checks": expected_checks,
                    "completed_checks": [],
                    "child_results": {},
                    "final_decision": None,
                    "final_decision_emitted": False,
                },
            )
            self.repository.log_event(
                workflow_run_id,
                "init_context",
                self.id,
                {"application_id": app.application_id, "message_received": True},
            )
            with workflow_stage_span(
                "stage.fan_out",
                {**attributes, "workflow.child_count": len(expected_checks)},
            ):
                for check_type in CheckType:
                    await ctx.send_message(
                        CheckRequest(
                            workflow_run_id=workflow_run_id, application=app, check_type=check_type
                        )
                    )
