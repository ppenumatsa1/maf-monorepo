from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.executors.medical_check import MedicalCheckExecutor


def build_child_medical_workflow(repository: WorkflowRunRepository, settings: Settings) -> Workflow:
    executor = MedicalCheckExecutor(repository, settings)
    return WorkflowBuilder(name="medical-child-workflow", start_executor=executor).build()
