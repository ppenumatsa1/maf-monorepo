from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import app.infrastructure.checkpointing.postgres_checkpoint_storage as checkpoint_module
import app.maf.executors.credit_check as credit_module
import app.maf.executors.driving_check as driving_module
import app.maf.executors.fan_in_aggregator as fan_in_module
import app.maf.executors.final_decision as final_decision_module
import app.maf.executors.init_context as init_context_module
import app.maf.executors.medical_check as medical_module
import app.maf.executors.risk_score as risk_module
import app.maf.middleware.resilience as resilience_module
import app.maf.runner as runner_module
import foundry.main as hosted_main
from app.core.config import Settings
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL


@dataclass
class _Span:
    name: str
    attributes: dict[str, object]
    parent: _Span | None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


@dataclass
class _CorrelationTracer:
    spans: list[_Span] = field(default_factory=list)
    _active: ContextVar[_Span | None] = field(
        default_factory=lambda: ContextVar("active_test_span", default=None)
    )

    @contextmanager
    def start_as_current_span(
        self, name: str, *, attributes: dict[str, object] | None = None, **_kwargs: object
    ):
        span = _Span(name, dict(attributes or {}), self._active.get())
        self.spans.append(span)
        token = self._active.set(span)
        try:
            yield span
        finally:
            self._active.reset(token)


def _settings(tmp_path) -> Settings:
    return Settings(
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
        database_url=f"sqlite:///{tmp_path / 'telemetry-correlation.db'}",
    )


def _request() -> dict[str, object]:
    return {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-trace-correlation",
        "action": "start",
        "application": {
            "application_id": "app-trace-correlation",
            "applicant_name": "Private Applicant",
            "age": 38,
            "income": 145000,
            "requested_coverage": 500000,
            "health_disclosures": "private health detail",
            "driving_history": "private driving detail",
            "credit_score": 760,
        },
        "options": {
            "fail_risk_once": True,
            "fail_credit_randomly": False,
            "crash_after_executor": "medical_check",
        },
    }


def _text_response(_context, _request, *, text: str):
    return json.loads(text)


def test_hosted_workflow_telemetry_is_correlated_to_responses_operation(
    monkeypatch, tmp_path
) -> None:
    tracer = _CorrelationTracer()
    monkeypatch.setattr(hosted_main, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(hosted_main, "_tracer", tracer)

    @contextmanager
    def stage_span(stage: str, attributes: dict[str, object] | None = None):
        with tracer.start_as_current_span(f"workflow.{stage}", attributes=attributes) as span:
            yield span

    for module in (
        checkpoint_module,
        credit_module,
        driving_module,
        fan_in_module,
        final_decision_module,
        init_context_module,
        medical_module,
        resilience_module,
        risk_module,
        runner_module,
    ):
        monkeypatch.setattr(module, "workflow_stage_span", stage_span)

    crashed = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_request())},
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
                        "workflow_run_id": "run-trace-correlation",
                        "action": "resume",
                    }
                )
            },
            context=None,
            text_response=_text_response,
        )
    )

    assert crashed["status"] == "CRASHED"
    assert resumed["status"] == "COMPLETED"
    spans = {span.name: span for span in tracer.spans}
    required_spans = {
        "foundry.responses.invoke",
        "underwriting.hosted.workflow",
        "workflow.stage.fan_out",
        "workflow.stage.risk_check",
        "workflow.stage.retry_attempt",
        "workflow.stage.retry_backoff",
        "workflow.stage.failure_injected",
        "workflow.stage.idempotency_skip",
        "workflow.checkpoint.save",
        "workflow.checkpoint.load",
        "workflow.stage.fan_in",
        "workflow.stage.final_decision",
    }
    assert required_spans <= spans.keys()
    response_span = spans["foundry.responses.invoke"]
    workflow_span = spans["underwriting.hosted.workflow"]
    assert workflow_span.parent is response_span
    correlated = [
        span
        for span in tracer.spans
        if span.name.startswith("workflow.") and "workflow.run_id" in span.attributes
    ]
    assert correlated
    assert all(span.attributes["workflow.run_id"] == "run-trace-correlation" for span in correlated)
    assert all(
        "Private Applicant" not in json.dumps(span.attributes)
        and "145000" not in json.dumps(span.attributes)
        and "760" not in json.dumps(span.attributes)
        for span in tracer.spans
    )
