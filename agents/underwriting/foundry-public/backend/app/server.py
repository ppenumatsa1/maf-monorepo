from __future__ import annotations

from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.copilotkit import router as copilotkit_router
from app.api.v1.routes.underwriting import router as underwriting_router
from app.api.v1.routes.underwriting import service as underwriting_service
from app.core.config import load_settings
from app.core.observability import configure_observability, instrument_http_request
from app.maf.agui import build_underwriting_agui_agent

settings = load_settings()
configure_observability(settings.log_level)
app = FastAPI(title="Underwriting MAF Prototype API", version="0.2.0")
app.middleware("http")(instrument_http_request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(underwriting_router)
app.include_router(copilotkit_router)
add_agent_framework_fastapi_endpoint(
    app=app,
    agent=build_underwriting_agui_agent(underwriting_service),
    path="/api/v1/underwriting/ag-ui",
    tags=["underwriting"],
)
