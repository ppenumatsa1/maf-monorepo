from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


def maybe_fail_once(
    settings: Settings,
    repository: WorkflowRunRepository,
    workflow_run_id: str,
    idempotency_key: str,
    check_type: str,
) -> None:
    if check_type == "risk" and settings.fail_risk_once:
        marker_key = f"{idempotency_key}:fail-once"
        marker = repository.get_idempotency(marker_key)
        if marker is None:
            repository.upsert_idempotency(
                marker_key, "failure-injection", "completed", {"injected": True}
            )
            raise RuntimeError("Injected FAIL_RISK_ONCE failure")


def should_fail_credit(settings: Settings, repository: WorkflowRunRepository) -> bool:
    return settings.fail_credit_randomly and repository.should_fail_credit_randomly()


def maybe_crash_after_executor(
    settings: Settings, repository: WorkflowRunRepository, workflow_run_id: str, executor_name: str
) -> None:
    if not settings.crash_after_executor:
        return
    if settings.crash_after_executor != executor_name:
        return
    crash_key = f"crash:{workflow_run_id}:{executor_name}"
    marker = repository.get_idempotency(crash_key)
    if marker is None:
        repository.upsert_idempotency(
            crash_key, "crash-injection", "completed", {"executor_name": executor_name}
        )
        raise RuntimeError(f"Injected crash after executor {executor_name}")
