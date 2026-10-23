#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/.venv/bin/python"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

for binary in az azd jq; do
  require_bin "$binary"
done
[[ -x "$PYTHON" ]] || {
  echo "Project virtual environment is required; run make install first." >&2
  exit 1
}
[[ -n "${RELEASE_ID:-}" && -n "${FOUNDRY_RELEASE_STARTED_AT:-}" ]] || {
  echo "RELEASE_ID and FOUNDRY_RELEASE_STARTED_AT are required." >&2
  exit 2
}

if [[ -z "${FOUNDRY_ROLLBACK_BASELINE_FILE:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
agent_name="$(required_env AGENT_UNDERWRITING_HOSTED_NAME)"
agent_version="$(required_env AGENT_UNDERWRITING_HOSTED_VERSION)"
runtime_connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"

az account set --subscription "$subscription_id" >/dev/null
backend_json="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --output json
)"
frontend_json="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --output json
)"
hosted_json="$(
  AZURE_AI_PROJECT_ENDPOINT="$project_endpoint" \
  HOSTED_AGENT_NAME="$agent_name" \
  HOSTED_AGENT_VERSION="$agent_version" \
  FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name" \
    "$PYTHON" "$ROOT_DIR/scripts/foundry/inspect_hosted_agent.py"
)"

jq -e '
  .status == "active"
  and .is_active_version
  and .immutable_image_digest
' >/dev/null <<<"$hosted_json" || {
  echo "Current hosted-agent baseline is not an active immutable version." >&2
  exit 1
}

mkdir -p "$(dirname "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
jq -n \
  --arg release_id "$RELEASE_ID" \
  --arg release_started_at "$FOUNDRY_RELEASE_STARTED_AT" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg backend_name "$backend_name" \
  --arg backend_revision "$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$backend_json")" \
  --arg backend_image "$(jq -r '.properties.template.containers[0].image // empty' <<<"$backend_json")" \
  --arg frontend_name "$frontend_name" \
  --arg frontend_revision "$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$frontend_json")" \
  --arg frontend_image "$(jq -r '.properties.template.containers[0].image // empty' <<<"$frontend_json")" \
  --argjson hosted "$hosted_json" \
  '{
    schema_version: 1,
    evidence_type: "rollback_baseline",
    status: "captured",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    hosted_agent: $hosted,
    container_apps: {
      backend: {
        name: $backend_name,
        revision: $backend_revision,
        image: $backend_image
      },
      frontend: {
        name: $frontend_name,
        revision: $frontend_revision,
        image: $frontend_image
      }
    }
  }' >"$FOUNDRY_ROLLBACK_BASELINE_FILE"

echo "Captured immutable rollback baseline: ${FOUNDRY_ROLLBACK_BASELINE_FILE}"
