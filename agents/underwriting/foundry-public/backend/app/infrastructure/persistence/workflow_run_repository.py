from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, insert, or_, select, update
from sqlalchemy.engine import Engine

from app.infrastructure.db.tables import (
    business_state,
    idempotency_records,
    maf_checkpoints,
    underwriting_approvals,
    underwriting_results,
    workflow_events,
    workflow_runs,
)
from app.modules.underwriting.models import (
    ApprovalClaim,
    ApprovalStatus,
    Decision,
    OriginChannel,
    ReviewerOutcome,
    ReviewerType,
)


class MachineRecommendationConflictError(RuntimeError):
    pass


class ApprovalDecisionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class WorkflowRunRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_workflow_run(
        self,
        workflow_run_id: str,
        maf_workflow_id: str,
        workflow_type: str,
        application_id: str,
        applicant_name: str,
        *,
        origin_channel: OriginChannel = OriginChannel.API,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(workflow_runs).values(
                    id=workflow_run_id,
                    maf_workflow_id=maf_workflow_id,
                    workflow_type=workflow_type,
                    application_id=application_id,
                    applicant_name=applicant_name,
                    origin_channel=origin_channel.value,
                    status="RUNNING",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

    def get_workflow_origin_channel(self, workflow_run_id: str) -> OriginChannel | None:
        with self.engine.begin() as conn:
            value = conn.execute(
                select(workflow_runs.c.origin_channel).where(workflow_runs.c.id == workflow_run_id)
            ).scalar_one_or_none()
        return OriginChannel(str(value)) if value is not None else None

    def set_machine_recommendation(
        self,
        workflow_run_id: str,
        recommendation: str,
        *,
        connection: Any | None = None,
    ) -> None:
        if recommendation not in {decision.value for decision in Decision}:
            raise ValueError("Unsupported machine recommendation")

        def persist(conn: Any) -> None:
            result = conn.execute(
                update(workflow_runs)
                .where(
                    workflow_runs.c.id == workflow_run_id,
                    workflow_runs.c.machine_recommendation.is_(None),
                )
                .values(
                    machine_recommendation=recommendation,
                    updated_at=datetime.utcnow(),
                )
            )
            if result.rowcount:
                return
            current = conn.execute(
                select(workflow_runs.c.machine_recommendation).where(
                    workflow_runs.c.id == workflow_run_id
                )
            ).scalar_one_or_none()
            if current is None:
                raise ValueError(f"Unknown workflow run: {workflow_run_id}")
            if current != recommendation:
                raise MachineRecommendationConflictError(
                    "Machine recommendation is immutable once selected"
                )

        if connection is not None:
            persist(connection)
            return
        with self.engine.begin() as conn:
            persist(conn)

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
            if row is None:
                return None
            result = dict(row)
            approval = (
                conn.execute(
                    select(underwriting_approvals)
                    .where(underwriting_approvals.c.workflow_run_id == workflow_run_id)
                    .order_by(underwriting_approvals.c.created_at.desc())
                )
                .mappings()
                .first()
            )
            if approval is not None:
                result.update(
                    {
                        "review_checkpoint_id": approval["checkpoint_id"],
                        "review_status": approval["status"],
                        "reviewer_outcome": approval["reviewer_outcome"],
                    }
                )
            return result

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
            approvals = (
                conn.execute(
                    select(
                        underwriting_approvals.c.workflow_run_id,
                        underwriting_approvals.c.checkpoint_id,
                        underwriting_approvals.c.status,
                        underwriting_approvals.c.reviewer_outcome,
                    )
                    .where(underwriting_approvals.c.workflow_run_id.in_(run_ids))
                    .order_by(underwriting_approvals.c.created_at.asc())
                )
                .mappings()
                .all()
            )
            approval_summary = {
                str(approval["workflow_run_id"]): dict(approval) for approval in approvals
            }
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
                    "machine_recommendation": item.get("machine_recommendation"),
                    "reviewer_outcome": (approval_summary.get(run_id, {}).get("reviewer_outcome")),
                    "review_status": approval_summary.get(run_id, {}).get("status"),
                    "review_checkpoint_id": (approval_summary.get(run_id, {}).get("checkpoint_id")),
                    "checkpoint_count": checkpoint["count"],
                    "latest_checkpoint_at": checkpoint["latest"],
                    "resumable": item["status"] == "CRASHED" and checkpoint["count"] > 0,
                    "reviewable": (
                        item["status"] == "PENDING_REVIEW"
                        and approval_summary.get(run_id, {}).get("status")
                        == ApprovalStatus.PENDING.value
                    ),
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
            if check_type == "final_decision":
                recommendation = result_json.get("decision")
                if not isinstance(recommendation, str):
                    raise ValueError("Final decision result requires a machine recommendation")
                self.set_machine_recommendation(
                    workflow_run_id,
                    recommendation,
                    connection=conn,
                )
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

    def create_pending_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        request_id = request_id or f"underwriting-review:{workflow_run_id}"
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            run = (
                conn.execute(
                    select(
                        workflow_runs.c.id,
                        workflow_runs.c.machine_recommendation,
                        workflow_runs.c.origin_channel,
                    )
                    .where(workflow_runs.c.id == workflow_run_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if run is None:
                raise ValueError(f"Unknown workflow run: {workflow_run_id}")
            if run["machine_recommendation"] != "REFER_TO_HUMAN_UNDERWRITER":
                raise ValueError("Only REFER_TO_HUMAN_UNDERWRITER may create a pending approval")
            checkpoint_run_id = conn.execute(
                select(maf_checkpoints.c.workflow_run_id).where(
                    maf_checkpoints.c.checkpoint_id == checkpoint_id
                )
            ).scalar_one_or_none()
            if checkpoint_run_id != workflow_run_id:
                raise ValueError("Checkpoint does not belong to the workflow run")
            latest_checkpoint_id = conn.execute(
                select(maf_checkpoints.c.checkpoint_id)
                .where(maf_checkpoints.c.workflow_run_id == workflow_run_id)
                .order_by(maf_checkpoints.c.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_checkpoint_id != checkpoint_id:
                raise ValueError("Checkpoint is stale for the workflow run")

            existing = (
                conn.execute(
                    select(underwriting_approvals).where(
                        or_(
                            underwriting_approvals.c.checkpoint_id == checkpoint_id,
                            underwriting_approvals.c.request_id == request_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if (
                    existing["workflow_run_id"] != workflow_run_id
                    or existing["checkpoint_id"] != checkpoint_id
                    or existing["request_id"] != request_id
                ):
                    raise ValueError("Approval request binding conflict")
                return dict(existing)

            approval_id = f"approval-{uuid4().hex}"
            conn.execute(
                insert(underwriting_approvals).values(
                    approval_id=approval_id,
                    workflow_run_id=workflow_run_id,
                    checkpoint_id=checkpoint_id,
                    request_id=request_id,
                    origin_channel=run["origin_channel"],
                    status=ApprovalStatus.PENDING.value,
                    requested_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = (
                conn.execute(
                    select(underwriting_approvals).where(
                        underwriting_approvals.c.approval_id == approval_id
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)

    def get_pending_approval(self, checkpoint_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(underwriting_approvals).where(
                        underwriting_approvals.c.checkpoint_id == checkpoint_id,
                        underwriting_approvals.c.status == ApprovalStatus.PENDING.value,
                    )
                )
                .mappings()
                .first()
            )
        return dict(row) if row is not None else None

    def get_approval(self, workflow_run_id: str, checkpoint_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(underwriting_approvals).where(
                        underwriting_approvals.c.workflow_run_id == workflow_run_id,
                        underwriting_approvals.c.checkpoint_id == checkpoint_id,
                    )
                )
                .mappings()
                .first()
            )
        return dict(row) if row is not None else None

    def get_review_projection(self, workflow_run_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(
                        underwriting_approvals.c.workflow_run_id,
                        underwriting_approvals.c.checkpoint_id,
                        underwriting_approvals.c.status,
                        underwriting_approvals.c.reviewer_outcome,
                        underwriting_approvals.c.requested_at,
                        underwriting_approvals.c.resolved_at,
                        workflow_runs.c.machine_recommendation,
                    )
                    .join(
                        workflow_runs,
                        workflow_runs.c.id == underwriting_approvals.c.workflow_run_id,
                    )
                    .where(underwriting_approvals.c.workflow_run_id == workflow_run_id)
                    .order_by(underwriting_approvals.c.created_at.desc())
                )
                .mappings()
                .first()
            )
        return dict(row) if row is not None else None

    def claim_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        origin_channel: OriginChannel,
        reviewer_type: ReviewerType,
    ) -> ApprovalClaim:
        if not reviewer_id:
            raise ApprovalDecisionError("unauthorized", "Reviewer identity is required")
        now = datetime.now(UTC)
        reviewer_hash = hashlib.sha256(reviewer_id.encode("utf-8")).hexdigest()
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(
                        underwriting_approvals,
                        workflow_runs.c.origin_channel.label("run_origin_channel"),
                    )
                    .join(
                        workflow_runs,
                        workflow_runs.c.id == underwriting_approvals.c.workflow_run_id,
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
            if row is None:
                raise ApprovalDecisionError("approval_not_found", "Pending review was not found")
            if (
                row["origin_channel"] != origin_channel.value
                or row["run_origin_channel"] != origin_channel.value
            ):
                raise ApprovalDecisionError(
                    "origin_mismatch",
                    "Review decision origin does not match the pending approval",
                )
            status = ApprovalStatus(str(row["status"]))
            existing_outcome = row["reviewer_outcome"]
            if status == ApprovalStatus.COMPLETED:
                if existing_outcome != outcome.value:
                    raise ApprovalDecisionError(
                        "decision_conflict",
                        "Review was already completed with a different outcome",
                    )
                return ApprovalClaim(
                    workflow_run_id=workflow_run_id,
                    checkpoint_id=checkpoint_id,
                    request_id=str(row["request_id"]),
                    outcome=outcome,
                    origin_channel=origin_channel,
                    reviewer_type=ReviewerType(
                        str(row["reviewer_type"] or ReviewerType.UNKNOWN_LEGACY.value)
                    ),
                    acquired=False,
                    completed=True,
                )
            if status == ApprovalStatus.PROCESSING:
                raise ApprovalDecisionError(
                    "decision_in_progress", "Review decision is already being processed"
                )
            latest_checkpoint_id = conn.execute(
                select(maf_checkpoints.c.checkpoint_id)
                .where(maf_checkpoints.c.workflow_run_id == workflow_run_id)
                .order_by(maf_checkpoints.c.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_checkpoint_id != checkpoint_id:
                raise ApprovalDecisionError("stale_checkpoint", "Review checkpoint is stale")
            result = conn.execute(
                update(underwriting_approvals)
                .where(
                    underwriting_approvals.c.workflow_run_id == workflow_run_id,
                    underwriting_approvals.c.checkpoint_id == checkpoint_id,
                    underwriting_approvals.c.status == ApprovalStatus.PENDING.value,
                )
                .values(
                    status=ApprovalStatus.PROCESSING.value,
                    reviewer_outcome=outcome.value,
                    reviewer_hash=reviewer_hash,
                    reviewer_type=reviewer_type.value,
                    updated_at=now,
                )
            )
            if not result.rowcount:
                raise ApprovalDecisionError(
                    "decision_in_progress", "Review decision is already being processed"
                )
            return ApprovalClaim(
                workflow_run_id=workflow_run_id,
                checkpoint_id=checkpoint_id,
                request_id=str(row["request_id"]),
                outcome=outcome,
                origin_channel=origin_channel,
                reviewer_type=reviewer_type,
                acquired=True,
                completed=False,
            )

    def finish_approval(self, claim: ApprovalClaim) -> bool:
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            result = conn.execute(
                update(underwriting_approvals)
                .where(
                    underwriting_approvals.c.workflow_run_id == claim.workflow_run_id,
                    underwriting_approvals.c.checkpoint_id == claim.checkpoint_id,
                    underwriting_approvals.c.origin_channel == claim.origin_channel.value,
                    underwriting_approvals.c.status == ApprovalStatus.PROCESSING.value,
                    underwriting_approvals.c.reviewer_outcome == claim.outcome.value,
                )
                .values(
                    status=ApprovalStatus.COMPLETED.value,
                    resolved_at=now,
                    updated_at=now,
                )
            )
        return bool(result.rowcount)

    def release_approval(self, claim: ApprovalClaim) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(underwriting_approvals)
                .where(
                    underwriting_approvals.c.workflow_run_id == claim.workflow_run_id,
                    underwriting_approvals.c.checkpoint_id == claim.checkpoint_id,
                    underwriting_approvals.c.status == ApprovalStatus.PROCESSING.value,
                    underwriting_approvals.c.reviewer_outcome == claim.outcome.value,
                )
                .values(
                    status=ApprovalStatus.PENDING.value,
                    reviewer_outcome=None,
                    reviewer_hash=None,
                    reviewer_type=None,
                    updated_at=datetime.now(UTC),
                )
            )
        return bool(result.rowcount)

    def complete_approval(
        self,
        *,
        workflow_run_id: str,
        checkpoint_id: str,
        outcome: ReviewerOutcome,
        reviewer_id: str,
        reviewer_type: ReviewerType = ReviewerType.HUMAN,
    ) -> bool:
        origin = self.get_workflow_origin_channel(workflow_run_id)
        if origin is None:
            return False
        claim = self.claim_approval(
            workflow_run_id=workflow_run_id,
            checkpoint_id=checkpoint_id,
            outcome=outcome,
            reviewer_id=reviewer_id,
            origin_channel=origin,
            reviewer_type=reviewer_type,
        )
        if claim.completed:
            return False
        return self.finish_approval(claim)

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
