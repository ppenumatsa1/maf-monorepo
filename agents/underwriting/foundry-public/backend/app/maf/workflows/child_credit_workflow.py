from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.credit_check import CreditCheckExecutor


def build_child_credit_workflow(repository: WorkflowRunRepository, settings: Settings) -> Workflow:
    executor = CreditCheckExecutor(repository, settings)
    return WorkflowBuilder(name="credit-child-workflow", start_executor=executor).build()
