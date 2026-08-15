from __future__ import annotations

from azure.identity import DefaultAzureCredential
from sqlalchemy import create_engine, delete, event, inspect, text
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.infrastructure.db.tables import (
    business_state,
    idempotency_records,
    maf_checkpoints,
    metadata,
    underwriting_results,
    workflow_events,
    workflow_runs,
)


def create_db_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.db_url, future=True, pool_pre_ping=True)
    if settings.db_auth_mode.lower() not in {"managed_identity", "entra"}:
        return engine

    credential = DefaultAzureCredential(
        managed_identity_client_id=settings.azure_client_id or None,
    )

    @event.listens_for(engine, "do_connect")
    def provide_postgres_access_token(
        dialect, connection_record, connection_args, connection_params
    ) -> None:
        connection_params["password"] = credential.get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        ).token

    return engine


def init_db(engine: Engine, *, schema_managed_externally: bool = False) -> None:
    if schema_managed_externally:
        assert_schema_ready(engine)
        return
    metadata.create_all(engine)
    _migrate_workflow_runs(engine)


def assert_schema_ready(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(metadata.tables) - existing_tables)
    missing_columns: list[str] = []
    missing_indexes: list[str] = []

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns.extend(
            f"{table.name}.{column.name}"
            for column in table.columns
            if column.name not in existing_columns
        )
        existing_indexes = {
            index["name"] for index in inspector.get_indexes(table.name) if index.get("name")
        }
        missing_indexes.extend(
            f"{table.name}.{index.name}"
            for index in table.indexes
            if index.name and index.name not in existing_indexes
        )

    if missing_tables or missing_columns or missing_indexes:
        details = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(missing_tables)}")
        if missing_columns:
            details.append(f"missing columns: {', '.join(sorted(missing_columns))}")
        if missing_indexes:
            details.append(f"missing indexes: {', '.join(sorted(missing_indexes))}")
        raise RuntimeError("Externally managed database schema is not ready; " + "; ".join(details))


def _migrate_workflow_runs(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("workflow_runs")}
    if "applicant_name" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE workflow_runs ADD COLUMN applicant_name VARCHAR(256)"))
    for index in workflow_runs.indexes:
        index.create(engine, checkfirst=True)


def reset_db(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in [
            maf_checkpoints,
            idempotency_records,
            workflow_events,
            underwriting_results,
            business_state,
            workflow_runs,
        ]:
            conn.execute(delete(table))
