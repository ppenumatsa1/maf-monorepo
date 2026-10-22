#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
RESULTS_DIR="$ROOT_DIR/backend/.foundry/results"
EVIDENCE_FILE="${FOUNDRY_MODEL_PREFLIGHT_EVIDENCE_FILE:-$RESULTS_DIR/model-preflight-evidence.json}"
SUMMARY_FILE="$ROOT_DIR/backend/.tmp/capacity-preflight-$$.json"
CAPACITY_MODE="${FOUNDRY_CAPACITY_MODE:-app_only}"
PREFLIGHT_SCOPE="${FOUNDRY_PREFLIGHT_SCOPE:-all}"
[[ "$CAPACITY_MODE" == "app_only" || "$CAPACITY_MODE" == "full_infra" ]] || {
  echo "FOUNDRY_CAPACITY_MODE must be app_only or full_infra." >&2
  exit 2
}
[[ "$PREFLIGHT_SCOPE" == "all" || "$PREFLIGHT_SCOPE" == "hosted" ]] || {
  echo "FOUNDRY_PREFLIGHT_SCOPE must be all or hosted." >&2
  exit 2
}

cleanup() {
  rm -f -- "$SUMMARY_FILE"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$(dirname "$SUMMARY_FILE")" "$(dirname "$EVIDENCE_FILE")"

for command in az azd jq python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

get_env() {
  local value
  if value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    printf '%s' "$value"
  fi
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  export "$name=$value"
}

for key in \
  AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION \
  FOUNDRY_LOCATION FOUNDRY_ACCOUNT_NAME FOUNDRY_PROJECT_NAME \
  FOUNDRY_MODEL_DEPLOYMENT_NAME FOUNDRY_MODEL_FORMAT FOUNDRY_MODEL_NAME \
  FOUNDRY_MODEL_VERSION FOUNDRY_MODEL_SKU_NAME FOUNDRY_MODEL_CAPACITY \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME FOUNDRY_EMBEDDINGS_MODEL_FORMAT \
  FOUNDRY_EMBEDDINGS_MODEL_NAME FOUNDRY_EMBEDDINGS_MODEL_VERSION \
  FOUNDRY_EMBEDDINGS_MODEL_SKU_NAME FOUNDRY_EMBEDDINGS_MODEL_CAPACITY \
  FOUNDRY_EVAL_MODEL FOUNDRY_EVALUATION_MODEL_FORMAT \
  FOUNDRY_EVALUATION_MODEL_NAME FOUNDRY_EVALUATION_MODEL_VERSION \
  FOUNDRY_EVALUATION_MODEL_SKU_NAME FOUNDRY_EVALUATION_MODEL_CAPACITY \
  AI_SEARCH_SERVICE_NAME AI_SEARCH_LOCATION AI_SEARCH_SKU_NAME \
  POSTGRES_SERVER_NAME POSTGRES_SERVER_LOCATION POSTGRES_SKU_NAME \
  POSTGRES_SKU_TIER POSTGRES_VERSION CONTAINER_APPS_ENVIRONMENT_NAME \
  BACKEND_CONTAINER_APP_NAME FRONTEND_CONTAINER_APP_NAME \
  CONTAINER_REGISTRY_NAME CONTAINER_REGISTRY_SKU_NAME \
  BOT_SERVICE_NAME BOT_SERVICE_SKU_NAME; do
  required_env "$key"
done

actual_subscription="$(az account show --query id --output tsv)"
[[ "$actual_subscription" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI subscription does not match the selected external profile." >&2
  exit 1
}

python3 "$ROOT_DIR/scripts/foundry/capacity_preflight.py" \
  --mode "$CAPACITY_MODE" \
  --scope "$PREFLIGHT_SCOPE" \
  --output json >"$SUMMARY_FILE"

release_id="${FOUNDRY_RELEASE_ID:-manual-capacity-preflight}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
jq \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    schema_version: 1,
    evidence_type: "model_preflight",
    status: .status,
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    mode: .mode,
    scope: .scope,
    mutation_performed: .mutation_performed,
    incremental: .incremental,
    checks: .messages
  }' "$SUMMARY_FILE" >"$EVIDENCE_FILE"

echo "Public incremental-capacity preflight passed without changing Azure."
echo "Evidence written to ${EVIDENCE_FILE}."
