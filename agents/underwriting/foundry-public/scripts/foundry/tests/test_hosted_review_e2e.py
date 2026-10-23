from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "foundry"
sys.path.insert(0, str(SCRIPTS))

import hosted_review_e2e as review_e2e  # noqa: E402


def review(
    outcome: str,
    *,
    run_id: str,
    reviewer_type: str = "human",
    card_action_count: int = 2,
    completed_action_count: int = 1,
) -> review_e2e.NativeTeamsReview:
    return review_e2e.NativeTeamsReview(
        workflow_run_id=run_id,
        reviewer_outcome=outcome,
        reviewer_type=reviewer_type,
        conversation_hash="a" * 64,
        card_action_count=card_action_count,
        completed_action_count=completed_action_count,
        review_resolved_events=1,
        workflow_completed_events=1,
    )


def test_select_acceptance_requires_human_approved_and_declined_reviews() -> None:
    accepted = review_e2e.select_acceptance(
        [
            review("APPROVED", run_id="run-teams-approved"),
            review("DECLINED", run_id="run-teams-declined"),
        ]
    )

    assert accepted is not None
    assert accepted["APPROVED"].workflow_run_id == "run-teams-approved"
    assert accepted["DECLINED"].workflow_run_id == "run-teams-declined"


def test_select_acceptance_rejects_incomplete_or_nonhuman_reviews() -> None:
    assert (
        review_e2e.select_acceptance(
            [
                review(
                    "APPROVED",
                    run_id="run-teams-approved",
                    reviewer_type="administrative",
                ),
                review(
                    "DECLINED",
                    run_id="run-teams-declined",
                    completed_action_count=0,
                ),
            ]
        )
        is None
    )


def test_native_teams_evidence_contains_only_hashed_channel_binding() -> None:
    accepted = {
        "APPROVED": review("APPROVED", run_id="run-teams-approved"),
        "DECLINED": review("DECLINED", run_id="run-teams-declined"),
    }

    payload = review_e2e.build_evidence(
        accepted,
        release_id="release-001",
        release_started_at=datetime(2026, 8, 5, tzinfo=UTC),
        observation_started_at=datetime(2026, 8, 5, 0, 1, tzinfo=UTC),
    )

    assert payload["status"] == "passed"
    assert payload["observation_started_at"] == "2026-08-05T00:01:00Z"
    assert payload["workflow_run_ids"] == [
        "run-teams-approved",
        "run-teams-declined",
    ]
    assert payload["conversation_hashes"] == ["a" * 64]
    scenarios = {item["name"]: item for item in payload["scenarios"]}
    assert scenarios["teams_activity_card_delivery"]["card_action_count"] == 2
    assert scenarios["teams_approved"]["reviewer_outcome"] == "APPROVED"
    assert scenarios["teams_declined"]["reviewer_outcome"] == "DECLINED"
    serialized = json.dumps(payload)
    for private_value in (
        "applicant_name",
        "health_disclosures",
        "credit_score",
        "requested_coverage",
        "conversation_id",
        "user_id",
    ):
        assert private_value not in serialized
