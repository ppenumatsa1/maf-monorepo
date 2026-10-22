from __future__ import annotations

from typing import Any

ADAPTIVE_ACTION_INVOKE = "adaptiveCard/action"
ADAPTIVE_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
APPROVE_VERB = "order_resolution.approve"
REJECT_VERB = "order_resolution.reject"


def _display_action(value: Any) -> str:
    action = str(value or "").strip().replace("_", " ")
    return action.capitalize() if action else "Proposed resolution"


def build_pending_approval_card(
    *,
    action: Any,
    approve_token: str,
    reject_token: str,
) -> dict[str, Any]:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Human approval required",
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "Review the proposed resolution and choose an action.",
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": [
                    {
                        "title": "Proposed action",
                        "value": _display_action(action),
                    }
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Execute",
                "title": "Approve",
                "verb": APPROVE_VERB,
                "data": {"token": approve_token},
                "style": "positive",
            },
            {
                "type": "Action.Execute",
                "title": "Reject",
                "verb": REJECT_VERB,
                "data": {"token": reject_token},
                "style": "destructive",
            },
        ],
    }


def build_resolved_approval_card(*, status: str, message: str | None = None) -> dict[str, Any]:
    normalized = status.strip().lower()
    if normalized == "approved":
        title = "Approved"
        detail = message or "The workflow resumed with approval."
        color = "Good"
    elif normalized == "rejected":
        title = "Rejected"
        detail = message or "The request was rejected and escalated."
        color = "Attention"
    else:
        title = "Approval unavailable"
        detail = message or "This approval is no longer pending."
        color = "Warning"

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
                "color": color,
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": detail,
                "wrap": True,
            },
        ],
    }


def parse_approval_action(activity: Any) -> tuple[str, str] | None:
    value = getattr(activity, "value", None)
    if not isinstance(value, dict):
        dump = getattr(value, "model_dump", None)
        value = dump(by_alias=True) if callable(dump) else None
    if not isinstance(value, dict):
        return None

    action = value.get("action") or {}
    if not isinstance(action, dict):
        dump = getattr(action, "model_dump", None)
        action = dump(by_alias=True) if callable(dump) else {}

    verb = str(action.get("verb") or "").strip()
    data = action.get("data") or {}
    if not isinstance(data, dict):
        dump = getattr(data, "model_dump", None)
        data = dump(by_alias=True) if callable(dump) else {}
    token = str(data.get("token") or "").strip()
    if not token:
        return None
    if verb == APPROVE_VERB:
        return "approve", token
    if verb == REJECT_VERB:
        return "reject", token
    return None


def card_invoke_response(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "type": ADAPTIVE_CONTENT_TYPE,
        "value": card,
    }


def error_invoke_response(*, status_code: int, code: str, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "type": "application/vnd.microsoft.error",
        "value": {
            "code": code,
            "message": message,
        },
    }
