from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from app.infrastructure.persistence.teams_card_action_repository import TeamsCardActionError
from app.modules.underwriting.models import CardActionClaim, OriginChannel, ReviewerOutcome
from azure.ai.agentserver.activity import ActivityAgentServerHost
from azure.ai.agentserver.responses import ResponsesAgentServerHost
from foundry import main as foundry_main
from foundry import teams_cards
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
    ConversationAccount,
    InvokeResponse,
)


class _Context:
    def __init__(self, activity: Activity) -> None:
        self.activity = activity
        self.sent: list[Any] = []

    async def send_activity(self, activity: Any) -> None:
        self.sent.append(activity)


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


class _Tracer:
    @contextmanager
    def start_as_current_span(self, _name: str, *, attributes: dict[str, Any]):
        span = _Span()
        span.attributes.update(attributes)
        yield span


class _CardActions:
    def __init__(self, *, pending: bool = False) -> None:
        self.pending = pending

    def has_pending_action_for_conversation(self, _conversation_id: str) -> bool:
        return self.pending


class _Service:
    def __init__(self, *, pending: bool = False) -> None:
        self.card_actions = _CardActions(pending=pending)
        self.issued: list[dict[str, Any]] = []
        self.claim_error: TeamsCardActionError | None = None
        self.decide_error: Exception | None = None
        self.decisions: list[dict[str, Any]] = []
        self.completed: list[str] = []
        self.released: list[str] = []

    def issue_teams_review_actions(self, **kwargs: Any) -> dict[ReviewerOutcome, str]:
        self.issued.append(kwargs)
        return {
            ReviewerOutcome.APPROVED: "opaque-approve-token",
            ReviewerOutcome.DECLINED: "opaque-decline-token",
        }

    def claim_teams_review_action(self, **kwargs: Any) -> CardActionClaim:
        if self.claim_error is not None:
            raise self.claim_error
        return CardActionClaim(
            workflow_run_id="run-teams-review",
            checkpoint_id="checkpoint-teams-review",
            decision=kwargs["decision"],
            batch_id="batch-teams-review",
        )

    async def decide_review(self, **kwargs: Any) -> list[Any]:
        self.decisions.append(kwargs)
        if self.decide_error is not None:
            raise self.decide_error
        return []

    def complete_teams_review_action(self, batch_id: str) -> bool:
        self.completed.append(batch_id)
        return True

    def release_teams_review_action(self, batch_id: str) -> bool:
        self.released.append(batch_id)
        return True


def _activity(
    *,
    activity_type: str,
    text: str | None = None,
    name: str | None = None,
    value: Any = None,
    conversation_id: str = "teams-conversation",
    user_id: str = "teams-user",
) -> Activity:
    kwargs: dict[str, Any] = {
        "type": activity_type,
        "id": "teams-activity-id",
        "conversation": ConversationAccount(id=conversation_id),
        "from_property": ChannelAccount(id="channel-user", aadObjectId=user_id),
    }
    if text is not None:
        kwargs["text"] = text
    if name is not None:
        kwargs["name"] = name
    if value is not None:
        kwargs["value"] = value
    return Activity(
        **kwargs,
    )


def _pending_result() -> dict[str, Any]:
    return {
        "workflow_run_id": "run-teams-review",
        "status": "PENDING_REVIEW",
        "machine_recommendation": "REFER_TO_HUMAN_UNDERWRITER",
        "review_checkpoint_id": "checkpoint-teams-review",
        "outputs": [
            {
                "application_id": "APP-1042",
                "applicant_name": "Private Applicant",
                "age": 44,
                "income": 123456,
                "requested_coverage": 900000,
                "health_disclosures": "private medical disclosure",
                "credit_score": 612,
                "rationale": "raw model rationale",
                "score_breakdown": {
                    "risk": 0.52,
                    "credit": 0.72,
                    "medical": 0.4,
                    "driving": 0.9,
                },
            }
        ],
    }


def test_pending_card_contains_only_safe_categorical_review_content() -> None:
    summary = teams_cards.safe_review_summary(_pending_result())
    card = teams_cards.build_pending_review_card(
        application_id=summary["application_id"],
        machine_recommendation=summary["machine_recommendation"],
        risk_bands=summary["risk_bands"],
        reason_categories=summary["reason_categories"],
        approve_token="random-approve",
        decline_token="random-decline",
    )
    serialized = json.dumps(card)

    assert "APP-1042" in serialized
    assert "REFER_TO_HUMAN_UNDERWRITER" in serialized
    assert {"Low", "Moderate", "High"} <= set(summary["risk_bands"].values())
    for prohibited in (
        "Private Applicant",
        "123456",
        "900000",
        "private medical disclosure",
        "612",
        "raw model rationale",
        "0.52",
        "0.72",
        "0.4",
        "0.9",
        "checkpoint-teams-review",
        "run-teams-review",
    ):
        assert prohibited not in serialized
    assert card["actions"][0]["data"] == {"token": "random-approve"}
    assert card["actions"][1]["data"] == {"token": "random-decline"}


def test_review_action_parses_real_activity_alias_contract() -> None:
    activity = _activity(
        activity_type="invoke",
        name=teams_cards.ADAPTIVE_ACTION_INVOKE,
        value={
            "action": {
                "verb": teams_cards.APPROVE_VERB,
                "data": {"token": "opaque-token"},
            }
        },
    )

    assert activity.model_dump(by_alias=True)["from"]["aadObjectId"] == "teams-user"
    assert teams_cards.parse_review_action(activity) == (
        ReviewerOutcome.APPROVED,
        "opaque-token",
    )


@pytest.mark.asyncio
async def test_activity_message_renders_card_and_uses_exact_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _Service()
    handled: list[dict[str, Any]] = []

    async def fake_handle(
        request: Any,
        _context: Any,
        text_response: Any,
        *,
        origin_channel: OriginChannel,
    ) -> Any:
        assert origin_channel == OriginChannel.TEAMS_ACTIVITY
        handled.append(json.loads(request["input"]))
        return text_response(None, None, text=json.dumps(_pending_result()))

    monkeypatch.setattr(foundry_main, "LocalUnderwritingService", lambda _settings: service)
    monkeypatch.setattr(foundry_main, "load_settings", lambda: object())
    monkeypatch.setattr(foundry_main, "_handle", fake_handle)
    monkeypatch.setattr(foundry_main, "_tracer", _Tracer())
    context = _Context(
        _activity(
            activity_type="message",
            text=foundry_main.TEAMS_SAMPLE_REVIEW_COMMAND,
        )
    )

    await foundry_main._run_from_activity_message(
        context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        attachment_type=Attachment,
    )

    assert service.issued == [
        {
            "workflow_run_id": "run-teams-review",
            "checkpoint_id": "checkpoint-teams-review",
            "conversation_id": "teams-conversation",
            "user_id": "teams-user",
            "ttl_seconds": 86400,
        }
    ]
    assert handled[0]["protocol"] == foundry_main.HOSTED_WORKFLOW_PROTOCOL
    assert handled[0]["workflow_run_id"].startswith("run-teams-")
    assert handled[0]["application"]["applicant_name"] == "Synthetic Applicant"
    assert handled[0]["application"]["driving_history"] == "accident"
    sent = context.sent[0]
    assert sent.type == ActivityTypes.message
    assert sent.attachments[0].content_type == teams_cards.ADAPTIVE_CONTENT_TYPE
    assert "Private Applicant" not in json.dumps(sent.attachments[0].content)


def test_sample_review_command_is_idempotent_per_teams_activity() -> None:
    activity = _activity(
        activity_type="message",
        text=foundry_main.TEAMS_SAMPLE_REVIEW_COMMAND,
    )

    first = json.loads(
        foundry_main._activity_workflow_input(
            activity,
            foundry_main.TEAMS_SAMPLE_REVIEW_COMMAND,
        )
    )
    second = json.loads(
        foundry_main._activity_workflow_input(
            activity,
            foundry_main.TEAMS_SAMPLE_REVIEW_COMMAND,
        )
    )

    assert first == second
    assert first["workflow_run_id"] == "run-teams-766db1bd91924976ad1e"


def test_non_demo_activity_message_is_preserved() -> None:
    activity = _activity(activity_type="message", text="Explain underwriting")

    assert (
        foundry_main._activity_workflow_input(activity, "Explain underwriting")
        == "Explain underwriting"
    )


@pytest.mark.asyncio
async def test_only_standalone_decision_is_blocked_while_teams_review_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _Service(pending=True)
    handled: list[str] = []

    async def fake_handle(
        request: Any,
        _context: Any,
        text_response: Any,
        *,
        origin_channel: OriginChannel,
    ) -> Any:
        handled.append(request["input"])
        return text_response(
            None,
            None,
            text=json.dumps({"status": "REJECTED", "workflow_run_id": "run-ordinary"}),
        )

    monkeypatch.setattr(foundry_main, "LocalUnderwritingService", lambda _settings: service)
    monkeypatch.setattr(foundry_main, "load_settings", lambda: object())
    monkeypatch.setattr(foundry_main, "_handle", fake_handle)
    monkeypatch.setattr(foundry_main, "_tracer", _Tracer())

    decision_context = _Context(_activity(activity_type="message", text="Decline"))
    await foundry_main._run_from_activity_message(
        decision_context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        attachment_type=Attachment,
    )
    ordinary_context = _Context(
        _activity(activity_type="message", text="Please explain the review process")
    )
    await foundry_main._run_from_activity_message(
        ordinary_context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        attachment_type=Attachment,
    )

    assert decision_context.sent == ["Use the pending review card to submit a decision."]
    assert handled == ["Please explain the review process"]
    assert ordinary_context.sent == ["Underwriting request status: REJECTED."]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verb", "outcome", "title"),
    [
        (teams_cards.APPROVE_VERB, ReviewerOutcome.APPROVED, "Review approved"),
        (teams_cards.DECLINE_VERB, ReviewerOutcome.DECLINED, "Review declined"),
    ],
)
async def test_activity_action_decides_exact_review_and_updates_card(
    monkeypatch: pytest.MonkeyPatch,
    verb: str,
    outcome: ReviewerOutcome,
    title: str,
) -> None:
    service = _Service()
    monkeypatch.setattr(foundry_main, "LocalUnderwritingService", lambda _settings: service)
    monkeypatch.setattr(foundry_main, "load_settings", lambda: object())
    monkeypatch.setattr(foundry_main, "_tracer", _Tracer())
    context = _Context(
        _activity(
            activity_type="invoke",
            name=teams_cards.ADAPTIVE_ACTION_INVOKE,
            value={"action": {"verb": verb, "data": {"token": "opaque-token"}}},
        )
    )

    await foundry_main._run_from_activity_invoke(
        context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        invoke_response_type=InvokeResponse,
    )

    assert service.decisions == [
        {
            "workflow_run_id": "run-teams-review",
            "checkpoint_id": "checkpoint-teams-review",
            "outcome": outcome,
            "reviewer_id": "teams-user",
            "origin_channel": OriginChannel.TEAMS_ACTIVITY,
        }
    ]
    assert service.completed == ["batch-teams-review"]
    invoke = context.sent[0]
    assert invoke.type == ActivityTypes.invoke_response
    assert invoke.value.body["value"]["body"][0]["text"] == title


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("user_mismatch", 403),
        ("conversation_mismatch", 403),
        ("action_expired", 409),
        ("action_replayed", 409),
        ("action_superseded", 409),
        ("channel_mismatch", 403),
    ],
)
async def test_activity_action_returns_safe_bound_action_errors(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    status_code: int,
) -> None:
    service = _Service()
    service.claim_error = TeamsCardActionError(code, f"safe {code} status")
    monkeypatch.setattr(foundry_main, "LocalUnderwritingService", lambda _settings: service)
    monkeypatch.setattr(foundry_main, "load_settings", lambda: object())
    monkeypatch.setattr(foundry_main, "_tracer", _Tracer())
    context = _Context(
        _activity(
            activity_type="invoke",
            name=teams_cards.ADAPTIVE_ACTION_INVOKE,
            value={
                "action": {
                    "verb": teams_cards.APPROVE_VERB,
                    "data": {"token": "opaque-token"},
                }
            },
        )
    )

    await foundry_main._run_from_activity_invoke(
        context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        invoke_response_type=InvokeResponse,
    )

    body = context.sent[0].value.body
    assert body["statusCode"] == status_code
    assert body["value"]["code"] == code
    assert service.decisions == []


@pytest.mark.asyncio
async def test_activity_action_releases_after_failed_resume_and_reports_stale_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _Service()

    async def fail_decision(**kwargs: Any) -> list[Any]:
        service.decisions.append(kwargs)
        error = RuntimeError("private workflow failure")
        error.code = "stale_checkpoint"  # type: ignore[attr-defined]
        raise error

    service.decide_review = fail_decision  # type: ignore[method-assign]
    monkeypatch.setattr(foundry_main, "LocalUnderwritingService", lambda _settings: service)
    monkeypatch.setattr(foundry_main, "load_settings", lambda: object())
    monkeypatch.setattr(foundry_main, "_tracer", _Tracer())
    context = _Context(
        _activity(
            activity_type="invoke",
            name=teams_cards.ADAPTIVE_ACTION_INVOKE,
            value={
                "action": {
                    "verb": teams_cards.DECLINE_VERB,
                    "data": {"token": "opaque-token"},
                }
            },
        )
    )

    await foundry_main._run_from_activity_invoke(
        context,
        activity_type=Activity,
        activity_types=ActivityTypes,
        invoke_response_type=InvokeResponse,
    )

    assert service.released == ["batch-teams-review"]
    assert service.completed == []
    body = context.sent[0].value.body
    assert body["statusCode"] == 409
    assert body["value"] == {
        "code": "stale_checkpoint",
        "message": "The review checkpoint is stale.",
    }


def test_dual_host_and_declared_protocols_preserve_responses_and_activity() -> None:
    host = foundry_main.build_app()
    assert isinstance(host, ResponsesAgentServerHost)
    assert isinstance(host, ActivityAgentServerHost)

    azure_yaml = (Path(__file__).parents[2] / "infra" / "foundry-hosted" / "azure.yaml").read_text()
    assert "protocol: responses" in azure_yaml
    assert "protocol: activity" in azure_yaml
    assert "name: maf-underwriting-foundry-public" in azure_yaml
