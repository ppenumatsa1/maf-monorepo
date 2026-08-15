#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
source "${ROOT_DIR}/scripts/foundry/private_profile.sh"
PROFILE_FILE="$(private_profile_resolve "$ROOT_DIR")"
RELEASE_TOOL="${ROOT_DIR}/scripts/foundry/release_record.py"
BUILD_LOG=""
BUILD_PID=""
RELEASE_INITIALIZED=false
RELEASE_STAGE="initialization"
APP_ONLY_TIMING_STARTED=false
APP_ONLY_TIMING_ENDED=false
PACKAGE_TIMING_RUNNING=false
ACA_TIMING_RUNNING=false
VERIFICATION_TIMING_RUNNING=false
ACTIVATION_TIMING_RUNNING=false

timing_start() {
  python3 "$RELEASE_TOOL" timing-start --project-root "$ROOT_DIR" \
    --release-id "$PRIVATE_RELEASE_ID" --stage "$1"
}

timing_end() {
  python3 "$RELEASE_TOOL" timing-end --project-root "$ROOT_DIR" \
    --release-id "$PRIVATE_RELEASE_ID" --stage "$1" --status "$2"
}

cleanup() {
  local status=$?
  if [[ -n "$BUILD_PID" ]] && kill -0 "$BUILD_PID" 2>/dev/null; then
    kill "$BUILD_PID"
    wait "$BUILD_PID" 2>/dev/null || true
  fi
  if [[ "$status" -ne 0 && "$RELEASE_INITIALIZED" == true ]]; then
    if [[ "$ACTIVATION_TIMING_RUNNING" == true ]]; then
      timing_end hosted_agent_activation failed || true
    fi
    if [[ "$VERIFICATION_TIMING_RUNNING" == true ]]; then
      timing_end verification_smoke failed || true
    fi
    if [[ "$ACA_TIMING_RUNNING" == true ]]; then
      timing_end aca_deploy failed || true
    fi
    if [[ "$PACKAGE_TIMING_RUNNING" == true ]]; then
      timing_end hosted_image_package failed || true
    fi
    if [[ "$APP_ONLY_TIMING_STARTED" == true && "$APP_ONLY_TIMING_ENDED" == false ]]; then
      timing_end app_only failed || true
    fi
    python3 "$RELEASE_TOOL" finalize \
      --project-root "$ROOT_DIR" \
      --release-id "$PRIVATE_RELEASE_ID" \
      --status failed \
      --failed-stage "$RELEASE_STAGE" \
      --error "Private application release failed; inspect ignored release logs." || true
  fi
  return "$status"
}
trap cleanup EXIT

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "${PRIVATE_RELEASE_PREREQUISITES_PASSED:-}" == "true" ]] || {
  echo "Release initialization requires successful private preflight and PostgreSQL readiness." >&2
  exit 1
}

source_commit="$(git -C "$ROOT_DIR" rev-parse HEAD)"
source_repository="$(git -C "$ROOT_DIR" config --get remote.origin.url || printf 'local:%s' "$ROOT_DIR")"
PRIVATE_RELEASE_ID="${PRIVATE_RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-${source_commit:0:12}}"
export PRIVATE_RELEASE_ID
executor="local"
init_args=()
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  executor="github-actions"
fi
if [[ -n "${GITHUB_RUN_ID:-}" ]]; then
  init_args+=(--workflow-run-id "$GITHUB_RUN_ID")
fi
RELEASE_DIR="$(
  python3 "$RELEASE_TOOL" init \
    --project-root "$ROOT_DIR" \
    --release-id "$PRIVATE_RELEASE_ID" \
    --profile "$PROFILE_FILE" \
    --repository "$source_repository" \
    --commit "$source_commit" \
    --environment "$AZURE_ENV_NAME" \
    --subscription-id "$AZURE_SUBSCRIPTION_ID" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --executor "$executor" \
    "${init_args[@]}"
)"
RELEASE_INITIALIZED=true
BUILD_LOG="${RELEASE_DIR}/logs/hosted-image-build.log"
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate private_app_preflight --status succeeded
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate postgres_readiness --status succeeded

RELEASE_STAGE="target-validation"
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
RELEASE_STAGE="application-deployment"
timing_start app_only
APP_ONLY_TIMING_STARTED=true
timing_start hosted_image_package
PACKAGE_TIMING_RUNNING=true
./scripts/foundry/sync_hosted_source.sh
docker build \
  --platform linux/amd64 \
  --tag "$hosted_image" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent" >"$BUILD_LOG" 2>&1 &
BUILD_PID="$!"

app_status=0
timing_start aca_deploy
ACA_TIMING_RUNNING=true
make foundry-app-deploy || app_status=$?
if [[ "$app_status" -eq 0 ]]; then
  timing_end aca_deploy succeeded
else
  timing_end aca_deploy failed
fi
ACA_TIMING_RUNNING=false
build_status=0
wait "$BUILD_PID" || build_status=$?
BUILD_PID=""
if [[ "$build_status" -eq 0 ]]; then
  timing_end hosted_image_package succeeded
else
  timing_end hosted_image_package failed
fi
PACKAGE_TIMING_RUNNING=false
cat "$BUILD_LOG"

if [[ "$app_status" -ne 0 ]]; then
  echo "Backend/frontend deployment failed while the hosted image was building." >&2
  exit "$app_status"
fi
if [[ "$build_status" -ne 0 ]]; then
  echo "Hosted-agent image build failed." >&2
  exit "$build_status"
fi

timing_start verification_smoke
VERIFICATION_TIMING_RUNNING=true
make foundry-app-images-verify
timing_end verification_smoke succeeded
VERIFICATION_TIMING_RUNNING=false
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate app_deployment --status succeeded
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate image_verification --status succeeded
RELEASE_STAGE="hosted-agent-deployment"
timing_start hosted_agent_activation
ACTIVATION_TIMING_RUNNING=true
HOSTED_AGENT_IMAGE_TAG="$image_tag" \
HOSTED_AGENT_SKIP_BUILD=true \
  ./scripts/foundry/deploy_hosted_container.sh
timing_end hosted_agent_activation succeeded
ACTIVATION_TIMING_RUNNING=false
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n \
  --arg release_id "$PRIVATE_RELEASE_ID" \
  --arg started_at "$(jq -r '.started_at' "${RELEASE_DIR}/release.json")" \
  --arg generated_at "$completed_at" \
  --arg image_tag "$image_tag" \
  '{
    release_id: $release_id,
    started_at: $started_at,
    generated_at: $generated_at,
    app_deployment: "succeeded",
    image_verification: "succeeded",
    hosted_agent_deployment: "succeeded",
    hosted_image_tag: $image_tag
  }' >"${RELEASE_DIR}/evidence/deployment.json"
for gate in app_deployment image_verification hosted_agent_deployment; do
  python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
    --gate "$gate" --status succeeded --artifact evidence/deployment.json
done
timing_end app_only succeeded
APP_ONLY_TIMING_ENDED=true
echo "Private release context initialized: ${PRIVATE_RELEASE_ID}"
