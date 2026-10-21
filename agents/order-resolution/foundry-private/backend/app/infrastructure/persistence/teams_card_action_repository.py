from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.database import postgres_db
from psycopg.rows import dict_row


class TeamsCardActionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TeamsCardAction:
    checkpoint_id: str
    thread_id: str
    decision: str
    batch_id: str


class TeamsCardActionRepository:
    def __init__(self) -> None:
        postgres_db.ensure_schema()
        self._pool = postgres_db.get_pool()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def issue_actions(
        self,
        *,
        thread_id: str,
        checkpoint_id: str,
        conversation_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> dict[str, str]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        conversation_hash = self._hash(conversation_id)
        user_hash = self._hash(user_id)
        batch_id = uuid4()
        tokens = {
            "approve": secrets.token_urlsafe(32),
            "reject": secrets.token_urlsafe(32),
        }

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT approval_id
                    FROM approvals
                    WHERE thread_id = %s
                      AND checkpoint_id = %s::uuid
                      AND status = 'pending'
                    FOR UPDATE
                    """,
                    (thread_id, checkpoint_id),
                )
                if cur.fetchone() is None:
                    raise TeamsCardActionError(
                        "approval_not_pending",
                        "The approval is no longer pending.",
                    )

                cur.execute(
                    """
                    UPDATE teams_card_actions
                    SET status = 'superseded', updated_at = NOW()
                    WHERE checkpoint_id = %s::uuid
                      AND status = 'pending'
                    """,
                    (checkpoint_id,),
                )
                for decision, token in tokens.items():
                    cur.execute(
                        """
                        INSERT INTO teams_card_actions (
                            token_hash, batch_id, thread_id, checkpoint_id, decision,
                            conversation_hash, user_hash, status, expires_at,
                            created_at, updated_at
                        ) VALUES (
                            %s, %s::uuid, %s, %s::uuid, %s,
                            %s, %s, 'pending', %s,
                            NOW(), NOW()
                        )
                        """,
                        (
                            self._hash(token),
                            str(batch_id),
                            thread_id,
                            checkpoint_id,
                            decision,
                            conversation_hash,
                            user_hash,
                            expires_at,
                        ),
                    )
        return tokens

    def claim_action(
        self,
        *,
        token: str,
        decision: str,
        conversation_id: str,
        user_id: str,
    ) -> TeamsCardAction:
        token_hash = self._hash(token)
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT action.thread_id, action.checkpoint_id, action.decision,
                           action.batch_id,
                           action.conversation_hash, action.user_hash,
                           action.status, action.expires_at,
                           approval.status AS approval_status
                    FROM teams_card_actions AS action
                    INNER JOIN approvals AS approval
                        ON approval.thread_id = action.thread_id
                       AND approval.checkpoint_id = action.checkpoint_id
                    WHERE action.token_hash = %s
                    ORDER BY approval.requested_at DESC
                    LIMIT 1
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()

        if row is None:
            raise TeamsCardActionError("invalid_token", "The approval action is invalid.")
        if row["status"] != "pending":
            raise TeamsCardActionError(
                "action_already_used",
                "This approval action was already used or replaced.",
            )
        expires_at = row["expires_at"]
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise TeamsCardActionError("action_expired", "This approval action has expired.")
        if row["approval_status"] != "pending":
            raise TeamsCardActionError(
                "approval_not_pending",
                "The approval is no longer pending.",
            )
        if row["decision"] != decision:
            raise TeamsCardActionError("decision_mismatch", "The approval action is invalid.")
        if not hmac.compare_digest(
            str(row["conversation_hash"]),
            self._hash(conversation_id),
        ):
            raise TeamsCardActionError(
                "conversation_mismatch",
                "This approval belongs to a different conversation.",
            )
        if not hmac.compare_digest(str(row["user_hash"]), self._hash(user_id)):
            raise TeamsCardActionError(
                "user_mismatch",
                "This approval belongs to a different user.",
            )

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    WITH eligible AS (
                        SELECT action.checkpoint_id, action.batch_id
                        FROM teams_card_actions AS action
                        INNER JOIN approvals AS approval
                            ON approval.thread_id = action.thread_id
                           AND approval.checkpoint_id = action.checkpoint_id
                        WHERE action.token_hash = %s
                          AND action.status = 'pending'
                          AND action.expires_at > NOW()
                          AND action.decision = %s
                          AND action.conversation_hash = %s
                          AND action.user_hash = %s
                          AND approval.status = 'pending'
                        ORDER BY approval.requested_at DESC
                        LIMIT 1
                    ),
                    claimed AS (
                        UPDATE teams_card_actions AS action
                        SET status = CASE
                                WHEN action.token_hash = %s THEN 'processing'
                                ELSE 'superseded'
                            END,
                            updated_at = NOW()
                        FROM eligible
                        WHERE action.checkpoint_id = eligible.checkpoint_id
                          AND action.batch_id = eligible.batch_id
                          AND action.status = 'pending'
                        RETURNING action.token_hash, action.checkpoint_id,
                                  action.thread_id, action.decision,
                                  action.batch_id, action.status
                    )
                    SELECT checkpoint_id, thread_id, decision, batch_id
                    FROM claimed
                    WHERE token_hash = %s
                      AND status = 'processing'
                    """,
                    (
                        token_hash,
                        decision,
                        self._hash(conversation_id),
                        self._hash(user_id),
                        token_hash,
                        token_hash,
                    ),
                )
                claimed = cur.fetchone()
        if claimed is None:
            raise TeamsCardActionError(
                "action_already_used",
                "This approval action was already used or replaced.",
            )
        return TeamsCardAction(
            checkpoint_id=str(claimed["checkpoint_id"]),
            thread_id=str(claimed["thread_id"]),
            decision=str(claimed["decision"]),
            batch_id=str(claimed["batch_id"]),
        )

    def complete_action(self, batch_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE teams_card_actions
                    SET status = 'consumed', consumed_at = NOW(), updated_at = NOW()
                    WHERE batch_id = %s::uuid
                      AND status = 'processing'
                    """,
                    (batch_id,),
                )

    def release_action(self, batch_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE teams_card_actions AS action
                    SET status = 'pending', updated_at = NOW()
                    FROM approvals AS approval
                    WHERE action.batch_id = %s::uuid
                      AND action.status IN ('processing', 'superseded')
                      AND approval.thread_id = action.thread_id
                      AND approval.checkpoint_id = action.checkpoint_id
                      AND approval.status = 'pending'
                    """,
                    (batch_id,),
                )
