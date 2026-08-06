from __future__ import annotations

import logging
from datetime import datetime

from agent_framework._workflows._checkpoint import CheckpointStorage, WorkflowCheckpoint
from agent_framework._workflows._checkpoint_encoding import (
    decode_checkpoint_value,
    encode_checkpoint_value,
)
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine

from app.core.telemetry import workflow_stage_span
from app.infrastructure.db.tables import maf_checkpoints
from app.modules.underwriting.models import UnderwritingRunRequest

logger = logging.getLogger(__name__)

CHECKPOINT_ALLOWED_TYPES = frozenset(
    {
        "app.modules.underwriting.models:AllChecksComplete",
        "app.modules.underwriting.models:CheckRequest",
        "app.modules.underwriting.models:CheckResult",
        "app.modules.underwriting.models:CheckType",
        "app.modules.underwriting.models:Decision",
        "app.modules.underwriting.models:FinalDecisionResult",
        "app.modules.underwriting.models:UnderwritingApplication",
        "app.modules.underwriting.models:UnderwritingRunRequest",
    }
)


class PostgresCheckpointStorage(CheckpointStorage):
    """Real MAF checkpoint storage backed by PostgreSQL."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _workflow_run_id_from_checkpoint(checkpoint: WorkflowCheckpoint) -> str:
        workflow_run_id = checkpoint.state.get("workflow_run_id")
        if isinstance(workflow_run_id, str) and workflow_run_id:
            return workflow_run_id
        for messages in checkpoint.messages.values():
            for message in messages:
                if isinstance(message.data, UnderwritingRunRequest):
                    return message.data.workflow_run_id
        return checkpoint.workflow_name

    async def save(self, checkpoint: WorkflowCheckpoint) -> str:
        workflow_run_id = self._workflow_run_id_from_checkpoint(checkpoint)
        with workflow_stage_span(
            "checkpoint.save",
            {
                "workflow.run_id": workflow_run_id,
                "workflow.executor": "checkpoint_storage",
            },
        ):
            with self.engine.begin() as conn:
                conn.execute(
                    insert(maf_checkpoints).values(
                        workflow_run_id=workflow_run_id,
                        workflow_id=checkpoint.workflow_name,
                        checkpoint_id=checkpoint.checkpoint_id,
                        checkpoint_json=encode_checkpoint_value(checkpoint.to_dict()),
                        metadata_json=checkpoint.metadata or {},
                        created_at=datetime.utcnow(),
                    )
                )
        logger.info(
            "checkpoint saved to postgres workflow_run_id=%s workflow_name=%s checkpoint_id=%s",
            workflow_run_id,
            checkpoint.workflow_name,
            checkpoint.checkpoint_id,
        )
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> WorkflowCheckpoint | None:
        with workflow_stage_span(
            "checkpoint.load",
            {"workflow.executor": "checkpoint_storage"},
        ) as span:
            with self.engine.begin() as conn:
                row = conn.execute(
                    select(maf_checkpoints.c.checkpoint_json).where(
                        maf_checkpoints.c.checkpoint_id == checkpoint_id
                    )
                ).first()
            if not row:
                return None
            checkpoint = WorkflowCheckpoint.from_dict(
                decode_checkpoint_value(row[0], allowed_types=CHECKPOINT_ALLOWED_TYPES)
            )
            span.set_attribute(
                "workflow.run_id",
                self._workflow_run_id_from_checkpoint(checkpoint),
            )
            logger.info(
                "checkpoint loaded from postgres workflow_name=%s checkpoint_id=%s",
                checkpoint.workflow_name,
                checkpoint.checkpoint_id,
            )
            return checkpoint

    async def list_checkpoint_ids(self, *, workflow_name: str) -> list[str]:
        with self.engine.begin() as conn:
            stmt = select(maf_checkpoints.c.checkpoint_id).where(
                maf_checkpoints.c.workflow_id == workflow_name
            )
            rows = conn.execute(stmt.order_by(maf_checkpoints.c.id.asc())).all()
        return [str(r[0]) for r in rows]

    async def list_checkpoints(self, *, workflow_name: str) -> list[WorkflowCheckpoint]:
        with self.engine.begin() as conn:
            stmt = select(maf_checkpoints.c.checkpoint_json).where(
                maf_checkpoints.c.workflow_id == workflow_name
            )
            rows = conn.execute(stmt.order_by(maf_checkpoints.c.id.asc())).all()
        return [
            WorkflowCheckpoint.from_dict(
                decode_checkpoint_value(row[0], allowed_types=CHECKPOINT_ALLOWED_TYPES)
            )
            for row in rows
        ]

    async def delete(self, checkpoint_id: str) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                delete(maf_checkpoints).where(maf_checkpoints.c.checkpoint_id == checkpoint_id)
            )
        return bool(result.rowcount)

    async def get_latest(self, *, workflow_name: str) -> WorkflowCheckpoint | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(maf_checkpoints.c.checkpoint_json)
                .where(maf_checkpoints.c.workflow_id == workflow_name)
                .order_by(maf_checkpoints.c.id.desc())
            ).first()
        if row is None:
            return None
        return WorkflowCheckpoint.from_dict(
            decode_checkpoint_value(row[0], allowed_types=CHECKPOINT_ALLOWED_TYPES)
        )
