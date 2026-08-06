from __future__ import annotations

from app.maf.prompts.final_decision_prompt import render_final_decision_prompt
from app.modules.underwriting.models import Decision


def build_final_decision_context(
    decision: Decision, average_score: float, score_breakdown: dict[str, float]
) -> str:
    return render_final_decision_prompt(
        decision=decision,
        average_score=average_score,
        score_breakdown=score_breakdown,
    )
