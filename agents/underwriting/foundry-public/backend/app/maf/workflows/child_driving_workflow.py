from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.repositories.underwriting_repository import Repository
from app.maf.executors.driving_check import DrivingCheckExecutor


def build_child_driving_workflow(repository: Repository, settings: Settings) -> Workflow:
    executor = DrivingCheckExecutor(repository, settings)
    return WorkflowBuilder(name="driving-child-workflow", start_executor=executor).build()
