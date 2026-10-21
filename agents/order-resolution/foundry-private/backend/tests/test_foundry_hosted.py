from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
os.environ.setdefault("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS", "true")

from foundry import main as foundry_main


class _FakeTextResponse:
    def __init__(self, context: object, request: object, *, text: str) -> None:
        self.context = context
        self.request = request
        self.text = text


class _FakeRepository:
    def __init__(self) -> None:
        self.details_by_thread: dict[str, object] = {}
        self.origins_by_thread: dict[str, str] = {}

    def get_workflow_run(self, thread_id: str) -> object | None:
        return self.details_by_thread.get(thread_id)

    def get_workflow_origin_channel(self, thread_id: str) -> str | None:
        return self.origins_by_thread.get(thread_id)


class _FakeService:
    def __init__(self) -> None:
        self.started: list[dict[str, str]] = []
        self.resumed: list[dict[str, str]] = []
        self.origin_channels: list[str] = []

    async def start_chat_run(
        self,
        request: object,
        *,
        origin_channel: str = "api",
    ) -> object:
        self.origin_channels.append(origin_channel)
        self.started.append(
            {
                "thread_id": request.thread_id,  # type: ignore[attr-defined]
                "session_id": request.session_id,  # type: ignore[attr-defined]
                "message": request.message,  # type: ignore[attr-defined]
            }
        )
        return SimpleNamespace(run_id="run-1", thread_id=request.thread_id)

    async def respond_hitl(self, request: object) -> object:
        self.resumed.append(
            {
                "checkpoint_id": request.checkpoint_id,  # type: ignore[attr-defined]
                "decision": request.decision,  # type: ignore[attr-defined]
            }
        )
        return SimpleNamespace(accepted=True, checkpoint_id=request.checkpoint_id, thread_id="C1")


class _StatefulHitlService(_FakeService):
    def __init__(
        self,
        repository: _FakeRepository,
        checkpoint_threads: dict[str, str],
    ) -> None:
        super().__init__()
        self.repository = repository
        self.checkpoint_threads = checkpoint_threads

    async def respond_hitl(self, request: object) -> object:
        checkpoint_id = request.checkpoint_id  # type: ignore[attr-defined]
        decision = request.decision  # type: ignore[attr-defined]
        self.resumed.append(
            {
                "checkpoint_id": checkpoint_id,
                "decision": decision,
            }
        )
        thread_id = self.checkpoint_threads[checkpoint_id]
        self.repository.details_by_thread[thread_id] = _details(
            thread_id=thread_id,
            status="completed",
            pending=[
                {
                    "checkpoint_id": checkpoint_id,
                    "status": "approved" if decision == "approve" else "rejected",
                }
            ],
            output_message=f"Resumed {thread_id} with {decision}.",
        )
        return SimpleNamespace(
            accepted=True,
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
        )


class _FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, str | bool | int | float] = {}
        self.recorded_exceptions: list[Exception] = []

    def __enter__(self) -> _FakeSpan:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def set_attribute(self, key: str, value: str | bool | int | float) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.recorded_exceptions.append(exc)


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeSpan] = []

    def start_as_current_span(self, name: str) -> _FakeSpan:
        span = _FakeSpan(name)
        self.spans.append(span)
        return span


class _FakeResponsesHost:
    instances: list[_FakeResponsesHost] = []

    def __init__(self, **kwargs: object) -> None:
        self.store_supplied = "store" in kwargs
        self.store = kwargs.get("store")
        self.handler: object | None = None
        self.instances.append(self)

    def response_handler(self, handler: object) -> None:
        self.handler = handler


class _FakeAgentApp:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.error_handler: object | None = None

    def activity(self, activity_type: str):
        def decorator(handler: object) -> object:
            self.handlers[activity_type] = handler
            return handler

        return decorator

    def error(self, handler: object) -> object:
        self.error_handler = handler
        return handler


class _FakeActivityHost:
    def __init__(self, **kwargs: object) -> None:
        self.agent_app = _FakeAgentApp()
        super().__init__(**kwargs)


class _FakeActivity:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeActivityTypes:
    message = "message"
    invoke_response = "invokeResponse"


class _FakeAttachment(_FakeActivity):
    pass


class _FakeInvokeResponse(_FakeActivity):
    pass


class _FakeInMemoryResponseProvider:
    pass


class _FakeActivityContext:
    def __init__(self, activity: object) -> None:
        self.activity = activity
        self.sent: list[object] = []

    async def send_activity(self, activity: object) -> None:
        self.sent.append(activity)


class _FakeTeamsCardActionRepository:
    def __init__(self) -> None:
        self.issued: list[dict[str, object]] = []
        self.actions: dict[str, dict[str, str]] = {}
        self.completed: list[str] = []
        self.released: list[str] = []

    def issue_actions(self, **kwargs: object) -> dict[str, str]:
        self.issued.append(kwargs)
        checkpoint_id = str(kwargs["checkpoint_id"])
        thread_id = str(kwargs["thread_id"])
        conversation_id = str(kwargs["conversation_id"])
        user_id = str(kwargs["user_id"])
        tokens = {
            "approve": f"approve-{checkpoint_id}",
            "reject": f"reject-{checkpoint_id}",
        }
        batch_id = f"batch-{checkpoint_id}"
        for decision, token in tokens.items():
            self.actions[token] = {
                "checkpoint_id": checkpoint_id,
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "decision": decision,
                "batch_id": batch_id,
                "status": "pending",
            }
        return tokens

    def claim_action(
        self,
        *,
        token: str,
        decision: str,
        conversation_id: str,
        user_id: str,
    ) -> object:
        action = self.actions.get(token)
        if action is None:
            raise foundry_main.TeamsCardActionError("invalid_token", "invalid")
        if action["status"] != "pending":
            raise foundry_main.TeamsCardActionError("action_already_used", "used")
        if action["conversation_id"] != conversation_id:
            raise foundry_main.TeamsCardActionError("conversation_mismatch", "wrong conversation")
        if action["user_id"] != user_id:
            raise foundry_main.TeamsCardActionError("user_mismatch", "wrong user")
        if action["decision"] != decision:
            raise foundry_main.TeamsCardActionError("decision_mismatch", "wrong decision")
        batch_id = action["batch_id"]
        for candidate in self.actions.values():
            if candidate["batch_id"] == batch_id and candidate["status"] == "pending":
                candidate["status"] = "processing" if candidate is action else "superseded"
        return SimpleNamespace(
            checkpoint_id=action["checkpoint_id"],
            thread_id=action["thread_id"],
            decision=action["decision"],
            batch_id=batch_id,
        )

    def complete_action(self, batch_id: str) -> None:
        self.completed.append(batch_id)
        for action in self.actions.values():
            if action["batch_id"] == batch_id and action["status"] == "processing":
                action["status"] = "consumed"

    def release_action(self, batch_id: str) -> None:
        self.released.append(batch_id)
        for action in self.actions.values():
            if action["batch_id"] == batch_id:
                action["status"] = "pending"


def _details(
    *,
    thread_id: str,
    status: str,
    pending: list[dict[str, str]] | None = None,
    output_message: str = "",
) -> object:
    events = [
        SimpleNamespace(
            model_dump=lambda: {
                "id": "evt-1",
                "type": "workflow.stage",
                "thread_id": thread_id,
                "payload": {"agent": "triage", "status": "completed"},
            }
        ),
        SimpleNamespace(
            model_dump=lambda: {
                "id": "evt-2",
                "type": "tool.call",
                "thread_id": thread_id,
                "payload": {"local_tool": "fetch_order_status/fetch_policy"},
            }
        ),
    ]
    pending_models = [
        SimpleNamespace(
            status=item["status"], checkpoint_id=item["checkpoint_id"], model_dump=lambda i=item: i
        )
        for item in (pending or [])
    ]
    latest_output = {"message": output_message} if output_message else None
    return SimpleNamespace(
        thread_id=thread_id,
        status=status,
        events=events,
        pending_approvals=pending_models,
        latest_output=latest_output,
    )


def _fake_responses_types() -> tuple[
    type[object], type[object], type[object], type[object], type[object]
]:
    return (
        _FakeResponsesHost,
        object,
        object,
        _FakeTextResponse,
        _FakeInMemoryResponseProvider,
    )


def _fake_activity_types() -> tuple[
    type[object],
    type[object],
    type[object],
    type[object],
    type[object],
]:
    return (
        _FakeActivityHost,
        _FakeActivity,
        _FakeActivityTypes,
        _FakeAttachment,
        _FakeInvokeResponse,
    )


def _incoming_activity(
    *,
    conversation_id: str = "teams-conversation-1",
    user_id: str = "user-1",
    text: str | None = None,
    name: str | None = None,
    value: object | None = None,
    activity_type: str = "message",
) -> object:
    return SimpleNamespace(
        type=activity_type,
        conversation=SimpleNamespace(id=conversation_id),
        from_property=SimpleNamespace(id=f"channel-{user_id}", aad_object_id=user_id),
        text=text,
        name=name,
        value=value,
    )


def test_hosted_image_release_uses_private_safe_environment_settings() -> None:
    release_script = Path(__file__).parents[2] / "scripts/foundry/deploy_hosted_container.py"
    release_text = release_script.read_text()

    assert '"FOUNDRY_DEPLOYMENT_PROFILE"' not in release_text
    assert "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING" not in release_text
    assert '"OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false"' in release_text
    assert '"TRACE_EVALUATION_RECORD_CONTENT": require(' in release_text
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in release_text
    assert "APPINSIGHTS_CONNECTION_STRING" not in release_text
    assert "MAF_APPINSIGHTS_" not in release_text
    assert "MAF_MONITOR_" not in release_text
    assert '"FOUNDRY_PROJECTS_ENDPOINT":' not in release_text
    assert '"FOUNDRY_RUNTIME_DATABASE_URL":' not in release_text
    assert '"FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT":' not in release_text
    assert (
        '"AZURE_AI_MODEL_DEPLOYMENT_NAME": require("FOUNDRY_MODEL_DEPLOYMENT_NAME")' in release_text
    )
    assert "connections.{runtime_connection_name}.credentials.database_url" in release_text
    assert "create_version_with_transient_retry" in release_text
    assert "HttpResponseError" in release_text
    assert "enumerate((0, 30, 60), start=1)" in release_text
    assert not hasattr(foundry_main, "setup_observability")


def test_foundry_model_env_aliases_set_canonical_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECTS_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/order")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

    foundry_main._apply_foundry_model_env_aliases()

    assert os.getenv("FOUNDRY_PROJECTS_ENDPOINT") == "https://example.test/api/projects/order"
    assert os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") == "gpt-4o-mini"


def test_foundry_model_env_aliases_preserve_canonical_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECTS_ENDPOINT", "https://canonical.test/api/projects/order")
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "canonical-model")
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://hosted.test/api/projects/order")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "hosted-model")

    foundry_main._apply_foundry_model_env_aliases()

    assert os.getenv("FOUNDRY_PROJECTS_ENDPOINT") == "https://canonical.test/api/projects/order"
    assert os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") == "canonical-model"


@pytest.mark.parametrize("profile", ["private", ""])
def test_build_app_uses_in_memory_store_for_all_profiles(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
) -> None:
    _FakeResponsesHost.instances.clear()
    if profile:
        monkeypatch.setenv("FOUNDRY_DEPLOYMENT_PROFILE", profile)
    else:
        monkeypatch.delenv("FOUNDRY_DEPLOYMENT_PROFILE", raising=False)
    monkeypatch.setattr(foundry_main, "_load_responses_types", _fake_responses_types)
    monkeypatch.setattr(foundry_main, "_load_activity_types", _fake_activity_types)

    app = foundry_main._build_app()

    assert app is _FakeResponsesHost.instances[-1]
    assert app.store_supplied is True
    assert isinstance(app.store, _FakeInMemoryResponseProvider)
    assert set(app.agent_app.handlers) == {"message", "invoke"}
    assert app.agent_app.error_handler is not None


def test_runtime_database_url_override_sets_database_url_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == runtime_url


def test_runtime_database_url_override_prefers_foundry_runtime_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "FOUNDRY_RUNTIME_DATABASE_URL",
        "postgresql://user:pass@preferred.postgres.database.azure.com:5432/maf?sslmode=require",
    )
    monkeypatch.setenv(
        "RUNTIME_DATABASE_URL",
        "postgresql://user:pass@fallback.postgres.database.azure.com:5432/maf?sslmode=require",
    )

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL", "").startswith(
        "postgresql://user:pass@preferred.postgres.database.azure.com"
    )


def test_trace_evaluation_content_uses_custom_hosted_agent_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "false")
    monkeypatch.setenv("TRACE_EVALUATION_RECORD_CONTENT", "true")

    assert foundry_main._trace_evaluation_content_enabled(
        {"metadata": {"trace_evaluation_record_content": True}}, None
    )


def test_foundry_agent_identity_uses_platform_name_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "order-resolution-hosted")
    monkeypatch.setenv("FOUNDRY_AGENT_VERSION", "10")

    assert foundry_main._foundry_agent_identity() == (
        "order-resolution-hosted",
        "10",
        "order-resolution-hosted:10",
    )


def test_runtime_database_url_override_replaces_loopback_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/maf_workflow")

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == runtime_url


def test_runtime_database_url_override_keeps_existing_remote_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_url = (
        "postgresql://user:pass@existing.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("DATABASE_URL", existing_url)
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == existing_url


def test_parse_input_extracts_conversation_and_message() -> None:
    parsed = foundry_main._parse_input(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Resolve delayed order ORD-1001"}],
                }
            ],
            "conversation": {"id": "C1"},
        },
        None,
    )
    assert parsed.conversation_id == "C1"
    assert parsed.message == "Resolve delayed order ORD-1001"
    assert parsed.decision is None
    assert parsed.checkpoint_id is None


def test_parse_input_detects_function_call_output_decision() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation_id": "C1",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-123",
                    "output": {"decision": "approve"},
                }
            ],
        },
        None,
    )
    assert parsed.decision == "approve"
    assert parsed.checkpoint_id == "cp-123"


def test_parse_input_extracts_message_from_context_when_payload_is_empty() -> None:
    parsed = foundry_main._parse_input(
        {},
        SimpleNamespace(
            conversation_id="C2",
            request_body={
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Resolve delayed order ORD-1001"}
                        ],
                    }
                ]
            },
        ),
    )
    assert parsed.conversation_id == "C2"
    assert parsed.message == "Resolve delayed order ORD-1001"
    assert parsed.decision is None


def test_parse_input_extracts_function_call_output_from_context_request_body() -> None:
    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C3"}},
        SimpleNamespace(
            request_body={
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": "cp-456",
                        "output": "approve",
                    }
                ]
            }
        ),
    )

    assert parsed.conversation_id == "C3"
    assert parsed.message == "approve"
    assert parsed.decision == "approve"
    assert parsed.checkpoint_id == "cp-456"


def test_parse_input_extracts_function_call_output_from_resolved_context_items() -> None:
    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C4"}},
        None,
        input_items=[
            {
                "type": "function_call_output",
                "call_id": "cp-789",
                "output": "reject",
            }
        ],
    )

    assert parsed.conversation_id == "C4"
    assert parsed.message is None
    assert parsed.decision == "reject"
    assert parsed.checkpoint_id == "cp-789"


def test_parse_input_prefers_payload_response_id_over_context_session_id() -> None:
    parsed = foundry_main._parse_input(
        {"id": "resp-123", "input": "Resolve delayed order ORD-1001"},
        SimpleNamespace(session_id="sess-abc"),
    )
    assert parsed.conversation_id == "resp-123"


def test_parse_input_accepts_previous_response_id_for_resume() -> None:
    parsed = foundry_main._parse_input(
        {"previous_response_id": "resp-prev-1", "input": "Approve"},
        None,
    )
    assert parsed.conversation_id == "resp-prev-1"
    assert parsed.decision is None


def test_parse_input_prefers_payload_conversation_string_over_previous_response_id() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation": "conv-456",
            "previous_response_id": "resp-prev-2",
            "input": "Resolve delayed order ORD-1001",
        },
        None,
    )
    assert parsed.conversation_id == "conv-456"


def test_parse_input_uses_context_request_metadata_instead_of_response_id() -> None:
    parsed = foundry_main._parse_input(
        {"id": "resp-123", "input": "Resolve delayed order ORD-1009"},
        SimpleNamespace(request_body={"metadata": {"conversation_id": "conv-meta-1"}}),
    )
    assert parsed.conversation_id == "conv-meta-1"


def test_parse_input_prefers_stable_context_metadata_over_previous_response_id() -> None:
    parsed = foundry_main._parse_input(
        {
            "previous_response_id": "resp-previous-turn",
            "input": "Approve",
        },
        SimpleNamespace(
            request_body={"metadata": {"conversation_id": "teams-conversation-stable"}}
        ),
    )

    assert parsed.conversation_id == "teams-conversation-stable"
    assert parsed.decision is None


def test_parse_input_prefers_context_request_metadata_over_context_id() -> None:
    parsed = foundry_main._parse_input(
        {"input": "Resolve delayed order ORD-1001"},
        SimpleNamespace(
            id="resp-999", request_body={"metadata": {"conversation_id": "conv-meta-2"}}
        ),
    )
    assert parsed.conversation_id == "conv-meta-2"


@pytest.mark.parametrize(
    ("payload", "context", "expected_conversation_id"),
    [
        (
            {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Approve"}],
                    }
                ]
            },
            SimpleNamespace(conversation_id="teams-conversation-direct"),
            "teams-conversation-direct",
        ),
        (
            {"id": "response-turn-1", "input": "Approve"},
            SimpleNamespace(
                request_body={"metadata": {"conversation_id": "teams-conversation-metadata"}}
            ),
            "teams-conversation-metadata",
        ),
        (
            {"input": "Reject"},
            SimpleNamespace(request_body={"conversation": {"id": "teams-conversation-request"}}),
            "teams-conversation-request",
        ),
    ],
)
def test_parse_input_extracts_stable_conversation_from_teams_bridge_shapes(
    payload: dict[str, object],
    context: object,
    expected_conversation_id: str,
) -> None:
    parsed = foundry_main._parse_input(payload, context)

    assert parsed.conversation_id == expected_conversation_id
    assert parsed.decision is None


def test_parse_input_uses_payload_conversation_id_when_present() -> None:
    parsed = foundry_main._parse_input(
        {
            "id": "resp-123",
            "conversation": {"id": "conv-123"},
            "input": "Resolve delayed order ORD-1001",
        },
        None,
    )
    assert parsed.conversation_id == "conv-123"


def test_parse_input_does_not_infer_approval_from_nested_text() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation": {"id": "conv-approve-1"},
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": {"value": "Approve"}}],
                }
            ],
        },
        None,
    )
    assert parsed.message == "Approve"
    assert parsed.decision is None


def test_parse_input_does_not_infer_approval_from_serialized_context_input() -> None:
    context = SimpleNamespace(
        conversation_id="conv-approve-2",
        input="{'conversation': {'id': 'conv-approve-2'}, 'input': 'Approve'}",
    )
    parsed = foundry_main._parse_input({}, context)
    assert parsed.conversation_id == "conv-approve-2"
    assert parsed.decision is None


@pytest.mark.parametrize(
    "message",
    [
        "Approve",
        "  approved  ",
        "\nYES!\t",
        "Reject",
        "  ReJeCtEd.  ",
        "\tno?\n",
        "Do not approve this refund",
        "No refund; send a replacement",
    ],
)
def test_parse_input_never_infers_decision_from_free_form_text(message: str) -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation": {"id": "teams-conversation-1"},
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                }
            ],
        },
        None,
    )

    assert parsed.conversation_id == "teams-conversation-1"
    assert parsed.message == message.strip()
    assert parsed.decision is None


def test_parse_input_resume_hitl_without_decision_does_not_auto_approve() -> None:
    parsed = foundry_main._parse_input(
        {"conversation_id": "C1", "metadata": {"operation": "resume_hitl"}},
        None,
    )
    assert parsed.decision is None


@pytest.mark.asyncio
async def test_activity_message_emits_secure_pending_approval_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-1"] = _details(
        thread_id="teams-conversation-1",
        status="waiting_approval",
        pending=[
            {
                "checkpoint_id": "cp-card-1",
                "status": "pending",
                "action": "issue_partial_refund",
            }
        ],
    )
    service = _FakeService()
    card_repo = _FakeTeamsCardActionRepository()
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "teams_card_action_repository", card_repo)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())

    context = _FakeActivityContext(_incoming_activity(text="Resolve delayed order ORD-1001"))
    await foundry_main._run_from_activity_message(
        context,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        attachment_type=_FakeAttachment,
    )

    assert service.started == [
        {
            "thread_id": "teams-conversation-1",
            "session_id": "teams-conversation-1",
            "message": "Resolve delayed order ORD-1001",
        }
    ]
    assert card_repo.issued[0]["checkpoint_id"] == "cp-card-1"
    sent = context.sent[0]
    assert sent.type == "message"
    assert sent.text == "Approval required."
    card = sent.attachments[0].content
    assert [action["title"] for action in card["actions"]] == ["Approve", "Reject"]
    assert card["actions"][0]["data"] == {"token": "approve-cp-card-1"}
    assert card["actions"][1]["data"] == {"token": "reject-cp-card-1"}
    assert "checkpoint" not in json.dumps(card["actions"]).lower()
    assert "ord-1001" not in json.dumps(card).lower()


@pytest.mark.asyncio
async def test_activity_card_uses_m365_attachment_alias() -> None:
    from microsoft_agents.activity import Attachment

    context = _FakeActivityContext(_incoming_activity(text="test"))
    card = {"type": "AdaptiveCard", "version": "1.5"}

    await foundry_main._send_activity_card(
        context,
        card=card,
        text="Approval required.",
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        attachment_type=Attachment,
    )

    attachment = context.sent[0].attachments[0]
    assert attachment.content_type == foundry_main.teams_cards.ADAPTIVE_CONTENT_TYPE
    assert attachment.content == card


@pytest.mark.asyncio
async def test_activity_typed_decision_does_not_resume_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeService()
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-1"] = _details(
        thread_id="teams-conversation-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-card-1", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    context = _FakeActivityContext(_incoming_activity(text="Approve"))

    await foundry_main._run_from_activity_message(
        context,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        attachment_type=_FakeAttachment,
    )

    assert service.started == []
    assert service.resumed == []
    assert context.sent == ["Use the pending approval card to submit a decision."]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "verb", "resolved_status"),
    [
        ("approve", foundry_main.teams_cards.APPROVE_VERB, "Approved"),
        ("reject", foundry_main.teams_cards.REJECT_VERB, "Rejected"),
    ],
)
async def test_activity_card_decision_resumes_exact_checkpoint_and_updates_card(
    monkeypatch: pytest.MonkeyPatch,
    decision: str,
    verb: str,
    resolved_status: str,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-1"] = _details(
        thread_id="teams-conversation-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-card-1", "status": "pending"}],
    )
    service = _StatefulHitlService(repo, {"cp-card-1": "teams-conversation-1"})
    card_repo = _FakeTeamsCardActionRepository()
    tokens = card_repo.issue_actions(
        thread_id="teams-conversation-1",
        checkpoint_id="cp-card-1",
        conversation_id="teams-conversation-1",
        user_id="user-1",
        ttl_seconds=60,
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "teams_card_action_repository", card_repo)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())
    context = _FakeActivityContext(
        _incoming_activity(
            name=foundry_main.teams_cards.ADAPTIVE_ACTION_INVOKE,
            value={
                "action": {
                    "verb": verb,
                    "data": {"token": tokens[decision]},
                }
            },
            activity_type="invoke",
        )
    )

    await foundry_main._run_from_activity_invoke(
        context,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        invoke_response_type=_FakeInvokeResponse,
    )

    assert service.resumed == [{"checkpoint_id": "cp-card-1", "decision": decision}]
    assert card_repo.completed == ["batch-cp-card-1"]
    invoke = context.sent[0]
    assert invoke.type == "invokeResponse"
    assert invoke.value.status == 200
    assert invoke.value.body["statusCode"] == 200
    assert invoke.value.body["value"]["body"][0]["text"] == resolved_status


@pytest.mark.asyncio
async def test_activity_card_action_rejects_wrong_user_and_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeService()
    card_repo = _FakeTeamsCardActionRepository()
    tokens = card_repo.issue_actions(
        thread_id="teams-conversation-1",
        checkpoint_id="cp-card-1",
        conversation_id="teams-conversation-1",
        user_id="user-1",
        ttl_seconds=60,
    )
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "teams_card_action_repository", card_repo)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())
    context = _FakeActivityContext(
        _incoming_activity(
            conversation_id="teams-conversation-2",
            user_id="user-2",
            name=foundry_main.teams_cards.ADAPTIVE_ACTION_INVOKE,
            value={
                "action": {
                    "verb": foundry_main.teams_cards.REJECT_VERB,
                    "data": {"token": tokens["reject"]},
                }
            },
            activity_type="invoke",
        )
    )

    await foundry_main._run_from_activity_invoke(
        context,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        invoke_response_type=_FakeInvokeResponse,
    )

    assert service.resumed == []
    assert context.sent[0].value.body["statusCode"] == 403
    assert context.sent[0].value.body["value"]["code"] == "conversation_mismatch"


@pytest.mark.asyncio
async def test_activity_card_action_replay_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-1"] = _details(
        thread_id="teams-conversation-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-card-1", "status": "pending"}],
    )
    service = _StatefulHitlService(repo, {"cp-card-1": "teams-conversation-1"})
    card_repo = _FakeTeamsCardActionRepository()
    tokens = card_repo.issue_actions(
        thread_id="teams-conversation-1",
        checkpoint_id="cp-card-1",
        conversation_id="teams-conversation-1",
        user_id="user-1",
        ttl_seconds=60,
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "teams_card_action_repository", card_repo)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())

    def context() -> _FakeActivityContext:
        return _FakeActivityContext(
            _incoming_activity(
                name=foundry_main.teams_cards.ADAPTIVE_ACTION_INVOKE,
                value={
                    "action": {
                        "verb": foundry_main.teams_cards.APPROVE_VERB,
                        "data": {"token": tokens["approve"]},
                    }
                },
                activity_type="invoke",
            )
        )

    first = context()
    replay = context()
    await foundry_main._run_from_activity_invoke(
        first,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        invoke_response_type=_FakeInvokeResponse,
    )
    await foundry_main._run_from_activity_invoke(
        replay,
        activity_type=_FakeActivity,
        activity_types=_FakeActivityTypes,
        invoke_response_type=_FakeInvokeResponse,
    )

    assert service.resumed == [{"checkpoint_id": "cp-card-1", "decision": "approve"}]
    assert first.sent[0].value.body["statusCode"] == 200
    assert replay.sent[0].value.body["statusCode"] == 409
    assert replay.sent[0].value.body["value"]["code"] == "action_already_used"


@pytest.mark.asyncio
async def test_run_from_responses_starts_workflow_and_returns_final_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete. Action 'issue_partial_refund' submitted for order ord-1001.",
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response = await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Resolve delayed order ORD-1001"},
        None,
        _FakeTextResponse,
    )

    assert service.started == [
        {
            "thread_id": "C1",
            "session_id": "C1",
            "message": "Resolve delayed order ORD-1001",
        }
    ]
    assert (
        response.text
        == "Resolution complete. Action 'issue_partial_refund' submitted for order ord-1001."
    )


@pytest.mark.asyncio
async def test_run_from_responses_resumes_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)

    await foundry_main._run_from_responses(
        {
            "conversation": {"id": "C1"},
            "input": [{"type": "function_call_output", "call_id": "cp-123", "output": "approve"}],
        },
        None,
        _FakeTextResponse,
    )

    assert service.resumed == [{"checkpoint_id": "cp-123", "decision": "approve"}]
    span = tracer.spans[0]
    assert span.name == "foundry.responses.invoke"
    assert span.attributes["workflow.thread_id"] == "C1"
    assert span.attributes["workflow.session_id"] == "C1"
    assert span.attributes["foundry.protocol"] == "responses"
    assert span.attributes["workflow.checkpoint_id"] == "cp-123"
    assert span.attributes["workflow.status"] == "waiting_approval"
    assert span.attributes["workflow.event_count"] == 2
    assert span.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert span.attributes["gen_ai.conversation.id"] == "C1"


@pytest.mark.asyncio
async def test_run_from_responses_treats_approval_words_as_normal_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-none"},
            "input": "  APPROVED!  ",
        },
        None,
        _FakeTextResponse,
    )

    assert response.text == "Workflow run not found."
    assert service.started == [
        {
            "thread_id": "teams-conversation-none",
            "session_id": "teams-conversation-none",
            "message": "APPROVED!",
        }
    ]
    assert service.resumed == []


@pytest.mark.asyncio
async def test_run_from_responses_cannot_resume_teams_activity_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-1"] = _details(
        thread_id="teams-conversation-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-teams-1", "status": "pending"}],
    )
    service = _StatefulHitlService(
        repo,
        {"cp-teams-1": "teams-conversation-1"},
    )
    repo.origins_by_thread["teams-conversation-1"] = "teams_activity"
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response = await foundry_main._run_from_responses(
        {
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-teams-1",
                    "output": "approve",
                }
            ],
            "conversation": {"id": "teams-conversation-1"},
        },
        None,
        _FakeTextResponse,
    )

    assert service.started == []
    assert service.resumed == []
    assert response.text == "Use the pending approval card to submit a decision."


@pytest.mark.asyncio
async def test_run_from_responses_does_not_resume_checkpoint_from_another_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-a"] = _details(
        thread_id="teams-conversation-a",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-a", "status": "pending"}],
    )
    repo.details_by_thread["teams-conversation-b"] = _details(
        thread_id="teams-conversation-b",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-b", "status": "pending"}],
        output_message="Conversation B private state.",
    )
    service = _StatefulHitlService(
        repo,
        {
            "cp-a": "teams-conversation-a",
            "cp-b": "teams-conversation-b",
        },
    )
    repo.origins_by_thread.update(
        {
            "teams-conversation-a": "responses",
            "teams-conversation-b": "responses",
        }
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-a"},
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-b",
                    "output": "approve",
                }
            ],
        },
        None,
        _FakeTextResponse,
    )

    assert service.resumed == []
    assert response.text == "No pending approval found for this conversation."
    assert "Conversation B private state." not in response.text


@pytest.mark.asyncio
async def test_run_from_responses_isolates_independent_teams_conversations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-a"] = _details(
        thread_id="teams-conversation-a",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-a", "status": "pending"}],
    )
    repo.details_by_thread["teams-conversation-b"] = _details(
        thread_id="teams-conversation-b",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-b", "status": "pending"}],
    )
    service = _StatefulHitlService(
        repo,
        {
            "cp-a": "teams-conversation-a",
            "cp-b": "teams-conversation-b",
        },
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response_a = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-a"},
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-a",
                    "output": "approve",
                }
            ],
        },
        None,
        _FakeTextResponse,
    )
    response_b = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-b"},
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-b",
                    "output": "reject",
                }
            ],
        },
        None,
        _FakeTextResponse,
    )

    assert service.resumed == [
        {"checkpoint_id": "cp-a", "decision": "approve"},
        {"checkpoint_id": "cp-b", "decision": "reject"},
    ]
    assert response_a.text == "Resumed teams-conversation-a with approve."
    assert response_b.text == "Resumed teams-conversation-b with reject."
    assert response_a.text not in response_b.text
    assert response_b.text not in response_a.text


@pytest.mark.asyncio
async def test_run_from_responses_replayed_decision_does_not_resume_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["teams-conversation-replay"] = _details(
        thread_id="teams-conversation-replay",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-replay", "status": "pending"}],
    )
    service = _StatefulHitlService(
        repo,
        {"cp-replay": "teams-conversation-replay"},
    )
    repo.origins_by_thread["teams-conversation-replay"] = "responses"
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    first = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-replay"},
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-replay",
                    "output": "approve",
                }
            ],
        },
        None,
        _FakeTextResponse,
    )
    replay = await foundry_main._run_from_responses(
        {
            "conversation": {"id": "teams-conversation-replay"},
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-replay",
                    "output": "approve",
                }
            ],
        },
        None,
        _FakeTextResponse,
    )

    assert first.text == "Resumed teams-conversation-replay with approve."
    assert service.resumed == [{"checkpoint_id": "cp-replay", "decision": "approve"}]
    assert replay.text == "No pending approval found for this conversation."


@pytest.mark.asyncio
async def test_run_from_responses_records_exception_on_root_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingService:
        async def start_chat_run(
            self,
            request: object,
            *,
            origin_channel: str = "api",
        ) -> object:
            raise RuntimeError("boom")

    tracer = _FakeTracer()
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)
    monkeypatch.setattr(foundry_main, "order_resolution_service", _FailingService())

    with pytest.raises(RuntimeError, match="boom"):
        await foundry_main._run_from_responses(
            {"conversation_id": "C1", "input": "Resolve delayed order ORD-1001"},
            None,
            _FakeTextResponse,
        )

    span = tracer.spans[0]
    assert span.name == "foundry.responses.invoke"
    assert len(span.recorded_exceptions) == 1
    assert isinstance(span.recorded_exceptions[0], RuntimeError)


@pytest.mark.asyncio
async def test_run_from_responses_records_genai_messages_for_trace_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _AzureCreateResponse:
        def as_dict(self) -> dict[str, object]:
            return {
                "conversation": {"id": "C1"},
                "input": "Resolve delayed order ORD-1001",
                "structured_inputs": {"trace_evaluation_record_content": True},
            }

    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete.",
    )
    monkeypatch.setenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "true")
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "order-resolution-hosted")
    monkeypatch.setenv("FOUNDRY_AGENT_VERSION", "10")
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)

    await foundry_main._run_from_responses(
        _AzureCreateResponse(),
        None,
        _FakeTextResponse,
    )

    span = tracer.spans[0]
    assert json.loads(str(span.attributes["gen_ai.input.messages"])) == [
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "content": "Resolve delayed order ORD-1001",
                }
            ],
        }
    ]
    assert json.loads(str(span.attributes["gen_ai.output.messages"])) == [
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "text",
                    "content": "Resolution complete.",
                }
            ],
        }
    ]
    assert span.attributes["gen_ai.agent.name"] == "order-resolution-hosted"
    assert span.attributes["gen_ai.agent.version"] == "10"
    assert span.attributes["gen_ai.agent.id"] == "order-resolution-hosted:10"


@pytest.mark.asyncio
async def test_run_from_responses_does_not_record_unmarked_trace_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete.",
    )
    monkeypatch.setenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "true")
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)

    await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Resolve delayed order ORD-1001"},
        None,
        _FakeTextResponse,
    )

    span = tracer.spans[0]
    assert "gen_ai.input.messages" not in span.attributes
    assert "gen_ai.output.messages" not in span.attributes
    assert span.attributes["foundry.trace_evaluation.content_enabled"] is False


@pytest.mark.asyncio
async def test_run_from_responses_reads_trace_marker_from_response_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ResponseContext:
        client_headers = {
            "x-client-trace-evaluation-record-content": "true",
        }
        request_body = {"input": "Resolve delayed order ORD-1001"}

    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete.",
    )
    monkeypatch.setenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "true")
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)

    await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}},
        _ResponseContext(),
        _FakeTextResponse,
    )

    span = tracer.spans[0]
    assert span.attributes["foundry.trace_evaluation.content_enabled"] is True
    assert "gen_ai.input.messages" in span.attributes
    assert "gen_ai.output.messages" in span.attributes
