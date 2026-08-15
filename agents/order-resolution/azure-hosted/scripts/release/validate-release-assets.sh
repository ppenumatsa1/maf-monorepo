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
for required_parameter in (
    "targetSubscriptionId",
    "resourceGroupName",
    "infrastructureMode",
    "postgresBootstrapAllowedIp",
    "backendImage",
    "frontendImage",
    "foundryEvaluatorDeploymentSkuName",
):
    if required_parameter not in parameters["parameters"]:
        raise SystemExit(f"Hardened IaC parameter is missing: {required_parameter}")

reconcile = Path("scripts/release/reconcile-infrastructure.sh").read_text(encoding="utf-8")
for required in (
    "deployment sub what-if",
    "--result-format ResourceIdOnly",
    "steadyState mode must exclude it",
    '"infrastructureMode=steadyState"',
    "require_selected_target",
    "Infrastructure reconciliation completed while preserving PostgreSQL.",
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
    "INFRA_RECONCILIATION_APPROVED",
    "INFRA_RECONCILIATION_REFERENCE",
    "INFRA_RECONCILIATION_PREVIEW_SHA256",
    "INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256",
    "require_owner_confirmation",
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
):
    if required not in reconciliation_wrapper:
        raise SystemExit(f"Missing hardened reconciliation wrapper safeguard: {required}")
for removed in (
    "INFRA_RECONCILIATION_PR_NUMBER",
    "INFRA_RECONCILIATION_APPROVAL_COMMENT_ID",
    "GITHUB_WORKFLOW_REF",
    "INFRA_RECONCILIATION_APPROVED",
    "INFRA_RECONCILIATION_REFERENCE",
    "INFRA_RECONCILIATION_PREVIEW_SHA256",
    "INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256",
    "INFRA_RECONCILIATION_PARAMETERS_FILE",
):
    if removed in reconciliation_wrapper:
        raise SystemExit(f"Unexpected team-review wrapper input remains: {removed}")

reconciliation_test = Path(
    "scripts/release/test-reconcile-infrastructure-approval.sh"
).read_text(encoding="utf-8")
for required in (
    "Credential-free direct reconciliation guards passed",
    "PostgreSQL mutation",
    "FAKE_APPLY_SENTINEL",
):
    if required not in reconciliation_test:
        raise SystemExit(f"Missing reconciliation mock coverage: {required}")
for removed in (
    "INFRA_RECONCILIATION_APPROVED",
    "INFRA_RECONCILIATION_REFERENCE",
    "INFRA_RECONCILIATION_PREVIEW_SHA256",
    "INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256",
    "missing owner confirmation",
):
    if removed in reconciliation_test:
        raise SystemExit(f"Unexpected manual reconciliation gate remains in test: {removed}")

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
    'make --no-print-directory release-preflight',
    'make --no-print-directory release-verify',
    'make --no-print-directory release-smoke',
    'make --no-print-directory release-browser-e2e',
    'make --no-print-directory release-domain-e2e',
    'make --no-print-directory release-eval',
    'make --no-print-directory release-telemetry',
    'make --no-print-directory release-evidence',
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
    'revision_suffix="${revision_suffix,,}"',
    "Deployed the tested immutable backend and frontend image digests.",
    "azd-service-name",
    "require_selected_target",
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
    "require_selected_target",
    "Reconstructed non-secret AZD release-validation configuration.",
):
    if required not in ci_environment:
        raise SystemExit(f"Missing CI release-validation configuration safeguard: {required}")

selected_target = Path("scripts/release/selected-target.sh").read_text(encoding="utf-8")
for required in (
    "order_resolution_dir/deployment/profiles/azure-hosted.env",
    "order_resolution_dir/deployment/profile.sh",
):
    if required not in selected_target:
        raise SystemExit(f"Missing approved selected-target contract: {required}")
canonical_profile = Path(
    "../deployment/profiles/azure-hosted.env"
).read_text(encoding="utf-8")
for required in (
    "DEPLOYMENT_LANE=azure-hosted",
    "AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d",
    "AZURE_RESOURCE_GROUP=rg-maf-ora-azure",
    "AZURE_LOCATION=northcentralus",
):
    if required not in canonical_profile:
        raise SystemExit(f"Missing approved canonical profile contract: {required}")

bootstrap_profile = Path(
    "deployment/profiles/azure-hosted-bootstrap.env"
).read_text(encoding="utf-8")
if "legacy_pending_cutover" not in bootstrap_profile:
    raise SystemExit("Lane-local bootstrap profile must be labeled legacy_pending_cutover.")
for forbidden in ("PASSWORD=", "TOKEN=", "SECRET=", "BACKEND_IMAGE=", "FRONTEND_IMAGE="):
    if forbidden in bootstrap_profile:
        raise SystemExit(f"Tracked bootstrap profile contains forbidden deploy input: {forbidden}")

release_artifacts = Path("scripts/release/release-artifacts.sh").read_text(encoding="utf-8")
if 'canonical_profile="$ROOT_DIR/../deployment/profiles/azure-hosted.env"' not in release_artifacts:
    raise SystemExit("Release context must use the canonical Order Resolution profile.")

if Path("infra/azure-apphosted/iac/parameters.dev.json").exists():
    raise SystemExit("Tracked placeholder parameters.dev.json must not exist.")
for path in (
    Path("infra/azure-apphosted/iac/main.bicep"),
    Path("infra/azure-apphosted/iac/modules/foundry.bicep"),
    Path("infra/azure-apphosted/iac/main.parameters.json"),
):
    if "GlobalStandard" in path.read_text(encoding="utf-8"):
        raise SystemExit(f"Foundry bootstrap defaults must not assume GlobalStandard quota: {path}")

main_template = Path("infra/azure-apphosted/iac/main.bicep").read_text(encoding="utf-8")
for required in (
    "param foundryChatDeploymentSkuName string = 'Standard'",
    "param foundryEmbeddingsDeploymentSkuName string = 'DataZoneStandard'",
    "param foundryEvaluatorDeploymentSkuName string = 'Standard'",
    "module backend './modules/container-app.bicep' = if (infrastructureMode == 'bootstrap')",
    "module frontend './modules/container-app.bicep' = if (infrastructureMode == 'bootstrap')",
):
    if required not in main_template:
        raise SystemExit(f"Missing model-specific/app-config steady-state guard: {required}")

for required in (
    "required_azd_output FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME",
    "required_azd_output FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME",
    "required_azd_output FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME",
):
    if required not in reconcile:
        raise SystemExit(f"Missing stateful Foundry reconciliation input: {required}")
for forbidden in ("mcpApiKey=", "mcpBearerToken=", "mcpServerUrl="):
    if forbidden in reconcile:
        raise SystemExit(f"Steady-state reconciliation must exclude app secret/config input: {forbidden}")

postgres_grant = Path("scripts/azure/grant-postgres-identity.sh").read_text(
    encoding="utf-8"
)
for required in (
    "INFRASTRUCTURE_MODE",
    "Skipping PostgreSQL bootstrap grants in steadyState mode.",
    "require_selected_target",
    '--subscription "$AZURE_SUBSCRIPTION_ID"',
):
    if required not in postgres_grant:
        raise SystemExit(f"Missing PostgreSQL bootstrap target guard: {required}")

workflow = Path("../../../.github/workflows/order-resolution-azure-hosted-ci.yml").read_text(
    encoding="utf-8"
)
for required in (
    'paths:',
    '"agents/order-resolution/azure-hosted/**"',
    "Required cloud Docker E2E",
    "id-token: write",
    "Resolve canonical release identity",
    "Prepare canonical release context",
    "Run canonical release preflight",
    "Upload canonical release preflight bundle",
    "Download canonical release preflight bundle",
    "Build the immutable release images",
    "Deploy the tested immutable images",
    "Validate hosted release and aggregate final evidence",
    "make release-profile-apply",
    "make release-preflight",
    "make deploy-ci-images",
    "make release-validate",
    ".artifacts/releases/${{ needs.routing.outputs.release_id }}/",
    "RELEASE_STARTED_AT: ${{ needs.routing.outputs.release_started_at }}",
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
