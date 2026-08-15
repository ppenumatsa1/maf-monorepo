from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FORBIDDEN_KEY_PATTERN = re.compile(
    r"(api[_-]?key|bearer[_-]?token|connection[_-]?string|password|secret|database_url|runtime_database_url|access[_-]?token)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"AccountKey=", re.IGNORECASE),
    re.compile(r"SharedAccessSignature=", re.IGNORECASE),
    re.compile(r"DefaultEndpointsProtocol=", re.IGNORECASE),
    re.compile(r"://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]
REQUIRED_ARTIFACTS = {
    "release-context.json": "release_context",
    "source-validation.json": "source_validation",
    "images.json": "images",
    "deployment.json": "deployment",
    "smoke.json": "smoke",
    "domain-e2e.json": "domain_e2e",
    "evaluation.json": "evaluation",
    "telemetry.json": "telemetry",
}
REQUIRED_DOMAIN_SCENARIOS = {
    "low-risk-no-hitl",
    "high-risk-approval-resume",
    "damaged-item-approval-resume",
}
REQUIRED_EVALUATION_CASE_IDS = {
    "ord-1001-low-risk-late",
    "ord-1004-damaged-approve",
    "ord-1009-high-amount",
}


def parse_timestamp(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive formatting guard
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return payload


def scan_forbidden(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if FORBIDDEN_KEY_PATTERN.search(key_text):
                raise ValueError(f"Forbidden key in release evidence at {path}.{key_text}")
            if key_text in {"hosted_agent", "runtime_connection", "hosted-agent"}:
                raise ValueError(f"Unexpected Foundry hosted-agent field at {path}.{key_text}")
            scan_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_forbidden(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"Forbidden value detected in release evidence at {path}")


def expect(payload: dict[str, Any], artifact_type: str, release_id: str, release_started_at: str) -> None:
    if payload.get("contract") != "azure-hosted-release/v1":
        raise ValueError(f"{artifact_type} is missing the canonical release contract marker.")
    if payload.get("lane") != "azure-hosted":
        raise ValueError(f"{artifact_type} must remain lane-local to azure-hosted.")
    if payload.get("artifact_type") != artifact_type:
        raise ValueError(f"{artifact_type} artifact_type mismatch.")
    if payload.get("release_id") != release_id:
        raise ValueError(f"{artifact_type} belongs to a different release.")
    if payload.get("release_started_at") != release_started_at:
        raise ValueError(f"{artifact_type} uses a different release window.")
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str):
        raise ValueError(f"{artifact_type} is missing generated_at.")
    if parse_timestamp(generated_at, field_name=f"{artifact_type}.generated_at") < parse_timestamp(
        release_started_at, field_name=f"{artifact_type}.release_started_at"
    ):
        raise ValueError(f"{artifact_type} generated_at predates the release window.")
    scan_forbidden(payload)


def require_exact_ids(
    values: list[str],
    *,
    expected: set[str],
    artifact_name: str,
    field_name: str,
) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"{artifact_name} contains duplicate {field_name}: {duplicates}")
    actual = set(values)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise ValueError(f"{artifact_name} is missing required {field_name}: {missing}")
    if unexpected:
        raise ValueError(f"{artifact_name} contains unexpected {field_name}: {unexpected}")


def require_digest(image: Any, *, artifact_name: str, field_name: str) -> None:
    if not isinstance(image, str) or "@sha256:" not in image:
        raise ValueError(f"{artifact_name} {field_name} must be pinned by digest.")


def require_http_url(value: Any, *, artifact_name: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith("http"):
        raise ValueError(f"{artifact_name} is missing {field_name}.")


def validate_source_validation(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("source-validation.json did not pass.")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("source-validation.json must record checks.")
    for check in checks:
        if not isinstance(check, dict) or check.get("status") != "passed":
            raise ValueError("source-validation.json contains a failed check.")


def validate_images(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("images.json did not pass.")
    for service in ("backend", "frontend"):
        service_payload = payload.get(service)
        if not isinstance(service_payload, dict):
            raise ValueError(f"images.json is missing {service}.")
        require_digest(service_payload.get("image"), artifact_name="images.json", field_name=f"{service}.image")
        if not isinstance(service_payload.get("container_app"), str) or not service_payload["container_app"]:
            raise ValueError(f"images.json is missing {service}.container_app.")
        if not isinstance(service_payload.get("resource_id"), str) or not service_payload["resource_id"]:
            raise ValueError(f"images.json is missing {service}.resource_id.")
        if not isinstance(service_payload.get("image_digest"), str) or not service_payload["image_digest"].startswith(
            "sha256:"
        ):
            raise ValueError(f"images.json is missing {service}.image_digest.")


def validate_deployment(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("deployment.json did not pass.")
    if payload.get("deploy_mode") != "app_only":
        raise ValueError("deployment.json must preserve the app_only deployment mode.")
    for key in ("api_url", "web_url"):
        require_http_url(payload.get(key), artifact_name="deployment.json", field_name=key)

    services = payload.get("services")
    if not isinstance(services, dict):
        raise ValueError("deployment.json is missing services.")

    for service_name, expected_external in (("backend", False), ("frontend", True)):
        service_payload = services.get(service_name)
        if not isinstance(service_payload, dict):
            raise ValueError(f"deployment.json is missing services.{service_name}.")
        require_digest(
            service_payload.get("image"),
            artifact_name="deployment.json",
            field_name=f"services.{service_name}.image",
        )
        if service_payload.get("image_digest") != str(service_payload.get("image")).split("@", 1)[1]:
            raise ValueError(
                f"deployment.json services.{service_name}.image_digest does not match the pinned image."
            )
        if not isinstance(service_payload.get("resource_id"), str) or not service_payload["resource_id"]:
            raise ValueError(f"deployment.json is missing services.{service_name}.resource_id.")

        ingress = service_payload.get("ingress")
        if not isinstance(ingress, dict):
            raise ValueError(f"deployment.json is missing services.{service_name}.ingress.")
        if ingress.get("external") is not expected_external:
            raise ValueError(
                f"deployment.json services.{service_name}.ingress.external must be {expected_external}."
            )

        target_identity = service_payload.get("target_identity")
        if not isinstance(target_identity, dict):
            raise ValueError(f"deployment.json is missing services.{service_name}.target_identity.")
        if target_identity.get("resource_id") != service_payload.get("resource_id"):
            raise ValueError(
                f"deployment.json services.{service_name}.target_identity.resource_id mismatch."
            )

        active_revision = service_payload.get("active_revision")
        if not isinstance(active_revision, dict):
            raise ValueError(f"deployment.json is missing services.{service_name}.active_revision.")
        if active_revision.get("active") is not True:
            raise ValueError(
                f"deployment.json services.{service_name}.active_revision must be marked active."
            )
        if active_revision.get("traffic_weight") != 100:
            raise ValueError(
                f"deployment.json services.{service_name}.active_revision must receive 100% of traffic."
            )
        if active_revision.get("running_state") not in {"", "Running"}:
            raise ValueError(
                f"deployment.json services.{service_name}.active_revision is not running."
            )
        if active_revision.get("health_state") not in {"", "Healthy"}:
            raise ValueError(
                f"deployment.json services.{service_name}.active_revision is not healthy."
            )


def validate_smoke(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("smoke.json did not pass.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise ValueError("smoke.json must contain low/high smoke scenarios.")
    scenario_ids = [item.get("scenario_id") for item in scenarios if isinstance(item, dict)]
    require_exact_ids(
        [scenario_id for scenario_id in scenario_ids if isinstance(scenario_id, str)],
        expected={"low-risk-no-hitl", "high-risk-hitl-request"},
        artifact_name="smoke.json",
        field_name="scenario IDs",
    )
    correlations = payload.get("correlations")
    if not isinstance(correlations, list) or len(correlations) != 2:
        raise ValueError("smoke.json must include exactly two correlation pairs.")
    seen_pairs: set[tuple[str, str]] = set()
    for pair in correlations:
        if not isinstance(pair, dict):
            raise ValueError("smoke.json correlation entry must be an object.")
        thread_id = pair.get("thread_id")
        workflow_run_id = pair.get("workflow_run_id")
        if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
            raise ValueError("smoke.json correlation entry requires string identifiers.")
        pair_key = (thread_id, workflow_run_id)
        if pair_key in seen_pairs:
            raise ValueError("smoke.json contains a duplicate correlation pair.")
        seen_pairs.add(pair_key)


def validate_browser_e2e_log(release_dir: Path) -> None:
    browser_log = release_dir / "logs" / "browser-e2e.log"
    if not browser_log.is_file():
        raise ValueError("Missing required hosted browser E2E evidence: logs/browser-e2e.log")
    if browser_log.stat().st_size <= 0:
        raise ValueError("Hosted browser E2E evidence log is empty.")


def validate_domain_e2e(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("domain-e2e.json did not pass.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("domain-e2e.json must include scenarios.")

    scenario_map: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("domain-e2e.json scenario entry must be an object.")
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str):
            raise ValueError("domain-e2e.json scenario entry is missing scenario_id.")
        if scenario_id in scenario_map:
            raise ValueError(f"domain-e2e.json contains duplicate scenario_id: {scenario_id}")
        scenario_map[scenario_id] = scenario

    require_exact_ids(
        list(scenario_map),
        expected=REQUIRED_DOMAIN_SCENARIOS,
        artifact_name="domain-e2e.json",
        field_name="scenario IDs",
    )

    seen_pairs: set[tuple[str, str]] = set()
    for scenario_id, scenario in scenario_map.items():
        if scenario.get("status") != "passed":
            raise ValueError(f"domain-e2e.json scenario {scenario_id} did not pass.")
        if scenario.get("transport") != "http":
            raise ValueError(f"domain-e2e.json scenario {scenario_id} must remain HTTP-only.")
        if not isinstance(scenario.get("order_id"), str) or not scenario["order_id"]:
            raise ValueError(f"domain-e2e.json scenario {scenario_id} is missing order_id.")
        if scenario.get("terminal_status") != "completed":
            raise ValueError(
                f"domain-e2e.json scenario {scenario_id} must reach completed terminal status."
            )
        thread_id = scenario.get("thread_id")
        workflow_run_id = scenario.get("workflow_run_id")
        if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
            raise ValueError(
                f"domain-e2e.json scenario {scenario_id} is missing thread_id/workflow_run_id."
            )
        pair_key = (thread_id, workflow_run_id)
        if pair_key in seen_pairs:
            raise ValueError("domain-e2e.json contains a duplicate correlation pair.")
        seen_pairs.add(pair_key)

    correlations = payload.get("correlations")
    if not isinstance(correlations, list) or len(correlations) != len(REQUIRED_DOMAIN_SCENARIOS):
        raise ValueError("domain-e2e.json must include all HTTP scenario correlations.")
    correlation_pairs = {
        (pair.get("thread_id"), pair.get("workflow_run_id"))
        for pair in correlations
        if isinstance(pair, dict)
    }
    if len(correlation_pairs) != len(REQUIRED_DOMAIN_SCENARIOS):
        raise ValueError("domain-e2e.json contains duplicate or malformed top-level correlations.")
    if correlation_pairs != seen_pairs:
        raise ValueError("domain-e2e.json top-level correlations do not match the scenario evidence.")


def blocking_result_rows(result_counts: dict[str, Any]) -> int:
    total = 0
    for key, value in result_counts.items():
        lower_key = str(key).lower()
        if "fail" not in lower_key and "error" not in lower_key:
            continue
        if isinstance(value, (int, float)):
            total += int(value)
        elif isinstance(value, str) and value.isdigit():
            total += int(value)
    return total


def validate_evaluation(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("evaluation.json did not pass.")
    result_counts = payload.get("result_counts")
    if not isinstance(result_counts, dict):
        raise ValueError("evaluation.json must include result_counts.")
    if blocking_result_rows(result_counts) != 0:
        raise ValueError("evaluation.json contains errored rows.")

    case_ids = payload.get("case_ids")
    if not isinstance(case_ids, list) or not all(isinstance(case_id, str) for case_id in case_ids):
        raise ValueError("evaluation.json must include case_ids.")
    require_exact_ids(
        list(case_ids),
        expected=REQUIRED_EVALUATION_CASE_IDS,
        artifact_name="evaluation.json",
        field_name="case IDs",
    )

    captures = payload.get("captures")
    if not isinstance(captures, list) or len(captures) != len(REQUIRED_EVALUATION_CASE_IDS):
        raise ValueError("evaluation.json must include three captured evaluation scenarios.")
    capture_ids: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for capture in captures:
        if not isinstance(capture, dict):
            raise ValueError("evaluation.json capture entry must be an object.")
        scenario_id = capture.get("scenario_id")
        if not isinstance(scenario_id, str):
            raise ValueError("evaluation.json capture entry is missing scenario_id.")
        capture_ids.append(scenario_id)
        if capture.get("terminal_status") != "completed":
            raise ValueError(
                f"evaluation.json capture {scenario_id} must reach completed terminal status."
            )
        thread_id = capture.get("thread_id")
        workflow_run_id = capture.get("workflow_run_id")
        if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
            raise ValueError(
                f"evaluation.json capture {scenario_id} is missing thread_id/workflow_run_id."
            )
        pair_key = (thread_id, workflow_run_id)
        if pair_key in seen_pairs:
            raise ValueError("evaluation.json contains a duplicate capture correlation pair.")
        seen_pairs.add(pair_key)
    require_exact_ids(
        capture_ids,
        expected=REQUIRED_EVALUATION_CASE_IDS,
        artifact_name="evaluation.json",
        field_name="capture scenario IDs",
    )

    if not isinstance(payload.get("http_output_capture"), str) or not payload["http_output_capture"]:
        raise ValueError("evaluation.json must include the HTTP output capture path.")

    terminal_status = payload.get("run_status") or payload.get("terminal_status") or payload.get("provider_status")
    if terminal_status != "completed":
        raise ValueError("evaluation.json did not reach a completed terminal status.")


def validate_telemetry(payload: dict[str, Any]) -> None:
    if payload.get("status") != "passed":
        raise ValueError("telemetry.json did not pass.")
    required_scenarios = payload.get("required_scenarios")
    if not isinstance(required_scenarios, list) or not all(
        isinstance(scenario_id, str) for scenario_id in required_scenarios
    ):
        raise ValueError("telemetry.json must include required_scenarios.")
    require_exact_ids(
        list(required_scenarios),
        expected=REQUIRED_DOMAIN_SCENARIOS,
        artifact_name="telemetry.json",
        field_name="required scenarios",
    )

    pairs = payload.get("validated_pairs")
    if not isinstance(pairs, list) or len(pairs) != len(REQUIRED_DOMAIN_SCENARIOS):
        raise ValueError("telemetry.json must include three validated_pairs.")

    seen_pairs: set[tuple[str, str]] = set()
    scenario_ids: list[str] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("telemetry.json validated_pairs entry must be an object.")
        scenario_id = pair.get("scenario_id")
        if not isinstance(scenario_id, str):
            raise ValueError("telemetry.json validated_pairs entry is missing scenario_id.")
        scenario_ids.append(scenario_id)
        thread_id = pair.get("thread_id")
        workflow_run_id = pair.get("workflow_run_id")
        if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
            raise ValueError("telemetry.json validated_pairs entry requires exact correlation IDs.")
        pair_key = (thread_id, workflow_run_id)
        if pair_key in seen_pairs:
            raise ValueError("telemetry.json contains a duplicate validated pair.")
        seen_pairs.add(pair_key)
        telemetry_count = pair.get("telemetry_count")
        if not isinstance(telemetry_count, int) or telemetry_count <= 0:
            raise ValueError("telemetry.json validated_pairs must report positive telemetry_count.")
        if pair.get("exception_count") != 0:
            raise ValueError("telemetry.json includes exceptions for the release evidence pairs.")

    require_exact_ids(
        scenario_ids,
        expected=REQUIRED_DOMAIN_SCENARIOS,
        artifact_name="telemetry.json",
        field_name="scenario IDs",
    )


def aggregate(release_dir: Path) -> dict[str, Any]:
    evidence_dir = release_dir / "evidence"
    artifacts: dict[str, dict[str, Any]] = {}
    for filename, artifact_type in REQUIRED_ARTIFACTS.items():
        path = evidence_dir / filename
        if not path.is_file():
            raise ValueError(f"Missing required release artifact: {filename}")
        artifacts[filename] = load_json(path)

    context = artifacts["release-context.json"]
    release_id = context.get("release_id")
    release_started_at = context.get("release_started_at")
    if not isinstance(release_id, str) or not isinstance(release_started_at, str):
        raise ValueError("release-context.json is missing release identity.")
    expect(context, "release_context", release_id, release_started_at)
    if context.get("status") not in {"ready", "passed"}:
        raise ValueError("release-context.json is not ready.")

    for filename, artifact_type in REQUIRED_ARTIFACTS.items():
        if filename == "release-context.json":
            continue
        expect(artifacts[filename], artifact_type, release_id, release_started_at)

    validate_source_validation(artifacts["source-validation.json"])
    validate_images(artifacts["images.json"])
    validate_deployment(artifacts["deployment.json"])
    validate_smoke(artifacts["smoke.json"])
    validate_browser_e2e_log(release_dir)
    validate_domain_e2e(artifacts["domain-e2e.json"])
    validate_evaluation(artifacts["evaluation.json"])
    validate_telemetry(artifacts["telemetry.json"])

    images = artifacts["images.json"]
    deployment = artifacts["deployment.json"]
    for service_name in ("backend", "frontend"):
        if images[service_name]["image"] != deployment["services"][service_name]["image"]:
            raise ValueError(
                f"deployment.json services.{service_name}.image does not match images.json."
            )
        if images[service_name]["resource_id"] != deployment["services"][service_name]["resource_id"]:
            raise ValueError(
                f"deployment.json services.{service_name}.resource_id does not match images.json."
            )

    if (evidence_dir / "infrastructure.json").is_file():
        infrastructure = load_json(evidence_dir / "infrastructure.json")
        expect(infrastructure, "infrastructure", release_id, release_started_at)
        if infrastructure.get("status") != "passed":
            raise ValueError("infrastructure.json exists but did not pass.")
        artifacts["infrastructure.json"] = infrastructure

    return {
        "schema_version": 1,
        "contract": "azure-hosted-release/v1",
        "lane": "azure-hosted",
        "artifact_type": "release_evidence",
        "status": "passed",
        "release_id": release_id,
        "release_started_at": release_started_at,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "target": context.get("target"),
        "artifacts": {
            filename.replace(".json", "").replace("-", "_"): {
                "file": filename,
                "status": payload.get("status"),
            }
            for filename, payload in artifacts.items()
        },
        "summary": {
            "validated_artifacts": sorted(artifacts.keys()),
            "browser_e2e_log": "logs/browser-e2e.log",
            "domain_scenarios": sorted(REQUIRED_DOMAIN_SCENARIOS),
            "evaluation_case_ids": sorted(REQUIRED_EVALUATION_CASE_IDS),
            "telemetry_pairs": len(artifacts["telemetry.json"]["validated_pairs"]),
        },
    }


def main() -> int:
    release_dir = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else Path.cwd() / ".artifacts" / "releases" / (Path.cwd().name)
    )
    evidence_path = release_dir / "evidence" / "release-evidence.json"
    try:
        payload = aggregate(release_dir)
    except Exception as exc:  # noqa: BLE001
        failure_payload = {
            "schema_version": 1,
            "contract": "azure-hosted-release/v1",
            "lane": "azure-hosted",
            "artifact_type": "release_evidence",
            "status": "failed",
            "release_id": None,
            "release_started_at": None,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "error": str(exc),
        }
        if (release_dir / "evidence" / "release-context.json").is_file():
            try:
                context = load_json(release_dir / "evidence" / "release-context.json")
                failure_payload["release_id"] = context.get("release_id")
                failure_payload["release_started_at"] = context.get("release_started_at")
                failure_payload["target"] = context.get("target")
            except Exception:  # noqa: BLE001
                pass
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(failure_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(str(exc), file=sys.stderr)
        return 1

    evidence_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Aggregated release evidence: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
