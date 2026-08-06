from __future__ import annotations

import json

from app.modules.underwriting.models import Decision


def render_final_decision_prompt(
    decision: Decision, average_score: float, score_breakdown: dict[str, float]
) -> str:
    return (
        "Generate concise insurance underwriting rationale.\n"
        f"Decision: {decision.value}\n"
        f"Average score: {average_score:.3f}\n"
        f"Score breakdown: {json.dumps(score_breakdown, sort_keys=True)}"
    )
