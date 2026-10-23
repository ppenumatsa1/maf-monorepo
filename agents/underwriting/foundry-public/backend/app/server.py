from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers.copilotkit import router as copilotkit_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.underwriting import router as underwriting_router
from app.core.container import (
    close_underwriting_runtime,
    get_settings,
    get_underwriting_service,
)
from app.core.observability import configure_observability, instrument_http_request
from app.maf.agui import build_underwriting_agui_agent

settings = get_settings()
configure_observability(settings.log_level)


class _LazyUnderwritingService:
    async def start_run(self, **kwargs: Any) -> dict[str, Any]:
        return await get_underwriting_service().start_run(**kwargs)

    async def resume_run(self, workflow_run_id: str) -> dict[str, Any]:
        return await get_underwriting_service().resume_run(workflow_run_id)

    def get_events(self, workflow_run_id: str) -> list[dict[str, Any]]:
        return get_underwriting_service().get_events(workflow_run_id)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    underwriting_service = get_underwriting_service()
    try:
        yield
    finally:
        close_underwriting_runtime(underwriting_service)


app = FastAPI(
    title="Underwriting MAF Prototype API",
    version="0.2.0",
    lifespan=lifespan,
)
app.middleware("http")(instrument_http_request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(underwriting_router)
app.include_router(copilotkit_router)
app.include_router(health_router)
add_agent_framework_fastapi_endpoint(
    app=app,
    agent=build_underwriting_agui_agent(_LazyUnderwritingService()),  # type: ignore[arg-type]
    path="/api/v1/underwriting/ag-ui",
    tags=["underwriting"],
)
