from __future__ import annotations

import asyncio

import pytest
from app.core.config import Settings
from app.infrastructure.db.engine import create_db_engine, init_db
from app.infrastructure.db.tables import maf_checkpoints
from app.infrastructure.persistence.workflow_run_repository import (
    ApprovalDecisionError,
    WorkflowRunRepository,
)
from app.maf.runner import UnderwritingMafRunner
from app.modules.underwriting.models import (
    Decision,
    OriginChannel,
    ReviewerOutcome,
    UnderwritingApplication,
)
from app.modules.underwriting.projections import project_workflow_run


def _settings(tmp_path, name: str) -> Settings:
    return Settings(
        db_host="",
        db_port=0,
        db_name="",
        db_user="",
        db_password="",
        log_level="WARNING",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_jitter_ms=0,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        database_url=f"sqlite:///{tmp_path / name}",
        execution_mode="local",
    )


def _application(application_id: str) -> UnderwritingApplication:
    return UnderwritingApplication(
        application_id=application_id,
        applicant_name="Sensitive Applicant",
        age=20,
        income=50_000,
        requested_coverage=100_000,
        health_disclosures="none",
        driving_history="accident",
        credit_score=650,
    )


def _runtime(tmp_path, name: str):
    settings = _settings(tmp_path, name)
    engine = create_db_engine(settings)
    init_db(engine)
    repository = WorkflowRunRepository(engine)
    return engine, repository, UnderwritingMafRunner(repository, settings)


@pytest.mark.parametrize(
    "decision",
    [
        Decision.APPROVED,
        Decision.APPROVED_WITH_CONDITIONS,
        Decision.DECLINED,
    ],
)
def test_automatic_recommendations_are_terminal_without_review(
    monkeypatch, tmp_path, decision: Decision
) -> None:
    monkeypatch.setattr(
        "app.maf.executors.final_decision.compute_decision",
        lambda *_args, **_kwargs: decision,
    )
    _, repository, runner = _runtime(tmp_path, f"automatic-{decision.value}.db")
    run_id = f"run-automatic-{decision.value.lower()}"

    _, outputs = asyncio.run(
        runner.start(
            workflow_run_id=run_id,
            application=_application(f"app-{decision.value.lower()}"),
            origin_channel=OriginChannel.API,
        )
    )

    assert repository.get_workflow_run(run_id)["status"] == "COMPLETED"
    assert repository.get_review_projection(run_id) is None
    assert outputs[0].decision == decision


@pytest.mark.parametrize("outcome", list(ReviewerOutcome))
def test_referral_pauses_and_structured_decision_resumes(
    tmp_path, outcome: ReviewerOutcome
) -> None:
    engine, repository, runner = _runtime(tmp_path, f"review-{outcome.value}.db")
    run_id = f"run-review-{outcome.value.lower()}"

    _, outputs = asyncio.run(
        runner.start(
            workflow_run_id=run_id,
            application=_application(f"app-review-{outcome.value.lower()}"),
            origin_channel=OriginChannel.API,
        )
    )

    review = repository.get_review_projection(run_id)
    assert outputs == []
    assert repository.get_workflow_run(run_id)["status"] == "PENDING_REVIEW"
    assert review is not None
    assert review["machine_recommendation"] == "REFER_TO_HUMAN_UNDERWRITER"
    assert review["reviewer_outcome"] is None

    resumed = asyncio.run(
        runner.decide_review(
            workflow_run_id=run_id,
            checkpoint_id=review["checkpoint_id"],
            outcome=outcome,
            reviewer_id="authorized-reviewer",
            origin_channel=OriginChannel.API,
        )
    )

    persisted = WorkflowRunRepository(engine)
    resolved = persisted.get_review_projection(run_id)
    projection = project_workflow_run(
        persisted,
        run_id,
        fallback_status="COMPLETED",
        outputs=resumed,
    )
    assert persisted.get_workflow_run(run_id)["machine_recommendation"] == (
        "REFER_TO_HUMAN_UNDERWRITER"
    )
    assert resolved is not None
    assert resolved["status"] == "completed"
    assert resolved["reviewer_outcome"] == outcome.value
    assert projection["machine_recommendation"] == "REFER_TO_HUMAN_UNDERWRITER"
    assert projection["reviewer_outcome"] == outcome.value
    assert "Sensitive Applicant" not in str(resolved)


def test_review_requires_exact_current_checkpoint_and_matching_origin(tmp_path) -> None:
    _, repository, runner = _runtime(tmp_path, "review-binding.db")
    run_id = "run-review-binding"
    asyncio.run(
        runner.start(
            workflow_run_id=run_id,
            application=_application("app-review-binding"),
            origin_channel=OriginChannel.RESPONSES,
        )
    )
    review = repository.get_review_projection(run_id)
    assert review is not None

    with pytest.raises(ApprovalDecisionError) as wrong_checkpoint:
        asyncio.run(
            runner.decide_review(
                workflow_run_id=run_id,
                checkpoint_id="wrong-checkpoint",
                outcome=ReviewerOutcome.APPROVED,
                reviewer_id="reviewer",
                origin_channel=OriginChannel.RESPONSES,
            )
        )
    assert wrong_checkpoint.value.code == "approval_not_found"

    with pytest.raises(ApprovalDecisionError) as wrong_origin:
        asyncio.run(
            runner.decide_review(
                workflow_run_id=run_id,
                checkpoint_id=review["checkpoint_id"],
                outcome=ReviewerOutcome.APPROVED,
                reviewer_id="reviewer",
                origin_channel=OriginChannel.TEAMS_ACTIVITY,
            )
        )
    assert wrong_origin.value.code == "origin_mismatch"

    with repository.engine.begin() as conn:
        conn.execute(
            maf_checkpoints.insert().values(
                workflow_run_id=run_id,
                workflow_id="insurance-underwriting-workflow",
                checkpoint_id="stale-successor",
                checkpoint_json={},
                metadata_json={},
            )
        )
    with pytest.raises(ApprovalDecisionError) as stale:
        asyncio.run(
            runner.decide_review(
                workflow_run_id=run_id,
                checkpoint_id=review["checkpoint_id"],
                outcome=ReviewerOutcome.APPROVED,
                reviewer_id="reviewer",
                origin_channel=OriginChannel.RESPONSES,
            )
        )
    assert stale.value.code == "stale_checkpoint"


def test_duplicate_and_concurrent_review_resume_are_idempotent(tmp_path) -> None:
    _, repository, runner = _runtime(tmp_path, "review-idempotency.db")
    run_id = "run-review-idempotency"
    asyncio.run(
        runner.start(
            workflow_run_id=run_id,
            application=_application("app-review-idempotency"),
            origin_channel=OriginChannel.API,
        )
    )
    review = repository.get_review_projection(run_id)
    assert review is not None

    async def decide() -> object:
        try:
            return await runner.decide_review(
                workflow_run_id=run_id,
                checkpoint_id=review["checkpoint_id"],
                outcome=ReviewerOutcome.APPROVED,
                reviewer_id="reviewer",
                origin_channel=OriginChannel.API,
            )
        except ApprovalDecisionError as exc:
            return exc

    async def decide_concurrently() -> tuple[object, object]:
        first, second = await asyncio.gather(decide(), decide())
        return first, second

    first, second = asyncio.run(decide_concurrently())
    results = [first, second]
    assert len([result for result in results if isinstance(result, list)]) == 1
    errors = [result for result in results if isinstance(result, ApprovalDecisionError)]
    assert len(errors) == 1
    assert errors[0].code == "decision_in_progress"

    duplicate = asyncio.run(
        runner.decide_review(
            workflow_run_id=run_id,
            checkpoint_id=review["checkpoint_id"],
            outcome=ReviewerOutcome.APPROVED,
            reviewer_id="reviewer",
            origin_channel=OriginChannel.API,
        )
    )
    assert duplicate == []
    with pytest.raises(ApprovalDecisionError) as conflict:
        asyncio.run(
            runner.decide_review(
                workflow_run_id=run_id,
                checkpoint_id=review["checkpoint_id"],
                outcome=ReviewerOutcome.DECLINED,
                reviewer_id="reviewer",
                origin_channel=OriginChannel.API,
            )
        )
    assert conflict.value.code == "decision_conflict"
