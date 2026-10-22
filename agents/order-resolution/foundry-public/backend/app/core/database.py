from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.telemetry import get_tracer
from opentelemetry.trace import SpanKind, Status, StatusCode
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/maf_workflow"


EXTERNAL_SCHEMA_VALIDATION_QUERIES = (
    "SELECT 1",
    "SELECT origin_channel FROM public.workflow_runs LIMIT 0",
    "SELECT 1 FROM public.responses_dispatches LIMIT 0",
    "SELECT 1 FROM public.workflow_events LIMIT 0",
    "SELECT 1 FROM public.conversation_messages LIMIT 0",
    "SELECT 1 FROM public.checkpoints LIMIT 0",
    "SELECT 1 FROM public.approvals LIMIT 0",
    "SELECT batch_id, status FROM public.teams_card_actions LIMIT 0",
    "SELECT 1 FROM public.idempotency_keys LIMIT 0",
    "SELECT 1 FROM public.sessions LIMIT 0",
    "SELECT 1 FROM public.eval_runs LIMIT 0",
    "SELECT 1 FROM public.eval_results LIMIT 0",
)


def _integer_setting(name: str, default: int, *, minimum: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if parsed < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return parsed


def _is_hosted_runtime() -> bool:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    return app_env.startswith(("aca", "foundry")) or os.getenv(
        "DB_SCHEMA_MANAGED_EXTERNALLY", ""
    ).strip().lower() in {"1", "true", "yes"}


class ObservedConnectionPool:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    @contextmanager
    def connection(self, *args: Any, **kwargs: Any):
        tracer = get_tracer("app.database")
        with tracer.start_as_current_span(
            "postgresql.connection",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": "postgresql",
                "db.system.name": "postgresql",
                "db.operation.name": "connection",
            },
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                with self._pool.connection(*args, **kwargs) as conn:
                    yield conn
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR))
                span.add_event(
                    "database.error",
                    attributes={"exception.type": type(exc).__name__},
                )
                raise
            else:
                span.set_status(Status(StatusCode.OK))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pool, name)


class RestartableConnectionPool:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    @contextmanager
    def connection(self, *args: Any, **kwargs: Any):
        with self._database.get_pool().connection(*args, **kwargs) as conn:
            yield conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._database.get_pool(), name)


class PostgresDatabase:
    def __init__(self) -> None:
        self._pool: ObservedConnectionPool | None = None
        self.pool = RestartableConnectionPool(self)
        self._schema_initialized = False
        self._lock = RLock()

    @property
    def database_url(self) -> str:
        value = os.getenv("DATABASE_URL")
        if value:
            return value.replace("postgresql+psycopg://", "postgresql://", 1)
        if os.getenv("APP_ENV", "").lower().startswith("foundry"):
            raise RuntimeError("DATABASE_URL must be set for Foundry-hosted runtime.")
        return DEFAULT_DATABASE_URL

    @property
    def pool_configuration(self) -> dict[str, int]:
        hosted = _is_hosted_runtime()
        minimum_size = _integer_setting(
            "DB_POOL_MIN_SIZE",
            0 if hosted else 1,
            minimum=0,
        )
        maximum_size = _integer_setting(
            "DB_POOL_MAX_SIZE",
            2 if hosted else 10,
            minimum=1,
        )
        if maximum_size < minimum_size:
            raise RuntimeError("DB_POOL_MAX_SIZE must be at least DB_POOL_MIN_SIZE.")
        return {
            "min_size": minimum_size,
            "max_size": maximum_size,
            "max_idle": _integer_setting(
                "DB_POOL_MAX_IDLE_SECONDS",
                30 if hosted else 600,
                minimum=1,
            ),
        }

    def get_pool(self) -> ObservedConnectionPool:
        with self._lock:
            if self._pool is None:
                self._pool = ObservedConnectionPool(
                    ConnectionPool(
                        conninfo=self.database_url,
                        **self.pool_configuration,
                        open=True,
                        kwargs={"autocommit": True, "row_factory": dict_row},
                    )
                )
            return self._pool

    def ensure_schema(self) -> None:
        with self._lock:
            if self._schema_initialized:
                return
            pool = self.get_pool()
            if os.getenv("DB_SCHEMA_MANAGED_EXTERNALLY", "").lower() in {
                "1",
                "true",
                "yes",
            }:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        for statement in EXTERNAL_SCHEMA_VALIDATION_QUERIES:
                            cur.execute(statement)
                self._schema_initialized = True
                return
            schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
            schema_sql = schema_path.read_text(encoding="utf-8")
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
            self._schema_initialized = True

    def close(self) -> None:
        with self._lock:
            pool = self._pool
            self._pool = None
            self._schema_initialized = False
        if pool is not None:
            pool.close()


postgres_db = PostgresDatabase()
