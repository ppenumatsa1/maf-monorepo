from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, insert, select, update
from sqlalchemy.engine import Engine

from app.infrastructure.db.tables import (
    teams_card_actions,
    underwriting_approvals,
    workflow_runs,
)
from app.modules.underwriting.models import (
    ApprovalStatus,
    CardActionClaim,
    CardActionStatus,
    OriginChannel,
    ReviewerOutcome,
)


class TeamsCardActionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TeamsCardActionRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def issue_actions(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        conversation_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> dict[ReviewerOutcome, str]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if not conversation_id or not user_id:
            raise ValueError("conversation_id and user_id are required")

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        batch_id = str(uuid4())
        tokens = {
            ReviewerOutcome.APPROVED: secrets.token_urlsafe(32),
            ReviewerOutcome.DECLINED: secrets.token_urlsafe(32),
        }

        with self.engine.begin() as conn:
            approval = (
                conn.execute(
                    select(
                        underwriting_approvals.c.status,
                        workflow_runs.c.origin_channel,
                    )
                    .select_from(
                        underwriting_approvals.join(
                            workflow_runs,
                            workflow_runs.c.id == underwriting_approvals.c.workflow_run_id,
                        )
                    )
                    .where(
                        underwriting_approvals.c.workflow_run_id == workflow_run_id,
                        underwriting_approvals.c.checkpoint_id == checkpoint_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if approval is None or approval["status"] != ApprovalStatus.PENDING.value:
                raise TeamsCardActionError(
                    "approval_not_pending",
                    "The underwriting review is no longer pending.",
                )
            if approval["origin_channel"] != OriginChannel.TEAMS_ACTIVITY.value:
                raise TeamsCardActionError(
                    "channel_mismatch",
                    "This review is not authorized for Teams card actions.",
                )

            processing = conn.execute(
                select(teams_card_actions.c.token_hash).where(
                    teams_card_actions.c.workflow_run_id == workflow_run_id,
                    teams_card_actions.c.checkpoint_id == checkpoint_id,
                    teams_card_actions.c.status == CardActionStatus.PROCESSING.value,
                )
            ).first()
            if processing is not None:
                raise TeamsCardActionError(
                    "action_in_progress",
                    "An underwriting review action is already processing.",
                )

            conn.execute(
                update(teams_card_actions)
                .where(
                    teams_card_actions.c.workflow_run_id == workflow_run_id,
                    teams_card_actions.c.checkpoint_id == checkpoint_id,
                    teams_card_actions.c.status.in_(
                        (
                            CardActionStatus.PENDING.value,
                            CardActionStatus.PROCESSING.value,
                            CardActionStatus.RELEASED.value,
                            CardActionStatus.SUPERSEDED.value,
                        )
                    ),
                )
                .values(status=CardActionStatus.SUPERSEDED.value, updated_at=now)
            )
            for decision, token in tokens.items():
                conn.execute(
                    insert(teams_card_actions).values(
                        token_hash=_hash(token),
                        batch_id=batch_id,
                        workflow_run_id=workflow_run_id,
                        checkpoint_id=checkpoint_id,
                        decision=decision.value,
                        conversation_hash=_hash(conversation_id),
                        user_hash=_hash(user_id),
                        status=CardActionStatus.PENDING.value,
                        expires_at=expires_at,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return tokens

    def has_pending_action_for_conversation(self, conversation_id: str) -> bool:
        conversation_hash = _hash(conversation_id)
        with self.engine.begin() as conn:
            action = conn.execute(
                select(teams_card_actions.c.token_hash)
                .select_from(
                    teams_card_actions.join(
                        underwriting_approvals,
                        and_(
                            underwriting_approvals.c.workflow_run_id
                            == teams_card_actions.c.workflow_run_id,
                            underwriting_approvals.c.checkpoint_id
                            == teams_card_actions.c.checkpoint_id,
                        ),
                    ).join(
                        workflow_runs,
                        workflow_runs.c.id == teams_card_actions.c.workflow_run_id,
                    )
                )
                .where(
                    teams_card_actions.c.conversation_hash == conversation_hash,
                    teams_card_actions.c.status.in_(
                        (
                            CardActionStatus.PENDING.value,
                            CardActionStatus.RELEASED.value,
                        )
                    ),
                    underwriting_approvals.c.status == ApprovalStatus.PENDING.value,
                    workflow_runs.c.origin_channel == OriginChannel.TEAMS_ACTIVITY.value,
                )
                .limit(1)
            ).first()
        return action is not None

    def claim_action(
        self,
        *,
        token: str,
        decision: ReviewerOutcome,
        conversation_id: str,
        user_id: str,
    ) -> CardActionClaim:
        token_hash = _hash(token)
        conversation_hash = _hash(conversation_id)
        user_hash = _hash(user_id)
        now = datetime.now(UTC)

        with self.engine.begin() as conn:
            identity = (
                conn.execute(
                    select(
                        teams_card_actions.c.workflow_run_id,
                        teams_card_actions.c.checkpoint_id,
                    ).where(teams_card_actions.c.token_hash == token_hash)
                )
                .mappings()
                .first()
            )
            if identity is None:
                raise TeamsCardActionError(
                    "invalid_token",
                    "The underwriting review action is invalid.",
                )

            approval = (
                conn.execute(
                    select(
                        underwriting_approvals.c.status.label("approval_status"),
                        workflow_runs.c.origin_channel,
                    )
                    .select_from(
                        underwriting_approvals.join(
                            workflow_runs,
                            workflow_runs.c.id == underwriting_approvals.c.workflow_run_id,
                        )
                    )
                    .where(
                        underwriting_approvals.c.workflow_run_id == identity["workflow_run_id"],
                        underwriting_approvals.c.checkpoint_id == identity["checkpoint_id"],
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if approval is None:
                raise TeamsCardActionError(
                    "approval_not_pending",
                    "The underwriting review is no longer pending.",
                )

            action = (
                conn.execute(
                    select(
                        teams_card_actions.c.workflow_run_id,
                        teams_card_actions.c.checkpoint_id,
                        teams_card_actions.c.decision,
                        teams_card_actions.c.batch_id,
                        teams_card_actions.c.conversation_hash,
                        teams_card_actions.c.user_hash,
                        teams_card_actions.c.status,
                        teams_card_actions.c.expires_at,
                    ).where(teams_card_actions.c.token_hash == token_hash)
                )
                .mappings()
                .first()
            )

            if approval["origin_channel"] != OriginChannel.TEAMS_ACTIVITY.value:
                raise TeamsCardActionError(
                    "channel_mismatch",
                    "This review is not authorized for Teams card actions.",
                )
            action_status = CardActionStatus(str(action["status"]))
            if action_status == CardActionStatus.COMPLETED:
                raise TeamsCardActionError(
                    "action_replayed",
                    "This underwriting review action was already completed.",
                )
            if action_status == CardActionStatus.SUPERSEDED:
                raise TeamsCardActionError(
                    "action_superseded",
                    "This underwriting review action was replaced by another action.",
                )
            if action_status == CardActionStatus.PROCESSING:
                raise TeamsCardActionError(
                    "action_in_progress",
                    "This underwriting review action is already processing.",
                )
            if _as_utc(action["expires_at"]) <= now:
                raise TeamsCardActionError(
                    "action_expired",
                    "This underwriting review action has expired.",
                )
            if approval["approval_status"] != ApprovalStatus.PENDING.value:
                raise TeamsCardActionError(
                    "approval_not_pending",
                    "The underwriting review is no longer pending.",
                )
            if action["decision"] != decision.value:
                raise TeamsCardActionError(
                    "decision_mismatch",
                    "The underwriting review action is invalid.",
                )
            if not hmac.compare_digest(str(action["conversation_hash"]), conversation_hash):
                raise TeamsCardActionError(
                    "conversation_mismatch",
                    "This underwriting review belongs to a different conversation.",
                )
            if not hmac.compare_digest(str(action["user_hash"]), user_hash):
                raise TeamsCardActionError(
                    "user_mismatch",
                    "This underwriting review belongs to a different user.",
                )

            result = conn.execute(
                update(teams_card_actions)
                .where(
                    teams_card_actions.c.batch_id == action["batch_id"],
                    teams_card_actions.c.status.in_(
                        (
                            CardActionStatus.PENDING.value,
                            CardActionStatus.RELEASED.value,
                        )
                    ),
                )
                .values(
                    status=CardActionStatus.SUPERSEDED.value,
                    updated_at=now,
                )
            )
            if result.rowcount < 1:
                raise TeamsCardActionError(
                    "action_superseded",
                    "This underwriting review action was replaced by another action.",
                )
            claimed = conn.execute(
                update(teams_card_actions)
                .where(
                    teams_card_actions.c.token_hash == token_hash,
                    teams_card_actions.c.batch_id == action["batch_id"],
                    teams_card_actions.c.status == CardActionStatus.SUPERSEDED.value,
                )
                .values(
                    status=CardActionStatus.PROCESSING.value,
                    updated_at=now,
                )
            )
            if claimed.rowcount != 1:
                raise TeamsCardActionError(
                    "action_in_progress",
                    "This underwriting review action is already processing.",
                )

        return CardActionClaim(
            workflow_run_id=str(action["workflow_run_id"]),
            checkpoint_id=str(action["checkpoint_id"]),
            decision=decision,
            batch_id=str(action["batch_id"]),
        )

    def complete_action(self, batch_id: str) -> bool:
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            result = conn.execute(
                update(teams_card_actions)
                .where(
                    teams_card_actions.c.batch_id == batch_id,
                    teams_card_actions.c.status == CardActionStatus.PROCESSING.value,
                )
                .values(
                    status=CardActionStatus.COMPLETED.value,
                    completed_at=now,
                    updated_at=now,
                )
            )
        return result.rowcount == 1

    def release_action(self, batch_id: str) -> bool:
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            approval_pending = conn.execute(
                select(underwriting_approvals.c.approval_id)
                .select_from(
                    underwriting_approvals.join(
                        teams_card_actions,
                        and_(
                            underwriting_approvals.c.workflow_run_id
                            == teams_card_actions.c.workflow_run_id,
                            underwriting_approvals.c.checkpoint_id
                            == teams_card_actions.c.checkpoint_id,
                        ),
                    )
                )
                .where(
                    teams_card_actions.c.batch_id == batch_id,
                    underwriting_approvals.c.status == ApprovalStatus.PENDING.value,
                )
                .limit(1)
                .with_for_update()
            ).first()
            if approval_pending is None:
                return False
            result = conn.execute(
                update(teams_card_actions)
                .where(
                    teams_card_actions.c.batch_id == batch_id,
                    teams_card_actions.c.status.in_(
                        (
                            CardActionStatus.PROCESSING.value,
                            CardActionStatus.SUPERSEDED.value,
                        )
                    ),
                )
                .values(
                    status=CardActionStatus.RELEASED.value,
                    updated_at=now,
                )
            )
        return result.rowcount > 0
