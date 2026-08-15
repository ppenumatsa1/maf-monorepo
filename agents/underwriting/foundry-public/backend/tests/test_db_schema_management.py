from __future__ import annotations

from dataclasses import replace

import pytest
from app.core import container
from app.core.config import load_settings
from app.infrastructure.db.engine import init_db
from app.infrastructure.db.tables import metadata
from sqlalchemy import create_engine, event


def test_external_schema_mode_validates_without_ddl() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    metadata.create_all(engine)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_statement(connection, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    init_db(engine, schema_managed_externally=True)

    ddl_prefixes = ("CREATE ", "ALTER ", "DROP ", "REINDEX ")
    assert not [
        statement for statement in statements if statement.lstrip().upper().startswith(ddl_prefixes)
    ]


def test_external_schema_mode_fails_closed_when_schema_is_missing() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    with pytest.raises(RuntimeError, match="Externally managed database schema is not ready"):
        init_db(engine, schema_managed_externally=True)


def test_restricted_runtime_startup_uses_external_schema_mode(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    metadata.create_all(engine)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_statement(connection, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    settings = replace(
        load_settings(),
        database_url="sqlite:///:memory:",
        db_schema_managed_externally=True,
        execution_mode="local",
    )
    monkeypatch.setattr(container, "create_db_engine", lambda _settings: engine)

    service = container.build_underwriting_service(settings)

    assert service.repository.engine is engine
    assert not [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "REINDEX "))
    ]
