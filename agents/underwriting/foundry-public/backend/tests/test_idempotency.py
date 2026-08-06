from __future__ import annotations

import asyncio

from app.core.config import load_settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.repositories.underwriting_repository import Repository
from app.main import resume_workflow, run_workflow
from app.modules.underwriting.models import UnderwritingApplication


def test_idempotency_prevents_duplicate_final_result_after_resume(monkeypatch) -> None:
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

    repo = Repository(engine)
    assert repo.count_underwriting_results_by_key("underwriting:app-idem-001:risk") == 1
    assert repo.count_underwriting_results_by_key("underwriting:app-idem-001:credit") == 1
    assert repo.count_underwriting_results_by_key("underwriting:app-idem-001:medical") == 1
    assert repo.count_underwriting_results_by_key("underwriting:app-idem-001:driving") == 1
    assert repo.count_underwriting_results_by_key("underwriting:app-idem-001:final-decision") == 1
