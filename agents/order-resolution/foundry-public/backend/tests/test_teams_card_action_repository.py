from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from app.core.database import postgres_db
from app.infrastructure.persistence.checkpoint_store import CheckpointStore
from app.infrastructure.persistence.teams_card_action_repository import (
    TeamsCardActionError,
    TeamsCardActionRepository,
)
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


def _pending_approval(*, thread_id: str, origin_channel: str) -> tuple[str, str]:
    workflow_repository = WorkflowRunRepository()
    checkpoint_store = CheckpointStore()
    workflow_repository.create_workflow_run(
        thread_id=thread_id,
        input_text="synthetic card action test",
        session_id=thread_id,
        customer_id="synthetic",
        origin_channel=origin_channel,
    )
    checkpoint = checkpoint_store.create(
        thread_id,
        {
            "run_id": thread_id,
            "order_id": "synthetic-order",
            "action": "synthetic-action",
        },
    )
    checkpoint_id = checkpoint["checkpoint_id"]
    workflow_repository.add_pending_approval(
        thread_id,
        {
            "checkpoint_id": checkpoint_id,
            "action": "synthetic-action",
            "question": "Approve the proposed action?",
        },
    )
    return thread_id, checkpoint_id


def _delete_run(thread_id: str) -> None:
    with postgres_db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM workflow_runs WHERE thread_id = %s", (thread_id,))


def test_card_action_tokens_bind_channel_user_conversation_and_reject_replay() -> None:
    thread_id = f"teams-card-{uuid4()}"
    user_id = f"user-{uuid4()}"
    conversation_id = f"conversation-{uuid4()}"
    action_repository = TeamsCardActionRepository()

    try:
        _, checkpoint_id = _pending_approval(
            thread_id=thread_id,
            origin_channel="teams_activity",
        )
        tokens = action_repository.issue_actions(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ttl_seconds=60,
        )

        with pytest.raises(TeamsCardActionError, match="different user") as wrong_user:
            action_repository.claim_action(
                token=tokens["approve"],
                decision="approve",
                conversation_id=conversation_id,
                user_id="different-user",
            )
        assert wrong_user.value.code == "user_mismatch"

        action = action_repository.claim_action(
            token=tokens["approve"],
            decision="approve",
            conversation_id=conversation_id,
            user_id=user_id,
        )
        assert action.thread_id == thread_id
        assert action.checkpoint_id == checkpoint_id
        assert action.decision == "approve"

        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT token_hash, conversation_hash, user_hash, decision, status
                    FROM teams_card_actions
                    WHERE checkpoint_id = %s::uuid
                    ORDER BY decision
                    """,
                    (checkpoint_id,),
                )
                rows = cur.fetchall()
        assert len(rows) == 2
        assert all(tokens["approve"] not in row.values() for row in rows)
        assert all(conversation_id not in row.values() for row in rows)
        assert all(user_id not in row.values() for row in rows)
        assert {row["decision"]: row["status"] for row in rows} == {
            "approve": "processing",
            "reject": "superseded",
        }

        action_repository.complete_action(action.batch_id)
        with pytest.raises(TeamsCardActionError, match="already used") as replay:
            action_repository.claim_action(
                token=tokens["approve"],
                decision="approve",
                conversation_id=conversation_id,
                user_id=user_id,
            )
        assert replay.value.code == "action_already_used"
    finally:
        _delete_run(thread_id)


def test_card_actions_cannot_be_issued_for_api_workflow() -> None:
    thread_id = f"api-card-{uuid4()}"
    action_repository = TeamsCardActionRepository()

    try:
        _, checkpoint_id = _pending_approval(
            thread_id=thread_id,
            origin_channel="api",
        )

        with pytest.raises(TeamsCardActionError, match="not authorized") as mismatch:
            action_repository.issue_actions(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                conversation_id="conversation",
                user_id="user",
                ttl_seconds=60,
            )
        assert mismatch.value.code == "channel_mismatch"
    finally:
        _delete_run(thread_id)


def test_release_restores_siblings_only_while_approval_is_pending() -> None:
    thread_id = f"teams-card-release-{uuid4()}"
    action_repository = TeamsCardActionRepository()

    try:
        _, checkpoint_id = _pending_approval(
            thread_id=thread_id,
            origin_channel="teams_activity",
        )
        tokens = action_repository.issue_actions(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            conversation_id="conversation",
            user_id="user",
            ttl_seconds=60,
        )
        action = action_repository.claim_action(
            token=tokens["reject"],
            decision="reject",
            conversation_id="conversation",
            user_id="user",
        )

        action_repository.release_action(action.batch_id)
        retry = action_repository.claim_action(
            token=tokens["approve"],
            decision="approve",
            conversation_id="conversation",
            user_id="user",
        )
        action_repository.complete_action(retry.batch_id)
        WorkflowRunRepository().resolve_approval(
            thread_id,
            checkpoint_id,
            "approve",
            None,
            "synthetic-reviewer",
        )

        action_repository.release_action(retry.batch_id)
        with pytest.raises(TeamsCardActionError, match="already used"):
            action_repository.claim_action(
                token=tokens["reject"],
                decision="reject",
                conversation_id="conversation",
                user_id="user",
            )
    finally:
        _delete_run(thread_id)


def test_competing_card_actions_allow_only_one_atomic_claim() -> None:
    thread_id = f"teams-card-race-{uuid4()}"
    user_id = f"user-{uuid4()}"
    conversation_id = f"conversation-{uuid4()}"
    action_repository = TeamsCardActionRepository()

    try:
        _, checkpoint_id = _pending_approval(
            thread_id=thread_id,
            origin_channel="teams_activity",
        )
        tokens = action_repository.issue_actions(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ttl_seconds=60,
        )
        barrier = Barrier(2)

        def claim(decision: str) -> tuple[str, object]:
            barrier.wait()
            try:
                return (
                    "claimed",
                    action_repository.claim_action(
                        token=tokens[decision],
                        decision=decision,
                        conversation_id=conversation_id,
                        user_id=user_id,
                    ),
                )
            except TeamsCardActionError as exc:
                return ("error", exc.code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, ("approve", "reject")))

        claimed = [value for status, value in results if status == "claimed"]
        errors = [value for status, value in results if status == "error"]
        assert len(claimed) == 1
        assert errors == ["action_already_used"]
        action_repository.complete_action(claimed[0].batch_id)
    finally:
        _delete_run(thread_id)
