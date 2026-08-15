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
source "${ROOT_DIR}/scripts/foundry/private_profile.sh"
PROFILE_FILE="$(private_profile_resolve "$ROOT_DIR")"
RELEASE_TOOL="${ROOT_DIR}/scripts/foundry/release_record.py"
source_commit="$(git -C "$ROOT_DIR" rev-parse HEAD)"
resolve_args=()
if [[ -n "${PRIVATE_RELEASE_ID:-}" ]]; then
  resolve_args+=(--release-id "$PRIVATE_RELEASE_ID")
fi
RELEASE_DIR="$(
  python3 "$RELEASE_TOOL" resolve \
    --project-root "$ROOT_DIR" \
    "${resolve_args[@]}" \
    --commit "$source_commit" \
    --profile "$PROFILE_FILE"
)"
PRIVATE_RELEASE_ID="$(basename "$RELEASE_DIR")"
export PRIVATE_RELEASE_ID
RESULTS_DIR="${RELEASE_DIR}/evidence"
HOSTED_E2E_EVIDENCE_FILE="${FOUNDRY_E2E_EVIDENCE_FILE:-${RESULTS_DIR}/hosted-e2e-evidence.json}"
TELEMETRY_RESULT_FILE="${TELEMETRY_RESULT_FILE:-${RESULTS_DIR}/telemetry-verification.json}"
FOUNDRY_REPORT_FILE="${FOUNDRY_REPORT_FILE:-${RESULTS_DIR}/foundry-report.json}"
RELEASE_EVIDENCE_REPORT_FILE="${PRIVATE_RELEASE_EVIDENCE_REPORT_FILE:-${RESULTS_DIR}/private-release-evidence.json}"
export HOSTED_E2E_EVIDENCE_FILE TELEMETRY_RESULT_FILE FOUNDRY_REPORT_FILE
FINAL_EVIDENCE_TIMING_RUNNING=false

cleanup() {
  local status=$?
  if [[ "$status" -ne 0 && "$FINAL_EVIDENCE_TIMING_RUNNING" == true ]]; then
    python3 "$RELEASE_TOOL" timing-end --project-root "$ROOT_DIR" \
      --release-id "$PRIVATE_RELEASE_ID" --stage final_evidence --status failed || true
  fi
  return "$status"
}
trap cleanup EXIT

require_bin az
require_bin azd
require_bin jq

run_timed_stage() {
  local stage="$1"
  shift
  python3 "$RELEASE_TOOL" timing-start --project-root "$ROOT_DIR" \
    --release-id "$PRIVATE_RELEASE_ID" --stage "$stage"
  local status=0
  "$@" || status=$?
  if [[ "$status" -eq 0 ]]; then
    python3 "$RELEASE_TOOL" timing-end --project-root "$ROOT_DIR" \
      --release-id "$PRIVATE_RELEASE_ID" --stage "$stage" --status succeeded
  else
    python3 "$RELEASE_TOOL" timing-end --project-root "$ROOT_DIR" \
      --release-id "$PRIVATE_RELEASE_ID" --stage "$stage" --status failed
  fi
  return "$status"
}

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

timestamp_epoch() {
  date -u -d "$1" +%s 2>/dev/null || true
}

require_fresh_e2e_evidence() {
  local not_before="$1"
  local started_at
  local generated_at
  local not_before_epoch
  local started_epoch
  local generated_epoch

  [[ -f "$HOSTED_E2E_EVIDENCE_FILE" ]] || {
    echo "Hosted E2E evidence is required: ${HOSTED_E2E_EVIDENCE_FILE}" >&2
    exit 1
  }
  started_at="$(jq -r '.started_at // empty' "$HOSTED_E2E_EVIDENCE_FILE")"
  generated_at="$(jq -r '.generated_at // empty' "$HOSTED_E2E_EVIDENCE_FILE")"
  not_before_epoch="$(timestamp_epoch "$not_before")"
  started_epoch="$(timestamp_epoch "$started_at")"
  generated_epoch="$(timestamp_epoch "$generated_at")"
  if [[ -z "$not_before_epoch" || -z "$started_epoch" || -z "$generated_epoch" ||
    "$started_epoch" -lt "$not_before_epoch" || "$generated_epoch" -lt "$started_epoch" ]]; then
    echo "Hosted E2E evidence must be current for this release and have ordered UTC timestamps." >&2
    exit 1
  fi
}

write_release_evidence_report() {
  local completed_at
  completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  mkdir -p "$(dirname "$RELEASE_EVIDENCE_REPORT_FILE")"
  jq -n \
    --arg release_id "$PRIVATE_RELEASE_ID" \
    --arg release_started_at "$release_started_at" \
    --arg generated_at "$completed_at" \
    --arg subscription_id "$AZURE_SUBSCRIPTION_ID" \
    --arg resource_group "$AZURE_RESOURCE_GROUP" \
    --arg azd_environment "$AZURE_ENV_NAME" \
    --arg name_prefix "$NAME_PREFIX" \
    --arg hosted_agent_name "$hosted_agent_name" \
    --arg hosted_agent_version "$hosted_agent_version" \
    --arg hosted_e2e_evidence_file "evidence/$(basename "$HOSTED_E2E_EVIDENCE_FILE")" \
    --arg hosted_e2e_started_at "$(jq -r '.started_at' "$HOSTED_E2E_EVIDENCE_FILE")" \
    --arg hosted_e2e_generated_at "$(jq -r '.generated_at' "$HOSTED_E2E_EVIDENCE_FILE")" \
    --arg telemetry_result_file "evidence/$(basename "$TELEMETRY_RESULT_FILE")" \
    --arg telemetry_status "$(jq -r '.status' "$TELEMETRY_RESULT_FILE")" \
    --arg telemetry_generated_at "$(jq -r '.generated_at' "$TELEMETRY_RESULT_FILE")" \
    --arg foundry_report_file "evidence/$(basename "$FOUNDRY_REPORT_FILE")" \
    --arg foundry_evaluation_status "$(jq -r '.status' "$FOUNDRY_REPORT_FILE")" \
    '{
      release_started_at: $release_started_at,
      release_id: $release_id,
      generated_at: $generated_at,
      target: {
        subscription_id: $subscription_id,
        resource_group: $resource_group,
        azd_environment: $azd_environment,
        name_prefix: $name_prefix
      },
      hosted_agent: {
        name: $hosted_agent_name,
        version: $hosted_agent_version
      },
      hosted_e2e: {
        evidence_file: $hosted_e2e_evidence_file,
        started_at: $hosted_e2e_started_at,
        generated_at: $hosted_e2e_generated_at
      },
      telemetry: {
        result_file: $telemetry_result_file,
        status: $telemetry_status,
        generated_at: $telemetry_generated_at
      },
      foundry_evaluation: {
        report_file: $foundry_report_file,
        status: $foundry_evaluation_status
      }
    }' >"$RELEASE_EVIDENCE_REPORT_FILE"
}

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt
resource_group="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_RESOURCE_GROUP)"
subscription_id="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_SUBSCRIPTION_ID)"
name_prefix="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value NAME_PREFIX)"
[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" &&
  "$subscription_id" == "$AZURE_SUBSCRIPTION_ID" &&
  "$name_prefix" == "$NAME_PREFIX" ]] || {
  echo "Selected AZD target does not match the private deployment profile."
  exit 1
}
foundry_project_id="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value FOUNDRY_PROJECT_ID)"
connection_json="$(
  az rest \
    --method get \
    --url "https://management.azure.com${foundry_project_id}/connections/ApplicationInsights?api-version=2025-04-01-preview"
)"
application_insights_target="$(printf '%s' "$connection_json" | jq -r '.properties.target // empty')"
if [[ -z "$resource_group" || -z "$application_insights_target" ]]; then
  echo "Private release evidence requires an AZD resource group and ApplicationInsights project connection."
  exit 1
fi

hosted_agent_name="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_NAME)"
hosted_agent_version="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_VERSION)"
if [[ -z "$hosted_agent_name" || -z "$hosted_agent_version" ]]; then
  echo "Private release evidence requires the active hosted agent name and version."
  exit 1
fi

cd "$ROOT_DIR"
release_started_at="$(jq -r '.started_at' "${RELEASE_DIR}/release.json")"
FOUNDRY_E2E_EVIDENCE_FILE="$HOSTED_E2E_EVIDENCE_FILE" \
  run_timed_stage hitl_e2e ./scripts/github/foundry_hosted_e2e.sh
require_fresh_e2e_evidence "$release_started_at"
APPLICATION_INSIGHTS_RESOURCE_ID="$application_insights_target" \
FOUNDRY_EVALUATION_AGENT_ID="${hosted_agent_name}:${hosted_agent_version}" \
HOSTED_E2E_EVIDENCE_FILE="$HOSTED_E2E_EVIDENCE_FILE" \
TELEMETRY_RESULT_FILE="$TELEMETRY_RESULT_FILE" \
run_timed_stage telemetry ./scripts/foundry/verify_telemetry.sh
FOUNDRY_EVAL_ENFORCE_PASS=true \
FOUNDRY_EVAL_MAX_ERRORED=0 \
run_timed_stage evaluation make eval-foundry
python3 "$RELEASE_TOOL" timing-start --project-root "$ROOT_DIR" \
  --release-id "$PRIVATE_RELEASE_ID" --stage final_evidence
FINAL_EVIDENCE_TIMING_RUNNING=true
write_release_evidence_report
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate hitl_e2e --status succeeded --artifact evidence/hosted-e2e-evidence.json
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate telemetry --status succeeded --artifact evidence/telemetry-verification.json
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate foundry_evaluation --status succeeded --artifact evidence/foundry-report.json
python3 "$RELEASE_TOOL" gate --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --gate release_evidence --status succeeded --artifact evidence/private-release-evidence.json
python3 "$RELEASE_TOOL" timing-end --project-root "$ROOT_DIR" \
  --release-id "$PRIVATE_RELEASE_ID" --stage final_evidence --status succeeded
FINAL_EVIDENCE_TIMING_RUNNING=false
python3 "$RELEASE_TOOL" finalize --project-root "$ROOT_DIR" --release-id "$PRIVATE_RELEASE_ID" \
  --status succeeded

echo "Private release evidence collection completed: ${RELEASE_EVIDENCE_REPORT_FILE}"
