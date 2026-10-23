from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from app.infrastructure.db.engine import init_db
from app.infrastructure.db.tables import (
    maf_checkpoints,
    teams_card_actions,
    underwriting_approvals,
    workflow_runs,
)
from app.infrastructure.persistence.teams_card_action_repository import (
    TeamsCardActionError,
    TeamsCardActionRepository,
)
from app.infrastructure.persistence.workflow_run_repository import (
    MachineRecommendationConflictError,
    WorkflowRunRepository,
)
from app.modules.underwriting.models import OriginChannel, ReviewerOutcome
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.engine import Engine


def _create_pending_review(
    engine: Engine,
    *,
    origin_channel: OriginChannel = OriginChannel.TEAMS_ACTIVITY,
) -> tuple[str, str, WorkflowRunRepository]:
    run_id = f"run-{uuid4().hex}"
    checkpoint_id = f"checkpoint-{uuid4().hex}"
    repository = WorkflowRunRepository(engine)
    repository.create_workflow_run(
        run_id,
        "workflow",
        "underwriting-parent",
        f"application-{uuid4().hex}",
        "Synthetic Applicant",
        origin_channel=origin_channel,
    )
    repository.set_machine_recommendation(
        run_id,
        "REFER_TO_HUMAN_UNDERWRITER",
    )
    with engine.begin() as conn:
        conn.execute(
            maf_checkpoints.insert().values(
                workflow_run_id=run_id,
                workflow_id="workflow",
                checkpoint_id=checkpoint_id,
                checkpoint_json={},
                metadata_json={},
                created_at=datetime.utcnow(),
            )
        )
    repository.create_pending_approval(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
    )
    return run_id, checkpoint_id, repository


def test_machine_recommendation_is_immutable_and_reviewer_outcome_is_separate() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    run_id, checkpoint_id, repository = _create_pending_review(engine)

    repository.set_machine_recommendation(run_id, "REFER_TO_HUMAN_UNDERWRITER")
    with pytest.raises(MachineRecommendationConflictError, match="immutable"):
        repository.set_machine_recommendation(run_id, "APPROVED")

    assert repository.complete_approval(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
        outcome=ReviewerOutcome.APPROVED,
        reviewer_id="reviewer-object-id",
    )
    run = repository.get_workflow_run(run_id)
    assert run is not None
    assert run["machine_recommendation"] == "REFER_TO_HUMAN_UNDERWRITER"
    assert repository.get_pending_approval(checkpoint_id) is None
    with engine.begin() as conn:
        approval = (
            conn.execute(
                select(
                    underwriting_approvals.c.reviewer_outcome,
                    underwriting_approvals.c.reviewer_hash,
                    underwriting_approvals.c.reviewer_type,
                ).where(underwriting_approvals.c.checkpoint_id == checkpoint_id)
            )
            .mappings()
            .one()
        )
    assert approval["reviewer_outcome"] == "APPROVED"
    assert approval["reviewer_hash"] != "reviewer-object-id"
    assert approval["reviewer_type"] == "human"


def test_card_actions_bind_all_context_and_reject_replay() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    run_id, checkpoint_id, _ = _create_pending_review(engine)
    actions = TeamsCardActionRepository(engine)
    conversation_id = f"conversation-{uuid4()}"
    user_id = f"user-{uuid4()}"
    tokens = actions.issue_actions(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
        conversation_id=conversation_id,
        user_id=user_id,
        ttl_seconds=60,
    )
    assert actions.has_pending_action_for_conversation(conversation_id)

    with pytest.raises(TeamsCardActionError) as wrong_user:
        actions.claim_action(
            token=tokens[ReviewerOutcome.APPROVED],
            decision=ReviewerOutcome.APPROVED,
            conversation_id=conversation_id,
            user_id="different-user",
        )
    assert wrong_user.value.code == "user_mismatch"

    with pytest.raises(TeamsCardActionError) as wrong_conversation:
        actions.claim_action(
            token=tokens[ReviewerOutcome.APPROVED],
            decision=ReviewerOutcome.APPROVED,
            conversation_id="different-conversation",
            user_id=user_id,
        )
    assert wrong_conversation.value.code == "conversation_mismatch"

    with pytest.raises(TeamsCardActionError) as wrong_decision:
        actions.claim_action(
            token=tokens[ReviewerOutcome.APPROVED],
            decision=ReviewerOutcome.DECLINED,
            conversation_id=conversation_id,
            user_id=user_id,
        )
    assert wrong_decision.value.code == "decision_mismatch"

    claim = actions.claim_action(
        token=tokens[ReviewerOutcome.APPROVED],
        decision=ReviewerOutcome.APPROVED,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    assert claim.workflow_run_id == run_id
    assert claim.checkpoint_id == checkpoint_id
    assert actions.complete_action(claim.batch_id)
    assert not actions.has_pending_action_for_conversation(conversation_id)

    with pytest.raises(TeamsCardActionError) as replay:
        actions.claim_action(
            token=tokens[ReviewerOutcome.APPROVED],
            decision=ReviewerOutcome.APPROVED,
            conversation_id=conversation_id,
            user_id=user_id,
        )
    assert replay.value.code == "action_replayed"
    with pytest.raises(TeamsCardActionError) as superseded:
        actions.claim_action(
            token=tokens[ReviewerOutcome.DECLINED],
            decision=ReviewerOutcome.DECLINED,
            conversation_id=conversation_id,
            user_id=user_id,
        )
    assert superseded.value.code == "action_superseded"

    with engine.begin() as conn:
        rows = (
            conn.execute(
                select(
                    teams_card_actions.c.token_hash,
                    teams_card_actions.c.conversation_hash,
                    teams_card_actions.c.user_hash,
                    teams_card_actions.c.decision,
                    teams_card_actions.c.status,
                ).where(teams_card_actions.c.batch_id == claim.batch_id)
            )
            .mappings()
            .all()
        )
    assert all(token not in str(rows) for token in tokens.values())
    assert conversation_id not in str(rows)
    assert user_id not in str(rows)
    assert {row["decision"]: row["status"] for row in rows} == {
        "APPROVED": "completed",
        "DECLINED": "superseded",
    }


def test_expired_action_is_rejected_and_failed_claim_can_be_released() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    run_id, checkpoint_id, repository = _create_pending_review(engine)
    actions = TeamsCardActionRepository(engine)
    tokens = actions.issue_actions(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
        conversation_id="conversation",
        user_id="user",
        ttl_seconds=60,
    )
    with engine.begin() as conn:
        conn.execute(
            update(teams_card_actions)
            .where(
                teams_card_actions.c.workflow_run_id == run_id,
                teams_card_actions.c.decision == ReviewerOutcome.APPROVED.value,
            )
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )

    with pytest.raises(TeamsCardActionError) as expired:
        actions.claim_action(
            token=tokens[ReviewerOutcome.APPROVED],
            decision=ReviewerOutcome.APPROVED,
            conversation_id="conversation",
            user_id="user",
        )
    assert expired.value.code == "action_expired"

    claim = actions.claim_action(
        token=tokens[ReviewerOutcome.DECLINED],
        decision=ReviewerOutcome.DECLINED,
        conversation_id="conversation",
        user_id="user",
    )
    assert actions.release_action(claim.batch_id)
    with engine.begin() as conn:
        released_statuses = set(
            conn.execute(
                select(teams_card_actions.c.status).where(
                    teams_card_actions.c.batch_id == claim.batch_id
                )
            ).scalars()
        )
    assert released_statuses == {"released"}

    retry = actions.claim_action(
        token=tokens[ReviewerOutcome.DECLINED],
        decision=ReviewerOutcome.DECLINED,
        conversation_id="conversation",
        user_id="user",
    )
    assert repository.complete_approval(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
        outcome=ReviewerOutcome.DECLINED,
        reviewer_id="user",
    )
    assert actions.release_action(retry.batch_id) is False
    assert actions.complete_action(retry.batch_id)


def test_card_actions_require_teams_origin() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    run_id, checkpoint_id, _ = _create_pending_review(
        engine,
        origin_channel=OriginChannel.RESPONSES,
    )

    with pytest.raises(TeamsCardActionError) as mismatch:
        TeamsCardActionRepository(engine).issue_actions(
            workflow_run_id=run_id,
            checkpoint_id=checkpoint_id,
            conversation_id="conversation",
            user_id="user",
            ttl_seconds=60,
        )
    assert mismatch.value.code == "channel_mismatch"


@pytest.mark.skipif(
    not os.getenv("UNDERWRITING_TEST_POSTGRES_URL"),
    reason="UNDERWRITING_TEST_POSTGRES_URL is required for the real PostgreSQL race",
)
def test_postgres_competing_approve_decline_has_one_winner() -> None:
    engine = create_engine(
        os.environ["UNDERWRITING_TEST_POSTGRES_URL"],
        future=True,
        pool_size=2,
        max_overflow=0,
    )
    init_db(engine)
    run_id, checkpoint_id, _ = _create_pending_review(engine)
    actions = TeamsCardActionRepository(engine)
    tokens = actions.issue_actions(
        workflow_run_id=run_id,
        checkpoint_id=checkpoint_id,
        conversation_id="conversation",
        user_id="user",
        ttl_seconds=60,
    )
    barrier = Barrier(2)

    def claim(decision: ReviewerOutcome) -> tuple[str, object]:
        barrier.wait()
        try:
            return (
                "claimed",
                actions.claim_action(
                    token=tokens[decision],
                    decision=decision,
                    conversation_id="conversation",
                    user_id="user",
                ),
            )
        except TeamsCardActionError as exc:
            return ("error", exc.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    claim,
                    (ReviewerOutcome.APPROVED, ReviewerOutcome.DECLINED),
                )
            )
        assert len([value for status, value in results if status == "claimed"]) == 1
        assert [value for status, value in results if status == "error"] == ["action_superseded"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                delete(teams_card_actions).where(teams_card_actions.c.workflow_run_id == run_id)
            )
            conn.execute(
                delete(underwriting_approvals).where(
                    underwriting_approvals.c.workflow_run_id == run_id
                )
            )
            conn.execute(delete(maf_checkpoints).where(maf_checkpoints.c.workflow_run_id == run_id))
            conn.execute(delete(workflow_runs).where(workflow_runs.c.id == run_id))
        engine.dispose()
