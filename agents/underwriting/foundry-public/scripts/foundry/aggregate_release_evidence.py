from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from release_record import (
    atomic_json_write,
    configured_sensitive_values,
    finalize_record,
    finish_release_timing,
    register_artifact,
    validate_secret_free,
)

ROOT = Path(__file__).resolve().parents[2]
release_id = os.getenv("RELEASE_ID", "").strip()
DEFAULT_RESULTS = (
    ROOT / ".artifacts" / "releases" / release_id / "evidence"
    if release_id
    else ROOT / "backend" / ".foundry" / "results"
)
RESULTS = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_DIR", DEFAULT_RESULTS))
OUTPUT = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_FILE", RESULTS / "release-evidence.json"))
SOURCES: dict[str, Path] = {
    "verification": RESULTS / "foundry-verify.json",
    "hosted_e2e": RESULTS / "hosted-e2e-evidence.json",
    "teams_native_acceptance": RESULTS / "teams-native-acceptance.json",
    "hosted_smoke": RESULTS / "hosted-smoke-evidence.json",
    "trace_evaluation": RESULTS / "foundry-trace-eval.json",
    "application_insights": RESULTS / "appinsights-evidence.json",
}
if release_id:
    SOURCES.update(
        {
            "hosted_agent_deployment": RESULTS / "hosted-agent-deployment.json",
            "rollback_verification": RESULTS / "rollback-verification.json",
        }
    )

EXPECTED_STATUSES = {
    "verification": "passed",
    "hosted_e2e": "passed",
    "teams_native_acceptance": "passed",
    "hosted_smoke": "passed",
    "trace_evaluation": "completed",
    "application_insights": "passed",
    "hosted_agent_deployment": "deployed",
    "rollback_verification": "passed",
}
REQUIRED_HOSTED_E2E_SCENARIOS = {
    "automatic_completion",
    "retry_completion",
    "crash_resume_completion",
    "web_referral_pending",
    "web_review_missing_identity_rejected",
    "web_review_spoofed_identity_rejected",
}
REQUIRED_NATIVE_TEAMS_SCENARIOS = {
    "teams_activity_card_delivery",
    "teams_approved",
    "teams_declined",
}
FORBIDDEN_EVIDENCE_KEYS = {
    "action_token",
    "age",
    "applicant_name",
    "credit_score",
    "driving_history",
    "health_disclosures",
    "income",
    "rationale",
    "requested_coverage",
    "score_breakdown",
    "token",
    "token_hash",
}


def required_target_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    result = subprocess.run(
        [
            "azd",
            "env",
            "get-value",
            name,
            "--cwd",
            str(ROOT / "infra" / "foundry-hosted"),
            "--no-prompt",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "AZURE_DEV_USER_AGENT": "microsoft_foundry_skill"},
    )
    value = result.stdout.strip()
    if result.returncode == 0 and value:
        return value
    raise RuntimeError(f"Missing authenticated release target value: {name}")


def parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Evidence timestamps must include a timezone.")
    return timestamp.astimezone(UTC)


def unique_strings(document: dict[str, Any], field: str, evidence_name: str) -> list[str]:
    values = document.get(field)
    if not isinstance(values, list) or not values:
        raise RuntimeError(f"Release evidence {evidence_name} is missing {field}.")
    if not all(isinstance(value, str) and value for value in values):
        raise RuntimeError(f"Release evidence {evidence_name} has invalid {field}.")
    if len(values) != len(set(values)):
        raise RuntimeError(f"Release evidence {evidence_name} has duplicate {field}.")
    return values


def validate_evidence_privacy(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_EVIDENCE_KEYS:
                raise RuntimeError(f"Private hosted evidence field is forbidden: {path}.{key}")
            validate_evidence_privacy(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_evidence_privacy(item, f"{path}[{index}]")


def validate_hosted_e2e(document: dict[str, Any]) -> None:
    if document.get("playwright_status") != "passed":
        raise RuntimeError("Hosted E2E evidence did not pass deployed Playwright acceptance.")
    workflow_run_ids = unique_strings(document, "workflow_run_ids", "hosted_e2e")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise RuntimeError("Hosted E2E evidence is missing scenario results.")
    scenario_by_name: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise RuntimeError("Hosted E2E scenario evidence must be an object.")
        name = scenario.get("name")
        if not isinstance(name, str) or not name or name in scenario_by_name:
            raise RuntimeError("Hosted E2E scenario names must be unique non-empty strings.")
        if scenario.get("status") != "passed":
            raise RuntimeError(f"Hosted E2E scenario did not pass: {name}")
        workflow_run_id = scenario.get("workflow_run_id")
        if workflow_run_id not in workflow_run_ids:
            raise RuntimeError(f"Hosted E2E scenario has an unbound workflow_run_id: {name}")
        scenario_by_name[name] = scenario

    missing = sorted(REQUIRED_HOSTED_E2E_SCENARIOS - scenario_by_name.keys())
    if missing:
        raise RuntimeError(
            f"Hosted E2E evidence is missing required scenarios: {', '.join(missing)}"
        )
    web_referral = scenario_by_name["web_referral_pending"]
    if (
        web_referral.get("machine_recommendation") != "REFER_TO_HUMAN_UNDERWRITER"
        or web_referral.get("review_status") != "pending"
    ):
        raise RuntimeError("Hosted E2E did not prove a pending web referral.")
    for name in (
        "web_review_missing_identity_rejected",
        "web_review_spoofed_identity_rejected",
    ):
        if int(scenario_by_name[name].get("http_status", 0)) != 403:
            raise RuntimeError(f"Hosted E2E did not prove Teams-only production review: {name}")


def validate_native_teams_acceptance(document: dict[str, Any]) -> None:
    workflow_run_ids = unique_strings(
        document,
        "workflow_run_ids",
        "teams_native_acceptance",
    )
    conversation_hashes = unique_strings(
        document,
        "conversation_hashes",
        "teams_native_acceptance",
    )
    if len(workflow_run_ids) != 2:
        raise RuntimeError("Native Teams acceptance must contain exactly two workflow runs.")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise RuntimeError("Native Teams acceptance is missing scenario results.")
    scenario_by_name: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise RuntimeError("Native Teams acceptance scenarios must be objects.")
        name = scenario.get("name")
        if not isinstance(name, str) or not name or name in scenario_by_name:
            raise RuntimeError("Native Teams acceptance scenario names must be unique.")
        if scenario.get("status") != "passed":
            raise RuntimeError(f"Native Teams acceptance scenario did not pass: {name}")
        if scenario.get("workflow_run_id") not in workflow_run_ids:
            raise RuntimeError(f"Native Teams scenario has an unbound workflow run: {name}")
        if scenario.get("conversation_hash") not in conversation_hashes:
            raise RuntimeError(f"Native Teams scenario has an unbound conversation hash: {name}")
        scenario_by_name[name] = scenario
    missing = sorted(REQUIRED_NATIVE_TEAMS_SCENARIOS - scenario_by_name.keys())
    if missing:
        raise RuntimeError(
            f"Native Teams acceptance is missing required scenarios: {', '.join(missing)}"
        )
    if int(scenario_by_name["teams_activity_card_delivery"].get("card_action_count", 0)) < 2:
        raise RuntimeError("Native Teams acceptance did not prove card action delivery.")
    for name, outcome in (("teams_approved", "APPROVED"), ("teams_declined", "DECLINED")):
        scenario = scenario_by_name[name]
        if scenario.get("reviewer_outcome") != outcome or scenario.get("reviewer_type") != "human":
            raise RuntimeError(f"Native Teams scenario has the wrong human outcome: {name}")


def validate_hosted_smoke(document: dict[str, Any]) -> None:
    unique_strings(document, "conversation_ids", "hosted_smoke")
    workflow_run_id = document.get("workflow_run_id")
    if not isinstance(workflow_run_id, str) or not workflow_run_id.startswith("run-"):
        raise RuntimeError("Hosted smoke evidence is missing its exact workflow_run_id.")


def validate_trace_evaluation(
    document: dict[str, Any],
    smoke: dict[str, Any],
) -> None:
    conversation_ids = unique_strings(document, "conversation_ids", "trace_evaluation")
    smoke_conversation_ids = unique_strings(smoke, "conversation_ids", "hosted_smoke")
    if conversation_ids != smoke_conversation_ids:
        raise RuntimeError("Trace evaluation conversation IDs do not exactly match hosted smoke.")
    if document.get("trace_evidence_generated_at") != smoke.get("generated_at"):
        raise RuntimeError("Trace evaluation does not reference the exact hosted smoke evidence.")
    counts = document.get("result_counts")
    if not isinstance(counts, dict):
        raise RuntimeError("Trace evaluation evidence is missing result_counts.")
    expected_total = len(conversation_ids)
    if (
        int(counts.get("total", -1)) != expected_total
        or int(counts.get("passed", -1)) != expected_total
        or int(counts.get("failed", -1)) != 0
        or int(counts.get("errored", -1)) != 0
        or int(counts.get("skipped", -1)) != 0
    ):
        raise RuntimeError("Trace evaluation must have zero failed, errored, or skipped results.")
    criterion_counts = document.get("criterion_result_counts")
    if not isinstance(criterion_counts, dict):
        raise RuntimeError("Trace evaluation evidence is missing criterion_result_counts.")
    criterion_total = int(criterion_counts.get("total", -1))
    if (
        criterion_total < expected_total
        or int(criterion_counts.get("passed", -1)) != criterion_total
        or int(criterion_counts.get("failed", -1)) != 0
        or int(criterion_counts.get("errored", -1)) != 0
        or int(criterion_counts.get("skipped", -1)) != 0
    ):
        raise RuntimeError("Every trace evaluation criterion must pass.")


def validate_telemetry(
    document: dict[str, Any],
    hosted_e2e: dict[str, Any],
    teams_native_acceptance: dict[str, Any],
) -> None:
    workflow_run_ids = unique_strings(document, "workflow_run_ids", "application_insights")
    e2e_workflow_run_ids = unique_strings(hosted_e2e, "workflow_run_ids", "hosted_e2e")
    teams_workflow_run_ids = unique_strings(
        teams_native_acceptance,
        "workflow_run_ids",
        "teams_native_acceptance",
    )
    expected_workflow_run_ids = sorted(e2e_workflow_run_ids + teams_workflow_run_ids)
    if sorted(workflow_run_ids) != expected_workflow_run_ids:
        raise RuntimeError(
            "Telemetry workflow run IDs do not exactly match web and native Teams evidence."
        )
    expected = len(workflow_run_ids)
    for field in (
        "matched_count",
        "entrypoint_run_count",
        "hosted_invocation_run_count",
        "workflow_span_run_count",
    ):
        if int(document.get(field, -1)) != expected:
            raise RuntimeError(f"Telemetry evidence does not cover every hosted E2E run: {field}")
    if int(document.get("exception_rows", -1)) != 0:
        raise RuntimeError("Telemetry evidence contains hosted E2E exceptions.")


def validate_verification(document: dict[str, Any]) -> None:
    hosted = document.get("hosted_agent")
    if not isinstance(hosted, dict):
        raise RuntimeError("Deployment verification is missing hosted-agent metadata.")
    protocols = hosted.get("protocols")
    if not isinstance(protocols, list):
        raise RuntimeError("Deployment verification is missing hosted-agent protocols.")
    protocol_pairs = {
        (item.get("protocol"), item.get("version")) for item in protocols if isinstance(item, dict)
    }
    if not {
        ("responses", "2.0.0"),
        ("activity", "2.0.0"),
    }.issubset(protocol_pairs):
        raise RuntimeError("Deployment verification must prove Responses and Activity 2.0.0.")
    image_repository = hosted.get("image_repository")
    image = hosted.get("image")
    if (
        not isinstance(image_repository, str)
        or not image_repository
        or not isinstance(image, str)
        or f"/{image_repository}@sha256:" not in image
    ):
        raise RuntimeError("Deployment verification has an invalid hosted image repository.")


def main() -> None:
    documents: dict[str, Any] = {}
    timestamps: list[datetime] = []
    sensitive_values = configured_sensitive_values()
    configured_start = os.getenv("RELEASE_WINDOW_START", "").strip()
    window_start = parse_timestamp(configured_start) if configured_start else None
    now = datetime.now(UTC)
    for name, path in SOURCES.items():
        if not path.is_file():
            raise RuntimeError(f"Missing release evidence: {path}")
        document = json.loads(path.read_text())
        validate_secret_free(document, sensitive_values=sensitive_values)
        validate_evidence_privacy(document)
        status = document.get("status")
        if status != EXPECTED_STATUSES[name]:
            raise RuntimeError(
                f"Release evidence {name} has status {status!r}; "
                f"expected {EXPECTED_STATUSES[name]!r}."
            )
        timestamp = document.get("generated_at")
        if not isinstance(timestamp, str) or not timestamp:
            raise RuntimeError(f"Release evidence {name} is missing generated_at.")
        generated_at = parse_timestamp(timestamp)
        if generated_at > now + timedelta(minutes=5):
            raise RuntimeError(f"Release evidence {name} is dated in the future.")
        timestamps.append(generated_at)
        if release_id:
            if document.get("release_id") != release_id:
                raise RuntimeError(f"Release evidence {name} belongs to another release.")
            if window_start is None:
                raise RuntimeError("RELEASE_WINDOW_START is required for release aggregation.")
            release_started_at = document.get("release_started_at")
            if (
                not isinstance(release_started_at, str)
                or parse_timestamp(release_started_at) != window_start
            ):
                raise RuntimeError(f"Release evidence {name} has a mismatched release window.")
            if generated_at < window_start:
                raise RuntimeError(f"Release evidence {name} predates the release window.")
        documents[name] = document

    validate_verification(documents["verification"])
    validate_hosted_e2e(documents["hosted_e2e"])
    validate_native_teams_acceptance(documents["teams_native_acceptance"])
    validate_hosted_smoke(documents["hosted_smoke"])
    validate_trace_evaluation(documents["trace_evaluation"], documents["hosted_smoke"])
    validate_telemetry(
        documents["application_insights"],
        documents["hosted_e2e"],
        documents["teams_native_acceptance"],
    )
    if release_id:
        deployment = documents["hosted_agent_deployment"]
        verified_hosted = documents["verification"]["hosted_agent"]
        if (
            deployment.get("name") != verified_hosted.get("name")
            or deployment.get("version") != verified_hosted.get("version")
            or deployment.get("image") != verified_hosted.get("image")
            or deployment.get("image_repository") != verified_hosted.get("image_repository")
        ):
            raise RuntimeError(
                "Hosted deployment evidence does not match the verified active version."
            )

    window_start = window_start or min(timestamps)
    if any(timestamp < window_start for timestamp in timestamps):
        raise RuntimeError("One or more evidence files predate RELEASE_WINDOW_START.")

    payload = {
        "status": "passed",
        "release_id": release_id or "manual-evidence",
        "release_started_at": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_window": {
            "start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "target": {
            "subscription_id": required_target_value("AZURE_SUBSCRIPTION_ID"),
            "resource_group": required_target_value("AZURE_RESOURCE_GROUP"),
            "location": required_target_value("AZURE_LOCATION"),
        },
        "evidence": documents,
    }
    validate_secret_free(payload, sensitive_values=sensitive_values)
    atomic_json_write(OUTPUT, payload)
    if release_id:
        gates = {
            "verification": "foundry-verify.json",
            "hosted_e2e": "hosted-e2e-evidence.json",
            "teams_native_acceptance": "teams-native-acceptance.json",
            "hosted_smoke": "hosted-smoke-evidence.json",
            "trace_evaluation": "foundry-trace-eval.json",
            "application_insights": "appinsights-evidence.json",
            "rollback_verification": "rollback-verification.json",
        }
        for gate, filename in gates.items():
            register_artifact(release_id, f"evidence/{filename}", gate)
        register_artifact(
            release_id,
            "evidence/hosted-agent-deployment.json",
        )
        register_artifact(
            release_id,
            "evidence/rollback-baseline.json",
        )
        register_artifact(release_id, f"evidence/{OUTPUT.name}")
        finish_release_timing(release_id, "final_evidence", "succeeded")
        finalize_record(release_id, "succeeded")
    print(f"Release-window evidence written to {OUTPUT}.")


if __name__ == "__main__":
    main()
