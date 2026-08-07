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
RESULTS_DIR="${ROOT_DIR}/backend/.foundry/results"
HOSTED_E2E_EVIDENCE_FILE="${FOUNDRY_E2E_EVIDENCE_FILE:-${RESULTS_DIR}/hosted-e2e-evidence.json}"
TELEMETRY_RESULT_FILE="${TELEMETRY_RESULT_FILE:-${RESULTS_DIR}/telemetry-verification.json}"
FOUNDRY_REPORT_FILE="${FOUNDRY_REPORT_FILE:-${RESULTS_DIR}/foundry-report.json}"
RELEASE_EVIDENCE_REPORT_FILE="${PRIVATE_RELEASE_EVIDENCE_REPORT_FILE:-${RESULTS_DIR}/private-release-evidence.json}"

require_bin az
require_bin azd
require_bin jq

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
    --arg release_started_at "$release_started_at" \
    --arg generated_at "$completed_at" \
    --arg hosted_e2e_evidence_file "$HOSTED_E2E_EVIDENCE_FILE" \
    --arg hosted_e2e_started_at "$(jq -r '.started_at' "$HOSTED_E2E_EVIDENCE_FILE")" \
    --arg hosted_e2e_generated_at "$(jq -r '.generated_at' "$HOSTED_E2E_EVIDENCE_FILE")" \
    --arg telemetry_result_file "$TELEMETRY_RESULT_FILE" \
    --arg telemetry_status "$(jq -r '.status' "$TELEMETRY_RESULT_FILE")" \
    --arg telemetry_generated_at "$(jq -r '.generated_at' "$TELEMETRY_RESULT_FILE")" \
    --arg foundry_report_file "$FOUNDRY_REPORT_FILE" \
    --arg foundry_evaluation_status "$(jq -r '.status' "$FOUNDRY_REPORT_FILE")" \
    '{
      release_started_at: $release_started_at,
      generated_at: $generated_at,
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
resource_group="$(azd env get-value AZURE_RESOURCE_GROUP)"
connection_json="$(azd ai connection show ApplicationInsights --output json --no-prompt)"
application_insights_target="$(printf '%s' "$connection_json" | jq -r '.target // .metadata.ResourceId // .properties.target // empty')"
if [[ -z "$resource_group" || -z "$application_insights_target" ]]; then
  echo "Private release evidence requires an AZD resource group and ApplicationInsights project connection."
  exit 1
fi

hosted_agent_name="$(azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_NAME)"
hosted_agent_version="$(azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_VERSION)"
if [[ -z "$hosted_agent_name" || -z "$hosted_agent_version" ]]; then
  echo "Private release evidence requires the active hosted agent name and version."
  exit 1
fi

cd "$ROOT_DIR"
release_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FOUNDRY_E2E_EVIDENCE_FILE="$HOSTED_E2E_EVIDENCE_FILE" \
  ./scripts/github/foundry_hosted_e2e.sh
require_fresh_e2e_evidence "$release_started_at"
APPLICATION_INSIGHTS_RESOURCE_ID="$application_insights_target" \
FOUNDRY_EVALUATION_AGENT_ID="${hosted_agent_name}:${hosted_agent_version}" \
HOSTED_E2E_EVIDENCE_FILE="$HOSTED_E2E_EVIDENCE_FILE" \
TELEMETRY_RESULT_FILE="$TELEMETRY_RESULT_FILE" \
./scripts/foundry/verify_telemetry.sh
FOUNDRY_EVAL_ENFORCE_PASS=true \
FOUNDRY_EVAL_MAX_ERRORED=0 \
make eval-foundry
write_release_evidence_report

echo "Private release evidence collection completed: ${RELEASE_EVIDENCE_REPORT_FILE}"
