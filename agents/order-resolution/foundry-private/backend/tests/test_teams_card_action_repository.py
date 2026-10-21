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


def test_card_action_tokens_bind_user_conversation_and_reject_replay() -> None:
    thread_id = f"teams-card-{uuid4()}"
    user_id = f"user-{uuid4()}"
    conversation_id = f"conversation-{uuid4()}"
    workflow_repository = WorkflowRunRepository()
    checkpoint_store = CheckpointStore()
    action_repository = TeamsCardActionRepository()

    try:
        workflow_repository.create_workflow_run(
            thread_id=thread_id,
            input_text="synthetic card action test",
            session_id=thread_id,
            customer_id="synthetic",
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
        assert action.batch_id

        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT token_hash, conversation_hash, user_hash
                    FROM teams_card_actions
                    WHERE checkpoint_id = %s::uuid
                    ORDER BY decision
                    """,
                    (checkpoint_id,),
                )
                rows = cur.fetchall()
        assert len(rows) == 2
        assert all(tokens["approve"] not in row for row in rows)
        assert all(conversation_id not in row for row in rows)
        assert all(user_id not in row for row in rows)

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
        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM workflow_runs WHERE thread_id = %s",
                    (thread_id,),
                )


def test_competing_card_actions_allow_only_one_atomic_claim() -> None:
    thread_id = f"teams-card-race-{uuid4()}"
    user_id = f"user-{uuid4()}"
    conversation_id = f"conversation-{uuid4()}"
    workflow_repository = WorkflowRunRepository()
    checkpoint_store = CheckpointStore()
    action_repository = TeamsCardActionRepository()

    try:
        workflow_repository.create_workflow_run(
            thread_id=thread_id,
            input_text="synthetic concurrent card action test",
            session_id=thread_id,
            customer_id="synthetic",
            origin_channel="teams_activity",
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
        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM workflow_runs WHERE thread_id = %s",
                    (thread_id,),
                )
