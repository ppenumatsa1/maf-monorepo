from __future__ import annotations

from app.core.database import PostgresDatabase


def test_database_url_normalizes_psycopg_dialect(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://runtime:password@server.postgres.database.azure.com:5432/order_resolution?sslmode=require",
    )

    assert PostgresDatabase().database_url == (
        "postgresql://runtime:password@server.postgres.database.azure.com:5432/"
        "order_resolution?sslmode=require"
    )


def test_externally_managed_schema_skips_runtime_ddl(monkeypatch) -> None:
    database = PostgresDatabase()
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setattr(
        database,
        "get_pool",
        lambda: (_ for _ in ()).throw(AssertionError("runtime DDL is not allowed")),
    )

    database.ensure_schema()

    assert database._schema_initialized is True
