#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

python3 - <<'PY'
from pathlib import Path


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"Missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise SystemExit(f"Unexpected {label}: {needle}")


run_domain_e2e = Path("scripts/release/run-domain-e2e.sh").read_text(encoding="utf-8")
for required in (
    'scenario_id="low-risk-no-hitl"',
    'scenario_id="high-risk-approval-resume"',
    'scenario_id="damaged-item-approval-resume"',
    'order_id="ORD-1001"',
    'order_id="ORD-1009"',
    '"artifact_type": "domain_e2e"',
    '"terminal_status"',
):
    require(run_domain_e2e, required, "domain E2E contract")
for forbidden in ('browser-e2e', 'browser_e2e', 'make --no-print-directory test-e2e'):
    forbid(run_domain_e2e, forbidden, "browser E2E coupling")

telemetry = Path("scripts/release/verify-app-insights-correlation.sh").read_text(
    encoding="utf-8"
)
for required in (
    'REQUIRED_DOMAIN_SCENARIOS_JSON',
    'domain-e2e.json',
    'required_scenarios',
    'threadId == {json.dumps(thread_id)} and workflowRunId == {json.dumps(workflow_run_id)}',
    '"artifact_type": "telemetry"',
    'telemetry_count',
):
    require(telemetry, required, "telemetry contract")
for forbidden in ('smoke.json', 'smoke_file='):
    forbid(telemetry, forbidden, "smoke telemetry dependency")

release_validation = Path("scripts/release/validate-hosted-release.sh").read_text(
    encoding="utf-8"
)
for required in (
    'make --no-print-directory release-preflight',
    'make --no-print-directory release-verify',
    'make --no-print-directory release-smoke',
    'make --no-print-directory release-browser-e2e',
    'make --no-print-directory release-domain-e2e',
    'make --no-print-directory release-eval',
    'make --no-print-directory release-telemetry',
    'make --no-print-directory release-evidence',
    'Hosted release validation failed:',
):
    require(release_validation, required, "release validation orchestration")

run_browser_e2e = Path("scripts/release/run-browser-e2e.sh").read_text(encoding="utf-8")
for required in (
    'PLAYWRIGHT_BASE_URL',
    'browser-e2e.log',
    'make --no-print-directory test-e2e',
):
    require(run_browser_e2e, required, "browser E2E release gate")

deploy_app_only = Path("scripts/release/deploy-app-only.sh").read_text(encoding="utf-8")
for required in ('source "$ROOT_DIR/scripts/release/release-artifacts.sh"', 'RELEASE_LOGS_DIR'):
    require(deploy_app_only, required, "app-only release path")

deploy_ci_images = Path("scripts/release/deploy-ci-images.sh").read_text(encoding="utf-8")
for required in (
    'source "$ROOT_DIR/scripts/release/release-artifacts.sh"',
    'release_artifact_path images.json',
    'image-deploy.log',
    'service_name.image-deploy.log',
):
    require(deploy_ci_images, required, "CI image release path")

verify_deployment = Path("scripts/release/verify-release-deployment.sh").read_text(
    encoding="utf-8"
)
for required in ('"target_identity"', '"active_revision"', '"image_digest"', '"artifact_type": "deployment"'):
    require(verify_deployment, required, "deployment evidence contract")

foundry_eval_runner = Path("backend/evals/foundry_eval_runner.py").read_text(encoding="utf-8")
for required in ('FOUNDRY_EVAL_OUTPUT_FILE', 'http_output_capture', 'blocking_result_rows', 'run_status'):
    require(foundry_eval_runner, required, "Foundry evaluation gate")

eval_yaml = Path("backend/eval.yaml").read_text(encoding="utf-8")
require(eval_yaml, 'ord-1004-damaged-approve', "stable damaged evaluation scenario")
PY

echo "Azure-hosted runtime gates contract passed"
