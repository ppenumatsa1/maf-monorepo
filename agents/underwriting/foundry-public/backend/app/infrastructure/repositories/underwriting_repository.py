from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, insert, or_, select, update
from sqlalchemy.engine import Engine

from app.infrastructure.db.tables import (
    business_state,
    idempotency_records,
    maf_checkpoints,
    underwriting_results,
    workflow_events,
    workflow_runs,
)


class Repository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_workflow_run(
        self,
        workflow_run_id: str,
        maf_workflow_id: str,
        workflow_type: str,
        application_id: str,
        applicant_name: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(workflow_runs).values(
                    id=workflow_run_id,
                    maf_workflow_id=maf_workflow_id,
                    workflow_type=workflow_type,
                    application_id=application_id,
                    applicant_name=applicant_name,
                    status="RUNNING",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

    def update_workflow_run_status(self, workflow_run_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(workflow_runs)
                .where(workflow_runs.c.id == workflow_run_id)
                .values(status=status, updated_at=datetime.utcnow())
            )

    def get_workflow_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(select(workflow_runs).where(workflow_runs.c.id == workflow_run_id))
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def get_safe_run_status(self, workflow_run_id: str) -> str | None:
        with self.engine.begin() as conn:
            return conn.execute(
                select(workflow_runs.c.status).where(workflow_runs.c.id == workflow_run_id)
            ).scalar_one_or_none()

    def list_safe_event_summaries(
        self, workflow_run_id: str, *, limit: int
    ) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(
                        workflow_events.c.event_type,
                        workflow_events.c.executor_name,
                        workflow_events.c.created_at,
                    )
                    .where(workflow_events.c.workflow_run_id == workflow_run_id)
                    .order_by(workflow_events.c.id.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in reversed(rows)]

    def get_safe_checkpoint_summary(self, workflow_run_id: str) -> tuple[int, datetime | None]:
        with self.engine.begin() as conn:
            count, latest = conn.execute(
                select(
                    func.count(maf_checkpoints.c.id), func.max(maf_checkpoints.c.created_at)
                ).where(maf_checkpoints.c.workflow_run_id == workflow_run_id)
            ).one()
        return int(count), latest

    def get_safe_final_decision(self, workflow_run_id: str) -> str | None:
        decision = underwriting_results.c.result_json["decision"].as_string()
        with self.engine.begin() as conn:
            return conn.execute(
                select(decision)
                .where(
                    underwriting_results.c.workflow_run_id == workflow_run_id,
                    underwriting_results.c.check_type == "final_decision",
                )
                .order_by(underwriting_results.c.id.desc())
            ).scalar_one_or_none()

    def list_workflow_runs(
        self,
        *,
        search: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        filters = []
        if search:
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(workflow_runs.c.id).like(pattern),
                    func.lower(workflow_runs.c.application_id).like(pattern),
                    func.lower(workflow_runs.c.applicant_name).like(pattern),
                )
            )
        if status:
            filters.append(workflow_runs.c.status == status.upper())

        with self.engine.begin() as conn:
            total = int(
                conn.execute(
                    select(func.count()).select_from(workflow_runs).where(*filters)
                ).scalar_one()
            )
            rows = (
                conn.execute(
                    select(workflow_runs)
                    .where(*filters)
                    .order_by(workflow_runs.c.created_at.desc(), workflow_runs.c.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
                .mappings()
                .all()
            )
            run_ids = [str(row["id"]) for row in rows]
            if not run_ids:
                return total, []

            results = (
                conn.execute(
                    select(
                        underwriting_results.c.workflow_run_id,
                        underwriting_results.c.result_json,
                    ).where(
                        underwriting_results.c.workflow_run_id.in_(run_ids),
                        underwriting_results.c.check_type == "final_decision",
                    )
                )
                .mappings()
                .all()
            )
            decisions = {
                str(result["workflow_run_id"]): str(
                    (result["result_json"] or {}).get("decision", "")
                )
                for result in results
            }
            checkpoints = (
                conn.execute(
                    select(maf_checkpoints.c.workflow_run_id, maf_checkpoints.c.created_at)
                    .where(maf_checkpoints.c.workflow_run_id.in_(run_ids))
                    .order_by(maf_checkpoints.c.id.asc())
                )
                .mappings()
                .all()
            )
            checkpoint_summary: dict[str, dict[str, Any]] = {}
            for checkpoint in checkpoints:
                run_id = str(checkpoint["workflow_run_id"])
                summary = checkpoint_summary.setdefault(run_id, {"count": 0, "latest": None})
                summary["count"] += 1
                summary["latest"] = checkpoint["created_at"]

        summaries: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            run_id = str(item["id"])
            checkpoint = checkpoint_summary.get(run_id, {"count": 0, "latest": None})
            summaries.append(
                {
                    "workflow_run_id": run_id,
                    "application_id": item["application_id"],
                    "applicant_name": item.get("applicant_name") or "Unknown applicant",
                    "status": item["status"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "final_decision": decisions.get(run_id) or None,
                    "checkpoint_count": checkpoint["count"],
                    "latest_checkpoint_at": checkpoint["latest"],
                    "resumable": item["status"] == "CRASHED" and checkpoint["count"] > 0,
                }
            )
        return total, summaries

    def write_business_state(
        self, workflow_run_id: str, application_id: str, state_key: str, state_json: dict[str, Any]
    ) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(business_state.c.id).where(
                    business_state.c.workflow_run_id == workflow_run_id,
                    business_state.c.state_key == state_key,
                )
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(
                    insert(business_state).values(
                        workflow_run_id=workflow_run_id,
                        application_id=application_id,
                        state_key=state_key,
                        state_json=state_json,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    update(business_state)
                    .where(business_state.c.id == existing)
                    .values(state_json=state_json, updated_at=datetime.utcnow())
                )

    def list_business_state(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(business_state)
                    .where(business_state.c.workflow_run_id == workflow_run_id)
                    .order_by(business_state.c.id.asc())
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def log_event(
        self,
        workflow_run_id: str,
        event_type: str,
        executor_name: str,
        payload_json: dict[str, Any],
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(workflow_events).values(
                    workflow_run_id=workflow_run_id,
                    event_type=event_type,
                    executor_name=executor_name,
                    payload_json=payload_json,
                    created_at=datetime.utcnow(),
                )
            )

    def list_events(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(workflow_events)
                    .where(workflow_events.c.workflow_run_id == workflow_run_id)
                    .order_by(workflow_events.c.id.asc())
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def get_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(idempotency_records).where(
                        idempotency_records.c.idempotency_key == idempotency_key
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def upsert_idempotency(
        self,
        idempotency_key: str,
        operation_name: str,
        status: str,
        result_json: dict[str, Any] | None,
    ) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(idempotency_records.c.id).where(
                    idempotency_records.c.idempotency_key == idempotency_key
                )
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(
                    insert(idempotency_records).values(
                        idempotency_key=idempotency_key,
                        operation_name=operation_name,
                        status=status,
                        result_json=result_json,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    update(idempotency_records)
                    .where(idempotency_records.c.id == existing)
                    .values(status=status, result_json=result_json, updated_at=datetime.utcnow())
                )

    def save_underwriting_result(
        self,
        workflow_run_id: str,
        application_id: str,
        check_type: str,
        result_json: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(underwriting_results.c.id).where(
                    underwriting_results.c.idempotency_key == idempotency_key
                )
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(
                    insert(underwriting_results).values(
                        workflow_run_id=workflow_run_id,
                        application_id=application_id,
                        check_type=check_type,
                        result_json=result_json,
                        idempotency_key=idempotency_key,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def count_underwriting_results_by_key(self, idempotency_key: str) -> int:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(underwriting_results.c.id).where(
                    underwriting_results.c.idempotency_key == idempotency_key
                )
            ).all()
            return len(rows)

    def get_underwriting_result_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(underwriting_results.c.result_json).where(
                    underwriting_results.c.idempotency_key == idempotency_key
                )
            ).first()
            if not row:
                return None
            return row[0]

    def list_underwriting_results(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(underwriting_results)
                    .where(underwriting_results.c.workflow_run_id == workflow_run_id)
                    .order_by(underwriting_results.c.id.asc())
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def list_checkpoints(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(maf_checkpoints)
                    .where(maf_checkpoints.c.workflow_run_id == workflow_run_id)
                    .order_by(maf_checkpoints.c.id.asc())
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    def latest_checkpoint_id(self, workflow_run_id: str) -> str | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(maf_checkpoints.c.checkpoint_id)
                .where(maf_checkpoints.c.workflow_run_id == workflow_run_id)
                .order_by(desc(maf_checkpoints.c.id))
            ).first()
            return str(row[0]) if row else None

    def should_fail_credit_randomly(self, threshold: float = 0.5) -> bool:
        return random.random() < threshold
