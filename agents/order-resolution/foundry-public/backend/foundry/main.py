from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any
from uuid import uuid4

from app.api.v1.schemas.chat import ChatRunRequest
from app.api.v1.schemas.hitl import HitlResponseRequest
from app.core import telemetry as _telemetry
from app.core.telemetry import get_tracer
from app.infrastructure.persistence.teams_card_action_repository import (
    TeamsCardActionError,
    TeamsCardActionRepository,
)
from foundry import teams_cards

logger = logging.getLogger(__name__)


def _apply_foundry_model_env_aliases() -> None:
    aliases = {
        "FOUNDRY_PROJECTS_ENDPOINT": "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT_NAME": "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    }
    for canonical_name, hosted_name in aliases.items():
        if os.getenv(canonical_name, "").strip():
            continue
        hosted_value = os.getenv(hosted_name, "").strip()
        if hosted_value:
            os.environ[canonical_name] = hosted_value


def _database_url_host(value: str) -> str:
    if not value:
        return ""
    match = re.match(r"^[a-zA-Z0-9+.-]+://(?:[^@/]+@)?([^:/?]+)", value)
    return match.group(1).strip().lower() if match else ""


def _apply_runtime_database_url_override() -> None:
    runtime_database_url = os.getenv("FOUNDRY_RUNTIME_DATABASE_URL", "").strip()
    if not runtime_database_url:
        runtime_database_url = os.getenv("RUNTIME_DATABASE_URL", "").strip()
    if not runtime_database_url:
        return
    database_url = os.getenv("DATABASE_URL", "").strip()
    database_host = _database_url_host(database_url)
    if not database_url or database_host in {"localhost", "127.0.0.1"}:
        os.environ["DATABASE_URL"] = runtime_database_url


def _apply_appinsights_connection_env_aliases() -> None:
    canonical = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if canonical and not canonical.startswith("${"):
        return

    appinsights_alias = os.getenv("APPINSIGHTS_CONNECTION_STRING", "").strip()
    if not appinsights_alias or appinsights_alias.startswith("${"):
        return

    # AgentServer's bootstrap parser is strict; provide a compact canonical form.
    match = re.search(r"InstrumentationKey=([^;\s]+)", appinsights_alias)
    if match:
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = f"InstrumentationKey={match.group(1)}"
        return

    os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = appinsights_alias


_apply_foundry_model_env_aliases()
_apply_runtime_database_url_override()
_apply_appinsights_connection_env_aliases()

if os.getenv("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS", "").strip().lower() == "true":
    order_resolution_service = None
    teams_card_action_repository = None
    workflow_run_repository = None
else:
    from app.core.database import postgres_db

    postgres_db.ensure_schema()
    from app.core.container import order_resolution_service, workflow_run_repository

    teams_card_action_repository = TeamsCardActionRepository()


@dataclass(frozen=True)
class _ParsedInput:
    conversation_id: str
    message: str | None
    decision: str | None
    checkpoint_id: str | None


def _parse_debug_enabled() -> bool:
    return os.getenv("FOUNDRY_DEBUG_PARSE_INPUT", "").strip().lower() in {"1", "true", "yes", "on"}


def _emit_parse_debug(payload: dict[str, Any], context: Any | None, parsed: _ParsedInput) -> None:
    if not _parse_debug_enabled():
        return

    payload_input = payload.get("input")
    payload_summary: dict[str, Any] = {
        "parsed_conversation_id": parsed.conversation_id,
        "parsed_decision": parsed.decision,
        "parsed_checkpoint_id": parsed.checkpoint_id,
        "parsed_message_preview": (parsed.message or "")[:120],
        "payload_keys": sorted(payload.keys()),
        "input_type": type(payload_input).__name__,
        "has_conversation": isinstance(payload.get("conversation"), dict),
    }
    if isinstance(payload_input, list) and payload_input:
        first_item = payload_input[0]
        payload_summary["input_first_type"] = type(first_item).__name__
        if isinstance(first_item, dict):
            payload_summary["input_first_keys"] = sorted(first_item.keys())

    if context is not None:
        context_attrs = [
            name
            for name in ("id", "session_id", "conversation_id", "request_body")
            if hasattr(context, name)
        ]
        payload_summary["context_attrs"] = context_attrs
        context_request_body = getattr(context, "request_body", None)
        if isinstance(context_request_body, dict):
            payload_summary["context_request_body_keys"] = sorted(context_request_body.keys())

    print(f"FOUNDRY_PARSE_DEBUG {json.dumps(payload_summary, default=str)}", flush=True)


def _load_responses_types() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    # Compatibility shim for hosted images where agentserver-core is missing
    # CHAT_ISOLATION_KEY expected by azure-ai-agentserver-responses.
    try:
        platform_headers = import_module("azure.ai.agentserver.core._platform_headers")

        fallback_headers = {
            "CHAT_ISOLATION_KEY": "x-agent-chat-isolation-key",
            "USER_ISOLATION_KEY": "x-agent-user-isolation-key",
        }
        for header_name, header_value in fallback_headers.items():
            if not hasattr(platform_headers, header_name):
                setattr(platform_headers, header_name, header_value)
    except Exception:
        # Let the canonical import below raise with its own actionable error.
        pass

    from azure.ai.agentserver.responses import (  # type: ignore[import-not-found]
        CreateResponse,
        InMemoryResponseProvider,
        ResponseContext,
        ResponsesAgentServerHost,
        TextResponse,
    )

    return (
        ResponsesAgentServerHost,
        CreateResponse,
        ResponseContext,
        TextResponse,
        InMemoryResponseProvider,
    )


def _load_activity_types() -> tuple[
    type[Any],
    type[Any],
    type[Any],
    type[Any],
    type[Any],
]:
    from azure.ai.agentserver.activity import (  # type: ignore[import-not-found]
        ActivityAgentServerHost,
    )
    from microsoft_agents.activity import (  # type: ignore[import-not-found]
        Activity,
        ActivityTypes,
        Attachment,
        InvokeResponse,
    )

    return (
        ActivityAgentServerHost,
        Activity,
        ActivityTypes,
        Attachment,
        InvokeResponse,
    )


def _coerce_payload(create_response: Any) -> dict[str, Any]:
    if isinstance(create_response, dict):
        return dict(create_response)
    if hasattr(create_response, "model_dump"):
        return create_response.model_dump()
    if hasattr(create_response, "as_dict"):
        return create_response.as_dict()
    if hasattr(create_response, "dict"):
        return create_response.dict()
    return {}


def _request_payloads(create_response: Any, context: Any | None) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    primary_payload = _coerce_payload(create_response)
    if primary_payload:
        payloads.append(primary_payload)
    if context is not None:
        for key in ("request", "request_body", "body", "payload", "raw_request"):
            payload = _coerce_payload(getattr(context, key, None))
            if payload:
                payloads.append(payload)
    return payloads


def _nested_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "value" in value:
            return _nested_text(value["value"])
        if "text" in value:
            return _nested_text(value["text"])
        if "input_text" in value:
            return _nested_text(value["input_text"])
        if "content" in value:
            return _nested_text(value["content"])
        if "input" in value:
            return _nested_text(value["input"])
        if "message" in value:
            return _nested_text(value["message"])
        if "output" in value:
            return _nested_text(value["output"])
        return ""
    if isinstance(value, list):
        parts = [_nested_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def _conversation_id_from_mapping(value: dict[str, Any]) -> str | None:
    conversation = value.get("conversation")
    if isinstance(conversation, str) and conversation.strip():
        return conversation.strip()
    if isinstance(conversation, dict):
        conversation_id = conversation.get("id")
        if isinstance(conversation_id, str) and conversation_id.strip():
            return conversation_id.strip()

    for key in ("conversation_id", "conversationId"):
        conversation_id = value.get(key)
        if isinstance(conversation_id, str) and conversation_id.strip():
            return conversation_id.strip()

    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        metadata_conversation_id = _conversation_id_from_mapping(metadata)
        if metadata_conversation_id:
            return metadata_conversation_id
    return None


def _coerce_conversation_id(payload: dict[str, Any], context: Any | None) -> str:
    payload_conversation_id = _conversation_id_from_mapping(payload)
    if payload_conversation_id:
        return payload_conversation_id

    if context is not None:
        for key in ("conversation_id", "conversation"):
            value = getattr(context, key, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                conversation_id = value.get("id")
                if isinstance(conversation_id, str) and conversation_id.strip():
                    return conversation_id.strip()

        for key in ("metadata", "request", "request_body", "body", "payload", "raw_request"):
            nested = getattr(context, key, None)
            if hasattr(nested, "model_dump"):
                nested = nested.model_dump()
            elif hasattr(nested, "dict"):
                nested = nested.dict()
            if isinstance(nested, dict):
                nested_conversation_id = _conversation_id_from_mapping(nested)
                if nested_conversation_id:
                    return nested_conversation_id

        context_previous_response_id = getattr(context, "previous_response_id", None)
        if isinstance(context_previous_response_id, str) and context_previous_response_id.strip():
            return context_previous_response_id.strip()

    previous_response_id = payload.get("previous_response_id")
    if isinstance(previous_response_id, str) and previous_response_id.strip():
        return previous_response_id.strip()

    payload_id = payload.get("id")
    if isinstance(payload_id, str) and payload_id.strip():
        return payload_id.strip()
    return str(uuid4())


def _iter_input_items(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    raw_input = payload.get("input")
    if isinstance(raw_input, dict):
        return [raw_input]
    if isinstance(raw_input, list):
        return [item for item in raw_input if isinstance(item, dict)]
    return []


def _parse_function_call_output(items: Iterable[dict[str, Any]]) -> tuple[str | None, str | None]:
    checkpoint_id: str | None = None
    decision: str | None = None
    for item in items:
        if str(item.get("type", "")).strip().lower() != "function_call_output":
            continue
        call_id = item.get("call_id")
        if isinstance(call_id, str) and call_id.strip():
            checkpoint_id = call_id.strip()
        output = item.get("output")
        if isinstance(output, dict):
            out_checkpoint = output.get("checkpoint_id")
            out_decision = output.get("decision")
            if isinstance(out_checkpoint, str) and out_checkpoint.strip():
                checkpoint_id = out_checkpoint.strip()
            if isinstance(out_decision, str):
                lowered = out_decision.strip().lower()
                if lowered in {"approve", "reject"}:
                    decision = lowered
        elif isinstance(output, str):
            lowered = output.strip().lower()
            if lowered in {"approve", "reject"}:
                decision = lowered
    return checkpoint_id, decision


def _message_from_context(context: Any | None) -> str | None:
    if context is None:
        return None
    direct_fields = (
        "input",
        "message",
        "user_message",
        "prompt",
        "text",
        "query",
    )
    nested_fields = (
        "request",
        "request_body",
        "body",
        "payload",
        "raw_request",
    )
    for field in direct_fields:
        text = _nested_text(getattr(context, field, None))
        if text:
            return text
    for field in nested_fields:
        raw_value = getattr(context, field, None)
        if hasattr(raw_value, "model_dump"):
            raw_value = raw_value.model_dump()
        elif hasattr(raw_value, "dict"):
            raw_value = raw_value.dict()
        text = _nested_text(raw_value)
        if text:
            return text
    return None


def _pending_checkpoint_id(
    thread_id: str,
    requested_checkpoint_id: str | None = None,
) -> str | None:
    details = workflow_run_repository.get_workflow_run(thread_id)
    if not details:
        return None
    for approval in details.pending_approvals:
        if approval.status == "pending" and (
            requested_checkpoint_id is None or approval.checkpoint_id == requested_checkpoint_id
        ):
            return approval.checkpoint_id
    return None


def _is_standalone_decision_command(message: str | None) -> bool:
    if not message:
        return False
    normalized = re.sub(r"[^a-z]", "", message.casefold())
    return normalized in {"approve", "approved", "yes", "reject", "rejected", "no"}


def _parse_input(
    create_response: Any,
    context: Any | None,
    *,
    input_items: Iterable[dict[str, Any]] = (),
) -> _ParsedInput:
    payload = _coerce_payload(create_response)
    request_payloads = _request_payloads(create_response, context)
    message = next(
        (
            candidate
            for request_payload in request_payloads
            if (
                candidate := (
                    _nested_text(request_payload.get("message"))
                    or _nested_text(request_payload.get("input"))
                )
            )
        ),
        "",
    )
    message = message or _message_from_context(context)
    checkpoint_id: str | None = None
    decision: str | None = None
    for request_payload in request_payloads:
        metadata = request_payload.get("metadata")
        if isinstance(metadata, dict):
            maybe_checkpoint = metadata.get("checkpoint_id")
            if isinstance(maybe_checkpoint, str) and maybe_checkpoint.strip():
                checkpoint_id = maybe_checkpoint.strip()
            maybe_decision = metadata.get("decision")
            if isinstance(maybe_decision, str):
                lowered = maybe_decision.strip().lower()
                if lowered in {"approve", "reject"}:
                    decision = lowered
        input_checkpoint, input_decision = _parse_function_call_output(
            _iter_input_items(request_payload)
        )
        if input_checkpoint:
            checkpoint_id = input_checkpoint
        if input_decision:
            decision = input_decision
    input_checkpoint, input_decision = _parse_function_call_output(input_items)
    if input_checkpoint:
        checkpoint_id = input_checkpoint
    if input_decision:
        decision = input_decision
    parsed = _ParsedInput(
        conversation_id=_coerce_conversation_id(payload, context),
        message=message or None,
        decision=decision,
        checkpoint_id=checkpoint_id,
    )
    _emit_parse_debug(payload, context, parsed)
    return parsed


def _serialize_workflow(thread_id: str) -> dict[str, Any]:
    details = workflow_run_repository.get_workflow_run(thread_id)
    if details is None:
        return {
            "thread_id": thread_id,
            "status": "failed",
            "events": [],
            "pending_approvals": [],
            "latest_output": None,
            "message": "Workflow run not found.",
        }
    return {
        "thread_id": details.thread_id,
        "status": details.status,
        "events": [event.model_dump() for event in details.events],
        "pending_approvals": [approval.model_dump() for approval in details.pending_approvals],
        "latest_output": details.latest_output,
        "message": (
            str(details.latest_output.get("message"))
            if isinstance(details.latest_output, dict) and details.latest_output.get("message")
            else ""
        ),
    }


def _teams_response_text(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()

    if payload.get("status") == "waiting_approval":
        return "Approval required. Submit the decision through the approval interface."

    status = str(payload.get("status", "unknown")).strip() or "unknown"
    return f"Workflow status: {status}."


def _activity_conversation_id(activity: Any) -> str:
    conversation = getattr(activity, "conversation", None)
    return str(getattr(conversation, "id", "") or "").strip()


def _activity_user_id(activity: Any) -> str:
    sender = getattr(activity, "from_property", None)
    if sender is None:
        sender = getattr(activity, "from", None)
    aad_object_id = str(getattr(sender, "aad_object_id", "") or "").strip()
    if aad_object_id:
        return aad_object_id
    return str(getattr(sender, "id", "") or "").strip()


def _pending_approval(payload: dict[str, Any]) -> dict[str, Any] | None:
    approvals = payload.get("pending_approvals")
    if not isinstance(approvals, list):
        return None
    for approval in approvals:
        if isinstance(approval, dict) and approval.get("status") == "pending":
            return approval
    return None


def _approval_status(payload: dict[str, Any], checkpoint_id: str) -> str:
    approvals = payload.get("pending_approvals")
    if not isinstance(approvals, list):
        return "unavailable"
    for approval in approvals:
        if not isinstance(approval, dict):
            continue
        if str(approval.get("checkpoint_id") or "") == checkpoint_id:
            return str(approval.get("status") or "unavailable")
    return "unavailable"


def _card_action_ttl_seconds() -> int:
    value = os.getenv("TEAMS_CARD_ACTION_TTL_SECONDS", "86400").strip()
    try:
        ttl_seconds = int(value)
    except ValueError as exc:
        raise RuntimeError("TEAMS_CARD_ACTION_TTL_SECONDS must be an integer.") from exc
    if ttl_seconds <= 0:
        raise RuntimeError("TEAMS_CARD_ACTION_TTL_SECONDS must be greater than zero.")
    return ttl_seconds


async def _send_activity_card(
    context: Any,
    *,
    card: dict[str, Any],
    text: str,
    activity_type: type[Any],
    activity_types: type[Any],
    attachment_type: type[Any],
) -> None:
    attachment = attachment_type(
        contentType=teams_cards.ADAPTIVE_CONTENT_TYPE,
        content=card,
    )
    await context.send_activity(
        activity_type(
            type=activity_types.message,
            text=text,
            attachments=[attachment],
        )
    )


async def _send_invoke_response(
    context: Any,
    *,
    body: dict[str, Any],
    activity_type: type[Any],
    activity_types: type[Any],
    invoke_response_type: type[Any],
) -> None:
    await context.send_activity(
        activity_type(
            type=activity_types.invoke_response,
            value=invoke_response_type(status=200, body=body),
        )
    )


async def _run_from_activity_message(
    context: Any,
    *,
    activity_type: type[Any],
    activity_types: type[Any],
    attachment_type: type[Any],
) -> None:
    activity = context.activity
    conversation_id = _activity_conversation_id(activity)
    user_id = _activity_user_id(activity)
    message = str(getattr(activity, "text", "") or "").strip()
    if not conversation_id or not user_id or not message:
        raise ValueError("Teams activity is missing conversation, user, or message context.")

    if _is_standalone_decision_command(message) and _pending_checkpoint_id(conversation_id):
        await context.send_activity("Use the pending approval card to submit a decision.")
        return

    tracer = get_tracer("foundry.activity")
    with tracer.start_as_current_span("foundry.activity.message") as span:
        _set_span_attribute(span, "workflow.thread_id", conversation_id)
        _set_span_attribute(span, "workflow.session_id", conversation_id)
        _set_span_attribute(span, "foundry.protocol", "activity")
        _set_span_attribute(span, "gen_ai.operation.name", "invoke_agent")
        _set_span_attribute(
            span,
            "gen_ai.agent.name",
            os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "order-resolution-hosted"),
        )
        _set_span_attribute(
            span,
            "gen_ai.agent.id",
            os.getenv("FOUNDRY_HOSTED_AGENT_ID", "order-resolution-hosted"),
        )
        _set_span_attribute(span, "gen_ai.conversation.id", conversation_id)
        try:
            await order_resolution_service.start_chat_run(
                ChatRunRequest(
                    message=message,
                    thread_id=conversation_id,
                    session_id=conversation_id,
                    customer_id="foundry-teams",
                ),
                origin_channel="teams_activity",
            )
            payload = _serialize_workflow(conversation_id)
            _set_span_attribute(span, "workflow.status", payload.get("status"))
            pending = _pending_approval(payload)
            if pending is None:
                await context.send_activity(_teams_response_text(payload))
                return

            checkpoint_id = str(pending.get("checkpoint_id") or "").strip()
            if not checkpoint_id:
                raise RuntimeError("Pending approval is missing its checkpoint identifier.")
            tokens = teams_card_action_repository.issue_actions(
                thread_id=conversation_id,
                checkpoint_id=checkpoint_id,
                conversation_id=conversation_id,
                user_id=user_id,
                ttl_seconds=_card_action_ttl_seconds(),
            )
            _set_span_attribute(span, "workflow.checkpoint_id", checkpoint_id)
            card = teams_cards.build_pending_approval_card(
                action=pending.get("action"),
                approve_token=tokens["approve"],
                reject_token=tokens["reject"],
            )
            await _send_activity_card(
                context,
                card=card,
                text="Approval required.",
                activity_type=activity_type,
                activity_types=activity_types,
                attachment_type=attachment_type,
            )
        except Exception as exc:
            span.record_exception(exc)
            raise


def _card_action_error_status(code: str) -> int:
    if code in {"conversation_mismatch", "user_mismatch"}:
        return 403
    if code in {"action_already_used", "action_expired", "approval_not_pending"}:
        return 409
    return 400


async def _run_from_activity_invoke(
    context: Any,
    *,
    activity_type: type[Any],
    activity_types: type[Any],
    invoke_response_type: type[Any],
) -> None:
    activity = context.activity
    if getattr(activity, "name", None) != teams_cards.ADAPTIVE_ACTION_INVOKE:
        return

    conversation_id = _activity_conversation_id(activity)
    user_id = _activity_user_id(activity)
    parsed = teams_cards.parse_approval_action(activity)
    if not conversation_id or not user_id or parsed is None:
        await _send_invoke_response(
            context,
            body=teams_cards.error_invoke_response(
                status_code=400,
                code="InvalidApprovalAction",
                message="The approval action is invalid.",
            ),
            activity_type=activity_type,
            activity_types=activity_types,
            invoke_response_type=invoke_response_type,
        )
        return

    decision, token = parsed
    tracer = get_tracer("foundry.activity")
    with tracer.start_as_current_span("foundry.activity.approval") as span:
        _set_span_attribute(span, "foundry.protocol", "activity")
        _set_span_attribute(span, "gen_ai.operation.name", "execute_tool")
        try:
            action = teams_card_action_repository.claim_action(
                token=token,
                decision=decision,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            _set_span_attribute(span, "workflow.thread_id", action.thread_id)
            _set_span_attribute(span, "workflow.checkpoint_id", action.checkpoint_id)
            _set_span_attribute(span, "workflow.hitl.decision", action.decision)
            try:
                await order_resolution_service.respond_hitl(
                    HitlResponseRequest(
                        checkpoint_id=action.checkpoint_id,
                        decision=action.decision,
                        reviewer="teams-card",
                        comments="decision received from Teams Adaptive Card",
                    ),
                    origin_channel="teams_activity",
                )
            except Exception:
                teams_card_action_repository.release_action(action.batch_id)
                raise
            teams_card_action_repository.complete_action(action.batch_id)
            payload = _serialize_workflow(action.thread_id)
            status = _approval_status(payload, action.checkpoint_id)
            _set_span_attribute(span, "workflow.status", payload.get("status"))
            message = payload.get("message")
            card = teams_cards.build_resolved_approval_card(
                status=status,
                message=message if isinstance(message, str) and message.strip() else None,
            )
            await _send_invoke_response(
                context,
                body=teams_cards.card_invoke_response(card),
                activity_type=activity_type,
                activity_types=activity_types,
                invoke_response_type=invoke_response_type,
            )
        except TeamsCardActionError as exc:
            _set_span_attribute(span, "workflow.hitl.error_code", exc.code)
            await _send_invoke_response(
                context,
                body=teams_cards.error_invoke_response(
                    status_code=_card_action_error_status(exc.code),
                    code=exc.code,
                    message=str(exc),
                ),
                activity_type=activity_type,
                activity_types=activity_types,
                invoke_response_type=invoke_response_type,
            )
        except Exception as exc:
            span.record_exception(exc)
            await _send_invoke_response(
                context,
                body=teams_cards.error_invoke_response(
                    status_code=500,
                    code="ApprovalActionFailed",
                    message="The approval action could not be completed.",
                ),
                activity_type=activity_type,
                activity_types=activity_types,
                invoke_response_type=invoke_response_type,
            )


def _set_span_attribute(span: Any, key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str | bool | int | float):
        span.set_attribute(key, value)


def _trace_evaluation_content_enabled() -> bool:
    value = os.getenv(
        "TRACE_EVALUATION_RECORD_CONTENT",
        os.getenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "false"),
    )
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _set_trace_evaluation_input(span: Any, parsed: _ParsedInput) -> None:
    if not _trace_evaluation_content_enabled():
        return
    input_text = parsed.message or parsed.decision
    if not input_text:
        return
    span.set_attribute(
        "gen_ai.input.messages",
        json.dumps(
            [
                {
                    "role": "user",
                    "parts": [{"type": "text", "content": input_text}],
                }
            ]
        ),
    )


def _set_trace_evaluation_output(span: Any, payload: dict[str, Any]) -> None:
    if not _trace_evaluation_content_enabled():
        return
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        return
    span.set_attribute(
        "gen_ai.output.messages",
        json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": message}],
                    "finish_reason": "stop",
                }
            ]
        ),
    )


async def _run_from_responses(
    create_response: Any, context: Any | None, text_response: type[Any]
) -> Any:
    input_items: list[dict[str, Any]] = []
    get_input_items = getattr(context, "get_input_items", None)
    if callable(get_input_items):
        resolved_items = await get_input_items(resolve_references=False)
        input_items = [payload for item in resolved_items if (payload := _coerce_payload(item))]
    parsed = _parse_input(create_response, context, input_items=input_items)
    tracer = get_tracer("foundry.responses")
    # Anchor all turn-level telemetry under a single invocation span.
    with tracer.start_as_current_span("foundry.responses.invoke") as span:
        _set_span_attribute(span, "workflow.thread_id", parsed.conversation_id)
        _set_span_attribute(span, "workflow.session_id", parsed.conversation_id)
        _set_span_attribute(span, "foundry.protocol", "responses")
        _set_span_attribute(span, "gen_ai.operation.name", "invoke_agent")
        _set_span_attribute(
            span,
            "gen_ai.agent.name",
            os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "order-resolution-hosted"),
        )
        _set_span_attribute(
            span,
            "gen_ai.agent.id",
            os.getenv("FOUNDRY_HOSTED_AGENT_ID", "order-resolution-hosted"),
        )
        _set_span_attribute(span, "gen_ai.conversation.id", parsed.conversation_id)
        _set_trace_evaluation_input(span, parsed)
        checkpoint_id_for_span: str | None = None
        try:
            if parsed.decision:
                origin_channel = workflow_run_repository.get_workflow_origin_channel(
                    parsed.conversation_id
                )
                checkpoint_id = (
                    _pending_checkpoint_id(
                        parsed.conversation_id,
                        parsed.checkpoint_id,
                    )
                    if origin_channel == "responses"
                    else None
                )
                checkpoint_id_for_span = checkpoint_id
                if checkpoint_id is None:
                    message = (
                        "Use the pending approval card to submit a decision."
                        if origin_channel == "teams_activity"
                        else "No pending approval found for this conversation."
                    )
                    payload = {
                        "thread_id": parsed.conversation_id,
                        "status": "failed",
                        "events": [],
                        "pending_approvals": [],
                        "message": message,
                    }
                else:
                    hitl_result = await order_resolution_service.respond_hitl(
                        HitlResponseRequest(
                            checkpoint_id=checkpoint_id,
                            decision=parsed.decision,
                            reviewer="foundry-conversation",
                            comments="decision received from responses conversation",
                        ),
                        origin_channel="responses",
                    )
                    resumed_thread_id = getattr(hitl_result, "thread_id", parsed.conversation_id)
                    payload = _serialize_workflow(resumed_thread_id)
            elif parsed.message:
                await order_resolution_service.start_chat_run(
                    ChatRunRequest(
                        message=parsed.message,
                        thread_id=parsed.conversation_id,
                        session_id=parsed.conversation_id,
                        customer_id="foundry-hosted",
                    ),
                    origin_channel="responses",
                )
                payload = _serialize_workflow(parsed.conversation_id)
            else:
                payload = {
                    "thread_id": parsed.conversation_id,
                    "status": "failed",
                    "events": [],
                    "pending_approvals": [],
                    "message": "message or input is required",
                }
            _set_span_attribute(span, "workflow.checkpoint_id", checkpoint_id_for_span)
            _set_span_attribute(span, "workflow.status", payload.get("status"))
            events = payload.get("events")
            if isinstance(events, list):
                _set_span_attribute(span, "workflow.event_count", len(events))
            _set_trace_evaluation_output(span, payload)
            response_text = json.dumps(payload)
            return text_response(context, create_response, text=response_text)
        except Exception as exc:
            span.record_exception(exc)
            raise


def _build_app() -> Any:
    ResponsesAgentServerHost, _, _, TextResponse, _ = _load_responses_types()
    (
        ActivityAgentServerHost,
        Activity,
        ActivityTypes,
        Attachment,
        InvokeResponse,
    ) = _load_activity_types()

    class OrderResolutionAgentServerHost(
        ActivityAgentServerHost,
        ResponsesAgentServerHost,
    ):
        pass

    host = OrderResolutionAgentServerHost()

    async def handler(
        create_response: Any,
        context: Any | None = None,
        cancellation_signal: Any | None = None,
    ) -> Any:
        return await _run_from_responses(create_response, context, TextResponse)

    host.response_handler(handler)
    agent_app = host.agent_app

    @agent_app.activity("message")
    async def activity_message_handler(context: Any, _state: Any) -> None:
        await _run_from_activity_message(
            context,
            activity_type=Activity,
            activity_types=ActivityTypes,
            attachment_type=Attachment,
        )

    @agent_app.activity("invoke")
    async def activity_invoke_handler(context: Any, _state: Any) -> None:
        await _run_from_activity_invoke(
            context,
            activity_type=Activity,
            activity_types=ActivityTypes,
            invoke_response_type=InvokeResponse,
        )

    @agent_app.error
    async def activity_error_handler(context: Any, error: Exception) -> None:
        logger.error("Activity handler failed: %s", error, exc_info=True)
        activity = getattr(context, "activity", None)
        if getattr(activity, "type", None) == "invoke":
            await _send_invoke_response(
                context,
                body=teams_cards.error_invoke_response(
                    status_code=500,
                    code="ActivityHandlerFailed",
                    message="The request could not be completed.",
                ),
                activity_type=Activity,
                activity_types=ActivityTypes,
                invoke_response_type=InvokeResponse,
            )
            return
        await context.send_activity("The request could not be completed.")

    return host


def _initialize_app() -> Any:
    def _env_state(name: str) -> dict[str, Any]:
        value = os.getenv(name, "")
        segments = [segment for segment in value.split(";") if segment]
        kv_segments = [segment for segment in segments if "=" in segment]
        return {
            "present": bool(value),
            "placeholder": value.startswith("${"),
            "has_instrumentation_key": "InstrumentationKey=" in value,
            "length": len(value),
            "semicolon_count": value.count(";"),
            "equals_count": value.count("="),
            "segment_count": len(segments),
            "kv_segment_count": len(kv_segments),
        }

    # AgentServerHost must configure the provider first so its Foundry
    # enrichment processors can emit portal-indexable GenAI transaction spans.
    telemetry_status = _telemetry.setup_observability()
    logger.info(
        "Hosted observability initialized: telemetry_enabled=%s instrumentation_enabled=%s azure_monitor=%s otlp=%s",
        telemetry_status.telemetry_enabled,
        telemetry_status.instrumentation_enabled,
        telemetry_status.azure_monitor_configured,
        telemetry_status.otlp_configured,
    )
    logger.info(
        "Hosted env diagnostic: appinsights=%s appinsights_alias=%s database_url=%s runtime_database_url=%s",
        _env_state("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        _env_state("APPINSIGHTS_CONNECTION_STRING"),
        _env_state("DATABASE_URL"),
        _env_state("FOUNDRY_RUNTIME_DATABASE_URL"),
    )
    print(
        "HOSTED_ENV_DIAGNOSTIC "
        + json.dumps(
            {
                "applicationinsights_connection_string": _env_state(
                    "APPLICATIONINSIGHTS_CONNECTION_STRING"
                ),
                "appinsights_connection_string": _env_state("APPINSIGHTS_CONNECTION_STRING"),
                "database_url": _env_state("DATABASE_URL"),
                "foundry_runtime_database_url": _env_state("FOUNDRY_RUNTIME_DATABASE_URL"),
            },
            separators=(",", ":"),
        ),
        file=sys.stderr,
        flush=True,
    )
    return _build_app()


app = None if os.getenv("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS") == "true" else _initialize_app()


if __name__ == "__main__":
    (_initialize_app() if app is None else app).run()
