from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]
FOUNDRY_DIR = ROOT / "infra" / "foundry-hosted"


@dataclass(frozen=True)
class NativeTeamsReview:
    workflow_run_id: str
    reviewer_outcome: str
    reviewer_type: str
    conversation_hash: str
    card_action_count: int
    completed_action_count: int
    review_resolved_events: int
    workflow_completed_events: int


def run_command(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "AZURE_DEV_USER_AGENT": "microsoft_foundry_skill"},
    )
    return completed.stdout.strip()


def azd_value(name: str) -> str:
    return run_command(
        "azd",
        "env",
        "get-value",
        name,
        "--cwd",
        str(FOUNDRY_DIR),
        "--no-prompt",
    )


def parse_utc(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Native Teams acceptance timestamps must include a timezone.")
    return timestamp.astimezone(UTC)


class NativeTeamsObserver:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)

    def close(self) -> None:
        self.engine.dispose()

    def completed_reviews_since(self, started_at: datetime) -> list[NativeTeamsReview]:
        statement = text(
            """
            SELECT
                workflow.id AS workflow_run_id,
                approval.reviewer_outcome,
                approval.reviewer_type,
                MIN(action.conversation_hash) AS conversation_hash,
                COUNT(action.token_hash) AS card_action_count,
                COUNT(action.token_hash) FILTER (
                    WHERE action.status = 'completed'
                      AND action.decision = approval.reviewer_outcome
                ) AS completed_action_count,
                (
                    SELECT COUNT(*)
                    FROM workflow_events AS event
                    WHERE event.workflow_run_id = workflow.id
                      AND event.event_type = 'review_resolved'
                ) AS review_resolved_events,
                (
                    SELECT COUNT(*)
                    FROM workflow_events AS event
                    WHERE event.workflow_run_id = workflow.id
                      AND event.event_type = 'workflow_completed'
                ) AS workflow_completed_events
            FROM workflow_runs AS workflow
            INNER JOIN underwriting_approvals AS approval
                ON approval.workflow_run_id = workflow.id
            INNER JOIN teams_card_actions AS action
                ON action.workflow_run_id = approval.workflow_run_id
               AND action.checkpoint_id = approval.checkpoint_id
            WHERE workflow.origin_channel = 'teams_activity'
              AND workflow.id LIKE 'run-teams-%'
              AND workflow.created_at >= :started_at
              AND workflow.status = 'COMPLETED'
              AND approval.status = 'completed'
              AND approval.reviewer_outcome IN ('APPROVED', 'DECLINED')
            GROUP BY
                workflow.id,
                approval.reviewer_outcome,
                approval.reviewer_type,
                approval.resolved_at
            ORDER BY approval.resolved_at DESC
            """
        )
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    statement,
                    {"started_at": started_at.replace(tzinfo=None)},
                )
                .mappings()
                .all()
            )
        return [
            NativeTeamsReview(
                workflow_run_id=str(row["workflow_run_id"]),
                reviewer_outcome=str(row["reviewer_outcome"]),
                reviewer_type=str(row["reviewer_type"] or ""),
                conversation_hash=str(row["conversation_hash"] or ""),
                card_action_count=int(row["card_action_count"]),
                completed_action_count=int(row["completed_action_count"]),
                review_resolved_events=int(row["review_resolved_events"]),
                workflow_completed_events=int(row["workflow_completed_events"]),
            )
            for row in rows
        ]


def select_acceptance(
    reviews: list[NativeTeamsReview],
) -> dict[str, NativeTeamsReview] | None:
    accepted: dict[str, NativeTeamsReview] = {}
    for review in reviews:
        if (
            review.reviewer_type != "human"
            or not review.conversation_hash
            or review.card_action_count < 2
            or review.completed_action_count != 1
            or review.review_resolved_events < 1
            or review.workflow_completed_events < 1
        ):
            continue
        accepted.setdefault(review.reviewer_outcome, review)
    if {"APPROVED", "DECLINED"}.issubset(accepted):
        return accepted
    return None


def build_evidence(
    accepted: dict[str, NativeTeamsReview],
    *,
    release_id: str,
    release_started_at: datetime,
    observation_started_at: datetime,
) -> dict[str, Any]:
    approved = accepted["APPROVED"]
    declined = accepted["DECLINED"]
    reviews = [approved, declined]
    return {
        "schema_version": 1,
        "evidence_type": "native_teams_acceptance",
        "status": "passed",
        "release_id": release_id,
        "release_started_at": release_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "observation_started_at": observation_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow_run_ids": [review.workflow_run_id for review in reviews],
        "conversation_hashes": list(dict.fromkeys(review.conversation_hash for review in reviews)),
        "scenarios": [
            {
                "name": "teams_activity_card_delivery",
                "status": "passed",
                "workflow_run_id": approved.workflow_run_id,
                "conversation_hash": approved.conversation_hash,
                "card_action_count": approved.card_action_count,
            },
            {
                "name": "teams_approved",
                "status": "passed",
                "workflow_run_id": approved.workflow_run_id,
                "conversation_hash": approved.conversation_hash,
                "reviewer_outcome": approved.reviewer_outcome,
                "reviewer_type": approved.reviewer_type,
            },
            {
                "name": "teams_declined",
                "status": "passed",
                "workflow_run_id": declined.workflow_run_id,
                "conversation_hash": declined.conversation_hash,
                "reviewer_outcome": declined.reviewer_outcome,
                "reviewer_type": declined.reviewer_type,
            },
        ],
        "reviews": [asdict(review) for review in reviews],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Observe real Microsoft Teams review outcomes in PostgreSQL. "
            "This script does not synthesize Bot or Activity traffic."
        )
    )
    parser.add_argument(
        "--output",
        default=os.getenv(
            "TEAMS_NATIVE_ACCEPTANCE_EVIDENCE_FILE",
            str(ROOT / "backend" / ".foundry" / "results" / "teams-native-acceptance.json"),
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("FOUNDRY_TEAMS_ACCEPTANCE_TIMEOUT_SECONDS", "7200")),
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=float(os.getenv("FOUNDRY_TEAMS_ACCEPTANCE_POLL_SECONDS", "5")),
    )
    parser.add_argument(
        "--observation-started-at",
        default="",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.timeout_seconds <= 0 or args.poll_interval_seconds <= 0:
        raise ValueError("Native Teams acceptance timeout and poll interval must be positive.")
    release_started_at_value = os.getenv("FOUNDRY_RELEASE_STARTED_AT", "")
    release_started_at = (
        parse_utc(release_started_at_value) if release_started_at_value else datetime.now(UTC)
    )
    observation_started_at = (
        parse_utc(args.observation_started_at) if args.observation_started_at else datetime.now(UTC)
    )
    release_id = os.getenv("RELEASE_ID", "manual-native-teams")
    database_url = azd_value("RUNTIME_DATABASE_URL")
    if not database_url:
        raise RuntimeError("Native Teams acceptance could not resolve the runtime database.")

    print(
        "Native Teams acceptance is waiting for two new reviews. In the published "
        "Teams agent, send 'start sample underwriting review' twice; approve one "
        "card and decline the other.",
        flush=True,
    )
    observer = NativeTeamsObserver(database_url)
    deadline = time.monotonic() + args.timeout_seconds
    try:
        while time.monotonic() < deadline:
            accepted = select_acceptance(observer.completed_reviews_since(observation_started_at))
            if accepted is not None:
                evidence = build_evidence(
                    accepted,
                    release_id=release_id,
                    release_started_at=release_started_at,
                    observation_started_at=observation_started_at,
                )
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                print(
                    f"Native Teams acceptance passed. Evidence written to {output}.",
                    flush=True,
                )
                return
            time.sleep(args.poll_interval_seconds)
    finally:
        observer.close()
    raise TimeoutError("Timed out waiting for one approved and one declined native Teams review.")


if __name__ == "__main__":
    main()
