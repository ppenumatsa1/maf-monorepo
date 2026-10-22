from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from app.core.database import postgres_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


def test_workflow_origin_is_server_persisted() -> None:
    repository = WorkflowRunRepository()
    thread_id = f"origin-{uuid4()}"

    try:
        repository.create_workflow_run(
            thread_id=thread_id,
            input_text="synthetic origin test",
            session_id=thread_id,
            origin_channel="responses",
        )

        assert repository.get_workflow_origin_channel(thread_id) == "responses"
    finally:
        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workflow_runs WHERE thread_id = %s", (thread_id,))


def test_concurrent_responses_dispatch_has_one_server_selected_winner() -> None:
    repository = WorkflowRunRepository()
    idempotency_key = f"dispatch-race-{uuid4()}"
    request_hash = "same-request"
    barrier = Barrier(2)

    def create(candidate: str) -> dict[str, object]:
        barrier.wait()
        return repository.create_or_get_responses_dispatch(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            run_id=f"run-{candidate}",
            thread_id=f"thread-{candidate}",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, ("a", "b")))

        assert sum(bool(result["created"]) for result in results) == 1
        assert {result["run_id"] for result in results} in ({"run-a"}, {"run-b"})
        assert {result["thread_id"] for result in results} in (
            {"thread-a"},
            {"thread-b"},
        )
    finally:
        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM responses_dispatches WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
