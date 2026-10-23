from __future__ import annotations

import asyncio

from app import server as server_module


def test_fastapi_lifespan_initializes_and_closes_runtime(monkeypatch) -> None:
    runtime = object()
    calls: list[object] = []
    monkeypatch.setattr(
        server_module,
        "get_underwriting_service",
        lambda: calls.append("initialize") or runtime,
    )
    monkeypatch.setattr(
        server_module,
        "close_underwriting_runtime",
        lambda service: calls.append(service),
    )

    async def exercise_lifespan() -> None:
        async with server_module.lifespan(server_module.app):
            assert calls == ["initialize"]

    asyncio.run(exercise_lifespan())
    assert calls == ["initialize", runtime]
