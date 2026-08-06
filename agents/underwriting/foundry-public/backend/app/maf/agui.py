from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Never

from ag_ui.core import ActivitySnapshotEvent, BaseEvent, CustomEvent
from agent_framework import Executor, Message, Workflow, WorkflowBuilder, WorkflowContext, handler
from agent_framework.ag_ui import AgentFrameworkWorkflow

from app.core.telemetry import annotate_current_span
from app.modules.underwriting.models import UnderwritingApplication
from app.modules.underwriting.service import UnderwritingHostedAdapter

logger = logging.getLogger(__name__)


class UnderwritingAGUIExecutor(Executor):
    def __init__(self, service: UnderwritingHostedAdapter):
        super().__init__(id="underwriting_live_run")
        self.service = service

    @handler
    async def run(self, messages: list[Message], ctx: WorkflowContext[Never, BaseEvent]) -> None:
        request = _parse_request(messages)
        workflow_run_id = request["workflow_run_id"]
        action = request.get("action", "start")
        annotate_current_span(workflow_run_id, action)
        if action == "resume":
            task = asyncio.create_task(self.service.resume_workflow(workflow_run_id))
        else:
            application = UnderwritingApplication(**request["application"])
            task = asyncio.create_task(
                self.service.start_workflow(
                    workflow_run_id=workflow_run_id,
                    application=application,
                    fail_risk_once=bool(request.get("fail_risk_once", False)),
                    fail_credit_randomly=bool(request.get("fail_credit_randomly", False)),
                    crash_after_executor=request.get("crash_after_executor"),
                )
            )

        emitted_event_ids: set[int] = set()
        while not task.done():
            await _emit_new_events(
                ctx=ctx,
                service=self.service,
                workflow_run_id=workflow_run_id,
                emitted_event_ids=emitted_event_ids,
            )
            await asyncio.sleep(0.1)

        try:
            await task
        except Exception:
            logger.exception(
                "hosted_workflow_failed workflow_run_id=%s action=%s",
                workflow_run_id,
                action,
            )
            raise

        await _emit_new_events(
            ctx=ctx,
            service=self.service,
            workflow_run_id=workflow_run_id,
            emitted_event_ids=emitted_event_ids,
        )


def build_underwriting_agui_workflow(service: UnderwritingHostedAdapter) -> Workflow:
    executor = UnderwritingAGUIExecutor(service)
    return WorkflowBuilder(
        name="underwriting-agui-live-run",
        start_executor=executor,
        output_from=[executor],
    ).build()


class UnderwritingAGUIWorkflow(AgentFrameworkWorkflow):
    async def run(self, input_data: dict[str, Any]) -> AsyncGenerator[BaseEvent, None]:
        async for event in super().run(input_data):
            if isinstance(event, ActivitySnapshotEvent):
                continue
            yield event


def build_underwriting_agui_agent(service: UnderwritingHostedAdapter) -> AgentFrameworkWorkflow:
    return UnderwritingAGUIWorkflow(
        workflow_factory=lambda _thread_id: build_underwriting_agui_workflow(service),
        name="underwriting-live-run",
        description="Streams safe underwriting workflow progress while the durable run executes.",
    )


def _parse_request(messages: list[Message]) -> dict[str, Any]:
    for message in reversed(messages):
        if message.role != "user" or not message.text:
            continue
        try:
            payload = json.loads(message.text)
        except json.JSONDecodeError as exc:
            raise ValueError("AG-UI request message must contain JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("AG-UI request payload must be an object")
        workflow_run_id = payload.get("workflow_run_id")
        if not isinstance(workflow_run_id, str) or not workflow_run_id.startswith("run-"):
            raise ValueError("AG-UI request requires a workflow_run_id beginning with 'run-'")
        return payload
    raise ValueError("AG-UI request requires a user message")


async def _emit_new_events(
    *,
    ctx: WorkflowContext[Never, BaseEvent],
    service: UnderwritingHostedAdapter,
    workflow_run_id: str,
    emitted_event_ids: set[int],
) -> None:
    for event in service.get_events(workflow_run_id):
        event_id = event.get("id")
        if not isinstance(event_id, int) or event_id in emitted_event_ids:
            continue
        emitted_event_ids.add(event_id)
        await ctx.yield_output(
            CustomEvent(
                name="underwriting.event",
                value={
                    "workflowRunId": workflow_run_id,
                    "eventType": str(event.get("event_type", "event")),
                    "executorName": str(event.get("executor_name", "workflow")),
                    "createdAt": str(event.get("created_at", "")),
                },
            )
        )
