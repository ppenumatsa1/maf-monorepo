from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.core.telemetry import record_business_event
from app.modules.order_resolution.models import WorkflowContext

T = TypeVar("T")


@dataclass
class WorkflowMiddlewareContext:
    workflow: str
    run: WorkflowContext
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowEventEnricher:
    def enrich(
        self,
        context: WorkflowContext,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        enriched = dict(payload)
        enriched["workflow_run_id"] = context.run_id
        enriched["session_id"] = context.session_id
        enriched["thread_id"] = context.thread_id
        if event_id is not None:
            enriched["event_id"] = event_id
        return enriched


def safe_failure_payload(exc: Exception) -> dict[str, str]:
    return {
        "status": "failed",
        "code": exc.__class__.__name__,
        "message": "The resolution workflow could not be completed.",
    }


class MafUsageTracker:
    def observe_stream_event(
        self, event: Any, *, workflow_name: str, context: WorkflowContext
    ) -> None:
        event_type = getattr(event, "type", None)
        if event_type not in {"executor_invoked", "executor_completed", "output"}:
            return
        attributes = {
            "maf.workflow": workflow_name,
            "maf.event.type": event_type,
            "maf.executor_id": getattr(event, "executor_id", None),
            "workflow.thread_id": context.thread_id,
            "workflow.run_id": context.run_id,
            "workflow.session_id": context.session_id,
        }
        record_business_event("maf.middleware.stream_event", attributes)


async def execute_with_failure_event(
    middleware_context: WorkflowMiddlewareContext,
    operation: Callable[[], Awaitable[T]],
    emit_failure: Callable[[WorkflowContext, Exception], Awaitable[None]],
) -> T:
    try:
        return await operation()
    except Exception as exc:
        await emit_failure(middleware_context.run, exc)
        raise


def create_chat_usage_middleware(
    *,
    workflow_name: str,
    context: WorkflowContext,
) -> Callable[[Any, Callable[[], Awaitable[None]]], Awaitable[None]]:
    from agent_framework import ChatResponse, ChatResponseUpdate, chat_middleware

    @chat_middleware
    async def capture_usage(chat_context: Any, call_next: Callable[[], Awaitable[None]]) -> None:
        if getattr(chat_context, "stream", False):

            def capture_usage_update(update: ChatResponseUpdate) -> ChatResponseUpdate:
                for content in getattr(update, "contents", []):
                    if getattr(content, "type", None) == "usage":
                        record_business_event(
                            "maf.middleware.usage",
                            {
                                "maf.workflow": workflow_name,
                                "workflow.thread_id": context.thread_id,
                                "workflow.run_id": context.run_id,
                                "workflow.session_id": context.session_id,
                            },
                        )
                return update

            def capture_final_usage(result: ChatResponse) -> ChatResponse:
                if getattr(result, "usage_details", None):
                    record_business_event(
                        "maf.middleware.usage",
                        {
                            "maf.workflow": workflow_name,
                            "workflow.thread_id": context.thread_id,
                            "workflow.run_id": context.run_id,
                            "workflow.session_id": context.session_id,
                        },
                    )
                return result

            chat_context.stream_transform_hooks.append(capture_usage_update)
            chat_context.stream_result_hooks.append(capture_final_usage)
            await call_next()
            return

        await call_next()
        response = getattr(chat_context, "result", None)
        if isinstance(response, ChatResponse) and response.usage_details:
            record_business_event(
                "maf.middleware.usage",
                {
                    "maf.workflow": workflow_name,
                    "workflow.thread_id": context.thread_id,
                    "workflow.run_id": context.run_id,
                    "workflow.session_id": context.session_id,
                },
            )

    return capture_usage


__all__ = [
    "MafUsageTracker",
    "WorkflowEventEnricher",
    "WorkflowMiddlewareContext",
    "create_chat_usage_middleware",
    "execute_with_failure_event",
    "safe_failure_payload",
]
