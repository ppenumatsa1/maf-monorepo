from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from app.api.v1.routers import copilotkit as copilotkit_router
from app.api.v1.schemas.chat import ChatRunRequest
from app.api.v1.schemas.copilotkit import CopilotKitBridgeRequest
from app.api.v1.schemas.hitl import HitlResponseRequest
from app.infrastructure.events import EventBus
from app.maf.middleware import (
    WorkflowEventEnricher,
    WorkflowMiddlewareContext,
    execute_with_failure_event,
)
from app.modules.order_resolution import events as event_types
from app.modules.order_resolution.agui import native_agui_events_for_workflow_event
from app.modules.order_resolution.durable_events import iter_durable_workflow_events
from app.modules.order_resolution.models import WorkflowContext, WorkflowEvent
from app.modules.order_resolution.projections import WorkflowRunEventProjector
from app.modules.order_resolution.rich_events import rich_events_for_workflow_event
from app.modules.order_resolution.service import OrderResolutionService


class FakeWorkflow:
    def __init__(self) -> None:
        self.started_context: WorkflowContext | None = None
        self.hitl_response: dict[str, Any] | None = None

    async def start(self, context: WorkflowContext) -> None:
        self.started_context = context

    async def handle_hitl_response(
        self,
        checkpoint_id: str,
        decision: str,
        reviewer: str,
        comments: str | None,
    ) -> str:
        self.hitl_response = {
            "checkpoint_id": checkpoint_id,
            "decision": decision,
            "reviewer": reviewer,
            "comments": comments,
        }
        return "thread-123"


class FakeWorkflowRunRepository:
    def __init__(self) -> None:
        self.created_runs: list[dict[str, Any]] = []
        self.events: list[WorkflowEvent] = []
        self.status_updates: list[tuple[str, str]] = []
        self.stage_updates: list[tuple[str, str | None]] = []
        self.latest_outputs: list[tuple[str, dict[str, Any]]] = []
        self.pending_approvals: list[tuple[str, dict[str, Any]]] = []
        self.resolved_approvals: list[dict[str, Any]] = []

    def create_workflow_run(
        self,
        thread_id: str,
        input_text: str,
        session_id: str | None = None,
        customer_id: str | None = None,
    ) -> None:
        self.created_runs.append(
            {
                "thread_id": thread_id,
                "input_text": input_text,
                "session_id": session_id,
                "customer_id": customer_id,
            }
        )

    def append_workflow_event(self, _thread_id: str, event: WorkflowEvent) -> None:
        self.events.append(event)

    def update_current_stage(self, thread_id: str, stage: str | None) -> None:
        self.stage_updates.append((thread_id, stage))

    def add_pending_approval(self, thread_id: str, approval: dict[str, Any]) -> None:
        self.pending_approvals.append((thread_id, approval))

    def update_workflow_status(self, thread_id: str, status: str) -> None:
        self.status_updates.append((thread_id, status))

    def resolve_approval(
        self,
        thread_id: str,
        checkpoint_id: str,
        decision: str,
        comment: str | None,
        reviewer: str | None,
    ) -> None:
        self.resolved_approvals.append(
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "decision": decision,
                "comment": comment,
                "reviewer": reviewer,
            }
        )

    def update_latest_output(self, thread_id: str, output: dict[str, Any]) -> None:
        self.latest_outputs.append((thread_id, output))


@pytest.mark.asyncio
async def test_order_resolution_service_starts_workflow_through_facade() -> None:
    workflow = FakeWorkflow()
    repository = FakeWorkflowRunRepository()
    service = OrderResolutionService(
        workflow=workflow,
        workflow_run_repository=repository,
    )

    response = await service.start_chat_run(
        ChatRunRequest(
            message="Order ORD-1001 arrived late.",
            thread_id="thread-123",
            session_id="session-123",
            customer_id="cust-123",
        )
    )

    assert response.thread_id == "thread-123"
    assert workflow.started_context == WorkflowContext(
        run_id=response.run_id,
        thread_id="thread-123",
        session_id="session-123",
        customer_id="cust-123",
        user_message="Order ORD-1001 arrived late.",
    )
    assert repository.created_runs == [
        {
            "thread_id": "thread-123",
            "input_text": "Order ORD-1001 arrived late.",
            "session_id": "session-123",
            "customer_id": "cust-123",
        }
    ]


@pytest.mark.asyncio
async def test_order_resolution_service_handles_hitl_through_facade() -> None:
    workflow = FakeWorkflow()
    repository = FakeWorkflowRunRepository()
    service = OrderResolutionService(
        workflow=workflow,
        workflow_run_repository=repository,
    )

    response = await service.respond_hitl(
        HitlResponseRequest(
            checkpoint_id="checkpoint-123",
            decision="approve",
            reviewer="reviewer-123",
            comments="approved",
        )
    )

    assert response.thread_id == "thread-123"
    assert workflow.hitl_response == {
        "checkpoint_id": "checkpoint-123",
        "decision": "approve",
        "reviewer": "reviewer-123",
        "comments": "approved",
    }


def test_workflow_run_event_projector_syncs_hitl_and_output_events() -> None:
    repository = FakeWorkflowRunRepository()
    projector = WorkflowRunEventProjector(repository)

    projector.sync_event_to_run(
        WorkflowEvent(
            type="hitl.request",
            thread_id="thread-123",
            payload={"checkpoint_id": "11111111-1111-1111-1111-111111111111"},
        )
    )
    projector.sync_event_to_run(
        WorkflowEvent(
            type="hitl.response",
            thread_id="thread-123",
            payload={
                "checkpoint_id": "11111111-1111-1111-1111-111111111111",
                "decision": "approve",
                "reviewer": "reviewer-123",
                "comments": "approved",
            },
        )
    )
    projector.sync_event_to_run(
        WorkflowEvent(
            type="workflow.output",
            thread_id="thread-123",
            payload={"status": "completed", "message": "done"},
        )
    )

    assert repository.pending_approvals == [
        (
            "thread-123",
            {"checkpoint_id": "11111111-1111-1111-1111-111111111111"},
        )
    ]
    assert repository.resolved_approvals == [
        {
            "thread_id": "thread-123",
            "checkpoint_id": "11111111-1111-1111-1111-111111111111",
            "decision": "approve",
            "comment": "approved",
            "reviewer": "reviewer-123",
        }
    ]
    assert repository.latest_outputs == [("thread-123", {"status": "completed", "message": "done"})]
    assert repository.status_updates == [
        ("thread-123", "waiting_approval"),
        ("thread-123", "running"),
        ("thread-123", "completed"),
    ]


def test_workflow_event_enricher_adds_correlation_without_overwriting_payload() -> None:
    context = WorkflowContext(
        run_id="run-123",
        thread_id="thread-123",
        session_id="session-123",
        customer_id="cust-123",
        user_message="Order ORD-1001 arrived late.",
    )
    payload = {"agent": "triage", "workflow_run_id": "existing-run"}

    enriched = WorkflowEventEnricher().enrich(context, payload)

    assert enriched == {
        "agent": "triage",
        "workflow_run_id": "existing-run",
        "session_id": "session-123",
    }
    assert payload == {"agent": "triage", "workflow_run_id": "existing-run"}


@pytest.mark.asyncio
async def test_workflow_middleware_emits_failure_before_reraising() -> None:
    context = WorkflowContext(
        run_id="run-123",
        thread_id="thread-123",
        session_id="session-123",
        customer_id="cust-123",
        user_message="Order ORD-1001 arrived late.",
    )
    failures: list[tuple[WorkflowContext, Exception]] = []

    async def operation() -> None:
        raise RuntimeError("model unavailable")

    async def emit_failure(run_context: WorkflowContext, exc: Exception) -> None:
        failures.append((run_context, exc))

    with pytest.raises(RuntimeError, match="model unavailable"):
        await execute_with_failure_event(
            WorkflowMiddlewareContext(workflow="order_resolution", run=context),
            operation,
            emit_failure,
        )

    assert failures[0][0] == context
    assert str(failures[0][1]) == "model unavailable"


def test_rich_events_project_native_stage_tool_hitl_and_output_events() -> None:
    stage_events = rich_events_for_workflow_event(
        WorkflowEvent(
            type=event_types.WORKFLOW_STAGE,
            thread_id="thread-123",
            payload={"agent": "triage", "status": "started", "workflow_run_id": "run-123"},
        )
    )
    tool_events = rich_events_for_workflow_event(
        WorkflowEvent(
            type=event_types.TOOL_CALL,
            thread_id="thread-123",
            payload={"local_tool": "fetch_order_status", "workflow_run_id": "run-123"},
        )
    )
    hitl_events = rich_events_for_workflow_event(
        WorkflowEvent(
            type=event_types.HITL_REQUEST,
            thread_id="thread-123",
            payload={"checkpoint_id": "checkpoint-123", "workflow_run_id": "run-123"},
        )
    )
    output_events = rich_events_for_workflow_event(
        WorkflowEvent(
            type=event_types.WORKFLOW_OUTPUT,
            thread_id="thread-123",
            payload={"message": "done", "status": "completed", "workflow_run_id": "run-123"},
        )
    )

    assert stage_events[0]["type"] == "STEP_STARTED"
    assert stage_events[0]["stepName"] == "triage"
    assert [event["type"] for event in tool_events] == [
        "TOOL_CALL_START",
        "TOOL_CALL_RESULT",
        "TOOL_CALL_END",
    ]
    assert hitl_events[0]["type"] == "CUSTOM"
    assert hitl_events[0]["name"] == "hitl.request"
    assert [event["type"] for event in output_events] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]


@pytest.mark.asyncio
async def test_event_bus_rich_stream_emits_additive_agui_envelope() -> None:
    event_bus = EventBus()
    await event_bus.publish(
        WorkflowEvent(
            type=event_types.WORKFLOW_OUTPUT,
            thread_id="thread-123",
            payload={"message": "done", "status": "completed"},
        )
    )

    stream = event_bus.rich_sse_stream("thread-123")
    try:
        chunk = await stream.__anext__()
    finally:
        await stream.aclose()

    assert chunk.startswith("event: workflow.rich\n")
    data = chunk.split("data: ", 1)[1].strip()
    envelope = json.loads(data)
    assert envelope["type"] == "workflow.rich"
    assert envelope["version"] == "ag-ui-compatible.v1"
    assert envelope["native_event"]["type"] == "workflow.output"
    assert envelope["events"][0]["type"] == "RUN_STARTED"
    assert envelope["events"][-1]["type"] == "RUN_FINISHED"


def test_native_agui_projection_allowlists_and_redacts_workflow_payloads() -> None:
    checkpoint_id = str(uuid4())
    secret_values = {
        "ORD-9000",
        "customer@example.com",
        "******",
        "confidential policy text",
        "reviewer-private",
        "untrusted-checkpoint",
        "raw workflow prompt",
        "failure credential private-token",
    }
    events = [
        WorkflowEvent(
            type=event_types.WORKFLOW_STAGE,
            thread_id="thread-123",
            payload={
                "agent": "triage",
                "status": "completed",
                "result": {"prompt": "raw workflow prompt"},
            },
        ),
        WorkflowEvent(
            type=event_types.TOOL_CALL,
            thread_id="thread-123",
            payload={
                "local_tool": "fetch_order_status/fetch_policy",
                "order": {"id": "ORD-9000", "email": "customer@example.com"},
                "policy": "confidential policy text",
                "mcp_result": {"authorization": "******"},
            },
        ),
        WorkflowEvent(
            type=event_types.HITL_REQUEST,
            thread_id="thread-123",
            payload={
                "checkpoint_id": checkpoint_id,
                "order_id": "ORD-9000",
                "question": "raw workflow prompt",
            },
        ),
        WorkflowEvent(
            type=event_types.HITL_RESPONSE,
            thread_id="thread-123",
            payload={
                "checkpoint_id": "untrusted-checkpoint",
                "decision": "approve",
                "reviewer": "reviewer-private",
            },
        ),
        WorkflowEvent(
            type=event_types.WORKFLOW_FAILED,
            thread_id="thread-123",
            payload={"message": "failure credential private-token"},
        ),
        WorkflowEvent(
            type=event_types.WORKFLOW_OUTPUT,
            thread_id="thread-123",
            payload={
                "message": "ORD-9000 and customer@example.com",
                "status": "completed",
                "submission_id": "******",
            },
        ),
    ]

    projected = [
        agui_event
        for event in events
        for agui_event in native_agui_events_for_workflow_event(event)
    ]
    serialized = json.dumps(projected)

    assert [event["type"] for event in projected] == [
        "STEP_FINISHED",
        "TOOL_CALL_START",
        "TOOL_CALL_RESULT",
        "TOOL_CALL_END",
        "CUSTOM",
        "CUSTOM",
        "RUN_ERROR",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert projected[1]["toolCallName"] == "policy-lookup"
    assert projected[2]["content"] == {"status": "completed"}
    assert projected[4]["value"] == {"status": "pending", "checkpointId": checkpoint_id}
    assert projected[5]["value"] == {"decision": "approve"}
    assert next(event for event in projected if event["type"] == "RUN_ERROR") == {
        "type": "RUN_ERROR",
        "message": "The resolution workflow could not be completed.",
        "code": "workflow_failed",
    }
    assert next(event for event in projected if event["type"] == "TEXT_MESSAGE_CONTENT")[
        "delta"
    ] == ("The resolution workflow completed.")
    assert "rawEvent" not in serialized
    assert "native_event" not in serialized
    assert all(value not in serialized for value in secret_values)


@pytest.mark.asyncio
async def test_durable_event_iterator_replays_persisted_pages_before_tailing() -> None:
    persisted_event = WorkflowEvent(
        type=event_types.WORKFLOW_STAGE,
        thread_id="thread-123",
        payload={"agent": "triage", "status": "started"},
    )
    calls: list[tuple[str, int, str | None]] = []

    def read_page(thread_id: str, limit: int, cursor: str | None):
        calls.append((thread_id, limit, cursor))
        return [persisted_event], None, False

    stream = iter_durable_workflow_events("thread-123", read_page)
    try:
        assert await stream.__anext__() == persisted_event
    finally:
        await stream.aclose()

    assert calls == [("thread-123", 100, None)]

    idle_stream = iter_durable_workflow_events(
        "thread-123",
        lambda _thread_id, _limit, _cursor: ([], None, False),
        poll_interval_seconds=0,
        emit_heartbeats=True,
    )
    try:
        assert await idle_stream.__anext__() is None
    finally:
        await idle_stream.aclose()


@pytest.mark.asyncio
async def test_copilotkit_bridge_streams_selected_thread_projection_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted_event = WorkflowEvent(
        type=event_types.WORKFLOW_OUTPUT,
        thread_id="thread-123",
        payload={
            "message": "Order ORD-9000 uses customer@example.com",
            "status": "completed",
            "credential": "******",
        },
    )

    class SelectedThreadRepository:
        def get_workflow_run(self, thread_id: str) -> SimpleNamespace | None:
            return SimpleNamespace(thread_id=thread_id) if thread_id == "thread-123" else None

        def list_workflow_events(
            self,
            thread_id: str,
            limit: int,
            cursor: str | None,
        ) -> tuple[list[WorkflowEvent], str | None, bool]:
            assert thread_id == "thread-123"
            assert limit == 100
            assert cursor is None
            return [persisted_event], None, False

    monkeypatch.setattr(copilotkit_router, "workflow_run_repository", SelectedThreadRepository())
    response = await copilotkit_router.stream_selected_thread(
        CopilotKitBridgeRequest(
            threadId="thread-123",
            messages=[{"role": "user", "content": "raw workflow prompt"}],
        )
    )
    stream = response.body_iterator
    try:
        started = await stream.__anext__()
        output_start = await stream.__anext__()
        output_content = await stream.__anext__()
    finally:
        await stream.aclose()

    serialized = b"".join(
        item if isinstance(item, bytes) else item.encode()
        for item in [started, output_start, output_content]
    ).decode()
    assert '"type":"RUN_STARTED"' in serialized
    assert '"type":"TEXT_MESSAGE_CONTENT"' in serialized
    assert "The resolution workflow completed." in serialized
    assert "ORD-9000" not in serialized
    assert "customer@example.com" not in serialized
    assert "private-token" not in serialized
    assert "raw workflow prompt" not in serialized


def test_copilotkit_bridge_request_accepts_standard_input_without_exposing_it() -> None:
    request = CopilotKitBridgeRequest(
        threadId="thread-123",
        runId="run-123",
        messages=[{"role": "user", "content": "raw workflow prompt"}],
        state={"credential": "******"},
        tools=[{"name": "unsafe_tool"}],
        context=[{"order": "ORD-9000"}],
        forwardedProps={"prompt": "raw workflow prompt"},
    )

    assert request.thread_id == "thread-123"
    assert request.model_dump() == {"thread_id": "thread-123"}
    with pytest.raises(ValueError):
        CopilotKitBridgeRequest(threadId="thread-123", apiKey="private-token")
