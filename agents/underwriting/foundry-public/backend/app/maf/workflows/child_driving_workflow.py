from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.driving_check import DrivingCheckExecutor


def build_child_driving_workflow(repository: WorkflowRunRepository, settings: Settings) -> Workflow:
    executor = DrivingCheckExecutor(repository, settings)
    return WorkflowBuilder(name="driving-child-workflow", start_executor=executor).build()
