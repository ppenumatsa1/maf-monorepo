#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/../deployment/profiles/foundry-private.env}"
RESULT_FILE="${POSTGRES_CONNECTIVITY_EVIDENCE_FILE:-${ROOT_DIR}/backend/.foundry/results/private-connectivity-proof.json}"

require_bin az
require_bin azd
require_bin curl
require_bin jq

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

cd "${FOUNDRY_DIR}"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt

get_env_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null || true
}

resource_group="$(get_env_value AZURE_RESOURCE_GROUP)"
subscription_id="$(get_env_value AZURE_SUBSCRIPTION_ID)"
backend_name="${SERVICE_BACKEND_NAME:-$(get_env_value SERVICE_BACKEND_NAME)}"
postgres_fqdn="${POSTGRES_SERVER_FQDN:-$(get_env_value POSTGRES_SERVER_FQDN)}"
hosted_agent_name="${HOSTED_AGENT_NAME:-$(get_env_value HOSTED_AGENT_NAME)}"
web_url="${WEB_URL:-$(get_env_value WEB_URL)}"

: "${resource_group:?AZURE_RESOURCE_GROUP is required}"
: "${backend_name:?SERVICE_BACKEND_NAME is required}"
: "${postgres_fqdn:?POSTGRES_SERVER_FQDN is required}"
: "${hosted_agent_name:?HOSTED_AGENT_NAME is required}"
: "${web_url:?WEB_URL is required}"

[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" ]] || {
  echo "Selected AZD resource group does not match the private deployment profile."
  exit 1
}
[[ "$subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Selected AZD subscription does not match the private deployment profile."
  exit 1
}

latest_ready_revision="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.latestReadyRevisionName' \
    --output tsv
)"
if [[ -z "$latest_ready_revision" ]]; then
  echo "Backend Container App has no ready revision; it cannot prove PostgreSQL connectivity."
  exit 1
fi

revision_state="$(
  az containerapp revision show \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --revision "$latest_ready_revision" \
    --query 'properties.runningState' \
    --output tsv
)"
if [[ "$revision_state" != "Running" ]]; then
  echo "Backend revision ${latest_ready_revision} is not running."
  exit 1
fi

workflow_response="$(curl --fail --silent --show-error --max-time 30 \
  "${web_url%/}/api/workflows?limit=1")"
jq -e '.items and (.total | type == "number")' <<<"$workflow_response" >/dev/null || {
  echo "The deployed ACA runtime did not return a database-backed workflow listing."
  exit 1
}

SMOKE_MESSAGE="${SMOKE_MESSAGE:-Resolve delayed order ORD-1009}" \
  SMOKE_MAX_ATTEMPTS="${SMOKE_MAX_ATTEMPTS:-6}" \
  make -C "$ROOT_DIR" foundry-smoke

mkdir -p "$(dirname "$RESULT_FILE")"
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$AZURE_SUBSCRIPTION_ID" \
  --arg resource_group "$resource_group" \
  --arg azd_environment "$AZURE_ENV_NAME" \
  --arg name_prefix "$NAME_PREFIX" \
  --arg backend_name "$backend_name" \
  --arg backend_revision "$latest_ready_revision" \
  --arg postgres_fqdn "${postgres_fqdn,,}" \
  --arg hosted_agent_name "$hosted_agent_name" \
  '{
    status: "passed",
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    aca_database_connectivity: "passed",
    hosted_agent_database_connectivity: "passed",
    resource_group: $resource_group,
    azd_environment: $azd_environment,
    name_prefix: $name_prefix,
    backend_container_app: $backend_name,
    backend_revision: $backend_revision,
    aca_database_probe: "GET /api/workflows?limit=1",
    postgres_fqdn: $postgres_fqdn,
    hosted_agent_name: $hosted_agent_name
  }' >"$RESULT_FILE"

echo "Recorded private connectivity proof at ${RESULT_FILE}."
