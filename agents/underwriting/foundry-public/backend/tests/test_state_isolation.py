from types import SimpleNamespace

import app.maf.runner as runner_module
from app.core.config import Settings
from app.infrastructure.db.engine import create_db_engine
from app.maf.runner import UnderwritingMafRunner


def test_build_workflow_uses_fresh_dependencies_for_each_build(monkeypatch) -> None:
    settings = Settings(
        db_host="localhost",
        db_port=5432,
        db_name="underwriting",
        db_user="underwriting",
        db_password="underwriting",
        log_level="INFO",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=200,
        retry_jitter_ms=100,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
    )

    created_clients = []
    created_storages = []
    seen = []

    def fake_create_foundry_client(_settings):
        client = object()
        created_clients.append(client)
        return client

    def fake_checkpoint_storage(_engine):
        storage = object()
        created_storages.append(storage)
        return storage

    def fake_build_parent_underwriting_workflow(
        *, repository, settings, checkpoint_storage, foundry_client
    ):
        seen.append((id(checkpoint_storage), id(foundry_client)))
        return object()

    monkeypatch.setattr(runner_module, "create_foundry_maf_client", fake_create_foundry_client)
    monkeypatch.setattr(runner_module, "PostgresCheckpointStorage", fake_checkpoint_storage)
    monkeypatch.setattr(
        runner_module,
        "build_parent_underwriting_workflow",
        fake_build_parent_underwriting_workflow,
    )

    runner = UnderwritingMafRunner(SimpleNamespace(engine=object()), settings)

    runner._build_workflow(settings)
    runner._build_workflow(settings)

    assert len(created_clients) >= 2, "each workflow build should create its own foundry client"
    assert len(created_storages) >= 2, (
        "each workflow build should create its own checkpoint storage"
    )
    assert len({checkpoint_id for checkpoint_id, _ in seen}) == 2
    assert len({foundry_id for _, foundry_id in seen}) == 2


def test_entra_database_mode_registers_managed_identity_authentication() -> None:
    settings = Settings(
        db_host="localhost",
        db_port=5432,
        db_name="underwriting",
        db_user="underwriting",
        db_password="underwriting",
        log_level="INFO",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=200,
        retry_jitter_ms=100,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        db_auth_mode="entra",
    )

    engine = create_db_engine(settings)

    assert any(
        listener.__name__ == "provide_postgres_access_token"
        for listener in engine.dialect.dispatch.do_connect
    )
