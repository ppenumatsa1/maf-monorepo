#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin jq

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${APPLICATION_INSIGHTS_NAME:?APPLICATION_INSIGHTS_NAME is required}"
: "${FOUNDRY_EVALUATION_AGENT_ID:?FOUNDRY_EVALUATION_AGENT_ID is required}"

MAX_ATTEMPTS="${TELEMETRY_MAX_ATTEMPTS:-24}"
POLL_SECONDS="${TELEMETRY_POLL_SECONDS:-15}"
QUERY_MAX_ATTEMPTS="${APP_INSIGHTS_QUERY_MAX_ATTEMPTS:-3}"
QUERY_RETRY_SECONDS="${APP_INSIGHTS_QUERY_RETRY_SECONDS:-5}"
EVIDENCE_FILE="${HOSTED_E2E_EVIDENCE_FILE:-backend/.foundry/results/hosted-e2e-evidence.json}"
RESULT_FILE="${TELEMETRY_RESULT_FILE:-backend/.foundry/results/telemetry-verification.json}"

query_application_insights() {
  local analytics_query="$1"
  local attempt output

  for attempt in $(seq 1 "$QUERY_MAX_ATTEMPTS"); do
    if output="$(
      az monitor app-insights query \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --app "$APPLICATION_INSIGHTS_NAME" \
        --analytics-query "$analytics_query" \
        -o json 2>&1
    )"; then
      printf '%s' "$output"
      return 0
    fi

    echo "Application Insights query attempt ${attempt}/${QUERY_MAX_ATTEMPTS} failed: ${output}" >&2
    if [[ "$attempt" -lt "$QUERY_MAX_ATTEMPTS" ]]; then
      sleep "$QUERY_RETRY_SECONDS"
    fi
  done

  echo "Application Insights query did not succeed after ${QUERY_MAX_ATTEMPTS} attempts." >&2
  return 1
}

[[ -f "$EVIDENCE_FILE" ]] || {
  echo "Hosted E2E evidence is required: $EVIDENCE_FILE"
  exit 1
}

started_at="$(jq -r '.started_at // .generated_at // empty' "$EVIDENCE_FILE")"
mapfile -t conversation_ids < <(
  jq -r '
    (
      .conversation_ids
      // [
        .low_risk_thread_id,
        (.high_risk_thread_id // .approved_thread_id),
        (.damaged_item_thread_id // .damaged_thread_id)
      ]
    )
    | .[]
    | select(type == "string" and length > 0)
  ' "$EVIDENCE_FILE"
)

[[ -n "$started_at" && "${#conversation_ids[@]}" -ge 3 ]] || {
  echo "Hosted E2E evidence must contain a timestamp and all three scenario conversations."
  exit 1
}

mkdir -p "$(dirname "$RESULT_FILE")"
conversation_ids_json="$(printf '%s\n' "${conversation_ids[@]}" | jq -R . | jq -sc 'unique')"

query=$(cat <<EOF
let e2eStartedAt = todatetime('${started_at}');
let conversationIds = dynamic(${conversation_ids_json});
let expectedAgentId = '${FOUNDRY_EVALUATION_AGENT_ID}';
union isfuzzy=true traces, dependencies, requests, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| extend genAiConversationId = tostring(parse_json(dimensions)["gen_ai.conversation.id"])
| extend genAiAgentId = tostring(parse_json(dimensions)["gen_ai.agent.id"])
| mv-expand conversationId = conversationIds
| where dimensions has tostring(conversationId)
| summarize
    matched_count = dcount(tostring(conversationId)),
    telemetry_rows = count(),
    trace_rows = countif(itemType == "trace"),
    dependency_rows = countif(itemType == "dependency"),
    request_rows = countif(itemType == "request"),
    exception_rows = countif(itemType == "exception"),
    evaluation_trace_conversation_count = dcountif(
        tostring(conversationId),
        dimensions has '"gen_ai.operation.name":"invoke_agent"'
            and dimensions has 'gen_ai.input.messages'
            and dimensions has 'gen_ai.output.messages'
            and genAiConversationId == tostring(conversationId)
            and genAiAgentId == expectedAgentId
    ),
    evaluation_trace_rows = countif(
        dimensions has '"gen_ai.operation.name":"invoke_agent"'
            and dimensions has 'gen_ai.input.messages'
            and dimensions has 'gen_ai.output.messages'
            and genAiConversationId == tostring(conversationId)
            and genAiAgentId == expectedAgentId
    )
EOF
)

trace_ids_query=$(cat <<EOF
let e2eStartedAt = todatetime('${started_at}');
let conversationIds = dynamic(${conversation_ids_json});
let expectedAgentId = '${FOUNDRY_EVALUATION_AGENT_ID}';
union isfuzzy=true traces, dependencies, requests, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| extend genAiConversationId = tostring(parse_json(dimensions)["gen_ai.conversation.id"])
| extend genAiAgentId = tostring(parse_json(dimensions)["gen_ai.agent.id"])
| mv-expand conversationId = conversationIds
| where dimensions has tostring(conversationId)
| where dimensions has '"gen_ai.operation.name":"invoke_agent"'
    and dimensions has 'gen_ai.input.messages'
    and dimensions has 'gen_ai.output.messages'
    and genAiConversationId == tostring(conversationId)
    and genAiAgentId == expectedAgentId
| summarize operation_Id = arg_max(timestamp, operation_Id) by conversationId
| summarize evaluation_trace_ids = make_set(operation_Id)
EOF
)

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  result="$(query_application_insights "$query")"
  row="$(echo "$result" | jq -c '.tables[0].rows[0] // [0, 0, 0, 0, 0, 0, 0, 0]')"
  matched_count="$(echo "$row" | jq -r '.[0] // 0')"
  telemetry_rows="$(echo "$row" | jq -r '.[1] // 0')"
  trace_rows="$(echo "$row" | jq -r '.[2] // 0')"
  dependency_rows="$(echo "$row" | jq -r '.[3] // 0')"
  request_rows="$(echo "$row" | jq -r '.[4] // 0')"
  exception_rows="$(echo "$row" | jq -r '.[5] // 0')"
  evaluation_trace_conversation_count="$(echo "$row" | jq -r '.[6] // 0')"
  evaluation_trace_rows="$(echo "$row" | jq -r '.[7] // 0')"
  status="waiting"
  evaluation_trace_ids='[]'
  if [[ "$telemetry_rows" -gt 0 \
    && "$matched_count" -eq "${#conversation_ids[@]}" \
    && "$evaluation_trace_conversation_count" -eq "${#conversation_ids[@]}" \
    && "$evaluation_trace_rows" -gt 0 \
    && "$exception_rows" -eq 0 ]]; then
    trace_ids_result="$(query_application_insights "$trace_ids_query")"
    evaluation_trace_ids="$(echo "$trace_ids_result" | jq -c \
      '(.tables[0].rows[0][0] // []) | map(select(type == "string" and length > 0)) | unique')"
    if [[ "$(echo "$evaluation_trace_ids" | jq 'length')" -eq "${#conversation_ids[@]}" ]]; then
      status="passed"
    fi
  fi

  jq -n \
    --arg status "$status" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg started_at "$started_at" \
    --arg application_insights_name "$APPLICATION_INSIGHTS_NAME" \
    --arg evaluation_agent_id "$FOUNDRY_EVALUATION_AGENT_ID" \
    --argjson conversation_ids "$conversation_ids_json" \
    --argjson matched_count "$matched_count" \
    --argjson telemetry_rows "$telemetry_rows" \
    --argjson trace_rows "$trace_rows" \
    --argjson dependency_rows "$dependency_rows" \
    --argjson request_rows "$request_rows" \
    --argjson exception_rows "$exception_rows" \
    --argjson evaluation_trace_conversation_count "$evaluation_trace_conversation_count" \
    --argjson evaluation_trace_rows "$evaluation_trace_rows" \
    --argjson evaluation_trace_ids "$evaluation_trace_ids" \
    '{
      status: $status,
      generated_at: $generated_at,
      e2e_started_at: $started_at,
      application_insights_name: $application_insights_name,
      evaluation_agent_id: $evaluation_agent_id,
      conversation_ids: $conversation_ids,
      matched_conversation_count: $matched_count,
      telemetry_rows: $telemetry_rows,
      trace_rows: $trace_rows,
      dependency_rows: $dependency_rows,
      request_rows: $request_rows,
      exception_rows: $exception_rows,
      evaluation_trace_conversation_count: $evaluation_trace_conversation_count,
      evaluation_trace_rows: $evaluation_trace_rows,
      evaluation_trace_ids: $evaluation_trace_ids
    }' >"$RESULT_FILE"

  if [[ "$status" == "passed" ]]; then
    echo "Application Insights telemetry check passed: ${telemetry_rows} correlated rows and ${evaluation_trace_rows} eligible Foundry evaluation spans for ${matched_count} hosted E2E conversations."
    exit 0
  fi
  echo "Awaiting eligible evaluation telemetry (attempt ${attempt}/${MAX_ATTEMPTS}; rows=${telemetry_rows}, conversations=${matched_count}/${#conversation_ids[@]}, evaluation_conversations=${evaluation_trace_conversation_count}/${#conversation_ids[@]}, evaluation_rows=${evaluation_trace_rows}, exceptions=${exception_rows})."
  sleep "$POLL_SECONDS"
done

jq '.status = "failed"' "$RESULT_FILE" >"${RESULT_FILE}.tmp"
mv "${RESULT_FILE}.tmp" "$RESULT_FILE"
echo "Application Insights telemetry was not correlated to all current hosted E2E conversations within the bounded wait."
exit 1
