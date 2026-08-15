from __future__ import annotations

from contextlib import contextmanager

from app.core.database import PostgresDatabase


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


def test_database_url_normalizes_psycopg_dialect(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "******server.postgres.database.azure.com:5432/order_resolution?sslmode=require",
    )

    assert PostgresDatabase().database_url == (
        "******server.postgres.database.azure.com:5432/order_resolution?sslmode=require"
    )


def test_externally_managed_schema_verifies_connectivity_without_ddl(monkeypatch) -> None:
    database = PostgresDatabase()
    cursor = RecordingCursor()
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setattr(database, "get_pool", lambda: RecordingPool(cursor))

    database.ensure_schema()

    assert cursor.executed == ["SELECT 1"]
    assert cursor.fetchone_calls == 1
    assert database._schema_initialized is True
