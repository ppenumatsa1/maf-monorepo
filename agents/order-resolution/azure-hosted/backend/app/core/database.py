from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.telemetry import get_tracer
from azure.identity import DefaultAzureCredential
from opentelemetry.trace import SpanKind, Status, StatusCode
from psycopg import Connection
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/maf_workflow"
AZURE_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

EXTERNAL_SCHEMA_VALIDATION_QUERIES = (
    "SELECT 1",
    (
        "SELECT thread_id, session_id, status, input, input_summary, latest_output, "
        "started_at, completed_at, duration_ms, current_stage "
        "FROM public.workflow_runs LIMIT 0"
    ),
    "SELECT id, thread_id, type, timestamp, payload FROM public.workflow_events LIMIT 0",
    ("SELECT id, thread_id, role, content, created_at FROM public.conversation_messages LIMIT 0"),
    (
        "SELECT checkpoint_id, thread_id, created_at, status, state, reviewer, "
        "comments, updated_at FROM public.checkpoints LIMIT 0"
    ),
    (
        "SELECT approval_id, thread_id, checkpoint_id, action, order_id, amount, "
        "question, reviewer, comments, status, requested_at, resolved_at "
        "FROM public.approvals LIMIT 0"
    ),
    (
        "SELECT idempotency_key, workflow_run_id, step_name, business_id, status, "
        "result, created_at, updated_at FROM public.idempotency_keys LIMIT 0"
    ),
    "SELECT session_id, customer_id, created_at, updated_at FROM public.sessions LIMIT 0",
    (
        "SELECT id, thread_id, session_id, role, content, metadata, created_at "
        "FROM public.memory_items LIMIT 0"
    ),
    ("SELECT id, name, status, started_at, completed_at, summary FROM public.eval_runs LIMIT 0"),
    (
        "SELECT id, eval_run_id, case_id, passed, score, details, created_at "
        "FROM public.eval_results LIMIT 0"
    ),
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


def _is_azure_hosted_runtime() -> bool:
    return os.getenv("APP_ENV", "").strip().lower().startswith(("azure", "aca")) or os.getenv(
        "DB_SCHEMA_MANAGED_EXTERNALLY", ""
    ).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _azure_postgres_conninfo() -> str:
    host = os.getenv("AZURE_POSTGRES_HOST", "").strip()
    database = os.getenv("AZURE_POSTGRES_DATABASE", "").strip()
    user = os.getenv("AZURE_POSTGRES_USER", "").strip()
    if not host or not database or not user:
        raise RuntimeError(
            "AZURE_POSTGRES_HOST, AZURE_POSTGRES_DATABASE, and AZURE_POSTGRES_USER "
            "must be set for managed-identity PostgreSQL authentication."
        )

    token = DefaultAzureCredential().get_token(AZURE_POSTGRES_SCOPE).token
    return make_conninfo(
        host=host,
        port=os.getenv("AZURE_POSTGRES_PORT", "5432"),
        dbname=database,
        user=user,
        password=token,
        sslmode=os.getenv("AZURE_POSTGRES_SSLMODE", "require"),
    )


class AzurePostgresConnection(Connection[Any]):
    """Gets an Entra token whenever the pool opens a physical connection."""

    @classmethod
    def connect(cls, conninfo: str = "", **kwargs: Any) -> AzurePostgresConnection:
        return super().connect(_azure_postgres_conninfo(), **kwargs)


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
        return DEFAULT_DATABASE_URL

    @staticmethod
    def uses_azure_managed_identity() -> bool:
        return bool(os.getenv("AZURE_POSTGRES_HOST", "").strip())

    @property
    def pool_configuration(self) -> dict[str, int]:
        hosted = _is_azure_hosted_runtime()
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
            "max_lifetime": _integer_setting(
                "DB_POOL_MAX_LIFETIME_SECONDS",
                3300,
                minimum=1,
            ),
        }

    def get_pool(self) -> ObservedConnectionPool:
        with self._lock:
            if self._pool is None:
                options: dict[str, Any] = {
                    **self.pool_configuration,
                    "open": True,
                    "kwargs": {"autocommit": True, "row_factory": dict_row},
                }
                if self.uses_azure_managed_identity():
                    self._pool = ObservedConnectionPool(
                        ConnectionPool(
                            conninfo="",
                            connection_class=AzurePostgresConnection,
                            **options,
                        )
                    )
                else:
                    self._pool = ObservedConnectionPool(
                        ConnectionPool(conninfo=self.database_url, **options)
                    )
            return self._pool

    def ensure_schema(self) -> None:
        with self._lock:
            if self._schema_initialized:
                return
            pool = self.get_pool()
            if os.getenv("DB_SCHEMA_MANAGED_EXTERNALLY", "").strip().lower() in {
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
