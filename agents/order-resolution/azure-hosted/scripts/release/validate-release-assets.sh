#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

require_fixed_line() {
  local expected="$1"
  local file="$2"

  if ! grep -Fqx "$expected" "$file"; then
    echo "Missing required release safeguard in $file: $expected" >&2
    exit 1
  fi
}

require_fixed_line "    PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple" \
  backend/Dockerfile
require_fixed_line "**/__pycache__/" backend/.dockerignore
require_fixed_line "**/__pycache__/" .gitignore

grep -Fq "host: containerapp" azure.yaml
grep -Fq "deploy_mode=app_only" scripts/skills/deployment-mode-router.sh
grep -Fq "^(frontend/" scripts/skills/deployment-mode-router.sh
grep -Fq 'user: "${DOCKER_E2E_UID:-1000}:${DOCKER_E2E_GID:-1000}"' docker-compose.yml
grep -Fq 'DOCKER_E2E_UID="$$(id -u)"' Makefile

python3 - <<'PY'
import json
from pathlib import Path

parameters = json.loads(
    Path("infra/azure-apphosted/iac/main.parameters.json").read_text(encoding="utf-8")
)
if "postgresBootstrapAllowedIp" not in parameters["parameters"]:
    raise SystemExit("PostgreSQL bootstrap parameter is missing from the IaC parameter file")

reconcile = Path("scripts/release/reconcile-infrastructure.sh").read_text(encoding="utf-8")
for required in (
    "deployment sub what-if",
    "--result-format ResourceIdOnly",
    "Azure what-if includes a PostgreSQL resource mutation",
    "server_no_change",
    "database_no_change",
    "INFRA_RECONCILIATION_APPROVED",
    "INFRA_RECONCILIATION_REFERENCE",
    "INFRA_RECONCILIATION_PREVIEW_SHA256",
    "INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256",
    "require_owner_confirmation",
    "require_parameters_file",
    "Owner-confirmed infrastructure reconciliation",
    "deployment sub create",
    '--subscription "$AZURE_SUBSCRIPTION_ID"',
):
    if required not in reconcile:
        raise SystemExit(f"Missing infrastructure reconciliation safeguard: {required}")
for removed in (
    "verify-github-pr-approval.py",
    "INFRA_RECONCILIATION_PR_NUMBER",
    "INFRA_RECONCILIATION_APPROVAL_COMMENT_ID",
    "require_protected_apply_context",
    "capture_reviewer_comment_attestation",
):
    if removed in reconcile:
        raise SystemExit(f"Unexpected team-review guard remains: {removed}")
if "azd provision" in reconcile:
    raise SystemExit("Infrastructure reconciliation must use the reviewed Azure what-if template and parameters.")
if "--initial" in reconcile:
    raise SystemExit("Infrastructure reconciliation must not retain an initial PostgreSQL provisioning path.")

reconciliation_wrapper = Path(
    "scripts/release/run-reconcile-infrastructure.sh"
).read_text(encoding="utf-8")
for required in (
    "/usr/bin/env -i",
    "PATH=$safe_path",
    "INFRA_RECONCILIATION_APPROVED",
    "INFRA_RECONCILIATION_PREVIEW_SHA256",
):
    if required not in reconciliation_wrapper:
        raise SystemExit(f"Missing hardened reconciliation wrapper safeguard: {required}")
for removed in (
    "INFRA_RECONCILIATION_PR_NUMBER",
    "INFRA_RECONCILIATION_APPROVAL_COMMENT_ID",
    "GITHUB_WORKFLOW_REF",
):
    if removed in reconciliation_wrapper:
        raise SystemExit(f"Unexpected team-review wrapper input remains: {removed}")

reconciliation_test = Path(
    "scripts/release/test-reconcile-infrastructure-approval.sh"
).read_text(encoding="utf-8")
for required in (
    "Credential-free owner-confirmation reconciliation guards passed",
    "missing owner confirmation",
    "missing owner reference",
    "mismatched preview digest",
    "PostgreSQL mutation",
    "FAKE_APPLY_SENTINEL",
):
    if required not in reconciliation_test:
        raise SystemExit(f"Missing reconciliation mock coverage: {required}")

telemetry = Path("scripts/release/verify-app-insights-correlation.sh").read_text(encoding="utf-8")
for required in (
    'evidence.get("correlations")',
    'threadId == {json.dumps(thread_id)} and workflowRunId == {json.dumps(workflow_run_id)}',
    "exceptionCount",
    "Azure CLI flattens one KQL result row",
    "for (( pair_index = 0; pair_index < pair_count; pair_index++ ))",
    '--subscription "$AZURE_SUBSCRIPTION_ID"',
):
    if required not in telemetry:
        raise SystemExit(f"Missing App Insights correlation safeguard: {required}")

release_validation = Path("scripts/release/validate-hosted-release.sh").read_text(encoding="utf-8")
for required in (
    'evidence["correlations"] = correlations',
    "exactly one workflow_run_id for fresh thread",
    'start_stage "hosted browser E2E"',
    'start_stage "Foundry evaluation"',
    "Hosted release validation failed:",
):
    if required not in release_validation:
        raise SystemExit(f"Missing hosted evidence safeguard: {required}")

ci_deploy = Path("scripts/release/deploy-ci-images.sh").read_text(encoding="utf-8")
for required in (
    "docker image inspect",
    "docker push",
    "az acr manifest show-metadata",
    "az containerapp update",
    "Deployed the tested immutable backend and frontend image digests.",
    "azd-service-name",
):
    if required not in ci_deploy:
        raise SystemExit(f"Missing CI image-release safeguard: {required}")
if "azd provision" in ci_deploy:
    raise SystemExit("The CI image release must not reconcile infrastructure.")

ci_environment = Path(
    "scripts/release/bootstrap-ci-azd-environment.sh"
).read_text(encoding="utf-8")
for required in (
    "azd env new",
    "AZURE_LOG_ANALYTICS_WORKSPACE_ID",
    "FOUNDRY_PROJECTS_ENDPOINT",
    "Reconstructed non-secret AZD release-validation configuration.",
):
    if required not in ci_environment:
        raise SystemExit(f"Missing CI release-validation configuration safeguard: {required}")

workflow = Path("../../../.github/workflows/order-resolution-azure-hosted-ci.yml").read_text(
    encoding="utf-8"
)
for required in (
    'paths:',
    '"agents/order-resolution/azure-hosted/**"',
    "Required cloud Docker E2E",
    "id-token: write",
    "Build the immutable release images",
    "Deploy the tested immutable images",
    "Smoke, hosted E2E, Foundry evaluation, and telemetry validation",
    "make deploy-ci-images",
    "make release-validate",
    "Prebuild immutable release image cache",
    "docker/setup-buildx-action@v3",
    "docker/build-push-action@v6",
    "ignore-error=true",
    "Cache Playwright browser",
):
    if required not in workflow:
        raise SystemExit(f"Missing Azure-hosted CI release safeguard: {required}")
if "azd provision" in workflow:
    raise SystemExit("The Azure-hosted CI release lane must remain app-only.")
PY

echo "Azure-hosted release asset validation passed"
