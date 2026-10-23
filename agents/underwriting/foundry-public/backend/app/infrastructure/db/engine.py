from __future__ import annotations

from threading import RLock

from azure.identity import DefaultAzureCredential
from sqlalchemy import create_engine, delete, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from app.core.config import Settings
from app.infrastructure.db.tables import (
    business_state,
    idempotency_records,
    maf_checkpoints,
    metadata,
    teams_card_actions,
    underwriting_approvals,
    underwriting_results,
    workflow_events,
    workflow_runs,
)

_runtime_engine_lock = RLock()
_schema_init_lock = RLock()
_runtime_engines: dict[tuple[object, ...], Engine] = {}


def create_db_engine(settings: Settings) -> Engine:
    engine_options: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if make_url(settings.db_url).get_backend_name() == "postgresql":
        engine_options.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle_seconds,
            pool_use_lifo=True,
        )
    engine = create_engine(settings.db_url, **engine_options)
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

    engine._underwriting_azure_credential = credential  # type: ignore[attr-defined]
    return engine


def get_runtime_db_engine(settings: Settings) -> Engine:
    if (
        make_url(settings.db_url).get_backend_name() != "postgresql"
        or not settings.db_schema_managed_externally
    ):
        return create_db_engine(settings)
    key = (
        settings.db_url,
        settings.db_auth_mode.lower(),
        settings.azure_client_id,
        settings.db_pool_min_size,
        settings.db_pool_size,
        settings.db_max_overflow,
        settings.db_pool_recycle_seconds,
    )
    with _runtime_engine_lock:
        engine = _runtime_engines.get(key)
        if engine is None:
            engine = create_db_engine(settings)
            _runtime_engines[key] = engine
        return engine


def init_db(engine: Engine, *, schema_managed_externally: bool = False) -> None:
    with _schema_init_lock:
        requested_mode = "external" if schema_managed_externally else "managed"
        if getattr(engine, "_underwriting_schema_mode", None) == requested_mode:
            return
        if schema_managed_externally:
            assert_schema_ready(engine)
        else:
            metadata.create_all(engine)
            _migrate_runtime_schema(engine)
        engine._underwriting_schema_mode = requested_mode  # type: ignore[attr-defined]


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


def _migrate_runtime_schema(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("workflow_runs")}
    additions = {
        "applicant_name": "VARCHAR(256)",
        "origin_channel": "VARCHAR(32) NOT NULL DEFAULT 'api'",
        "machine_recommendation": "VARCHAR(64)",
    }
    with engine.begin() as conn:
        for column_name, column_type in additions.items():
            if column_name in columns:
                continue
            conn.execute(text(f"ALTER TABLE workflow_runs ADD COLUMN {column_name} {column_type}"))
    approval_columns = {
        column["name"] for column in inspect(engine).get_columns("underwriting_approvals")
    }
    approval_additions = {
        "request_id": "VARCHAR(128)",
        "origin_channel": "VARCHAR(32) NOT NULL DEFAULT 'api'",
        "reviewer_type": "VARCHAR(32)",
    }
    with engine.begin() as conn:
        for column_name, column_type in approval_additions.items():
            if column_name in approval_columns:
                continue
            conn.execute(
                text(f"ALTER TABLE underwriting_approvals ADD COLUMN {column_name} {column_type}")
            )
        conn.execute(
            text(
                "UPDATE underwriting_approvals "
                "SET request_id = 'legacy:' || checkpoint_id "
                "WHERE request_id IS NULL"
            )
        )
    for table in metadata.sorted_tables:
        for index in table.indexes:
            index.create(engine, checkfirst=True)


def close_db_engine(engine: Engine) -> None:
    with _runtime_engine_lock:
        for key, runtime_engine in list(_runtime_engines.items()):
            if runtime_engine is engine:
                del _runtime_engines[key]
    engine.dispose()
    if hasattr(engine, "_underwriting_schema_mode"):
        delattr(engine, "_underwriting_schema_mode")
    credential = getattr(engine, "_underwriting_azure_credential", None)
    if credential is not None:
        credential.close()
        delattr(engine, "_underwriting_azure_credential")


def reset_db(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in [
            teams_card_actions,
            underwriting_approvals,
            maf_checkpoints,
            idempotency_records,
            workflow_events,
            underwriting_results,
            business_state,
            workflow_runs,
        ]:
            conn.execute(delete(table))
