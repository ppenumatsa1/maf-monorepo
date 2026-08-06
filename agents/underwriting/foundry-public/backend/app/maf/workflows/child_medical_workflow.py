from __future__ import annotations

from agent_framework import Workflow, WorkflowBuilder

from app.core.config import Settings
from app.infrastructure.repositories.underwriting_repository import Repository
from app.maf.executors.medical_check import MedicalCheckExecutor


def build_child_medical_workflow(repository: Repository, settings: Settings) -> Workflow:
    executor = MedicalCheckExecutor(repository, settings)
    return WorkflowBuilder(name="medical-child-workflow", start_executor=executor).build()
