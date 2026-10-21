from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from app.core import database as database_module
from app.core.database import ObservedConnectionPool, PostgresDatabase
from opentelemetry.trace import SpanKind, StatusCode


class RecordingCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.fetchone_calls = 0

    def __enter__(self) -> RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def fetchone(self) -> tuple[int]:
        self.fetchone_calls += 1
        return (1,)


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> RecordingCursor:
        return self._cursor


class RecordingPool:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._connection = RecordingConnection(cursor)

    @contextmanager
    def connection(self):
        yield self._connection


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
        "******server.postgres.database.azure.com:5432/order_resolution?sslmode=require",
    )

    assert PostgresDatabase().database_url == (
        "******server.postgres.database.azure.com:5432/order_resolution?sslmode=require"
    )


def test_foundry_hosted_pool_releases_idle_connections(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "foundry-private")

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


def test_externally_managed_schema_verifies_connectivity_without_ddl(monkeypatch) -> None:
    database = PostgresDatabase()
    cursor = RecordingCursor()
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setattr(database, "get_pool", lambda: RecordingPool(cursor))

    database.ensure_schema()

    assert cursor.executed == ["SELECT 1"]
    assert cursor.fetchone_calls == 1
    assert database._schema_initialized is True


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
        with ObservedConnectionPool(FailingPool()).connection():
            pass

    assert span.status_codes == [StatusCode.ERROR]
    assert span.events == [
        ("database.error", {"exception.type": "RuntimeError"})
    ]
