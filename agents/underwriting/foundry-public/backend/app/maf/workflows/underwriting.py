from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.persistence.checkpoint_store import PostgresCheckpointStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.credit_check import CreditCheckExecutor
from app.maf.executors.driving_check import DrivingCheckExecutor
from app.maf.executors.fan_in_aggregator import FanInAggregatorExecutor
from app.maf.executors.final_decision import FinalDecisionExecutor
from app.maf.executors.init_context import InitContextExecutor
from app.maf.executors.medical_check import MedicalCheckExecutor
from app.maf.executors.risk_score import RiskScoreExecutor
from app.modules.underwriting.contracts import DecisionLLMClient


def build_underwriting_workflow(
    repository: WorkflowRunRepository,
    settings: Settings,
    checkpoint_storage: PostgresCheckpointStore,
    foundry_client: DecisionLLMClient | None,
) -> Workflow:
    init_context = InitContextExecutor(repository)
    risk_score = RiskScoreExecutor(repository, settings)
    credit_check = CreditCheckExecutor(repository, settings)
    medical_check = MedicalCheckExecutor(repository, settings)
    driving_check = DrivingCheckExecutor(repository, settings)
    fan_in_aggregator = FanInAggregatorExecutor(repository, settings)
    final_decision = FinalDecisionExecutor(repository, foundry_client)
    builder = (
        WorkflowBuilder(
            name="insurance-underwriting-workflow",
            start_executor=init_context,
            checkpoint_storage=checkpoint_storage,
        )
        .add_fan_out_edges(
            init_context,
            [
                risk_score,
                credit_check,
                medical_check,
                driving_check,
            ],
        )
        # Preserve incremental durable state as each direct check result arrives.
        .add_edge(risk_score, fan_in_aggregator)
        .add_edge(credit_check, fan_in_aggregator)
        .add_edge(medical_check, fan_in_aggregator)
        .add_edge(driving_check, fan_in_aggregator)
        .add_edge(fan_in_aggregator, final_decision)
    )
    return builder.build()
