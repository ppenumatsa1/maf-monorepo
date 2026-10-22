from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from app.core import database
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
        "postgresql+psycopg://app:local@localhost:5432/maf_workflow",
    )

    assert database.PostgresDatabase().database_url == (
        "postgresql://app:local@localhost:5432/maf_workflow"
    )


def test_azure_postgres_conninfo_uses_fresh_entra_token(
    monkeypatch,
) -> None:
    issued_tokens = iter(("token-one", "token-two"))

    class Credential:
        def get_token(self, scope: str):
            assert scope == database.AZURE_POSTGRES_SCOPE
            return type("Token", (), {"token": next(issued_tokens)})()

    monkeypatch.setattr(database, "DefaultAzureCredential", Credential)
    monkeypatch.setenv("AZURE_POSTGRES_HOST", "server.postgres.database.azure.com")
    monkeypatch.setenv("AZURE_POSTGRES_DATABASE", "maf_workflow")
    monkeypatch.setenv("AZURE_POSTGRES_USER", "maf-backend")

    first = database._azure_postgres_conninfo()
    second = database._azure_postgres_conninfo()

    assert "password=token-one" in first
    assert "password=token-two" in second
    assert "sslmode=require" in first


def test_managed_identity_mode_requires_complete_postgres_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AZURE_POSTGRES_HOST", "server.postgres.database.azure.com")
    monkeypatch.delenv("AZURE_POSTGRES_DATABASE", raising=False)
    monkeypatch.delenv("AZURE_POSTGRES_USER", raising=False)

    try:
        database._azure_postgres_conninfo()
    except RuntimeError as exc:
        assert "AZURE_POSTGRES_HOST" in str(exc)
    else:
        raise AssertionError("Expected managed-identity configuration validation to fail.")


def test_managed_identity_mode_is_selected_only_with_azure_host(
    monkeypatch,
) -> None:
    monkeypatch.delenv("AZURE_POSTGRES_HOST", raising=False)
    assert database.PostgresDatabase.uses_azure_managed_identity() is False

    monkeypatch.setenv("AZURE_POSTGRES_HOST", "server.postgres.database.azure.com")
    assert database.PostgresDatabase.uses_azure_managed_identity() is True


def test_connection_pool_does_not_retain_minimum_idle_connections(monkeypatch) -> None:
    created: list[dict[str, object]] = []

    class Pool:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

    monkeypatch.setattr(database, "ConnectionPool", Pool)
    monkeypatch.setenv("APP_ENV", "azure-apphosted")

    database.PostgresDatabase().get_pool()

    assert created[0]["min_size"] == 0
    assert created[0]["max_size"] == 2
    assert created[0]["max_idle"] == 30


def test_pool_configuration_supports_validated_overrides(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "4")
    monkeypatch.setenv("DB_POOL_MAX_IDLE_SECONDS", "45")
    monkeypatch.setenv("DB_POOL_MAX_LIFETIME_SECONDS", "3000")

    assert database.PostgresDatabase().pool_configuration == {
        "min_size": 2,
        "max_size": 4,
        "max_idle": 45,
        "max_lifetime": 3000,
    }


def test_pool_configuration_rejects_invalid_range(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "3")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "2")

    with pytest.raises(
        RuntimeError,
        match="DB_POOL_MAX_SIZE must be at least DB_POOL_MIN_SIZE",
    ):
        _ = database.PostgresDatabase().pool_configuration


def test_managed_identity_pool_keeps_fresh_token_connection_class(monkeypatch) -> None:
    created: list[dict[str, object]] = []

    class Pool:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

    monkeypatch.setattr(database, "ConnectionPool", Pool)
    monkeypatch.setenv("AZURE_POSTGRES_HOST", "server.postgres.database.azure.com")

    database.PostgresDatabase().get_pool()

    assert created[0]["conninfo"] == ""
    assert created[0]["connection_class"] is database.AzurePostgresConnection


def test_externally_managed_schema_validates_azure_tables_without_ddl(
    monkeypatch,
) -> None:
    instance = database.PostgresDatabase()
    cursor = RecordingCursor()
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setattr(instance, "get_pool", lambda: RecordingPool(cursor))

    instance.ensure_schema()

    assert cursor.executed == list(database.EXTERNAL_SCHEMA_VALIDATION_QUERIES)
    assert all("CREATE " not in statement for statement in cursor.executed)
    assert all("ALTER " not in statement for statement in cursor.executed)
    validation_sql = " ".join(cursor.executed)
    assert "responses_dispatches" not in validation_sql
    assert "teams_card_actions" not in validation_sql
    assert "origin_channel" not in validation_sql
    assert instance._schema_initialized is True


def test_restartable_pool_reopens_after_shutdown(monkeypatch) -> None:
    created: list[RecordingPool] = []

    class Pool(RecordingPool):
        def __init__(self, **_kwargs: object) -> None:
            super().__init__(RecordingCursor())
            created.append(self)

    monkeypatch.setattr(database, "ConnectionPool", Pool)
    monkeypatch.delenv("AZURE_POSTGRES_HOST", raising=False)
    instance = database.PostgresDatabase()

    with instance.pool.connection():
        pass
    instance.close()
    with instance.pool.connection():
        pass

    assert len(created) == 2
    assert created[0].closed is True
    assert created[1].closed is False


def test_observed_pool_emits_safe_postgres_client_span(monkeypatch) -> None:
    cursor = RecordingCursor()
    span = RecordingSpan()
    tracer = RecordingTracer(span)
    monkeypatch.setattr(database, "get_tracer", lambda _name: tracer)

    with database.ObservedConnectionPool(RecordingPool(cursor)).connection() as conn:
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
    monkeypatch.setattr(database, "get_tracer", lambda _name: tracer)

    with pytest.raises(RuntimeError, match="query and parameter content"):
        with database.ObservedConnectionPool(FailingPool()).connection():  # type: ignore[arg-type]
            pass

    assert span.status_codes == [StatusCode.ERROR]
    assert span.events == [("database.error", {"exception.type": "RuntimeError"})]
