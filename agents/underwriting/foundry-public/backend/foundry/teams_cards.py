from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.underwriting.models import ReviewerOutcome

ADAPTIVE_ACTION_INVOKE = "adaptiveCard/action"
ADAPTIVE_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
APPROVE_VERB = "underwriting.approve"
DECLINE_VERB = "underwriting.decline"

_BAND_LABELS = {
    "risk": "Risk",
    "credit": "Credit",
    "medical": "Medical",
    "driving": "Driving",
}


def risk_band(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "Unavailable"
    if value >= 0.75:
        return "Low"
    if value >= 0.45:
        return "Moderate"
    return "High"


def safe_review_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    outputs = payload.get("outputs")
    output = outputs[0] if isinstance(outputs, list) and outputs else {}
    if not isinstance(output, Mapping):
        output = {}

    score_breakdown = output.get("score_breakdown")
    if not isinstance(score_breakdown, Mapping):
        score_breakdown = {}
    bands = {label: risk_band(score_breakdown.get(key)) for key, label in _BAND_LABELS.items()}
    reasons = [f"{label} category" for label, band in bands.items() if band in {"Moderate", "High"}]
    if not reasons:
        reasons = ["Overall policy threshold"]

    return {
        "application_id": str(output.get("application_id") or "Unavailable"),
        "machine_recommendation": str(
            payload.get("machine_recommendation")
            or output.get("machine_recommendation")
            or output.get("decision")
            or "REFER_TO_HUMAN_UNDERWRITER"
        ),
        "risk_bands": bands,
        "reason_categories": reasons,
    }


def build_pending_review_card(
    *,
    application_id: str,
    machine_recommendation: str,
    risk_bands: Mapping[str, str],
    reason_categories: Sequence[str],
    approve_token: str,
    decline_token: str,
) -> dict[str, Any]:
    facts = [
        {"title": "Application ID", "value": application_id},
        {"title": "Machine recommendation", "value": machine_recommendation},
    ]
    facts.extend({"title": f"{label} risk", "value": band} for label, band in risk_bands.items())
    facts.append(
        {
            "title": "Reason categories",
            "value": ", ".join(reason_categories) or "Overall policy threshold",
        }
    )
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Underwriting review required",
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "Review the categorical assessment and record a decision.",
                "wrap": True,
            },
            {"type": "FactSet", "facts": facts},
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
                "title": "Decline",
                "verb": DECLINE_VERB,
                "data": {"token": decline_token},
                "style": "destructive",
            },
        ],
    }


def build_resolved_review_card(*, outcome: ReviewerOutcome) -> dict[str, Any]:
    approved = outcome == ReviewerOutcome.APPROVED
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Review approved" if approved else "Review declined",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Good" if approved else "Attention",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "The bound underwriting review was recorded successfully.",
                "wrap": True,
            },
        ],
    }


def parse_review_action(activity: Any) -> tuple[ReviewerOutcome, str] | None:
    value = getattr(activity, "value", None)
    if not isinstance(value, dict):
        dump = getattr(value, "model_dump", None)
        value = dump(by_alias=True) if callable(dump) else None
    if not isinstance(value, dict):
        return None

    action = value.get("action")
    if not isinstance(action, dict):
        dump = getattr(action, "model_dump", None)
        action = dump(by_alias=True) if callable(dump) else None
    if not isinstance(action, dict):
        return None

    data = action.get("data")
    if not isinstance(data, dict):
        dump = getattr(data, "model_dump", None)
        data = dump(by_alias=True) if callable(dump) else None
    if not isinstance(data, dict):
        return None

    token = str(data.get("token") or "").strip()
    verb = str(action.get("verb") or "").strip()
    if not token:
        return None
    if verb == APPROVE_VERB:
        return ReviewerOutcome.APPROVED, token
    if verb == DECLINE_VERB:
        return ReviewerOutcome.DECLINED, token
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
        "value": {"code": code, "message": message},
    }
