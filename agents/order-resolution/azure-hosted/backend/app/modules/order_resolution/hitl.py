from __future__ import annotations

import re


def extract_order_id(message: str) -> str:
    match = re.search(r"\bord[-\s]?(\d+)\b", message, re.IGNORECASE)
    return f"ord-{match.group(1)}" if match else "ord-1001"


def classify_issue(message: str) -> str:
    if "damage" in message or "broken" in message:
        return "damaged_item"
    if "wrong" in message:
        return "wrong_item"
    return "late_delivery"


def resolve_action(issue_type: str) -> str:
    if issue_type == "damaged_item":
        return "offer_replacement_or_full_refund"
    return "issue_partial_refund"


def requires_hitl(issue_type: str, amount: float, policy: str) -> bool:
    return amount >= 100 or "manual_review" in policy or issue_type == "damaged_item"
