#!/usr/bin/env python3
"""Emit administrator-owned idempotent PostgreSQL schema and upgrade DDL."""

from __future__ import annotations

from app.infrastructure.db.tables import metadata
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable


def build_ddl() -> str:
    dialect = postgresql.dialect()
    dependent_table_names = {
        "teams_card_actions",
        "underwriting_approvals",
    }
    independent_tables = [
        table for table in metadata.sorted_tables if table.name not in dependent_table_names
    ]
    dependent_tables = [
        table for table in metadata.sorted_tables if table.name in dependent_table_names
    ]
    statements = [
        str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
        for table in independent_tables
    ]
    statements.append(
        """
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.maf_checkpoints'::regclass
      AND contype = 'u'
      AND pg_get_constraintdef(oid) = 'UNIQUE (checkpoint_id)'
  ) THEN
    ALTER TABLE public.maf_checkpoints
      ADD CONSTRAINT uq_maf_checkpoints_checkpoint_id UNIQUE (checkpoint_id);
  END IF;
END
$migration$
""".strip()
    )
    statements.extend(
        str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
        for table in dependent_tables
    )
    statements.extend(
        [
            "ALTER TABLE public.workflow_runs "
            "ADD COLUMN IF NOT EXISTS applicant_name VARCHAR(256)",
            "ALTER TABLE public.workflow_runs "
            "ADD COLUMN IF NOT EXISTS origin_channel VARCHAR(32)",
            "ALTER TABLE public.workflow_runs "
            "ADD COLUMN IF NOT EXISTS machine_recommendation VARCHAR(64)",
            "UPDATE public.workflow_runs SET origin_channel = 'api' "
            "WHERE origin_channel IS NULL",
            "ALTER TABLE public.workflow_runs "
            "ALTER COLUMN origin_channel SET DEFAULT 'api'",
            "ALTER TABLE public.workflow_runs "
            "ALTER COLUMN origin_channel SET NOT NULL",
            """
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.workflow_runs'::regclass
      AND conname = 'ck_workflow_runs_origin_channel'
  ) THEN
    ALTER TABLE public.workflow_runs
      ADD CONSTRAINT ck_workflow_runs_origin_channel
      CHECK (origin_channel IN ('api', 'responses', 'teams_activity'));
  END IF;
END
$migration$
""".strip(),
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS request_id VARCHAR(128)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS origin_channel VARCHAR(32)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS status VARCHAR(32)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS reviewer_outcome VARCHAR(64)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS reviewer_hash VARCHAR(64)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS reviewer_type VARCHAR(32)",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ",
            "ALTER TABLE public.underwriting_approvals "
            "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
            "UPDATE public.underwriting_approvals "
            "SET request_id = 'legacy:' || checkpoint_id "
            "WHERE request_id IS NULL",
            """
UPDATE public.underwriting_approvals AS approval
SET origin_channel = COALESCE(run.origin_channel, 'api')
FROM public.workflow_runs AS run
WHERE approval.workflow_run_id = run.id
  AND approval.origin_channel IS NULL
""".strip(),
            "UPDATE public.underwriting_approvals SET origin_channel = 'api' "
            "WHERE origin_channel IS NULL",
            "UPDATE public.underwriting_approvals "
            "SET status = CASE "
            "WHEN reviewer_outcome IS NULL THEN 'pending' ELSE 'completed' END "
            "WHERE status IS NULL",
            "UPDATE public.underwriting_approvals "
            "SET reviewer_type = 'unknown_legacy' "
            "WHERE reviewer_type IS NULL "
            "AND (reviewer_hash IS NOT NULL OR reviewer_outcome IS NOT NULL "
            "OR status = 'completed')",
            "UPDATE public.underwriting_approvals "
            "SET requested_at = COALESCE(requested_at, created_at, CURRENT_TIMESTAMP), "
            "created_at = COALESCE(created_at, requested_at, CURRENT_TIMESTAMP), "
            "updated_at = COALESCE(updated_at, resolved_at, requested_at, "
            "created_at, CURRENT_TIMESTAMP)",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN request_id SET NOT NULL",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN origin_channel SET NOT NULL",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN status SET NOT NULL",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN requested_at SET NOT NULL",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN created_at SET NOT NULL",
            "ALTER TABLE public.underwriting_approvals "
            "ALTER COLUMN updated_at SET NOT NULL",
            """
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND conname = 'ck_underwriting_approvals_status'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT ck_underwriting_approvals_status
      CHECK (status IN ('pending', 'processing', 'completed'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND conname = 'ck_underwriting_approvals_origin_channel'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT ck_underwriting_approvals_origin_channel
      CHECK (origin_channel IN ('api', 'responses', 'teams_activity'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND conname = 'ck_underwriting_approvals_outcome'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT ck_underwriting_approvals_outcome
      CHECK (reviewer_outcome IS NULL OR reviewer_outcome IN ('APPROVED', 'DECLINED'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND conname = 'ck_underwriting_approvals_reviewer_type'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT ck_underwriting_approvals_reviewer_type
      CHECK (
        reviewer_type IS NULL
        OR reviewer_type IN ('human', 'administrative', 'unknown_legacy')
      );
  END IF;
END
$migration$
""".strip(),
            """
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND contype = 'u'
      AND pg_get_constraintdef(oid) = 'UNIQUE (checkpoint_id)'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT uq_underwriting_approvals_checkpoint_id UNIQUE (checkpoint_id);
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.underwriting_approvals'::regclass
      AND contype = 'u'
      AND pg_get_constraintdef(oid) = 'UNIQUE (request_id)'
  ) THEN
    ALTER TABLE public.underwriting_approvals
      ADD CONSTRAINT uq_underwriting_approvals_request_id UNIQUE (request_id);
  END IF;
END
$migration$
""".strip(),
        ]
    )
    statements.extend(
        str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect))
        for table in metadata.sorted_tables
        for index in table.indexes
    )
    return ";\n".join(dict.fromkeys(statements)) + ";"


def main() -> None:
    print(build_ddl())


if __name__ == "__main__":
    main()
