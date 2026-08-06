from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import Any

import foundry.main as hosted_main
from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL
from app.modules.underwriting.models import Decision, FinalDecisionResult


def _start_request() -> dict[str, Any]:
    return {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-responses-test",
        "action": "start",
        "application": {
            "application_id": "app-responses-test",
            "applicant_name": "Responses Test",
            "age": 38,
            "income": 145000,
            "requested_coverage": 500000,
            "health_disclosures": "none",
            "driving_history": "clean",
            "credit_score": 760,
        },
        "options": {
            "fail_risk_once": True,
            "fail_credit_randomly": False,
            "crash_after_executor": None,
        },
    }


def _text_response(_context, _request, *, text: str):
    return json.loads(text)


def test_workflow_request_parses_responses_input_text_content() -> None:
    request = _start_request()

    result = hosted_main._workflow_request(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request)}],
                }
            ]
        }
    )

    assert result == request


def test_workflow_request_parses_nested_responses_input_text_content() -> None:
    request = _start_request()

    result = hosted_main._workflow_request(
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": {"value": json.dumps(request)},
                        }
                    ],
                }
            ]
        }
    )

    assert result == request


def test_workflow_request_parses_agent_server_context_input() -> None:
    request = _start_request()

    class Context:
        request_body = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request)}],
                }
            ]
        }

    result = hosted_main._workflow_request({}, Context())

    assert result == request


def test_hosted_handler_executes_start_envelope(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeRepository:
        @staticmethod
        def list_underwriting_results(_workflow_run_id: str) -> list[dict[str, Any]]:
            return []

    class FakeService:
        repository = FakeRepository()

        def __init__(self, _settings: object) -> None:
            pass

        @staticmethod
        def get_run(_workflow_run_id: str) -> None:
            return None

        async def run_workflow(self, **kwargs: Any):
            captured.update(kwargs)
            application = kwargs["application"]
            return kwargs["workflow_run_id"], [
                FinalDecisionResult(
                    workflow_run_id=kwargs["workflow_run_id"],
                    application_id=application.application_id,
                    decision=Decision.APPROVED,
                    rationale="Hosted workflow rationale",
                    score_breakdown={},
                    idempotency_key="result-key",
                )
            ]

    monkeypatch.setattr(hosted_main, "LocalUnderwritingService", FakeService)

    result = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_start_request())},
            context=None,
            text_response=_text_response,
        )
    )

    assert result["workflow_run_id"] == "run-responses-test"
    assert result["status"] == "COMPLETED"
    assert result["outputs"][0]["rationale"] == "Hosted workflow rationale"
    assert captured["application"].applicant_name == "Responses Test"
    assert captured["fail_risk_once"] is True


def test_hosted_handler_executes_resume_envelope(monkeypatch) -> None:
    captured: list[str] = []

    class FakeRepository:
        @staticmethod
        def list_underwriting_results(_workflow_run_id: str) -> list[dict[str, Any]]:
            return []

    class FakeService:
        repository = FakeRepository()

        def __init__(self, _settings: object) -> None:
            pass

        @staticmethod
        def get_run(_workflow_run_id: str) -> dict[str, str]:
            return {"status": "CRASHED"}

        async def resume_workflow(self, workflow_run_id: str) -> list[dict[str, str]]:
            captured.append(workflow_run_id)
            return [{"decision": "APPROVED"}]

    monkeypatch.setattr(hosted_main, "LocalUnderwritingService", FakeService)
    request = {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-resume-test",
        "action": "resume",
    }

    result = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(request)},
            context=None,
            text_response=_text_response,
        )
    )

    assert captured == ["run-resume-test"]
    assert result == {
        "workflow_run_id": "run-resume-test",
        "status": "CRASHED",
        "outputs": [{"decision": "APPROVED"}],
    }


def test_hosted_handler_runs_maf_workflow_and_resumes_checkpoint(monkeypatch, tmp_path) -> None:
    settings = Settings(
        db_host="",
        db_port=0,
        db_name="",
        db_user="",
        db_password="",
        log_level="WARNING",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_jitter_ms=0,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        database_url=f"sqlite:///{tmp_path / 'hosted-workflow.db'}",
    )
    monkeypatch.setattr(hosted_main, "load_settings", lambda: settings)
    start = _start_request()
    start["options"]["fail_risk_once"] = True
    start["options"]["crash_after_executor"] = "medical_check"

    crashed = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(start)},
            context=None,
            text_response=_text_response,
        )
    )
    resumed = asyncio.run(
        hosted_main._handle(
            {
                "input": json.dumps(
                    {
                        "protocol": HOSTED_WORKFLOW_PROTOCOL,
                        "workflow_run_id": start["workflow_run_id"],
                        "action": "resume",
                    }
                )
            },
            context=None,
            text_response=_text_response,
        )
    )

    repository = WorkflowRunRepository(hosted_main.LocalUnderwritingService(settings).engine)
    events = repository.list_events(start["workflow_run_id"])
    assert crashed["status"] == "CRASHED"
    assert repository.latest_checkpoint_id(start["workflow_run_id"]) is not None
    assert resumed["status"] == "COMPLETED"
    assert resumed["outputs"]
    assert any(event["event_type"] == "retry_attempt" for event in events)
    assert len([event for event in events if event["event_type"] == "fan_in_result_received"]) == 4


def test_hosted_handler_rejects_trace_only_metadata() -> None:
    result = asyncio.run(
        hosted_main._handle(
            {
                "input": [],
                "metadata": {
                    "workflow_run_id": "run-trace-only-metadata-test",
                    "execution_mode": "trace_only",
                },
            },
            context=None,
            text_response=_text_response,
        )
    )

    assert result["status"] == "REJECTED"


def test_hosted_handler_never_copies_application_values_to_manual_trace_attributes(
    monkeypatch,
) -> None:
    spans: list[dict[str, object]] = []

    class FakeSpan:
        def __init__(self, attributes: dict[str, object]) -> None:
            self.attributes = dict(attributes)
            spans.append(self.attributes)

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, _name: str, *, attributes: dict[str, object]):
            yield FakeSpan(attributes)

    class FakeRepository:
        @staticmethod
        def list_underwriting_results(_workflow_run_id: str) -> list[dict[str, Any]]:
            return []

    class FakeService:
        repository = FakeRepository()

        def __init__(self, _settings: object) -> None:
            pass

        @staticmethod
        def get_run(_workflow_run_id: str) -> None:
            return None

        async def run_workflow(self, **kwargs: Any):
            return kwargs["workflow_run_id"], []

    monkeypatch.setattr(hosted_main, "_tracer", FakeTracer())
    monkeypatch.setattr(hosted_main, "LocalUnderwritingService", FakeService)

    asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_start_request())},
            context=None,
            text_response=_text_response,
        )
    )

    trace_values = json.dumps(spans)
    assert "Responses Test" not in trace_values
    assert "145000" not in trace_values
    assert "760" not in trace_values
