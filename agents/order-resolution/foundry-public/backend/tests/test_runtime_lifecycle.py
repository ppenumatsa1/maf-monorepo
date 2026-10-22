from __future__ import annotations

import pytest
from app import main as main_module


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


def test_configured_frontend_origin_is_the_only_trusted_cors_origin(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://orders.example.com/")

    assert main_module._trusted_frontend_origins() == ["https://orders.example.com"]


def test_local_cors_origins_remain_available_without_configuration(monkeypatch) -> None:
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)

    origins = main_module._trusted_frontend_origins()

    assert origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert "*" not in origins


def test_frontend_origin_rejects_paths(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://orders.example.com/untrusted-path")

    with pytest.raises(RuntimeError, match="must not include a path"):
        main_module._trusted_frontend_origins()
