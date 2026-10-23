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
[[ -f "$FOUNDRY_ROLLBACK_BASELINE_FILE" ]] || {
  echo "Rollback baseline is required: $FOUNDRY_ROLLBACK_BASELINE_FILE" >&2
  exit 1
}
[[ -f "$FOUNDRY_RELEASE_EVIDENCE_DIR/release-images.env" ]] || {
  echo "Release image authority is missing." >&2
  exit 1
}

# shellcheck disable=SC1090
source "$FOUNDRY_RELEASE_EVIDENCE_DIR/release-images.env"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
agent_name="$(required_env AGENT_UNDERWRITING_HOSTED_NAME)"
agent_version="$(required_env AGENT_UNDERWRITING_HOSTED_VERSION)"
runtime_connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"
backend_name="$(jq -er '.container_apps.backend.name' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
frontend_name="$(jq -er '.container_apps.frontend.name' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_backend_revision="$(jq -er '.container_apps.backend.revision' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_backend_image="$(jq -er '.container_apps.backend.image' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_frontend_revision="$(jq -er '.container_apps.frontend.revision' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_frontend_image="$(jq -er '.container_apps.frontend.image' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_agent_version="$(jq -er '.hosted_agent.version' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"
prior_agent_image="$(jq -er '.hosted_agent.image' "$FOUNDRY_ROLLBACK_BASELINE_FILE")"

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
backend_revisions="$(
  az containerapp revision list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --all \
    --output json
)"
frontend_revisions="$(
  az containerapp revision list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --all \
    --output json
)"

jq -e \
  --arg revision "$prior_backend_revision" \
  --arg image "$prior_backend_image" \
  'any(.[]; .name == $revision and .properties.template.containers[0].image == $image)' \
  >/dev/null <<<"$backend_revisions" || {
  echo "Prior backend revision/image is no longer available for rollback." >&2
  exit 1
}
jq -e \
  --arg revision "$prior_frontend_revision" \
  --arg image "$prior_frontend_image" \
  'any(.[]; .name == $revision and .properties.template.containers[0].image == $image)' \
  >/dev/null <<<"$frontend_revisions" || {
  echo "Prior frontend revision/image is no longer available for rollback." >&2
  exit 1
}

current_backend_revision="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$backend_json")"
current_backend_image="$(jq -r '.properties.template.containers[0].image // empty' <<<"$backend_json")"
current_frontend_revision="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$frontend_json")"
current_frontend_image="$(jq -r '.properties.template.containers[0].image // empty' <<<"$frontend_json")"
[[ "$current_backend_image" == "$PUBLIC_BACKEND_PREBUILT_IMAGE" &&
  "$current_frontend_image" == "$PUBLIC_FRONTEND_PREBUILT_IMAGE" ]] || {
  echo "Current Container App revisions do not use the release-authority digests." >&2
  exit 1
}

prior_hosted_json="$(
  AZURE_AI_PROJECT_ENDPOINT="$project_endpoint" \
  HOSTED_AGENT_NAME="$agent_name" \
  HOSTED_AGENT_VERSION="$prior_agent_version" \
  FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name" \
    "$PYTHON" "$ROOT_DIR/scripts/foundry/inspect_hosted_agent.py"
)"
current_hosted_json="$(
  AZURE_AI_PROJECT_ENDPOINT="$project_endpoint" \
  HOSTED_AGENT_NAME="$agent_name" \
  HOSTED_AGENT_VERSION="$agent_version" \
  FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name" \
    "$PYTHON" "$ROOT_DIR/scripts/foundry/inspect_hosted_agent.py"
)"
jq -e \
  --arg image "$prior_agent_image" \
  '.image == $image and .immutable_image_digest' \
  >/dev/null <<<"$prior_hosted_json" || {
  echo "Prior hosted-agent version/image is no longer available for rollback." >&2
  exit 1
}
jq -e \
  --arg image "$HOSTED_AGENT_PREBUILT_IMAGE" \
  '.status == "active" and .is_active_version and .image == $image and .immutable_image_digest' \
  >/dev/null <<<"$current_hosted_json" || {
  echo "Current hosted-agent active metadata does not match the release digest." >&2
  exit 1
}

mkdir -p "$(dirname "$FOUNDRY_ROLLBACK_EVIDENCE_FILE")"
jq -n \
  --arg release_id "$RELEASE_ID" \
  --arg release_started_at "$FOUNDRY_RELEASE_STARTED_AT" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg prior_agent_version "$prior_agent_version" \
  --arg prior_agent_image "$prior_agent_image" \
  --arg current_agent_version "$agent_version" \
  --arg current_agent_image "$HOSTED_AGENT_PREBUILT_IMAGE" \
  --arg prior_backend_revision "$prior_backend_revision" \
  --arg prior_backend_image "$prior_backend_image" \
  --arg current_backend_revision "$current_backend_revision" \
  --arg current_backend_image "$current_backend_image" \
  --arg prior_frontend_revision "$prior_frontend_revision" \
  --arg prior_frontend_image "$prior_frontend_image" \
  --arg current_frontend_revision "$current_frontend_revision" \
  --arg current_frontend_image "$current_frontend_image" \
  '{
    schema_version: 1,
    evidence_type: "rollback_verification",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    hosted_agent: {
      prior: {version: $prior_agent_version, image: $prior_agent_image, preserved: true},
      current: {version: $current_agent_version, image: $current_agent_image, active: true}
    },
    container_apps: {
      backend: {
        prior: {revision: $prior_backend_revision, image: $prior_backend_image, preserved: true},
        current: {revision: $current_backend_revision, image: $current_backend_image}
      },
      frontend: {
        prior: {revision: $prior_frontend_revision, image: $prior_frontend_image, preserved: true},
        current: {revision: $current_frontend_revision, image: $current_frontend_image}
      }
    }
  }' >"$FOUNDRY_ROLLBACK_EVIDENCE_FILE"

echo "Rollback verification passed for the prior hosted version and Container App revisions."
