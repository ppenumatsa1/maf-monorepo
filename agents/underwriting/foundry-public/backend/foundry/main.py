from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.core.config import load_settings
from app.core.telemetry import setup_hosted_observability, workflow_telemetry_context
from app.modules.underwriting.copilot import (
    SAFE_EXPLANATION_PROTOCOL,
    SafeRunExplanationRequest,
    build_safe_explanation,
)
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.service import UnderwritingService
from opentelemetry import trace

_tracer = trace.get_tracer("underwriting.foundry")


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


def _serialize_output(output: Any) -> Any:
    if isinstance(output, dict):
        return output
    if hasattr(output, "to_dict"):
        return output.to_dict()
    return str(output)


def _project_result(
    service: UnderwritingService,
    workflow_run_id: str,
    *,
    fallback_status: str,
    outputs: list[Any] | None = None,
) -> dict[str, Any]:
    run = service.get_run(workflow_run_id)
    if outputs is None:
        outputs = [
            result["result_json"]
            for result in service.repository.list_underwriting_results(workflow_run_id)
            if result.get("check_type") == "final_decision"
            and isinstance(result.get("result_json"), dict)
        ]
    return {
        "workflow_run_id": workflow_run_id,
        "status": str(run.get("status") if run is not None else fallback_status),
        "outputs": [_serialize_output(output) for output in outputs],
    }


async def _handle(create_response: Any, context: Any, text_response: type[Any]) -> Any:
    payload = _response_payload(create_response)
    request = _workflow_request(payload, context)
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
                    service = UnderwritingService(settings)
                    existing = service.get_run(run_id)
                    if existing is not None and (
                        envelope.action == "start" or existing.get("status") == "COMPLETED"
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
    return text_response(context, create_response, text=json.dumps(result))


def build_app() -> Any:
    from azure.ai.agentserver.responses import ResponsesAgentServerHost, TextResponse

    host = ResponsesAgentServerHost()

    async def handler(
        create_response: Any,
        context: Any = None,
        cancellation_signal: Any = None,
    ) -> Any:
        return await _handle(create_response, context, TextResponse)

    host.response_handler(handler)
    return host


def initialize_app() -> Any:
    setup_hosted_observability()
    return build_app()


app = initialize_app()


if __name__ == "__main__":
    app.run()
