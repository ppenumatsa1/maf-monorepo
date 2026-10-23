from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any
from uuid import uuid4

from app.core.config import load_settings
from app.core.telemetry import setup_hosted_observability, workflow_telemetry_context
from app.infrastructure.persistence.teams_card_action_repository import TeamsCardActionError
from app.modules.underwriting.copilot import (
    SAFE_EXPLANATION_PROTOCOL,
    SafeRunExplanationRequest,
    build_safe_explanation,
)
from app.modules.underwriting.hosted import (
    HOSTED_REVIEW_DECISION_PROTOCOL,
    HOSTED_WORKFLOW_PROTOCOL,
    HostedWorkflowEnvelope,
)
from app.modules.underwriting.models import OriginChannel, ReviewerOutcome
from app.modules.underwriting.projections import project_workflow_run
from app.modules.underwriting.service import LocalUnderwritingService
from opentelemetry import trace

from foundry import teams_cards

_tracer = trace.get_tracer("underwriting.foundry")
logger = logging.getLogger(__name__)
TEAMS_SAMPLE_REVIEW_COMMAND = "start sample underwriting review"


def _response_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _input_text(value: Any) -> str:
    parts: list[str] = []

    def collect_text(candidate: Any) -> None:
        if isinstance(candidate, str):
            parts.append(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                collect_text(item)
        elif isinstance(candidate, dict):
            for key in ("text", "content", "input", "message", "value"):
                if key in candidate:
                    collect_text(candidate[key])

    collect_text(value)
    return " ".join(parts)


def _trace_messages(action: str, result: dict[str, Any]) -> tuple[str, str]:
    """Return the minimum safe GenAI message content required for trace evaluation."""
    status = str(result.get("status", "UNKNOWN"))
    outputs = result.get("outputs")
    decision = ""
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], dict):
        output_decision = outputs[0].get("decision")
        if isinstance(output_decision, str):
            decision = output_decision
    input_messages = [
        {
            "role": "user",
            "content": f"Execute underwriting workflow action: {action}.",
        }
    ]
    output_messages = [
        {
            "role": "assistant",
            "content": (
                f"Underwriting workflow finished with status: {status}."
                + (f" Decision: {decision}." if decision else "")
            ),
        }
    ]
    return json.dumps(input_messages), json.dumps(output_messages)


def _workflow_request(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    values = [payload.get("input"), payload.get("message"), payload.get("input_text")]
    if context is not None:
        for name in (
            "input",
            "message",
            "input_text",
            "request",
            "request_body",
            "body",
            "payload",
        ):
            value = getattr(context, name, None)
            if value is not None:
                values.append(_response_payload(value))

    for value in values:
        text = _input_text(value).strip()
        if not text.startswith("{"):
            continue
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return {}


def _input_items(value: Any) -> list[dict[str, Any]]:
    payload = _response_payload(value)
    raw_input = payload.get("input")
    if isinstance(raw_input, dict):
        return [raw_input]
    if isinstance(raw_input, list):
        return [item for item in raw_input if isinstance(item, dict)]
    return []


def _parse_review_output(output: Any) -> dict[str, Any] | None:
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return None
    if not isinstance(output, dict):
        return None
    if set(output) != {
        "protocol",
        "workflow_run_id",
        "checkpoint_id",
        "outcome",
    }:
        return None
    if output.get("protocol") != HOSTED_REVIEW_DECISION_PROTOCOL:
        return None
    workflow_run_id = output.get("workflow_run_id")
    checkpoint_id = output.get("checkpoint_id")
    outcome = output.get("outcome")
    if (
        not isinstance(workflow_run_id, str)
        or not workflow_run_id.startswith("run-")
        or not isinstance(checkpoint_id, str)
        or not checkpoint_id
        or outcome not in {item.value for item in ReviewerOutcome}
    ):
        return None
    return output


async def _structured_review_decision(
    create_response: Any,
    context: Any,
) -> tuple[dict[str, Any] | None, bool]:
    items = _input_items(create_response)
    if context is not None:
        for name in ("request", "request_body", "body", "payload"):
            items.extend(_input_items(getattr(context, name, None)))
        get_input_items = getattr(context, "get_input_items", None)
        if callable(get_input_items):
            resolved_items = await get_input_items(resolve_references=False)
            items.extend(payload for item in resolved_items if (payload := _response_payload(item)))

    saw_function_output = False
    decision: dict[str, Any] | None = None
    for item in items:
        if str(item.get("type", "")).strip().lower() != "function_call_output":
            continue
        saw_function_output = True
        parsed = _parse_review_output(item.get("output"))
        if parsed is None or item.get("call_id") != parsed["checkpoint_id"]:
            return None, True
        if decision is not None and decision != parsed:
            return None, True
        decision = parsed
    return decision, saw_function_output


def _project_result(
    service: LocalUnderwritingService,
    workflow_run_id: str,
    *,
    fallback_status: str,
    outputs: list[Any] | None = None,
) -> dict[str, Any]:
    projection = project_workflow_run(
        service.repository,
        workflow_run_id,
        fallback_status=fallback_status,
        outputs=outputs,
    )
    run = service.get_run(workflow_run_id)
    if run is not None:
        projection["status"] = str(run.get("status", projection["status"]))
    return projection


async def _handle(
    create_response: Any,
    context: Any,
    text_response: type[Any],
    *,
    origin_channel: OriginChannel = OriginChannel.RESPONSES,
) -> Any:
    payload = _response_payload(create_response)
    review_decision, saw_function_output = await _structured_review_decision(
        create_response, context
    )
    request = (
        {
            "protocol": HOSTED_REVIEW_DECISION_PROTOCOL,
            "workflow_run_id": review_decision["workflow_run_id"],
            "action": "review",
        }
        if review_decision is not None
        else _workflow_request(payload, context)
    )
    requested_run_id = request.get("workflow_run_id")
    run_id = (
        requested_run_id
        if isinstance(requested_run_id, str) and requested_run_id.startswith("run-")
        else f"run-{uuid4().hex[:10]}"
    )
    settings = load_settings()
    context_attributes = {
        "gen_ai.agent.id": settings.foundry_hosted_agent_name,
        "gen_ai.agent.name": settings.foundry_hosted_agent_name,
        "gen_ai.conversation.id": run_id,
        "workflow.run_id": run_id,
        "workflow.action": str(request.get("action", "explain")),
    }
    with (
        workflow_telemetry_context(context_attributes),
        _tracer.start_as_current_span(
            "foundry.responses.invoke",
            attributes={"gen_ai.operation.name": "invoke_agent", **context_attributes},
        ) as invocation_span,
    ):
        if request.get("protocol") == SAFE_EXPLANATION_PROTOCOL:
            try:
                explanation_request = SafeRunExplanationRequest.from_dict(request)
            except ValueError:
                result = {
                    "workflow_run_id": run_id,
                    "status": "REJECTED",
                    "explanation": "",
                }
            else:
                run_id = explanation_request.workflow_run_id
                with _tracer.start_as_current_span(
                    "underwriting.hosted.safe_explanation",
                    attributes={
                        "workflow.run_id": run_id,
                        "workflow.protocol": "responses",
                        "workflow.intent": explanation_request.intent,
                    },
                ):
                    result = {
                        "workflow_run_id": run_id,
                        "status": explanation_request.context.status,
                        "explanation": build_safe_explanation(
                            explanation_request.context, explanation_request.intent
                        ),
                    }
        else:
            with _tracer.start_as_current_span(
                "underwriting.hosted.workflow",
                attributes={
                    "workflow.run_id": run_id,
                    "workflow.protocol": "responses",
                },
            ) as evaluation_span:
                if saw_function_output and review_decision is None:
                    result = {
                        "workflow_run_id": run_id,
                        "status": "REJECTED",
                        "outputs": [],
                    }
                elif review_decision is not None:
                    run_id = str(review_decision["workflow_run_id"])
                    evaluation_span.set_attribute("workflow.run_id", run_id)
                    evaluation_span.set_attribute("workflow.action", "review")
                    result = {
                        "workflow_run_id": run_id,
                        "status": "REJECTED",
                        "outputs": [],
                    }
                else:
                    try:
                        envelope = HostedWorkflowEnvelope.from_dict(request)
                    except ValueError:
                        result = {
                            "workflow_run_id": run_id,
                            "status": "REJECTED",
                            "outputs": [],
                        }
                    else:
                        run_id = envelope.workflow_run_id
                        evaluation_span.set_attribute("workflow.run_id", run_id)
                        evaluation_span.set_attribute("workflow.action", envelope.action)
                        service = LocalUnderwritingService(settings)
                        existing = service.get_run(run_id)
                        if existing is not None and (
                            envelope.action == "start"
                            or existing.get("status") in {"COMPLETED", "PENDING_REVIEW"}
                        ):
                            result = _project_result(
                                service,
                                run_id,
                                fallback_status=str(existing.get("status", "SUBMITTED")),
                            )
                        else:
                            try:
                                if envelope.action == "resume":
                                    outputs = await service.resume_workflow(run_id)
                                else:
                                    if envelope.application is None:
                                        raise ValueError("start requires an application")
                                    _, outputs = await service.run_workflow(
                                        workflow_run_id=run_id,
                                        application=envelope.application,
                                        fail_risk_once=envelope.fail_risk_once,
                                        fail_credit_randomly=envelope.fail_credit_randomly,
                                        crash_after_executor=envelope.crash_after_executor,
                                        origin_channel=origin_channel,
                                    )
                                result = _project_result(
                                    service,
                                    run_id,
                                    fallback_status="COMPLETED",
                                    outputs=outputs,
                                )
                            except Exception:
                                result = _project_result(service, run_id, fallback_status="CRASHED")
        invocation_span.set_attribute("workflow.run_id", run_id)
        invocation_span.set_attribute("workflow.status", result["status"])
        if "outputs" in result:
            invocation_span.set_attribute("workflow.output_count", len(result["outputs"]))
        input_messages, output_messages = _trace_messages(
            str(request.get("action", "explain")), result
        )
        invocation_span.set_attribute("gen_ai.input.messages", input_messages)
        invocation_span.set_attribute("gen_ai.output.messages", output_messages)
    return text_response(context, create_response, text=json.dumps(result))


def _activity_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(by_alias=True, exclude_none=True)
        return payload if isinstance(payload, dict) else {}
    return {}


def _activity_conversation_id(activity: Any) -> str:
    conversation = getattr(activity, "conversation", None)
    conversation_id = str(getattr(conversation, "id", "") or "").strip()
    if conversation_id:
        return conversation_id
    payload = _activity_mapping(activity)
    conversation_payload = payload.get("conversation")
    if isinstance(conversation_payload, dict):
        return str(conversation_payload.get("id") or "").strip()
    return ""


def _activity_user_id(activity: Any) -> str:
    sender = getattr(activity, "from_property", None)
    if sender is not None:
        aad_object_id = str(getattr(sender, "aad_object_id", "") or "").strip()
        if aad_object_id:
            return aad_object_id
        sender_id = str(getattr(sender, "id", "") or "").strip()
        if sender_id:
            return sender_id
    payload = _activity_mapping(activity)
    sender_payload = payload.get("from")
    if isinstance(sender_payload, dict):
        return str(
            sender_payload.get("aadObjectId")
            or sender_payload.get("aad_object_id")
            or sender_payload.get("id")
            or ""
        ).strip()
    return ""


def _activity_workflow_input(activity: Any, message: str) -> str:
    if message.casefold() != TEAMS_SAMPLE_REVIEW_COMMAND:
        return message
    activity_id = str(getattr(activity, "id", "") or "").strip()
    if not activity_id:
        raise ValueError("Teams activity is missing its message identifier")
    suffix = hashlib.sha256(activity_id.encode()).hexdigest()[:20]
    return json.dumps(
        {
            "protocol": HOSTED_WORKFLOW_PROTOCOL,
            "workflow_run_id": f"run-teams-{suffix}",
            "action": "start",
            "application": {
                "application_id": f"app-teams-{suffix}",
                "applicant_name": "Synthetic Applicant",
                "age": 20,
                "income": 50_000,
                "requested_coverage": 100_000,
                "health_disclosures": "none",
                "driving_history": "accident",
                "credit_score": 650,
            },
            "options": {
                "fail_risk_once": False,
                "fail_credit_randomly": False,
                "crash_after_executor": None,
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _is_standalone_decision(message: str) -> bool:
    normalized = re.sub(r"[^a-z]", "", message.casefold())
    return normalized in {
        "approve",
        "approved",
        "decline",
        "declined",
        "reject",
        "rejected",
        "yes",
        "no",
    }


def _card_action_ttl_seconds() -> int:
    raw_value = os.getenv("TEAMS_CARD_ACTION_TTL_SECONDS", "86400").strip()
    try:
        ttl_seconds = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("TEAMS_CARD_ACTION_TTL_SECONDS must be an integer") from exc
    if ttl_seconds <= 0:
        raise RuntimeError("TEAMS_CARD_ACTION_TTL_SECONDS must be greater than zero")
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
        raise ValueError("Teams activity is missing conversation, user, or message context")

    settings = load_settings()
    service = LocalUnderwritingService(settings)
    if _is_standalone_decision(
        message
    ) and service.card_actions.has_pending_action_for_conversation(conversation_id):
        await context.send_activity("Use the pending review card to submit a decision.")
        return

    def activity_result(_context: Any, _request: Any, *, text: str) -> dict[str, Any]:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}

    with _tracer.start_as_current_span(
        "foundry.activity.message",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "underwriting-foundry-public",
            "gen_ai.conversation.id": conversation_id,
            "workflow.protocol": "activity",
        },
    ) as span:
        result = await _handle(
            {"input": _activity_workflow_input(activity, message)},
            None,
            activity_result,
            origin_channel=OriginChannel.TEAMS_ACTIVITY,
        )
        span.set_attribute("workflow.status", str(result.get("status", "UNKNOWN")))
        if result.get("status") != "PENDING_REVIEW":
            status = str(result.get("status", "REJECTED"))
            await context.send_activity(f"Underwriting request status: {status}.")
            return

        checkpoint_id = str(result.get("review_checkpoint_id") or "").strip()
        if not checkpoint_id:
            raise RuntimeError("Pending underwriting review is missing its checkpoint binding")
        tokens = service.issue_teams_review_actions(
            workflow_run_id=str(result["workflow_run_id"]),
            checkpoint_id=checkpoint_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ttl_seconds=_card_action_ttl_seconds(),
        )
        summary = teams_cards.safe_review_summary(result)
        card = teams_cards.build_pending_review_card(
            application_id=summary["application_id"],
            machine_recommendation=summary["machine_recommendation"],
            risk_bands=summary["risk_bands"],
            reason_categories=summary["reason_categories"],
            approve_token=tokens[ReviewerOutcome.APPROVED],
            decline_token=tokens[ReviewerOutcome.DECLINED],
        )
        span.set_attribute("workflow.run_id", str(result["workflow_run_id"]))
        span.set_attribute("workflow.checkpoint_id", checkpoint_id)
        await _send_activity_card(
            context,
            card=card,
            text="Underwriting review required.",
            activity_type=activity_type,
            activity_types=activity_types,
            attachment_type=attachment_type,
        )


def _card_action_error_status(code: str) -> int:
    if code in {"conversation_mismatch", "user_mismatch", "channel_mismatch", "origin_mismatch"}:
        return 403
    if code in {
        "action_already_used",
        "action_expired",
        "action_in_progress",
        "action_replayed",
        "action_superseded",
        "approval_not_pending",
        "decision_in_progress",
        "stale_checkpoint",
    }:
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
    parsed = teams_cards.parse_review_action(activity)
    if not conversation_id or not user_id or parsed is None:
        await _send_invoke_response(
            context,
            body=teams_cards.error_invoke_response(
                status_code=400,
                code="InvalidReviewAction",
                message="The underwriting review action is invalid.",
            ),
            activity_type=activity_type,
            activity_types=activity_types,
            invoke_response_type=invoke_response_type,
        )
        return

    decision, token = parsed
    service = LocalUnderwritingService(load_settings())
    with _tracer.start_as_current_span(
        "foundry.activity.review",
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.agent.name": "underwriting-foundry-public",
            "gen_ai.conversation.id": conversation_id,
            "workflow.protocol": "activity",
        },
    ) as span:
        try:
            claim = service.claim_teams_review_action(
                token=token,
                decision=decision,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            span.set_attribute("workflow.run_id", claim.workflow_run_id)
            span.set_attribute("workflow.checkpoint_id", claim.checkpoint_id)
            span.set_attribute("workflow.review.outcome", decision.value)
            try:
                await service.decide_review(
                    workflow_run_id=claim.workflow_run_id,
                    checkpoint_id=claim.checkpoint_id,
                    outcome=decision,
                    reviewer_id=user_id,
                    origin_channel=OriginChannel.TEAMS_ACTIVITY,
                )
            except Exception as exc:
                service.release_teams_review_action(claim.batch_id)
                code = str(getattr(exc, "code", "review_failed"))
                await _send_invoke_response(
                    context,
                    body=teams_cards.error_invoke_response(
                        status_code=_card_action_error_status(code),
                        code=code,
                        message=(
                            "The review checkpoint is stale."
                            if code == "stale_checkpoint"
                            else "The underwriting review could not be completed."
                        ),
                    ),
                    activity_type=activity_type,
                    activity_types=activity_types,
                    invoke_response_type=invoke_response_type,
                )
                return
            if not service.complete_teams_review_action(claim.batch_id):
                raise RuntimeError("The claimed review action could not be completed")
            await _send_invoke_response(
                context,
                body=teams_cards.card_invoke_response(
                    teams_cards.build_resolved_review_card(outcome=decision)
                ),
                activity_type=activity_type,
                activity_types=activity_types,
                invoke_response_type=invoke_response_type,
            )
        except TeamsCardActionError as exc:
            span.set_attribute("workflow.review.error_code", exc.code)
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
                    code="ReviewActionFailed",
                    message="The underwriting review action could not be completed.",
                ),
                activity_type=activity_type,
                activity_types=activity_types,
                invoke_response_type=invoke_response_type,
            )


def build_app() -> Any:
    from azure.ai.agentserver.activity import ActivityAgentServerHost
    from azure.ai.agentserver.responses import ResponsesAgentServerHost, TextResponse
    from microsoft_agents.activity import Activity, ActivityTypes, Attachment, InvokeResponse

    class UnderwritingAgentServerHost(
        ActivityAgentServerHost,
        ResponsesAgentServerHost,
    ):
        pass

    host = UnderwritingAgentServerHost()

    async def handler(
        create_response: Any,
        context: Any = None,
        cancellation_signal: Any = None,
    ) -> Any:
        return await _handle(create_response, context, TextResponse)

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


def initialize_app() -> Any:
    setup_hosted_observability()
    return build_app()


app = initialize_app()


if __name__ == "__main__":
    app.run()
