from __future__ import annotations

import pytest
from app import main as main_module
from app.core.database import postgres_db
from app.infrastructure.persistence.checkpoint_store import CheckpointStore
from app.infrastructure.persistence.idempotency_store import IdempotencyStore
from app.infrastructure.persistence.session_memory import PostgresSessionMemoryStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


@pytest.mark.asyncio
async def test_fastapi_lifespan_validates_database_and_closes_pool(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        main_module.postgres_db,
        "ensure_schema",
        lambda: calls.append("ensure_schema"),
    )
    monkeypatch.setattr(
        main_module.postgres_db,
        "close",
        lambda: calls.append("close"),
    )

    async with main_module.lifespan(main_module.app):
        assert calls == ["ensure_schema"]

    assert calls == ["ensure_schema", "close"]


@pytest.mark.asyncio
async def test_fastapi_lifespan_closes_pool_when_startup_validation_fails(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fail_schema_validation() -> None:
        calls.append("ensure_schema")
        raise RuntimeError("schema not ready")

    monkeypatch.setattr(main_module.postgres_db, "ensure_schema", fail_schema_validation)
    monkeypatch.setattr(
        main_module.postgres_db,
        "close",
        lambda: calls.append("close"),
    )

    with pytest.raises(RuntimeError, match="schema not ready"):
        async with main_module.lifespan(main_module.app):
            pass

    assert calls == ["ensure_schema", "close"]


def test_persistence_adapters_do_not_initialize_schema_in_constructors(
    monkeypatch,
) -> None:
    restartable_pool = object()
    monkeypatch.setattr(postgres_db, "pool", restartable_pool)
    monkeypatch.setattr(
        postgres_db,
        "ensure_schema",
        lambda: pytest.fail("adapter constructor attempted schema initialization"),
    )

    adapters = (
        CheckpointStore(),
        IdempotencyStore(),
        PostgresSessionMemoryStore(),
        WorkflowRunRepository(),
    )

    assert all(adapter._pool is restartable_pool for adapter in adapters)


def test_configured_frontend_origin_is_the_only_trusted_cors_origin(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://orders.example.com/")

    assert main_module._trusted_frontend_origins() == ["https://orders.example.com"]


def test_local_cors_origins_remain_available_without_configuration(monkeypatch) -> None:
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)

    origins = main_module._trusted_frontend_origins()

    assert origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert "*" not in origins


@pytest.mark.parametrize(
    "origin,error",
    [
        ("https://orders.example.com/untrusted-path", "must not include a path"),
        ("https://user@orders.example.com", "must be an absolute HTTP"),
        ("https://orders.example.com:not-a-port", "must be an absolute HTTP"),
        ("ftp://orders.example.com", "must be an absolute HTTP"),
    ],
)
def test_frontend_origin_rejects_untrusted_values(
    monkeypatch,
    origin: str,
    error: str,
) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", origin)

    with pytest.raises(RuntimeError, match=error):
        main_module._trusted_frontend_origins()
