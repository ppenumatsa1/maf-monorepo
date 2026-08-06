from __future__ import annotations

import asyncio

from app.core.config import load_settings
from app.infrastructure.db.engine import create_db_engine, init_db, reset_db
from app.infrastructure.repositories.underwriting_repository import Repository
from app.main import run_workflow
from app.modules.underwriting.models import UnderwritingApplication


def test_fan_in_state_updates_one_result_at_a_time() -> None:
    settings = load_settings()
    engine = create_db_engine(settings)
    init_db(engine)
    reset_db(engine)

    app = UnderwritingApplication(
        application_id="app-fanin-001",
        applicant_name="Fan In Tester",
        age=41,
        income=120000,
        requested_coverage=400000,
        health_disclosures="none",
        driving_history="clean",
        credit_score=740,
    )
    run_id, _ = asyncio.run(run_workflow(workflow_run_id="run-fanin-001", app=app))

    repo = Repository(engine)
    state_entries = repo.list_business_state(run_id)
    aggregation = [row for row in state_entries if row["state_key"] == "aggregation_state"]
    assert aggregation, "aggregation_state should exist"
    latest = aggregation[-1]["state_json"]
    assert sorted(latest["expected_checks"]) == sorted(["risk", "credit", "medical", "driving"])
    assert sorted(latest["completed_checks"]) == sorted(["risk", "credit", "medical", "driving"])
    assert sorted(latest["child_results"].keys()) == sorted(
        ["risk", "credit", "medical", "driving"]
    )

    events = repo.list_events(run_id)
    fan_in_events = [e for e in events if e["event_type"] == "fan_in_result_received"]
    assert len(fan_in_events) == 4
    progression = [len(e["payload_json"]["completed_checks"]) for e in fan_in_events]
    assert progression == [1, 2, 3, 4]
