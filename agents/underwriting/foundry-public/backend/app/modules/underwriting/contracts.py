from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.modules.underwriting.models import Decision, HumanReviewDecision


class DecisionLLMClient(Protocol):
    async def generate_rationale(
        self,
        *,
        decision: Decision,
        average_score: float,
        score_breakdown: Mapping[str, float],
    ) -> str: ...


class ReviewDecisionAuthorizer(Protocol):
    def authorize(self, decision: HumanReviewDecision) -> str: ...
