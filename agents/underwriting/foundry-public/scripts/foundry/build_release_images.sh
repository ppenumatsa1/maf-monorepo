#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
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

for command in az azd docker git; do
  require_bin "$command"
done
[[ -n "${RELEASE_ID:-}" && -n "${FOUNDRY_RELEASE_EVIDENCE_DIR:-}" && -n "${FOUNDRY_RELEASE_LOG_DIR:-}" ]] || {
  echo "RELEASE_ID and canonical release paths are required." >&2
  exit 2
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
"$ROOT_DIR/scripts/foundry/sync_hosted_source.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_repository="$(required_env BACKEND_IMAGE_REPOSITORY)"
frontend_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"
hosted_repository="underwriting-hosted"
tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"

build_acr_image() {
  local repository="$1"
  local dockerfile="$2"
  local context="$3"
  local log_file="$4"
  az acr build \
    --subscription "$subscription_id" \
    --registry "$registry_name" \
    --image "${repository}:${tag}" \
    --file "$dockerfile" \
    "$context" >"$log_file" 2>&1
}

build_acr_image \
  "$backend_repository" \
  "$ROOT_DIR/backend/Dockerfile" \
  "$ROOT_DIR" \
  "$FOUNDRY_RELEASE_LOG_DIR/backend-image-build.log" &
backend_pid=$!

build_acr_image \
  "$hosted_repository" \
  "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent" \
  "$FOUNDRY_RELEASE_LOG_DIR/hosted-image-build.log" &
hosted_pid=$!

(
  frontend_image="${registry_endpoint}/${frontend_repository}:${tag}"
  az acr login \
    --subscription "$subscription_id" \
    --name "$registry_name" \
    --output none
  docker build \
    --file "$ROOT_DIR/frontend/Dockerfile" \
    --tag "$frontend_image" \
    "$ROOT_DIR/frontend"
  docker push "$frontend_image"
) >"$FOUNDRY_RELEASE_LOG_DIR/frontend-image-build.log" 2>&1 &
frontend_pid=$!

status=0
for pid in "$backend_pid" "$hosted_pid" "$frontend_pid"; do
  wait "$pid" || status=1
done
(( status == 0 )) || {
  echo "One or more release image builds failed; inspect canonical release logs." >&2
  exit 1
}

resolve_image() {
  local repository="$1"
  local digest
  digest="$(
    az acr repository show \
      --subscription "$subscription_id" \
      --name "$registry_name" \
      --image "${repository}:${tag}" \
      --query digest \
      --output tsv
  )"
  [[ "$digest" == sha256:* ]] || {
    echo "Unable to resolve immutable digest for ${repository}:${tag}." >&2
    exit 1
  }
  printf '%s/%s@%s' "$registry_endpoint" "$repository" "$digest"
}

backend_image="$(resolve_image "$backend_repository")"
frontend_image="$(resolve_image "$frontend_repository")"
hosted_image="$(resolve_image "$hosted_repository")"
image_env="$FOUNDRY_RELEASE_EVIDENCE_DIR/release-images.env"
umask 077
{
  printf 'PUBLIC_BACKEND_PREBUILT_IMAGE=%q\n' "$backend_image"
  printf 'PUBLIC_FRONTEND_PREBUILT_IMAGE=%q\n' "$frontend_image"
  printf 'HOSTED_AGENT_PREBUILT_IMAGE=%q\n' "$hosted_image"
} >"$image_env"

echo "Built immutable backend, frontend, and hosted-agent images."
