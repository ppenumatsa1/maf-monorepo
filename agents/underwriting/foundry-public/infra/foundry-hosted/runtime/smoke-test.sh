#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

usage() {
  cat <<'USAGE'
Usage: smoke-test.sh [--mode <happy|retry|crash-resume>]

Runs a direct Responses smoke against the deployed underwriting-hosted agent.
AZD output is treated as customer-facing text; workflow assertions come from
durable PostgreSQL projections.
USAGE
}

extract_conversation_id() {
  local raw_payload="$1"
  local conversation_id
  conversation_id="$(
    printf '%s\n' "$raw_payload" |
      sed -n 's/^Conversation:[[:space:]]*//p' |
      head -n 1
  )"
  if [[ -z "$conversation_id" ]]; then
    conversation_id="$(
      printf '%s\n' "$raw_payload" |
        grep -Eo 'conv_[A-Za-z0-9_-]+' |
        head -n 1 || true
    )"
  fi
  printf '%s' "$conversation_id"
}

extract_customer_output() {
  local raw_payload="$1"
  local agent_name="$2"
  local text
  text="$(
    printf '%s\n' "$raw_payload" |
      sed -n "s/^\\[${agent_name}\\][[:space:]]*//p" |
      tail -n 1
  )"
  if [[ -z "$text" ]]; then
    text="$(printf '%s\n' "$raw_payload" | tail -n 1)"
  fi
  printf '%s' "$text"
}

build_start_payload() {
  local workflow_run_id="$1"
  local application_id="$2"
  local fail_risk_once="$3"
  local crash_after_executor="$4"
  jq -nc \
    --arg workflow_run_id "$workflow_run_id" \
    --arg application_id "$application_id" \
    --arg applicant_name "Ada Lovelace" \
    --arg crash_after_executor "$crash_after_executor" \
    --argjson fail_risk_once "$fail_risk_once" \
    '{
      protocol: "underwriting-hosted-workflow/v1",
      workflow_run_id: $workflow_run_id,
      action: "start",
      application: {
        application_id: $application_id,
        applicant_name: $applicant_name,
        age: 38,
        income: 145000,
        requested_coverage: 500000,
        health_disclosures: "none",
        driving_history: "clean",
        credit_score: 760
      },
      options: {
        fail_risk_once: $fail_risk_once,
        fail_credit_randomly: false,
        crash_after_executor: (if $crash_after_executor == "" then null else $crash_after_executor end)
      }
    }'
}

build_resume_payload() {
  local workflow_run_id="$1"
  jq -nc \
    --arg workflow_run_id "$workflow_run_id" \
    '{
      protocol: "underwriting-hosted-workflow/v1",
      workflow_run_id: $workflow_run_id,
      action: "resume"
    }'
}

invoke_azd_text() {
  local agent_name="$1"
  local payload_json="$2"
  local mode="${3:-reuse}"
  local raw rc max_attempts retry_seconds
  max_attempts="${FOUNDRY_SMOKE_MAX_ATTEMPTS:-20}"
  retry_seconds="${FOUNDRY_SMOKE_RETRY_SECONDS:-15}"
  for attempt in $(seq 1 "$max_attempts"); do
    set +e
    if [[ "$mode" == "new" ]]; then
      raw="$(
        AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
          azd ai agent invoke "$agent_name" "$payload_json" \
          --protocol responses --new-conversation --new-session --output raw --no-prompt 2>&1
      )"
    else
      raw="$(
        AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
          azd ai agent invoke "$agent_name" "$payload_json" \
          --protocol responses --output raw --no-prompt 2>&1
      )"
    fi
    rc=$?
    set -e
    if [[ $rc -eq 0 ]] &&
      grep -Eqi 'session_not_ready|424 Failed Dependency|"code"[[:space:]]*:[[:space:]]*"session_not_ready"' <<<"$raw"; then
      rc=1
    fi
    if [[ $rc -eq 0 ]]; then
      printf '%s\n' "$raw"
      return
    fi
    if grep -Eqi 'HTTP (404|409|429|5[0-9]{2})|context deadline exceeded|session_not_ready|timed out' <<<"$raw"; then
      echo "Transient invoke failure (attempt $attempt/$max_attempts); retrying." >&2
      sleep "$retry_seconds"
      continue
    fi
    echo "Smoke invoke failed:" >&2
    printf '%s\n' "$raw" >&2
    exit "$rc"
  done
  echo "Smoke invoke did not become ready after $max_attempts attempts." >&2
  printf '%s\n' "$raw" >&2
  exit "${rc:-1}"
}

invoke_structured_responses() {
  local conversation_id="$1"
  local payload_json="$2"
  local response_file="$RESULTS_DIR/.smoke-response-${workflow_run_id}-$$.json"
  local request_file="$RESULTS_DIR/.smoke-request-${workflow_run_id}-$$.json"
  local endpoint token status response_text curl_rc jq_rc
  endpoint="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT --no-prompt
  )"
  token="$(
    az account get-access-token \
      --scope https://ai.azure.com/.default \
      --query accessToken \
      --output tsv
  )"
  [[ -n "$endpoint" && -n "$token" ]] || {
    echo "Unable to resolve the hosted Responses endpoint or access token." >&2
    exit 1
  }
  jq -cn \
    --arg conversation_id "$conversation_id" \
    --arg payload "$payload_json" \
    '{
      conversation: {id: $conversation_id},
      input: [{
        type: "message",
        role: "user",
        content: [{type: "input_text", text: $payload}]
      }],
      stream: false
    }' >"$request_file"
  set +e
  status="$(
    curl --silent --show-error --max-time 300 \
      --output "$response_file" \
      --write-out '%{http_code}' \
      --oauth2-bearer "$token" \
      --header "Content-Type: application/json" \
      --data-binary "@$request_file" \
      "$endpoint"
  )"
  curl_rc=$?
  set -e
  rm -f "$request_file"
  if [[ $curl_rc -ne 0 ]]; then
    rm -f "$response_file"
    echo "Structured Responses invocation failed before an HTTP response was received." >&2
    exit "$curl_rc"
  fi
  if [[ ! "$status" =~ ^2[0-9][0-9]$ ]]; then
    echo "Structured Responses invocation failed with HTTP ${status}." >&2
    jq -c '{error: .error, status: .status}' "$response_file" >&2 2>/dev/null || true
    rm -f "$response_file"
    exit 1
  fi
  set +e
  response_text="$(
    jq -er '
      [.output[]?.content[]? | select(.type == "output_text") | .text]
      | last
      | select(type == "string" and length > 0)
    ' "$response_file"
  )"
  jq_rc=$?
  set -e
  rm -f "$response_file"
  if [[ $jq_rc -ne 0 ]]; then
    echo "Structured Responses invocation returned no customer-facing output text." >&2
    exit "$jq_rc"
  fi
  printf '%s\n' "$response_text"
}

db_query() {
  local sql="$1"
  printf '%s\n' "$sql" |
    psql "$DATABASE_URL" \
      --no-psqlrc \
      --set=ON_ERROR_STOP=1 \
      --set=workflow_run_id="$workflow_run_id" \
      --tuples-only \
      --no-align \
      --quiet
}

workflow_status() {
  db_query "SELECT status FROM workflow_runs WHERE id = :'workflow_run_id';"
}

workflow_decision() {
  db_query \
    "SELECT result_json->>'decision' FROM underwriting_results WHERE workflow_run_id = :'workflow_run_id' AND check_type = 'final_decision' ORDER BY created_at DESC LIMIT 1;"
}

result_count() {
  db_query \
    "SELECT COUNT(DISTINCT check_type) FROM underwriting_results WHERE workflow_run_id = :'workflow_run_id' AND check_type IN ('risk', 'credit', 'medical', 'driving');"
}

event_count() {
  local event_type="$1"
  db_query \
    "SELECT COUNT(*) FROM workflow_events WHERE workflow_run_id = :'workflow_run_id' AND event_type = '${event_type}';"
}

checkpoint_count() {
  db_query \
    "SELECT COUNT(*) FROM maf_checkpoints WHERE workflow_run_id = :'workflow_run_id';"
}

assert_projection() {
  local expected_status="$1"
  local actual_status
  actual_status="$(workflow_status)"
  [[ "${actual_status^^}" == "$expected_status" ]] || {
    echo "Expected durable workflow status ${expected_status}; got ${actual_status:-<missing>}." >&2
    exit 1
  }
}

MODE="${SMOKE_MODE:-happy}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  happy|retry|crash-resume) ;;
  *)
    echo "Invalid mode: $MODE (expected happy|retry|crash-resume)" >&2
    exit 1
    ;;
esac

for binary in az azd curl jq psql; do
  require_bin "$binary"
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
RESULTS_DIR="${FOUNDRY_RELEASE_EVIDENCE_DIR:-$ROOT_DIR/backend/.foundry/results}"
EVIDENCE_FILE="${FOUNDRY_SMOKE_EVIDENCE_FILE:-$RESULTS_DIR/hosted-smoke-evidence.json}"
mkdir -p "$RESULTS_DIR"

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
cd "$FOUNDRY_DIR"
agent_name="${HOSTED_AGENT_NAME:-$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value HOSTED_AGENT_NAME --no-prompt 2>/dev/null || true)}"
agent_name="${agent_name:-underwriting-hosted}"
DATABASE_URL="$(
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value RUNTIME_DATABASE_URL --no-prompt
)"
DATABASE_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
export DATABASE_URL

run_nonce="$(date -u +%Y%m%d%H%M%S)-$$"
workflow_run_id="run-smoke-${run_nonce}"
application_id="app-smoke-${run_nonce}"
conversation_id=""
customer_output=""

if [[ "$MODE" == "crash-resume" ]]; then
  start_raw="$(
    invoke_azd_text \
      "$agent_name" \
      "$(build_start_payload "$workflow_run_id" "$application_id" true "medical_check")" \
      new
  )"
  conversation_id="$(extract_conversation_id "$start_raw")"
  customer_output="$(extract_customer_output "$start_raw" "$agent_name")"
  [[ -n "$conversation_id" && -n "$customer_output" ]] || {
    echo "Hosted client output did not include a conversation and customer-facing response." >&2
    exit 1
  }
  assert_projection CRASHED
  [[ "$(checkpoint_count)" -gt 0 ]] || {
    echo "Crash smoke did not persist a MAF checkpoint." >&2
    exit 1
  }
  customer_output="$(
    invoke_structured_responses \
      "$conversation_id" \
      "$(build_resume_payload "$workflow_run_id")"
  )"
  assert_projection COMPLETED
  [[ "$(event_count idempotency_skip)" -gt 0 ]] || {
    echo "Resume smoke did not persist an idempotency skip event." >&2
    exit 1
  }
else
  fail_risk_once=false
  [[ "$MODE" == "retry" ]] && fail_risk_once=true
  smoke_raw="$(
    invoke_azd_text \
      "$agent_name" \
      "$(build_start_payload "$workflow_run_id" "$application_id" "$fail_risk_once" "")" \
      new
  )"
  conversation_id="$(extract_conversation_id "$smoke_raw")"
  customer_output="$(extract_customer_output "$smoke_raw" "$agent_name")"
  [[ -n "$conversation_id" && -n "$customer_output" ]] || {
    echo "Hosted client output did not include a conversation and customer-facing response." >&2
    exit 1
  }
  assert_projection COMPLETED
  if [[ "$MODE" == "retry" && "$(event_count retry_backoff)" -eq 0 ]]; then
    echo "Retry smoke did not persist a retry_backoff event." >&2
    exit 1
  fi
fi

decision="$(workflow_decision)"
[[ -n "$decision" && "$(result_count)" -eq 4 ]] || {
  echo "Durable underwriting projections are incomplete." >&2
  exit 1
}
[[ "$(event_count workflow_completed)" -gt 0 ]] || {
  echo "Durable workflow completion event is missing." >&2
  exit 1
}

mkdir -p "$(dirname "$EVIDENCE_FILE")"
jq -n \
  --arg release_id "${RELEASE_ID:-manual-smoke}" \
  --arg release_started_at "${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg mode "$MODE" \
  --arg workflow_run_id "$workflow_run_id" \
  --arg decision "$decision" \
  --arg conversation_id "$conversation_id" \
  '{
    schema_version: 1,
    evidence_type: "hosted_smoke",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    mode: $mode,
    conversation_ids: [$conversation_id],
    workflow_run_id: $workflow_run_id,
    decision: $decision,
    durable_projection_assertions: true,
    client_output_contract: "customer_facing"
  }' >"$EVIDENCE_FILE"

echo "Hosted underwriting smoke passed (${MODE}) for workflow_run_id=${workflow_run_id}."
echo "Evidence written to ${EVIDENCE_FILE}."
