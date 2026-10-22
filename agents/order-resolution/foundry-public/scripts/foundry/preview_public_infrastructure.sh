#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PROFILE_FILE="${FOUNDRY_DEPLOYMENT_PROFILE:-$ROOT_DIR/deployment/profiles/foundry-public.env}"
PREVIEW_DIR="$ROOT_DIR/.artifacts/previews"
PREVIEW_FILE="$PREVIEW_DIR/public-reuse-preview-${FOUNDRY_RELEASE_ID:-manual}-$$.log"
SUMMARY_FILE="$ROOT_DIR/backend/.tmp/public-preview-summary-$$.json"
EVIDENCE_FILE="${FOUNDRY_PREVIEW_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/infrastructure-preview.json}"
PREVIEW_MODE="${FOUNDRY_PREVIEW_MODE:-reuse}"
[[ "$PREVIEW_MODE" == "reuse" || "$PREVIEW_MODE" == "full_infra" ]] || {
  echo "FOUNDRY_PREVIEW_MODE must be reuse or full_infra." >&2
  exit 2
}

cleanup() {
  rm -f -- "$SUMMARY_FILE"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$PREVIEW_DIR" "$(dirname "$SUMMARY_FILE")" "$(dirname "$EVIDENCE_FILE")"

for command in az azd jq python3 sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

[[ -f "$PROFILE_FILE" && ! -L "$PROFILE_FILE" ]] || {
  echo "External deployment profile is required: $PROFILE_FILE" >&2
  exit 1
}
bash "$ROOT_DIR/deployment/profile.sh" validate "$PROFILE_FILE"
source "$ROOT_DIR/deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$PREVIEW_MODE" == "full_infra" || "$INFRASTRUCTURE_MODE" == "reuse" ]] || {
  echo "Routine app-only preview requires INFRASTRUCTURE_MODE=reuse." >&2
  exit 1
}

AZD_PROJECT_DIR="$FOUNDRY_DIR" \
  bash "$ROOT_DIR/deployment/apply-azd-profile.sh" "$PROFILE_FILE" >/dev/null
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
if [[ "$PREVIEW_MODE" == "reuse" && "$(az group exists --name "$AZURE_RESOURCE_GROUP")" != "true" ]]; then
  echo "Non-mutating reuse preview requires an existing resource group." >&2
  exit 1
fi

(
  cd "$FOUNDRY_DIR"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd provision --preview --no-prompt
) >"$PREVIEW_FILE" 2>&1

if [[ "$PREVIEW_MODE" == "full_infra" ]]; then
  echo "Reviewed full-infrastructure preview completed without applying the plan."
  echo "Ignored preview log: $PREVIEW_FILE"
  exit 0
fi

python3 "$ROOT_DIR/scripts/foundry/validate_preview_output.py" \
  "$PREVIEW_FILE" --output json >"$SUMMARY_FILE"

release_id="${FOUNDRY_RELEASE_ID:-manual-preview}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
preview_sha256="$(sha256sum "$PREVIEW_FILE" | awk '{print $1}')"
jq \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg preview_sha256 "$preview_sha256" \
  '{
    schema_version: 1,
    evidence_type: "infrastructure_preview",
    status: .status,
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    mode: "reuse",
    mutation_performed: .mutation_performed,
    preview_sha256: $preview_sha256
  }' "$SUMMARY_FILE" >"$EVIDENCE_FILE"

echo "Non-mutating public reuse preview passed."
echo "Ignored preview log: $PREVIEW_FILE"
