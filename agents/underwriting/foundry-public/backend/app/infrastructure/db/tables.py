from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("maf_workflow_id", String(128), nullable=False, index=True),
    Column("workflow_type", String(128), nullable=False),
    Column("application_id", String(128), nullable=False, index=True),
    Column("applicant_name", String(256), nullable=True, index=True),
    Column("origin_channel", String(32), nullable=False, server_default=text("'api'"), index=True),
    Column("machine_recommendation", String(64), nullable=True),
    Column("status", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
    CheckConstraint(
        "origin_channel IN ('api', 'responses', 'teams_activity')",
        name="ck_workflow_runs_origin_channel",
    ),
)

business_state = Table(
    "business_state",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workflow_run_id", String(64), nullable=False, index=True),
    Column("application_id", String(128), nullable=False, index=True),
    Column("state_key", String(128), nullable=False),
    Column("state_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

underwriting_results = Table(
    "underwriting_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workflow_run_id", String(64), nullable=False, index=True),
    Column("application_id", String(128), nullable=False, index=True),
    Column("check_type", String(64), nullable=False),
    Column("result_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("idempotency_key", String(256), nullable=False, index=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

workflow_events = Table(
    "workflow_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workflow_run_id", String(64), nullable=False, index=True),
    Column("event_type", String(128), nullable=False),
    Column("executor_name", String(128), nullable=False),
    Column("payload_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

idempotency_records = Table(
    "idempotency_records",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("idempotency_key", String(256), nullable=False, unique=True),
    Column("operation_name", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("result_json", JSONB().with_variant(JSON, "sqlite"), nullable=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

maf_checkpoints = Table(
    "maf_checkpoints",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workflow_run_id", String(64), nullable=False, index=True),
    Column("workflow_id", String(128), nullable=False, index=True),
    Column("checkpoint_id", String(128), nullable=False, index=True),
    Column("checkpoint_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("metadata_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    UniqueConstraint(
        "checkpoint_id",
        name="uq_maf_checkpoints_checkpoint_id",
    ),
)

underwriting_approvals = Table(
    "underwriting_approvals",
    metadata,
    Column("approval_id", String(64), primary_key=True),
    Column(
        "workflow_run_id",
        String(64),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "checkpoint_id",
        String(128),
        ForeignKey("maf_checkpoints.checkpoint_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("request_id", String(128), nullable=False, unique=True),
    Column("origin_channel", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("reviewer_outcome", String(64), nullable=True),
    Column("reviewer_hash", String(64), nullable=True),
    Column("reviewer_type", String(32), nullable=True),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('pending', 'processing', 'completed')",
        name="ck_underwriting_approvals_status",
    ),
    CheckConstraint(
        "origin_channel IN ('api', 'responses', 'teams_activity')",
        name="ck_underwriting_approvals_origin_channel",
    ),
    CheckConstraint(
        "reviewer_outcome IS NULL OR reviewer_outcome IN ('APPROVED', 'DECLINED')",
        name="ck_underwriting_approvals_outcome",
    ),
    CheckConstraint(
        "reviewer_type IS NULL OR reviewer_type IN ('human', 'administrative', 'unknown_legacy')",
        name="ck_underwriting_approvals_reviewer_type",
    ),
)
Index(
    "ix_underwriting_approvals_run_status",
    underwriting_approvals.c.workflow_run_id,
    underwriting_approvals.c.status,
)
Index(
    "ix_underwriting_approvals_checkpoint_status",
    underwriting_approvals.c.checkpoint_id,
    underwriting_approvals.c.status,
)
Index(
    "ix_underwriting_approvals_run_origin_status",
    underwriting_approvals.c.workflow_run_id,
    underwriting_approvals.c.origin_channel,
    underwriting_approvals.c.status,
)

teams_card_actions = Table(
    "teams_card_actions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("batch_id", String(36), nullable=False),
    Column(
        "workflow_run_id",
        String(64),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "checkpoint_id",
        String(128),
        ForeignKey("maf_checkpoints.checkpoint_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("decision", String(64), nullable=False),
    Column("conversation_hash", String(64), nullable=False),
    Column("user_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "decision IN ('APPROVED', 'DECLINED')",
        name="ck_teams_card_actions_decision",
    ),
    CheckConstraint(
        "status IN ('pending', 'processing', 'completed', 'superseded', 'released')",
        name="ck_teams_card_actions_status",
    ),
)
Index(
    "ix_teams_card_actions_checkpoint_status",
    teams_card_actions.c.checkpoint_id,
    teams_card_actions.c.status,
)
Index(
    "ix_teams_card_actions_batch_status",
    teams_card_actions.c.batch_id,
    teams_card_actions.c.status,
)
Index(
    "ix_teams_card_actions_expiry_status",
    teams_card_actions.c.expires_at,
    teams_card_actions.c.status,
)
