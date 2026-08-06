from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table
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
    Column("status", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
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
    Column("checkpoint_id", String(128), nullable=False, unique=True, index=True),
    Column("checkpoint_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("metadata_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)
