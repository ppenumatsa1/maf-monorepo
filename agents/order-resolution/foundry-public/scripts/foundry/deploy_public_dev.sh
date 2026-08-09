#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin azd
require_bin make

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

FOUNDRY_AZD_ENV_NAME="${FOUNDRY_AZD_ENV_NAME:-foundry-public-dev2}"
AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-maf-ora-foundry-public-dev2}"
AZURE_LOCATION="${AZURE_LOCATION:-eastus2}"
FOUNDRY_ACCOUNT_NAME="${FOUNDRY_ACCOUNT_NAME:-maffndaibfscpfhjr7sp4}"
FOUNDRY_PROJECT_NAME="${FOUNDRY_PROJECT_NAME:-order-resolution-public-managed-dev2}"
FOUNDRY_HOSTED_AGENT_NAME="${FOUNDRY_HOSTED_AGENT_NAME:-order-resolution-hosted}"
POSTGRES_SERVER_NAME="${POSTGRES_SERVER_NAME:-maffndpgbfscpfhjr7sp4cu}"
RUNTIME_DATABASE_URL="${RUNTIME_DATABASE_URL:-${DATABASE_URL:-}}"
FOUNDRY_RELEASE_BASE_REF="${FOUNDRY_RELEASE_BASE_REF:-HEAD}"
FOUNDRY_VALIDATION_MODE="${FOUNDRY_VALIDATION_MODE:-}"
FOUNDRY_INFRA_RECONCILIATION_APPROVED="${FOUNDRY_INFRA_RECONCILIATION_APPROVED:-false}"
FOUNDRY_INFRA_RECONCILIATION_REFERENCE="${FOUNDRY_INFRA_RECONCILIATION_REFERENCE:-}"

if [[ -n "${FOUNDRY_DEPLOY_MODE:-}" ]]; then
  echo "FOUNDRY_DEPLOY_MODE is no longer supported; automatic releases are app_only." >&2
  exit 1
fi
if [[ -z "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "AZURE_SUBSCRIPTION_ID is required."
  exit 1
fi
if [[ -z "$RUNTIME_DATABASE_URL" ]]; then
  echo "RUNTIME_DATABASE_URL (or DATABASE_URL) is required."
  exit 1
fi
if [[ "$RUNTIME_DATABASE_URL" != *"sslmode=require"* ]]; then
  echo "RUNTIME_DATABASE_URL must include sslmode=require."
  exit 1
fi
if [[ "$RUNTIME_DATABASE_URL" != *"${POSTGRES_SERVER_NAME}.postgres.database.azure.com"* ]]; then
  echo "RUNTIME_DATABASE_URL must target ${POSTGRES_SERVER_NAME}.postgres.database.azure.com."
  exit 1
fi
if [[ ! -f backend/Dockerfile.hosted || ! -f backend/foundry/main.py ]]; then
  echo "Hosted source validation failed: backend/Dockerfile.hosted and backend/foundry/main.py are required."
  exit 1
fi

AZURE_TENANT_ID="${AZURE_TENANT_ID:-$(az account show --subscription "$AZURE_SUBSCRIPTION_ID" --query tenantId -o tsv)}"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query id -o tsv | grep -qx "$AZURE_SUBSCRIPTION_ID"
azd auth login --check-status >/dev/null

echo "Selecting AZD environment: ${FOUNDRY_AZD_ENV_NAME}"
(
  cd infra/foundry-hosted
  azd env select "$FOUNDRY_AZD_ENV_NAME" || azd env new "$FOUNDRY_AZD_ENV_NAME"
  azd env set AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
  azd env set AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
  azd env set AZURE_LOCATION "$AZURE_LOCATION"
  azd env set AZURE_TENANT_ID "$AZURE_TENANT_ID"
  azd env set FOUNDRY_ACCOUNT_NAME "$FOUNDRY_ACCOUNT_NAME"
  azd env set FOUNDRY_PROJECT_NAME "$FOUNDRY_PROJECT_NAME"
  azd env set HOSTED_AGENT_NAME "$FOUNDRY_HOSTED_AGENT_NAME"
  azd env set FOUNDRY_RUNTIME_DATABASE_URL "$RUNTIME_DATABASE_URL"
  azd env set DATABASE_URL "$RUNTIME_DATABASE_URL"
  azd env set RUNTIME_DATABASE_URL "$RUNTIME_DATABASE_URL"
  azd env set POSTGRES_SERVER_NAME "$POSTGRES_SERVER_NAME"
  azd env set APP_ENV "${APP_ENV:-foundry-public-dev2}"
  azd env set STORE_PROVIDER "${STORE_PROVIDER:-postgres}"
  azd env set ENABLE_TELEMETRY "${ENABLE_TELEMETRY:-true}"
  azd env set ENABLE_INSTRUMENTATION "${ENABLE_INSTRUMENTATION:-true}"
  azd env set OTEL_SERVICE_NAME "${OTEL_SERVICE_NAME:-maf-order-resolution-foundry-public}"
  azd env set OTEL_SERVICE_NAMESPACE "${OTEL_SERVICE_NAMESPACE:-maf-order-resolution}"
  azd env set OTEL_RECORD_CONTENT "${OTEL_RECORD_CONTENT:-false}"
  azd env set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT "${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-}"
  azd env set FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT "${FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT:-true}"
)

wait_for_parallel_jobs() {
  local status=0
  local pid
  for pid in "$@"; do
    if ! wait "$pid"; then
      status=1
    fi
  done
  return "$status"
}

router_output="$(./scripts/skills/deployment-mode-router.sh "$FOUNDRY_RELEASE_BASE_REF")"
printf '%s\n' "$router_output"

deploy_mode="$(printf '%s\n' "$router_output" | sed -n 's/^deploy_mode=//p' | tail -n 1)"
validation_mode="$(printf '%s\n' "$router_output" | sed -n 's/^validation_mode=//p' | tail -n 1)"
infrastructure_reconciliation="$(printf '%s\n' "$router_output" | sed -n 's/^infrastructure_reconciliation=//p' | tail -n 1)"
reason="$(printf '%s\n' "$router_output" | sed -n 's/^reason=//p' | tail -n 1)"

if [[ -n "$FOUNDRY_VALIDATION_MODE" ]]; then
  validation_mode="$FOUNDRY_VALIDATION_MODE"
fi

if [[ "$deploy_mode" != "app_only" ]]; then
  echo "Automatic release routing must remain app_only; received: $deploy_mode" >&2
  exit 1
fi

case "$FOUNDRY_INFRA_RECONCILIATION_APPROVED" in
  false)
    reconcile_infrastructure=false
    ;;
  true)
    if [[ -z "$FOUNDRY_INFRA_RECONCILIATION_REFERENCE" ]]; then
      echo "FOUNDRY_INFRA_RECONCILIATION_REFERENCE is required with approved infrastructure reconciliation." >&2
      exit 1
    fi
    reconcile_infrastructure=true
    ;;
  *)
    echo "FOUNDRY_INFRA_RECONCILIATION_APPROVED must be true or false." >&2
    exit 1
    ;;
esac

echo "Release router selected deploy_mode=${deploy_mode} validation_mode=${validation_mode} infrastructure_reconciliation=${infrastructure_reconciliation} reason=${reason} base_ref=${FOUNDRY_RELEASE_BASE_REF}"

case "$validation_mode" in
  quick)
    validation_target=validate-quick
    ;;
  full)
    validation_target=validate-full
    ;;
  *)
    echo "Unsupported validation mode: $validation_mode" >&2
    exit 1
    ;;
esac

(
  # Local validation uses its isolated test database, never the production
  # runtime connection required by the later deployment steps.
  unset RUNTIME_DATABASE_URL DATABASE_URL
  make "$validation_target"
) &
validation_pid=$!
make foundry-iac-build &
iac_pid=$!
wait_for_parallel_jobs "$validation_pid" "$iac_pid"

if [[ "$reconcile_infrastructure" == true ]]; then
  echo "Running explicitly approved infrastructure reconciliation: ${FOUNDRY_INFRA_RECONCILIATION_REFERENCE}"
  FOUNDRY_INFRA_RECONCILIATION_APPROVED=true \
    FOUNDRY_INFRA_RECONCILIATION_REFERENCE="$FOUNDRY_INFRA_RECONCILIATION_REFERENCE" \
    make foundry-provision
fi

make foundry-release-deploy
make foundry-appinsights-connection

make foundry-smoke
release_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FOUNDRY_E2E_EVIDENCE_NOT_BEFORE="$release_started_at" make foundry-eval &
evaluation_pid=$!
if ! make foundry-hosted-e2e; then
  echo "Hosted E2E failed; cancelling the pending trace evaluation." >&2
  kill "$evaluation_pid" 2>/dev/null || true
  wait "$evaluation_pid" || true
  exit 1
fi

make foundry-telemetry &
telemetry_pid=$!
wait_for_parallel_jobs "$evaluation_pid" "$telemetry_pid"

echo "Order Resolution Foundry public release completed for AZD environment: ${FOUNDRY_AZD_ENV_NAME}"
