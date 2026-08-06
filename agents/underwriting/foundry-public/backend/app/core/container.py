from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, load_settings
from app.infrastructure.db.engine import create_db_engine, init_db
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.factory import create_workflow_engine
from app.modules.underwriting.copilot_bridge import UnderwritingCopilotBridge
from app.modules.underwriting.ports import UnderwritingHostedWorkflowPort
from app.modules.underwriting.service import UnderwritingService


def build_underwriting_service(
    settings: Settings,
    *,
    responses_client: UnderwritingHostedWorkflowPort | None = None,
) -> UnderwritingService:
    if settings.execution_mode not in {"hosted", "local"}:
        raise ValueError("UNDERWRITING_EXECUTION_MODE must be 'hosted' or 'local'")

    engine = create_db_engine(settings)
    init_db(engine)
    repository = WorkflowRunRepository(engine)
    workflow = (
        create_workflow_engine(repository=repository, settings=settings)
        if settings.execution_mode == "local"
        else None
    )
    effective_responses_client = (
        responses_client
        if responses_client is not None
        else (
            UnderwritingResponsesClient(settings) if settings.execution_mode == "hosted" else None
        )
    )
    return UnderwritingService(
        settings=settings,
        workflow=workflow,
        workflow_run_repository=repository,
        responses_client=effective_responses_client,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_underwriting_service() -> UnderwritingService:
    return build_underwriting_service(get_settings())


@lru_cache(maxsize=1)
def get_copilot_bridge() -> UnderwritingCopilotBridge:
    service = get_underwriting_service()
    return UnderwritingCopilotBridge(
        get_settings(),
        repository=service.repository,
        responses_client=service.responses_client,
    )
