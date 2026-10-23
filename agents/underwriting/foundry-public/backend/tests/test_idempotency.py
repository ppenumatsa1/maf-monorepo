from __future__ import annotations

import asyncio
from dataclasses import replace

from app.core.config import load_settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.runner import UnderwritingMafRunner
from app.main import resume_workflow, run_workflow
from app.modules.underwriting.models import OriginChannel, UnderwritingApplication


def test_idempotency_prevents_duplicate_final_result_after_resume(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'idempotency.db'}")
    settings = load_settings()
    engine = create_db_engine(settings)
    init_db(engine)
    reset_db(engine)

    run_id = "run-idem-001"
    app = UnderwritingApplication(
        application_id="app-idem-001",
        applicant_name="Idempotency Tester",
        age=45,
        income=100000,
        requested_coverage=550000,
        health_disclosures="none",
        driving_history="clean",
        credit_score=730,
    )

    monkeypatch.setenv("CRASH_AFTER_EXECUTOR", "medical_check")
    try:
        asyncio.run(run_workflow(workflow_run_id=run_id, app=app))
    except Exception:
        pass

    monkeypatch.setenv("CRASH_AFTER_EXECUTOR", "")
    asyncio.run(resume_workflow(run_id))

    repo = WorkflowRunRepository(engine)
    prefix = "underwriting:run-idem-001:app-idem-001"
    assert repo.count_underwriting_results_by_key(f"{prefix}:risk") == 1
    assert repo.count_underwriting_results_by_key(f"{prefix}:credit") == 1
    assert repo.count_underwriting_results_by_key(f"{prefix}:medical") == 1
    assert repo.count_underwriting_results_by_key(f"{prefix}:driving") == 1
    assert repo.count_underwriting_results_by_key(f"{prefix}:final-decision") == 1


def test_same_application_isolated_across_runs_inputs_and_origins(tmp_path) -> None:
    settings = replace(
        load_settings(),
        database_url=f"sqlite:///{tmp_path / 'two-runs.db'}",
        execution_mode="local",
    )
    engine = create_db_engine(settings)
    init_db(engine)
    repository = WorkflowRunRepository(engine)
    runner = UnderwritingMafRunner(repository, settings)
    application_id = "app-shared"

    first = UnderwritingApplication(
        application_id=application_id,
        applicant_name="First Input",
        age=38,
        income=145000,
        requested_coverage=500000,
        health_disclosures="none",
        driving_history="clean",
        credit_score=760,
    )
    second = UnderwritingApplication(
        application_id=application_id,
        applicant_name="Second Input",
        age=18,
        income=20000,
        requested_coverage=100000,
        health_disclosures="chronic condition",
        driving_history="DUI",
        credit_score=300,
    )

    asyncio.run(
        runner.start(
            workflow_run_id="run-shared-api",
            application=first,
            origin_channel=OriginChannel.API,
        )
    )
    asyncio.run(
        runner.start(
            workflow_run_id="run-shared-responses",
            application=second,
            origin_channel=OriginChannel.RESPONSES,
        )
    )

    first_results = repository.list_underwriting_results("run-shared-api")
    second_results = repository.list_underwriting_results("run-shared-responses")
    assert {row["result_json"]["workflow_run_id"] for row in first_results} == {"run-shared-api"}
    assert {row["result_json"]["workflow_run_id"] for row in second_results} == {
        "run-shared-responses"
    }
    assert {row["idempotency_key"] for row in first_results}.isdisjoint(
        {row["idempotency_key"] for row in second_results}
    )
    assert repository.get_workflow_origin_channel("run-shared-api") == OriginChannel.API
    assert repository.get_workflow_origin_channel("run-shared-responses") == OriginChannel.RESPONSES
    first_final = next(
        row["result_json"] for row in first_results if row["check_type"] == "final_decision"
    )
    second_final = next(
        row["result_json"] for row in second_results if row["check_type"] == "final_decision"
    )
    assert first_final["decision"] != second_final["decision"]
