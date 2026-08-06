from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder, WorkflowExecutor

from app.core.config import Settings
from app.infrastructure.persistence.checkpoint_store import PostgresCheckpointStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.fan_in_aggregator import FanInAggregatorExecutor
from app.maf.executors.final_decision import FinalDecisionExecutor
from app.maf.executors.init_context import InitContextExecutor
from app.maf.workflows.child_credit_workflow import build_child_credit_workflow
from app.maf.workflows.child_driving_workflow import build_child_driving_workflow
from app.maf.workflows.child_medical_workflow import build_child_medical_workflow
from app.maf.workflows.child_risk_workflow import build_child_risk_workflow
from app.modules.underwriting.contracts import DecisionLLMClient


def build_underwriting_workflow(
    repository: WorkflowRunRepository,
    settings: Settings,
    checkpoint_storage: PostgresCheckpointStore,
    foundry_client: DecisionLLMClient | None,
) -> Workflow:
    init_context = InitContextExecutor(repository)
    risk_child_workflow = WorkflowExecutor(
        build_child_risk_workflow(repository, settings), id="risk_child_workflow"
    )
    credit_child_workflow = WorkflowExecutor(
        build_child_credit_workflow(repository, settings), id="credit_child_workflow"
    )
    medical_child_workflow = WorkflowExecutor(
        build_child_medical_workflow(repository, settings), id="medical_child_workflow"
    )
    driving_child_workflow = WorkflowExecutor(
        build_child_driving_workflow(repository, settings), id="driving_child_workflow"
    )
    fan_in_aggregator = FanInAggregatorExecutor(repository, settings)
    final_decision = FinalDecisionExecutor(repository, foundry_client)
    builder = (
        WorkflowBuilder(
            name="insurance-underwriting-parent-workflow",
            start_executor=init_context,
            checkpoint_storage=checkpoint_storage,
        )
        .add_fan_out_edges(
            init_context,
            [
                risk_child_workflow,
                credit_child_workflow,
                medical_child_workflow,
                driving_child_workflow,
            ],
        )
        # One-message-at-a-time fan-in: each child emits independently and aggregator updates shared state incrementally.
        .add_edge(risk_child_workflow, fan_in_aggregator)
        .add_edge(credit_child_workflow, fan_in_aggregator)
        .add_edge(medical_child_workflow, fan_in_aggregator)
        .add_edge(driving_child_workflow, fan_in_aggregator)
        .add_edge(fan_in_aggregator, final_decision)
    )
    return builder.build()
