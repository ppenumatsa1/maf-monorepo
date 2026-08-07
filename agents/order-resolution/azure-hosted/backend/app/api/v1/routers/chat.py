from __future__ import annotations

from collections.abc import AsyncGenerator

from app.api.v1.schemas.chat import ChatRunRequest, ChatRunResponse
from app.core.container import event_bus, order_resolution_service, workflow_run_repository
from app.modules.order_resolution.agui import (
    agui_run_started_event,
    encode_agui_sse,
    is_safe_thread_id,
    native_agui_events_for_workflow_event,
)
from app.modules.order_resolution.durable_events import iter_durable_workflow_events
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _require_selected_thread(thread_id: str) -> None:
    if (
        not is_safe_thread_id(thread_id)
        or workflow_run_repository.get_workflow_run(thread_id) is None
    ):
        raise HTTPException(status_code=404, detail="Selected workflow thread was not found.")


async def _agui_stream(thread_id: str) -> AsyncGenerator[str, None]:
    yield encode_agui_sse(agui_run_started_event(thread_id))
    async for workflow_event in iter_durable_workflow_events(
        thread_id,
        workflow_run_repository.list_workflow_events,
        emit_heartbeats=True,
    ):
        if workflow_event is None:
            yield ": ping\n\n"
            continue
        for event in native_agui_events_for_workflow_event(workflow_event):
            yield encode_agui_sse(event)


@router.post("/run", response_model=ChatRunResponse)
async def run_chat(request: ChatRunRequest) -> ChatRunResponse:
    return await order_resolution_service.start_chat_run(request)


@router.get("/stream/{thread_id}")
async def stream_chat(thread_id: str) -> StreamingResponse:
    return StreamingResponse(
        event_bus.sse_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/{thread_id}/rich")
async def stream_chat_rich(thread_id: str) -> StreamingResponse:
    return StreamingResponse(
        event_bus.rich_sse_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/{thread_id}/ag-ui")
async def stream_chat_agui(thread_id: str) -> StreamingResponse:
    _require_selected_thread(thread_id)
    return StreamingResponse(
        _agui_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
