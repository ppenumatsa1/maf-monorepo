from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from app.core import database as database_module
from app.core.database import (
    EXTERNAL_SCHEMA_VALIDATION_QUERIES,
    ObservedConnectionPool,
    PostgresDatabase,
)
from opentelemetry.trace import SpanKind, StatusCode


class RecordingCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def __enter__(self) -> RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.executed.append(statement)


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> RecordingCursor:
        return self._cursor


class RecordingPool:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._connection = RecordingConnection(cursor)
        self.closed = False

    @contextmanager
    def connection(self):
        yield self._connection

    def close(self) -> None:
        self.closed = True


class RecordingSpan:
    def __init__(self) -> None:
        self.status_codes: list[StatusCode] = []
        self.events: list[tuple[str, dict[str, Any]]] = []

    def set_status(self, status: Any) -> None:
        self.status_codes.append(status.status_code)

    def add_event(self, name: str, attributes: dict[str, Any]) -> None:
        self.events.append((name, attributes))


class RecordingTracer:
    def __init__(self, span: RecordingSpan) -> None:
        self.span = span
        self.calls: list[dict[str, Any]] = []

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any):
        self.calls.append({"name": name, **kwargs})
        yield self.span


def test_database_url_normalizes_psycopg_dialect(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://runtime:password@server.postgres.database.azure.com:5432/order_resolution?sslmode=require",
    )

    assert PostgresDatabase().database_url == (
        "postgresql://runtime:password@server.postgres.database.azure.com:5432/"
        "order_resolution?sslmode=require"
    )


@pytest.mark.parametrize("app_env", ["foundry-public", "aca-public"])
def test_hosted_pool_releases_idle_connections(monkeypatch, app_env: str) -> None:
    monkeypatch.setenv("APP_ENV", app_env)

    assert PostgresDatabase().pool_configuration == {
        "min_size": 0,
        "max_size": 2,
        "max_idle": 30,
    }


def test_pool_configuration_supports_validated_overrides(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "4")
    monkeypatch.setenv("DB_POOL_MAX_IDLE_SECONDS", "45")

    assert PostgresDatabase().pool_configuration == {
        "min_size": 2,
        "max_size": 4,
        "max_idle": 45,
    }


def test_pool_configuration_rejects_invalid_range(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "3")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "2")

    with pytest.raises(
        RuntimeError,
        match="DB_POOL_MAX_SIZE must be at least DB_POOL_MIN_SIZE",
    ):
        _ = PostgresDatabase().pool_configuration


def test_externally_managed_schema_validates_connectivity_and_schema_without_ddl(
    monkeypatch,
) -> None:
    database = PostgresDatabase()
    cursor = RecordingCursor()
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setattr(database, "get_pool", lambda: RecordingPool(cursor))

    database.ensure_schema()

    assert cursor.executed == list(EXTERNAL_SCHEMA_VALIDATION_QUERIES)
    assert all("CREATE " not in statement for statement in cursor.executed)
    assert all("ALTER " not in statement for statement in cursor.executed)
    assert database._schema_initialized is True


def test_close_retires_pool_and_allows_clean_restart() -> None:
    database = PostgresDatabase()
    pool = RecordingPool(RecordingCursor())
    database._pool = pool  # type: ignore[assignment]
    database._schema_initialized = True

    database.close()

    assert pool.closed is True
    assert database._pool is None
    assert database._schema_initialized is False


def test_schema_contains_idempotent_multichannel_migrations() -> None:
    schema = (Path(__file__).parents[1] / "app/sql/schema.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS origin_channel" in schema
    assert "ADD COLUMN IF NOT EXISTS batch_id UUID" in schema
    assert "UPDATE teams_card_actions\nSET batch_id = gen_random_uuid()" in schema
    assert "DROP CONSTRAINT IF EXISTS teams_card_actions_status_check" in schema
    assert "'processing'" in schema


def test_observed_pool_emits_safe_postgres_client_span(monkeypatch) -> None:
    cursor = RecordingCursor()
    span = RecordingSpan()
    tracer = RecordingTracer(span)
    monkeypatch.setattr(database_module, "get_tracer", lambda _name: tracer)

    with ObservedConnectionPool(RecordingPool(cursor)).connection() as conn:
        conn.cursor().execute("SELECT customer_secret FROM private_table")

    assert tracer.calls == [
        {
            "name": "postgresql.connection",
            "kind": SpanKind.CLIENT,
            "attributes": {
                "db.system": "postgresql",
                "db.system.name": "postgresql",
                "db.operation.name": "connection",
            },
            "record_exception": False,
            "set_status_on_exception": False,
        }
    ]
    assert span.status_codes == [StatusCode.OK]
    assert span.events == []
    assert "customer_secret" not in str(tracer.calls)


def test_observed_pool_records_only_exception_type(monkeypatch) -> None:
    class FailingPool:
        @contextmanager
        def connection(self):
            raise RuntimeError("query and parameter content")
            yield

    span = RecordingSpan()
    tracer = RecordingTracer(span)
    monkeypatch.setattr(database_module, "get_tracer", lambda _name: tracer)

    with pytest.raises(RuntimeError, match="query and parameter content"):
        with ObservedConnectionPool(FailingPool()).connection():  # type: ignore[arg-type]
            pass

    assert span.status_codes == [StatusCode.ERROR]
    assert span.events == [("database.error", {"exception.type": "RuntimeError"})]
