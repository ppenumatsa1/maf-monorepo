from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from app.api.v1.routers.chat import router as chat_router
from app.api.v1.routers.copilotkit import router as copilotkit_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.hitl import router as hitl_router
from app.api.v1.routers.sessions import router as sessions_router
from app.api.v1.routers.workflows import router as workflows_router
from app.core.database import postgres_db
from app.core.telemetry import instrument_fastapi_app, setup_observability
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

setup_observability()


def _trusted_frontend_origins() -> list[str]:
    configured = os.getenv("FRONTEND_ORIGIN", "").strip()
    if configured:
        parsed = urlsplit(configured)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise RuntimeError("FRONTEND_ORIGIN must be an absolute HTTP(S) origin.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise RuntimeError("FRONTEND_ORIGIN must be an absolute HTTP(S) origin.")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise RuntimeError("FRONTEND_ORIGIN must not include a path, query, or fragment.")
        return [configured[:-1] if parsed.path == "/" else configured]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        postgres_db.ensure_schema()
        yield
    finally:
        postgres_db.close()


app = FastAPI(
    title="MAF Multi-Agent Orchestration Demo",
    version="0.1.0",
    lifespan=lifespan,
)
instrument_fastapi_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_trusted_frontend_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(copilotkit_router)
app.include_router(hitl_router)
app.include_router(workflows_router)
app.include_router(sessions_router)
app.include_router(health_router)
