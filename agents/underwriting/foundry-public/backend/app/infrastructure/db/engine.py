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


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    _migrate_workflow_runs(engine)


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
