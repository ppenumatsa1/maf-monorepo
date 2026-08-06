from __future__ import annotations

from datetime import datetime, timedelta

from app.infrastructure.db.engine import init_db
from app.infrastructure.db.tables import maf_checkpoints
from app.infrastructure.repositories.underwriting_repository import Repository
from sqlalchemy import create_engine, inspect, text


def test_history_searches_filters_and_sorts_newest_first() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    repo = Repository(engine)

    repo.create_workflow_run(
        "run-older",
        "workflow",
        "underwriting-parent",
        "app-older",
        "Grace Hopper",
    )
    repo.create_workflow_run(
        "run-newer",
        "workflow",
        "underwriting-parent",
        "app-newer",
        "Ada Lovelace",
    )
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE workflow_runs SET created_at = :created WHERE id = :run_id"),
            {"created": datetime.utcnow() - timedelta(minutes=5), "run_id": "run-older"},
        )
        conn.execute(
            maf_checkpoints.insert().values(
                workflow_run_id="run-newer",
                workflow_id="workflow",
                checkpoint_id="checkpoint-newer",
                checkpoint_json={},
                metadata_json={},
                created_at=datetime.utcnow(),
            )
        )
    repo.update_workflow_run_status("run-newer", "CRASHED")
    repo.save_underwriting_result(
        "run-older",
        "app-older",
        "final_decision",
        {"decision": "APPROVED"},
        "underwriting:app-older:final-decision",
    )

    total, items = repo.list_workflow_runs(search=None, status=None, limit=25, offset=0)

    assert total == 2
    assert [item["workflow_run_id"] for item in items] == ["run-newer", "run-older"]
    assert items[0]["resumable"] is True
    assert items[1]["final_decision"] == "APPROVED"

    total, items = repo.list_workflow_runs(search="ada", status=None, limit=25, offset=0)
    assert total == 1
    assert items[0]["workflow_run_id"] == "run-newer"

    total, items = repo.list_workflow_runs(search=None, status="crashed", limit=25, offset=0)
    assert total == 1
    assert items[0]["workflow_run_id"] == "run-newer"


def test_init_db_adds_history_search_column_to_legacy_database() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
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
        )

    init_db(engine)

    assert "applicant_name" in {
        column["name"] for column in inspect(engine).get_columns("workflow_runs")
    }
