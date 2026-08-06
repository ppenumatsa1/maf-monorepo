from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.risk_score import RiskScoreExecutor


def build_child_risk_workflow(repository: WorkflowRunRepository, settings: Settings) -> Workflow:
    executor = RiskScoreExecutor(repository, settings)
    return WorkflowBuilder(name="risk-child-workflow", start_executor=executor).build()
