#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin azd
require_bin az
require_bin curl
require_bin jq
require_bin psql

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${FOUNDRY_DIR:-$ROOT_DIR/infra/foundry-hosted}"

if [[ ! -f "$FOUNDRY_DIR/azure.yaml" ]]; then
  echo "Unable to locate Foundry AZD project at $FOUNDRY_DIR"
  exit 1
fi

cd "$FOUNDRY_DIR"

BASE_ID="${1:-foundry-e2e-$(date +%s)}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RESULTS_DIR="$ROOT_DIR/backend/.foundry/results"
PAYLOAD_FILE="$RESULTS_DIR/.hosted-e2e-resume-${BASE_ID//[^[:alnum:]._-]/_}-$$.json"
RESPONSE_FILE="$RESULTS_DIR/.hosted-e2e-response-${BASE_ID//[^[:alnum:]._-]/_}-$$.json"
TRACE_EVALUATION_HEADER="x-client-trace-evaluation-record-content: true"
mkdir -p "$RESULTS_DIR"
trap 'rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE"' EXIT

extract_conversation_id() {
  local raw="${1:-}"
  printf '%s\n' "$raw" |
    sed -n 's/^Conversation:[[:space:]]*//p' |
    head -n 1
}

extract_response_text() {
  local raw="${1:-}"
  printf '%s\n' "$raw" |
    sed -n 's/^\[order-resolution-hosted\][[:space:]]*//p' |
    tail -n 1
}

invoke_responses_payload() {
  local conversation_id="${1:-}"
  local payload_json="${2:-}"
  local mode="${3:-reuse}"
  local input_text
  input_text="$(jq -er '.input | select(type == "string")' <<<"$payload_json")" || {
    echo "AZD Responses invocation requires a plain string input." >&2
    exit 1
  }

  local raw
  local rc
  for attempt in $(seq 1 20); do
    set +e
    if [[ -n "$conversation_id" ]]; then
      raw="$(azd ai agent invoke order-resolution-hosted "$input_text" --protocol responses --conversation-id "$conversation_id" --client-header "$TRACE_EVALUATION_HEADER" --no-prompt 2>&1)"
    elif [[ "$mode" == "new" ]]; then
      raw="$(azd ai agent invoke order-resolution-hosted "$input_text" --protocol responses --new-conversation --new-session --client-header "$TRACE_EVALUATION_HEADER" --no-prompt 2>&1)"
    else
      raw="$(azd ai agent invoke order-resolution-hosted "$input_text" --protocol responses --client-header "$TRACE_EVALUATION_HEADER" --no-prompt 2>&1)"
    fi
    rc=$?
    set -e
    if [[ $rc -eq 0 ]] && echo "$raw" | grep -Eqi 'session_not_ready|424 Failed Dependency|"code"[[:space:]]*:[[:space:]]*"session_not_ready"'; then
      rc=1
    fi
    if [[ $rc -eq 0 ]]; then
      break
    fi
    if echo "$raw" | grep -Eqi 'HTTP (404|409|429|5[0-9]{2})|context deadline exceeded|Client\.Timeout|timed out'; then
      echo "Transient payload invoke failure (attempt $attempt/20, conversation_id=${conversation_id:-<new>}). Retrying..." >&2
      sleep 15
      continue
    fi
    break
  done
  if [[ $rc -ne 0 ]]; then
    echo "azd payload invoke failed (rc=$rc, conversation_id=${conversation_id:-<new>}):" >&2
    echo "$raw" >&2
    exit $rc
  fi
  if [[ -z "$(extract_response_text "$raw")" ]]; then
    echo "Unable to extract the response text from azd payload invoke output (conversation_id=${conversation_id:-<new>}):" >&2
    echo "$raw" >&2
    exit 1
  fi
  rm -f "$PAYLOAD_FILE"
  printf '%s\n' "$raw"
}

invoke_structured_decision() {
  local conversation_id="$1"
  local checkpoint_id="$2"
  local decision="$3"
  local endpoint
  local token
  local status
  local response_text

  endpoint="$(azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_RESPONSES_ENDPOINT)"
  token="$(az account get-access-token --scope https://ai.azure.com/.default --query accessToken -o tsv)"
  [[ -n "$endpoint" && -n "$token" ]] || {
    echo "Unable to resolve the hosted Responses endpoint or access token." >&2
    exit 1
  }

  jq -cn \
    --arg conversation "$conversation_id" \
    --arg checkpoint "$checkpoint_id" \
    --arg decision "$decision" \
    '{
      conversation: {id: $conversation},
      input: [{
        type: "function_call_output",
        call_id: $checkpoint,
        output: $decision
      }],
      stream: false,
      structured_inputs: {trace_evaluation_record_content: true}
    }' >"$PAYLOAD_FILE"

  for attempt in $(seq 1 20); do
    status="$(
      curl -sS \
        --max-time 180 \
        --output "$RESPONSE_FILE" \
        --write-out '%{http_code}' \
        --header "Authorization: Bearer $token" \
        --header "Content-Type: application/json" \
        --header "$TRACE_EVALUATION_HEADER" \
        --data-binary "@$PAYLOAD_FILE" \
        "$endpoint"
    )"
    if [[ "$status" =~ ^2[0-9][0-9]$ ]]; then
      break
    fi
    if [[ "$status" =~ ^(404|409|429|5[0-9][0-9])$ ]]; then
      echo "Transient structured Responses failure (attempt $attempt/20, HTTP $status)." >&2
      sleep 15
      continue
    fi
    break
  done
  if [[ ! "$status" =~ ^2[0-9][0-9]$ ]]; then
    echo "Structured Responses invocation failed with HTTP $status." >&2
    jq -c '{error: .error, status: .status, incomplete_details: .incomplete_details}' \
      "$RESPONSE_FILE" >&2 2>/dev/null || true
    exit 1
  fi

  response_text="$(
    jq -r '
      [
        .output[]?.content[]?
        | select(.type == "output_text")
        | .text
      ]
      | last // empty
    ' "$RESPONSE_FILE"
  )"
  [[ -n "$response_text" ]] || {
    echo "Structured Responses invocation returned no output text." >&2
    exit 1
  }
  printf 'Conversation: %s\n' "$conversation_id"
  printf '[order-resolution-hosted] %s\n' "$response_text"
}

database_url="$(azd env get-value RUNTIME_DATABASE_URL)"
database_url="${database_url/postgresql+psycopg:/postgresql:}"
[[ -n "$database_url" ]] || {
  echo "RUNTIME_DATABASE_URL is required for hosted E2E state verification."
  exit 1
}

db_query() {
  local thread_id="$1"
  local sql="$2"
  printf '%s\n' "$sql" |
    psql "$database_url" \
      --no-psqlrc \
      --set=ON_ERROR_STOP=1 \
      --set=thread_id="$thread_id" \
      --tuples-only \
      --no-align \
      --quiet
}

workflow_status() {
  db_query "$1" "SELECT status FROM workflow_runs WHERE thread_id = :'thread_id';"
}

pending_checkpoint() {
  db_query "$1" \
    "SELECT checkpoint_id::text FROM approvals WHERE thread_id = :'thread_id' AND status = 'pending' ORDER BY requested_at DESC LIMIT 1;"
}

approval_status() {
  db_query "$1" \
    "SELECT status FROM approvals WHERE thread_id = :'thread_id' ORDER BY requested_at DESC LIMIT 1;"
}

assert_event() {
  local thread_id="$1"
  local event_type="$2"
  local count
  count="$(
    db_query "$thread_id" \
      "SELECT COUNT(*) FROM workflow_events WHERE thread_id = :'thread_id' AND type = '${event_type}';"
  )"
  [[ "$count" -gt 0 ]] || {
    echo "Expected event ${event_type} for conversation ${thread_id}."
    exit 1
  }
}

first_payload="$(jq -cn --arg input "Resolve delayed order ORD-1001" '{input: $input, structured_inputs: {trace_evaluation_record_content: true}}')"
first_turn="$(invoke_responses_payload "" "$first_payload" "new")"
C1="$(extract_conversation_id "$first_turn")"
if [[ -z "$C1" || "$C1" == "null" ]]; then
  echo "Missing thread_id in first responses turn"
  echo "$first_turn"
  exit 1
fi
[[ "$(extract_response_text "$first_turn")" == Resolution\ complete.* ]] || {
  echo "Low-risk response did not complete successfully."
  echo "$first_turn"
  exit 1
}
[[ "$(workflow_status "$C1")" == "completed" ]] || {
  echo "Low-risk workflow did not persist as completed."
  exit 1
}
assert_event "$C1" "tool.call"
assert_event "$C1" "workflow.output"

second_payload="$(jq -cn --arg input "Why was that resolution selected?" '{input: $input, structured_inputs: {trace_evaluation_record_content: true}}')"
second_turn="$(invoke_responses_payload "$C1" "$second_payload")"
if [[ "$(extract_conversation_id "$second_turn")" != "$C1" ]]; then
  echo "Second turn did not preserve thread_id."
  echo "$second_turn"
  exit 1
fi
extract_response_text "$second_turn" |
  grep -Eqi 'resolution was selected|resolution complete' || {
    echo "Second turn did not explain the selected resolution."
    echo "$second_turn"
    exit 1
  }

high_risk_payload="$(jq -cn --arg input "Resolve delayed order ORD-1009" '{input: $input, structured_inputs: {trace_evaluation_record_content: true}}')"
high_risk_start="$(invoke_responses_payload "" "$high_risk_payload" "new")"
HIGH_RISK="$(extract_conversation_id "$high_risk_start")"
if [[ -z "$HIGH_RISK" || "$HIGH_RISK" == "null" ]]; then
  echo "Missing thread_id in high-risk responses turn"
  echo "$high_risk_start"
  exit 1
fi
[[ "$(workflow_status "$HIGH_RISK")" == "waiting_approval" ]] || {
  echo "High-risk workflow did not enter waiting_approval."
  exit 1
}
assert_event "$HIGH_RISK" "hitl.request"
HIGH_RISK_CHECKPOINT="$(pending_checkpoint "$HIGH_RISK")"
if [[ -z "$HIGH_RISK_CHECKPOINT" ]]; then
  echo "Missing checkpoint_id in high-risk responses turn"
  exit 1
fi
high_risk_resume="$(invoke_structured_decision "$HIGH_RISK" "$HIGH_RISK_CHECKPOINT" "approve")"
[[ "$(workflow_status "$HIGH_RISK")" == "completed" &&
  "$(approval_status "$HIGH_RISK")" == "approved" ]] || {
  echo "High-risk approval did not complete the workflow."
  echo "workflow_status=$(workflow_status "$HIGH_RISK") approval_status=$(approval_status "$HIGH_RISK")"
  echo "$high_risk_resume"
  exit 1
}
assert_event "$HIGH_RISK" "hitl.response"
assert_event "$HIGH_RISK" "workflow.output"

damaged_payload="$(jq -cn --arg input "Customer reports a damaged item for order ORD-1001 and requests a replacement" '{input: $input, structured_inputs: {trace_evaluation_record_content: true}}')"
damaged_start="$(invoke_responses_payload "" "$damaged_payload" "new")"
DAMAGED_THREAD="$(extract_conversation_id "$damaged_start")"
if [[ -z "$DAMAGED_THREAD" || "$DAMAGED_THREAD" == "null" ]]; then
  echo "Missing thread_id in damaged-item responses turn"
  echo "$damaged_start"
  exit 1
fi
[[ "$(workflow_status "$DAMAGED_THREAD")" == "waiting_approval" ]] || {
  echo "Damaged-item workflow did not enter waiting_approval."
  exit 1
}
assert_event "$DAMAGED_THREAD" "checkpoint.created"
assert_event "$DAMAGED_THREAD" "hitl.request"
DAMAGED_CHECKPOINT="$(pending_checkpoint "$DAMAGED_THREAD")"
if [[ -z "$DAMAGED_CHECKPOINT" ]]; then
  echo "Missing checkpoint_id in damaged-item responses turn"
  exit 1
fi
damaged_resume="$(invoke_structured_decision "$DAMAGED_THREAD" "$DAMAGED_CHECKPOINT" "approve")"
[[ "$(workflow_status "$DAMAGED_THREAD")" == "completed" &&
  "$(approval_status "$DAMAGED_THREAD")" == "approved" ]] || {
  echo "Damaged-item approval did not complete the workflow."
  echo "workflow_status=$(workflow_status "$DAMAGED_THREAD") approval_status=$(approval_status "$DAMAGED_THREAD")"
  echo "$damaged_resume"
  exit 1
}
assert_event "$DAMAGED_THREAD" "hitl.response"
assert_event "$DAMAGED_THREAD" "workflow.output"

evidence_file="${FOUNDRY_E2E_EVIDENCE_FILE:-$RESULTS_DIR/hosted-e2e-evidence.json}"
mkdir -p "$(dirname "$evidence_file")"
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg started_at "$STARTED_AT" \
  --arg base_id "$BASE_ID" \
  --arg low_risk_thread_id "$C1" \
  --arg high_risk_thread_id "$HIGH_RISK" \
  --arg damaged_item_thread_id "$DAMAGED_THREAD" \
  '{
    generated_at: $generated_at,
    started_at: $started_at,
    base_id: $base_id,
    low_risk_thread_id: $low_risk_thread_id,
    high_risk_thread_id: $high_risk_thread_id,
    damaged_item_thread_id: $damaged_item_thread_id
  }' \
  >"$evidence_file"

echo "Foundry Responses hosted E2E passed for conversations: ${C1}, ${HIGH_RISK}, ${DAMAGED_THREAD} (base=${BASE_ID})"
