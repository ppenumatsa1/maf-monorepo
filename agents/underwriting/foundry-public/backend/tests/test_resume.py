from __future__ import annotations

import asyncio

from app.core.config import load_settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.main import resume_workflow, run_workflow
from app.modules.underwriting.models import UnderwritingApplication


def test_crash_then_resume_from_latest_maf_checkpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'resume.db'}")
    settings = load_settings()
    engine = create_db_engine(settings)
    init_db(engine)
    reset_db(engine)

    run_id = "run-resume-001"
    app = UnderwritingApplication(
        application_id="app-resume-001",
        applicant_name="Resume Tester",
        age=37,
        income=135000,
        requested_coverage=600000,
        health_disclosures="none",
        driving_history="minor speed ticket",
        credit_score=720,
    )

    monkeypatch.setenv("CRASH_AFTER_EXECUTOR", "medical_check")
    crashed = False
    try:
        asyncio.run(run_workflow(workflow_run_id=run_id, app=app))
    except Exception:
        crashed = True
    assert crashed, "run should crash for this scenario"

    repo = WorkflowRunRepository(engine)
    checkpoints_before = repo.list_checkpoints(run_id)
    assert checkpoints_before, "real MAF checkpoints should be present in postgres"

    monkeypatch.setenv("CRASH_AFTER_EXECUTOR", "")
    outputs = asyncio.run(resume_workflow(run_id))
    assert outputs, "resume should finish and produce outputs"
    checkpoints_after = repo.list_checkpoints(run_id)
    assert len(checkpoints_after) >= len(checkpoints_before)
