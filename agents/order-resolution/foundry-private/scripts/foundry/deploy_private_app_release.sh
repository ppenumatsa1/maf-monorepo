#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/../deployment/profiles/foundry-private.env}"
BUILD_LOG="$(mktemp)"
BUILD_PID=""

cleanup() {
  if [[ -n "$BUILD_PID" ]] && kill -0 "$BUILD_PID" 2>/dev/null; then
    kill "$BUILD_PID"
    wait "$BUILD_PID" 2>/dev/null || true
  fi
  rm -f "$BUILD_LOG"
}
trap cleanup EXIT

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt
resource_group="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_RESOURCE_GROUP)"
registry_endpoint="$(az acr list --resource-group "$resource_group" --query '[0].loginServer' --output tsv)"
[[ -n "$registry_endpoint" ]] || {
  echo "Private application deployment requires the selected ACR endpoint." >&2
  exit 1
}

image_tag="${HOSTED_AGENT_IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)}"
hosted_image="${registry_endpoint}/order-resolution-hosted:${image_tag}"

cd "$ROOT_DIR"
./scripts/foundry/sync_hosted_source.sh
docker build \
  --platform linux/amd64 \
  --tag "$hosted_image" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent" >"$BUILD_LOG" 2>&1 &
BUILD_PID="$!"

app_status=0
make foundry-app-deploy || app_status=$?
build_status=0
wait "$BUILD_PID" || build_status=$?
cat "$BUILD_LOG"

if [[ "$app_status" -ne 0 ]]; then
  echo "Backend/frontend deployment failed while the hosted image was building." >&2
  exit "$app_status"
fi
if [[ "$build_status" -ne 0 ]]; then
  echo "Hosted-agent image build failed." >&2
  exit "$build_status"
fi

make foundry-app-images-verify
HOSTED_AGENT_IMAGE_TAG="$image_tag" \
HOSTED_AGENT_SKIP_BUILD=true \
  ./scripts/foundry/deploy_hosted_container.sh
