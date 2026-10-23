from __future__ import annotations

import importlib.util
import os
from dataclasses import replace
from pathlib import Path

import pytest
from app.core import container
from app.core.config import load_settings
from app.infrastructure.db.engine import (
    assert_schema_ready,
    close_db_engine,
    create_db_engine,
    get_runtime_db_engine,
    init_db,
)
from app.infrastructure.db.tables import metadata, teams_card_actions
from sqlalchemy import create_engine, event, inspect, text

DDL_GENERATOR_PATH = (
    Path(__file__).parents[2] / "scripts" / "foundry" / "generate_postgres_schema_ddl.py"
)
DDL_SPEC = importlib.util.spec_from_file_location(
    "generate_postgres_schema_ddl", DDL_GENERATOR_PATH
)
assert DDL_SPEC and DDL_SPEC.loader
ddl_generator = importlib.util.module_from_spec(DDL_SPEC)
DDL_SPEC.loader.exec_module(ddl_generator)


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


def test_external_schema_mode_fails_closed_when_required_index_is_missing() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_teams_card_actions_checkpoint_status"))

    with pytest.raises(
        RuntimeError,
        match="teams_card_actions.ix_teams_card_actions_checkpoint_status",
    ):
        assert_schema_ready(engine)


def test_runtime_migration_adds_review_columns_tables_and_indexes_idempotently() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE workflow_runs (
                id VARCHAR(64) PRIMARY KEY,
                maf_workflow_id VARCHAR(128) NOT NULL,
                workflow_type VARCHAR(128) NOT NULL,
                application_id VARCHAR(128) NOT NULL,
                status VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )

    init_db(engine)
    init_db(engine)

    inspector = inspect(engine)
    workflow_columns = {column["name"] for column in inspector.get_columns("workflow_runs")}
    assert {
        "applicant_name",
        "origin_channel",
        "machine_recommendation",
    } <= workflow_columns
    assert {"underwriting_approvals", "teams_card_actions"} <= set(inspector.get_table_names())
    assert {index["name"] for index in inspector.get_indexes(teams_card_actions.name)} >= {
        "ix_teams_card_actions_checkpoint_status",
        "ix_teams_card_actions_batch_status",
        "ix_teams_card_actions_expiry_status",
    }
    assert_schema_ready(engine)


@pytest.mark.skipif(
    not os.getenv("UNDERWRITING_TEST_POSTGRES_URL"),
    reason="UNDERWRITING_TEST_POSTGRES_URL is required for the real PostgreSQL migration",
)
def test_generated_postgres_ddl_upgrades_legacy_schema_idempotently() -> None:
    engine = create_engine(os.environ["UNDERWRITING_TEST_POSTGRES_URL"], future=True)
    table_names = ", ".join(f'public."{name}"' for name in reversed(list(metadata.tables)))
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_names} CASCADE"))
            conn.exec_driver_sql(
                """
                    CREATE TABLE workflow_runs (
                        id VARCHAR(64) PRIMARY KEY,
                        maf_workflow_id VARCHAR(128) NOT NULL,
                        workflow_type VARCHAR(128) NOT NULL,
                        application_id VARCHAR(128) NOT NULL,
                        status VARCHAR(64) NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    );
                    CREATE TABLE maf_checkpoints (
                        id SERIAL PRIMARY KEY,
                        workflow_run_id VARCHAR(64) NOT NULL,
                        workflow_id VARCHAR(128) NOT NULL,
                        checkpoint_id VARCHAR(128) NOT NULL UNIQUE,
                        checkpoint_json JSONB NOT NULL,
                        metadata_json JSONB NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    );
                    CREATE TABLE underwriting_approvals (
                        approval_id VARCHAR(64) PRIMARY KEY,
                        workflow_run_id VARCHAR(64) NOT NULL
                            REFERENCES workflow_runs(id) ON DELETE CASCADE,
                        checkpoint_id VARCHAR(128) NOT NULL
                            REFERENCES maf_checkpoints(checkpoint_id) ON DELETE CASCADE,
                        reviewer_outcome VARCHAR(64),
                        reviewer_hash VARCHAR(64)
                    );
                    INSERT INTO workflow_runs VALUES (
                        'run-legacy', 'workflow', 'underwriting-parent', 'app-legacy',
                        'PENDING_REVIEW', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                    INSERT INTO maf_checkpoints (
                        workflow_run_id, workflow_id, checkpoint_id,
                        checkpoint_json, metadata_json, created_at
                    ) VALUES (
                        'run-legacy', 'workflow', 'checkpoint-legacy',
                        '{}', '{}', CURRENT_TIMESTAMP
                    );
                    INSERT INTO underwriting_approvals VALUES (
                        'approval-legacy', 'run-legacy', 'checkpoint-legacy',
                        'APPROVED', 'legacy-reviewer-hash'
                    )
                    """
            )
            ddl = ddl_generator.build_ddl()
            conn.exec_driver_sql(ddl)
            conn.exec_driver_sql(ddl)

            workflow = conn.execute(
                text(
                    "SELECT origin_channel, machine_recommendation "
                    "FROM workflow_runs WHERE id = 'run-legacy'"
                )
            ).one()
            approval = conn.execute(
                text(
                    "SELECT request_id, origin_channel, status, reviewer_type, "
                    "requested_at, created_at, updated_at "
                    "FROM underwriting_approvals "
                    "WHERE approval_id = 'approval-legacy'"
                )
            ).one()

        inspector = inspect(engine)
        assert workflow == ("api", None)
        assert approval[:4] == (
            "legacy:checkpoint-legacy",
            "api",
            "completed",
            "unknown_legacy",
        )
        assert all(value is not None for value in approval[4:])
        assert {"underwriting_approvals", "teams_card_actions"} <= set(inspector.get_table_names())
        assert {
            "ix_underwriting_approvals_run_status",
            "ix_underwriting_approvals_checkpoint_status",
            "ix_underwriting_approvals_run_origin_status",
        } <= {index["name"] for index in inspector.get_indexes("underwriting_approvals")}
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_names} CASCADE"))
        engine.dispose()


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
    monkeypatch.setattr(container, "get_runtime_db_engine", lambda _settings: engine)

    service = container.build_underwriting_service(settings)

    assert service.repository.engine is engine
    assert not [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "REINDEX "))
    ]


def test_hosted_postgres_pool_is_lazy_bounded_and_recycles_connections() -> None:
    settings = replace(
        load_settings(),
        database_url="postgresql+psycopg://user:password@localhost:5432/underwriting",
        db_pool_size=2,
        db_max_overflow=0,
        db_pool_recycle_seconds=30,
    )

    engine = create_db_engine(settings)
    try:
        assert engine.pool.size() == 2
        assert engine.pool.checkedout() == 0
        assert engine.pool.overflow() == -2
        assert engine.pool._max_overflow == 0
        assert engine.pool._recycle == 30
    finally:
        engine.dispose()


def test_external_postgres_runtime_reuses_single_engine() -> None:
    settings = replace(
        load_settings(),
        database_url="postgresql+psycopg://user:password@localhost:5432/underwriting",
        db_schema_managed_externally=True,
        db_pool_size=2,
        db_max_overflow=0,
        db_pool_recycle_seconds=30,
    )

    first = get_runtime_db_engine(settings)
    second = get_runtime_db_engine(settings)
    try:
        assert first is second
    finally:
        close_db_engine(first)


def test_hosted_pool_configuration_uses_min_zero_max_two_idle_thirty(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "foundry-public")
    monkeypatch.delenv("DB_POOL_MIN_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_MAX_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("DB_POOL_MAX_IDLE_SECONDS", raising=False)
    monkeypatch.delenv("DB_POOL_RECYCLE_SECONDS", raising=False)

    settings = load_settings()

    assert settings.db_pool_min_size == 0
    assert settings.db_pool_size == 2
    assert settings.db_max_overflow == 0
    assert settings.db_pool_recycle_seconds == 30


def test_nonzero_pool_minimum_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "1")

    with pytest.raises(RuntimeError, match="must be 0"):
        load_settings()


def test_sqlite_keeps_safe_local_pool_defaults() -> None:
    settings = replace(
        load_settings(),
        database_url="sqlite:///:memory:",
        db_pool_size=2,
        db_max_overflow=0,
        db_pool_recycle_seconds=30,
    )

    engine = create_db_engine(settings)
    try:
        assert not hasattr(engine.pool, "_max_overflow")
    finally:
        engine.dispose()
