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
    'RELEASE_API_BASE_URL:-${WEB_URL:-$(get_azd_output WEB_URL)}',
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
    'make --no-print-directory release-telemetry',
    'make --no-print-directory release-eval',
    'make --no-print-directory release-evidence',
    'Hosted release validation failed:',
):
    require(release_validation, required, "release validation orchestration")
if release_validation.index("run_stage \"telemetry correlation\"") > release_validation.index(
    "run_stage \"Foundry evaluation\""
):
    raise SystemExit("Telemetry must run before strict Foundry evaluation.")

run_browser_e2e = Path("scripts/release/run-browser-e2e.sh").read_text(encoding="utf-8")
for required in (
    'PLAYWRIGHT_BASE_URL',
    'browser-e2e.log',
    'make --no-print-directory test-e2e',
):
    require(run_browser_e2e, required, "browser E2E release gate")

release_smoke = Path("scripts/release/run-release-smoke.sh").read_text(encoding="utf-8")
require(
    release_smoke,
    'release_api_url="${RELEASE_API_BASE_URL:-$web_url}"',
    "same-origin smoke API base",
)

deploy_app_only = Path("scripts/release/deploy-app-only.sh").read_text(encoding="utf-8")
for required in (
    'source "$ROOT_DIR/scripts/release/release-artifacts.sh"',
    "RELEASE_LOGS_DIR",
    'converge_ingress "$backend_app" internal 8000',
    'DB_SCHEMA_MANAGED_EXTERNALLY=true',
    'Backend FRONTEND_ORIGIN must match the deployed frontend before release.',
    'NGINX_API_UPSTREAM=https://$backend_fqdn',
    'converge_ingress "$frontend_app" external 5173',
):
    require(deploy_app_only, required, "app-only release path")

deploy_ci_images = Path("scripts/release/deploy-ci-images.sh").read_text(encoding="utf-8")
for required in (
    'source "$ROOT_DIR/scripts/release/release-artifacts.sh"',
    'release_artifact_path images.json',
    'image-deploy.log',
    'service_name.image-deploy.log',
    "--type internal",
    "--type external",
    'DB_SCHEMA_MANAGED_EXTERNALLY=true',
    'FRONTEND_ORIGIN=https://$frontend_fqdn',
    'NGINX_API_UPSTREAM=https://$backend_fqdn',
):
    require(deploy_ci_images, required, "CI image release path")

verify_deployment = Path("scripts/release/verify-release-deployment.sh").read_text(
    encoding="utf-8"
)
for required in (
    '"target_identity"',
    '"active_revision"',
    '"image_digest"',
    '"artifact_type": "deployment"',
    'Expected backend DB_SCHEMA_MANAGED_EXTERNALLY=true.',
    'Expected backend FRONTEND_ORIGIN to match WEB_URL.',
):
    require(verify_deployment, required, "deployment evidence contract")

main_bicep = Path("infra/azure-apphosted/iac/main.bicep").read_text(encoding="utf-8")
for required in (
    "name: 'DB_SCHEMA_MANAGED_EXTERNALLY'",
    "name: 'FRONTEND_ORIGIN'",
    "value: frontendOrigin",
):
    require(main_bicep, required, "backend runtime environment")

foundry_eval_runner = Path("backend/evals/foundry_eval_runner.py").read_text(encoding="utf-8")
for required in (
    'FOUNDRY_EVAL_OUTPUT_FILE',
    'http_output_capture',
    'per_testing_criteria_results',
    'run_status',
    'evaluation_mode',
):
    require(foundry_eval_runner, required, "Foundry evaluation gate")

eval_yaml = Path("backend/eval.yaml").read_text(encoding="utf-8")
require(eval_yaml, 'ord-1004-damaged-approve', "stable damaged evaluation scenario")
require(eval_yaml, 'task_completion', "strict task-completion evaluator")
require(eval_yaml, 'coherence', "strict coherence evaluator")

eval_retry = Path("scripts/release/run-foundry-eval.sh").read_text(encoding="utf-8")
for required in (
    'FOUNDRY_EVAL_ERROR_RETRY_ATTEMPTS',
    'FOUNDRY_EVAL_ERROR_RETRY_SECONDS',
    '("failed", "skipped", "expected")',
    'errors += int(result.get("errored", 0))',
):
    require(eval_retry, required, "Foundry evaluator retry contract")
PY

echo "Azure-hosted runtime gates contract passed"
