from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware, FunctionTool

from app.core.config import Settings
from app.core.telemetry import workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting import events as event_types
from app.modules.underwriting.models import CheckType


@dataclass(slots=True)
class OperationContext:
    workflow_run_id: str
    application_id: str
    check_type: CheckType
    operation_name: str
    executor_name: str
    idempotency_key: str


@dataclass(slots=True)
class ResilientInvocationResult:
    idempotency_key: str
    payload: dict[str, Any]
    from_idempotency: bool


class IdempotencyMiddleware(FunctionMiddleware):
    def __init__(self, repository: WorkflowRunRepository):
        self.repository = repository

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        op: OperationContext = context.metadata["operation_context"]
        existing = self.repository.get_idempotency(op.idempotency_key)
        persisted_result = self.repository.get_underwriting_result_by_key(op.idempotency_key)

        if existing and existing.get("status") == "completed":
            payload = existing.get("result_json") or persisted_result
            if payload is None:
                raise ValueError(
                    f"idempotency completed without payload for key={op.idempotency_key}"
                )
            with workflow_stage_span(
                "stage.idempotency_skip",
                {
                    "workflow.run_id": op.workflow_run_id,
                    "underwriting.application_id": op.application_id,
                    "underwriting.check_type": op.check_type.value,
                    "workflow.executor": op.executor_name,
                    "workflow.idempotency_source": "record",
                },
            ):
                self.repository.log_event(
                    op.workflow_run_id,
                    event_types.IDEMPOTENCY_SKIP,
                    op.executor_name,
                    {"idempotency_key": op.idempotency_key},
                )
            context.metadata["from_idempotency"] = True
            context.result = payload
            return

        if persisted_result:
            with workflow_stage_span(
                "stage.idempotency_skip",
                {
                    "workflow.run_id": op.workflow_run_id,
                    "underwriting.application_id": op.application_id,
                    "underwriting.check_type": op.check_type.value,
                    "workflow.executor": op.executor_name,
                    "workflow.idempotency_source": "result_row",
                },
            ):
                self.repository.upsert_idempotency(
                    op.idempotency_key, op.operation_name, "completed", persisted_result
                )
                self.repository.log_event(
                    op.workflow_run_id,
                    event_types.IDEMPOTENCY_SKIP,
                    op.executor_name,
                    {"idempotency_key": op.idempotency_key, "source": "result_row"},
                )
            context.metadata["from_idempotency"] = True
            context.result = persisted_result
            return

        self.repository.upsert_idempotency(
            op.idempotency_key, op.operation_name, "in_progress", None
        )
        await next(context)


class RetryBackoffMiddleware(FunctionMiddleware):
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        op: OperationContext = context.metadata["operation_context"]
        attempt = 1
        while True:
            try:
                with workflow_stage_span(
                    "stage.retry_attempt",
                    {
                        "workflow.run_id": op.workflow_run_id,
                        "underwriting.application_id": op.application_id,
                        "workflow.executor": op.executor_name,
                        "workflow.retry_attempt": attempt,
                    },
                ):
                    self.repository.log_event(
                        op.workflow_run_id,
                        event_types.RETRY_ATTEMPT,
                        op.executor_name,
                        {"operation_name": op.operation_name, "attempt": attempt},
                    )
                    await next(context)
                return
            except Exception as exc:
                if attempt >= self.settings.retry_max_attempts:
                    with workflow_stage_span(
                        "stage.retry_exhausted",
                        {
                            "workflow.run_id": op.workflow_run_id,
                            "underwriting.application_id": op.application_id,
                            "underwriting.check_type": op.check_type.value,
                            "workflow.executor": op.executor_name,
                            "workflow.retry_attempt": attempt,
                        },
                    ):
                        self.repository.log_event(
                            op.workflow_run_id,
                            event_types.RETRY_EXHAUSTED,
                            op.executor_name,
                            {
                                "operation_name": op.operation_name,
                                "attempt": attempt,
                                "error": str(exc),
                            },
                        )
                    raise
                delay_s = (
                    (2 ** (attempt - 1)) * self.settings.retry_base_delay_ms
                    + random.randint(0, self.settings.retry_jitter_ms)
                ) / 1000.0
                with workflow_stage_span(
                    "stage.retry_backoff",
                    {
                        "workflow.run_id": op.workflow_run_id,
                        "underwriting.application_id": op.application_id,
                        "underwriting.check_type": op.check_type.value,
                        "workflow.executor": op.executor_name,
                        "workflow.retry_attempt": attempt,
                        "workflow.retry_delay_ms": round(delay_s * 1000),
                    },
                ):
                    self.repository.log_event(
                        op.workflow_run_id,
                        event_types.RETRY_BACKOFF,
                        op.executor_name,
                        {
                            "operation_name": op.operation_name,
                            "attempt": attempt,
                            "error": str(exc),
                            "delay_seconds": delay_s,
                        },
                    )
                await asyncio.sleep(delay_s)
                attempt += 1


class FailureInjectionMiddleware(FunctionMiddleware):
    def __init__(self, repository: WorkflowRunRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def process(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        op: OperationContext = context.metadata["operation_context"]
        if op.check_type == CheckType.RISK and self.settings.fail_risk_once:
            marker_key = f"{op.idempotency_key}:fail-once"
            marker = self.repository.get_idempotency(marker_key)
            if marker is None:
                with workflow_stage_span(
                    "stage.failure_injected",
                    {
                        "workflow.run_id": op.workflow_run_id,
                        "underwriting.application_id": op.application_id,
                        "underwriting.check_type": op.check_type.value,
                        "workflow.executor": op.executor_name,
                        "workflow.failure_mode": "risk_once",
                    },
                ):
                    self.repository.upsert_idempotency(
                        marker_key, "failure-injection", "completed", {"injected": True}
                    )
                    raise RuntimeError("Injected FAIL_RISK_ONCE failure")

        if op.check_type == CheckType.CREDIT and self.settings.fail_credit_randomly:
            if self.repository.should_fail_credit_randomly():
                with workflow_stage_span(
                    "stage.failure_injected",
                    {
                        "workflow.run_id": op.workflow_run_id,
                        "underwriting.application_id": op.application_id,
                        "underwriting.check_type": op.check_type.value,
                        "workflow.executor": op.executor_name,
                        "workflow.failure_mode": "credit_random",
                    },
                ):
                    raise RuntimeError("Injected FAIL_CREDIT_RANDOMLY failure")

        await next(context)


async def invoke_check_operation(
    *,
    repository: WorkflowRunRepository,
    settings: Settings,
    workflow_run_id: str,
    application_id: str,
    check_type: CheckType | str,
    operation_name: str,
    executor_name: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> ResilientInvocationResult:
    normalized_check_type = CheckType(check_type)
    op = OperationContext(
        workflow_run_id=workflow_run_id,
        application_id=application_id,
        check_type=normalized_check_type,
        operation_name=operation_name,
        executor_name=executor_name,
        idempotency_key=f"underwriting:{application_id}:{normalized_check_type.value}",
    )
    middlewares: list[FunctionMiddleware] = [
        IdempotencyMiddleware(repository),
        RetryBackoffMiddleware(repository, settings),
        FailureInjectionMiddleware(repository, settings),
    ]
    tool = FunctionTool(
        name=operation_name,
        description=f"{normalized_check_type.value} check operation",
        func=operation,
    )
    context = FunctionInvocationContext(
        function=tool, arguments=tool.input_model(), metadata={"operation_context": op}
    )

    async def call_chain(index: int) -> None:
        if index >= len(middlewares):
            context.result = await operation()
            return
        middleware = middlewares[index]
        await middleware.process(context, lambda _ctx: call_chain(index + 1))

    await call_chain(0)
    if not isinstance(context.result, dict):
        raise TypeError(
            f"Expected dict result from operation {operation_name}, got {type(context.result).__name__}"
        )
    return ResilientInvocationResult(
        idempotency_key=op.idempotency_key,
        payload=context.result,
        from_idempotency=bool(context.metadata.get("from_idempotency")),
    )
