from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.runner import UnderwritingMafRunner
from app.modules.underwriting.ports import UnderwritingWorkflowEngine


def create_workflow_engine(
    *,
    repository: WorkflowRunRepository,
    settings: Settings,
) -> UnderwritingWorkflowEngine:
    return UnderwritingMafRunner(repository=repository, settings=settings)


__all__ = ["create_workflow_engine"]
