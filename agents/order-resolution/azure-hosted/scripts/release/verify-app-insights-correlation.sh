#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"
attempts="${TELEMETRY_MAX_ATTEMPTS:-8}"
wait_seconds="${TELEMETRY_WAIT_SECONDS:-15}"
readonly REQUIRED_DOMAIN_SCENARIOS_JSON='["low-risk-no-hitl","high-risk-approval-resume","damaged-item-approval-resume"]'

[[ "$attempts" =~ ^[1-9][0-9]*$ && "$wait_seconds" =~ ^[0-9]+$ ]] || {
  echo "TELEMETRY_MAX_ATTEMPTS must be positive and TELEMETRY_WAIT_SECONDS must be non-negative integers." >&2
  exit 1
}

get_azd_output() {
  local name="$1"
  azd env get-value "$name" --environment "$environment" 2>/dev/null
}

write_release_context \
  "$environment" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"

domain_e2e_file="$(release_artifact_path domain-e2e.json)"
telemetry_file="$(release_artifact_path telemetry.json)"
pairs_file="$RELEASE_LOGS_DIR/app-insights-$RELEASE_ID-pairs.json"

[[ -f "$domain_e2e_file" ]] || {
  echo "Domain E2E evidence file is missing: $domain_e2e_file" >&2
  exit 1
}

azd_subscription_id="$(get_azd_output AZURE_SUBSCRIPTION_ID)"
resource_group="$(get_azd_output AZURE_RESOURCE_GROUP)"
location="$(get_azd_output AZURE_LOCATION)"
workspace_resource_id="$(get_azd_output AZURE_LOG_ANALYTICS_WORKSPACE_ID)"
[[ -n "$azd_subscription_id" && -n "$resource_group" && -n "$location" && -n "$workspace_resource_id" ]] || {
  echo "Selected AZD environment is missing required monitoring outputs." >&2
  exit 1
}

require_selected_target "$environment" "$azd_subscription_id" "$resource_group" "$location"
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" && "$AZURE_SUBSCRIPTION_ID" != "$azd_subscription_id" ]]; then
  echo "AZURE_SUBSCRIPTION_ID does not match the selected AZD environment." >&2
  exit 1
fi
export AZURE_SUBSCRIPTION_ID="$azd_subscription_id"
require_azure_cli_target "$AZURE_SUBSCRIPTION_ID"

expected_workspace_prefix="/subscriptions/${AZURE_SUBSCRIPTION_ID,,}/resourcegroups/${resource_group,,}/providers/microsoft.operationalinsights/workspaces/"
if [[ "${workspace_resource_id,,}" != "$expected_workspace_prefix"* ]]; then
  echo "Selected AZD Log Analytics workspace output does not belong to the selected subscription and resource group." >&2
  exit 1
fi

workspace_id="$(az monitor log-analytics workspace show \
  --ids "$workspace_resource_id" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query customerId \
  --output tsv)"
if [[ -z "$workspace_id" ]]; then
  echo "Unable to resolve the Log Analytics workspace for fresh telemetry validation." >&2
  exit 1
fi

python3 - "$domain_e2e_file" "$pairs_file" "$RELEASE_ID" "$RELEASE_STARTED_AT" "$REQUIRED_DOMAIN_SCENARIOS_JSON" <<'PY'
import json
import re
import sys
from pathlib import Path

domain_path, pairs_path, release_id, release_started_at, required_scenarios_json = sys.argv[1:]
identifier = re.compile(r"^[A-Za-z0-9._:-]+$")
required_scenarios = set(json.loads(required_scenarios_json))

def load(path: str, artifact_type: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("artifact_type") != artifact_type:
        raise SystemExit(f"{Path(path).name} has unexpected artifact_type.")
    if payload.get("release_id") != release_id:
        raise SystemExit(f"{Path(path).name} belongs to a different release.")
    if payload.get("release_started_at") != release_started_at:
        raise SystemExit(f"{Path(path).name} belongs to a different release window.")
    if payload.get("status") != "passed":
        raise SystemExit(f"{Path(path).name} did not pass.")
    return payload

evidence = load(domain_path, "domain_e2e")
scenarios = evidence.get("scenarios")
if not isinstance(scenarios, list):
    raise SystemExit("domain-e2e.json must include scenarios.")

validated_pairs: list[dict[str, str]] = []
seen_pairs: set[tuple[str, str]] = set()
seen_scenarios: set[str] = set()
for scenario in scenarios:
    if not isinstance(scenario, dict):
        raise SystemExit("Scenario entry must be an object.")
    scenario_id = scenario.get("scenario_id")
    if not isinstance(scenario_id, str):
        raise SystemExit("Scenario entry is missing scenario_id.")
    if scenario_id in seen_scenarios:
        raise SystemExit(f"domain-e2e.json contains a duplicate scenario_id: {scenario_id}")
    seen_scenarios.add(scenario_id)
    if scenario_id not in required_scenarios:
        continue
    if scenario.get("status") != "passed":
        raise SystemExit(f"domain-e2e.json scenario {scenario_id} did not pass.")
    if scenario.get("transport") != "http":
        raise SystemExit(f"domain-e2e.json scenario {scenario_id} must remain HTTP-only.")
    terminal_status = scenario.get("terminal_status")
    if terminal_status != "completed":
        raise SystemExit(
            f"domain-e2e.json scenario {scenario_id} must end in completed status."
        )
    thread_id = scenario.get("thread_id")
    workflow_run_id = scenario.get("workflow_run_id")
    if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
        raise SystemExit("Scenario entry requires string thread_id and workflow_run_id.")
    if not identifier.fullmatch(thread_id) or not identifier.fullmatch(workflow_run_id):
        raise SystemExit("Correlation identifiers contain unsupported characters.")
    if not thread_id.startswith(f"domain-e2e-{release_id}-"):
        raise SystemExit("Correlation evidence includes a thread outside this release run.")
    pair_key = (thread_id, workflow_run_id)
    if pair_key in seen_pairs:
        raise SystemExit("domain-e2e.json contains a duplicate correlation pair.")
    seen_pairs.add(pair_key)
    validated_pairs.append(
        {
            "scenario_id": scenario_id,
            "thread_id": thread_id,
            "workflow_run_id": workflow_run_id,
        }
    )

missing_scenarios = required_scenarios - seen_scenarios
if missing_scenarios:
    raise SystemExit(
        f"domain-e2e.json is missing required telemetry scenarios: {sorted(missing_scenarios)}"
    )
unexpected_scenarios = seen_scenarios - required_scenarios
if unexpected_scenarios:
    raise SystemExit(
        f"domain-e2e.json contains unexpected telemetry scenarios: {sorted(unexpected_scenarios)}"
    )

correlations = evidence.get("correlations")
if not isinstance(correlations, list) or len(correlations) != len(required_scenarios):
    raise SystemExit("domain-e2e.json must expose exactly three HTTP correlation pairs.")

correlation_pairs = {
    (pair.get("thread_id"), pair.get("workflow_run_id"))
    for pair in correlations
    if isinstance(pair, dict)
}
if correlation_pairs != seen_pairs:
    raise SystemExit("domain-e2e.json correlations do not match the scenario evidence exactly.")

Path(pairs_path).write_text(
    json.dumps(validated_pairs, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

pair_count="$(python3 - "$pairs_file" <<'PY'
import json
import sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))))
PY
)"

validated_pairs_json="[]"
for (( pair_index = 0; pair_index < pair_count; pair_index++ )); do
  readarray -t pair_values < <(python3 - "$pairs_file" "$pair_index" <<'PY'
import json
import sys

pairs = json.load(open(sys.argv[1], encoding="utf-8"))
pair = pairs[int(sys.argv[2])]
print(pair["scenario_id"])
print(pair["thread_id"])
print(pair["workflow_run_id"])
PY
)
  scenario_id="${pair_values[0]}"
  thread_id="${pair_values[1]}"
  workflow_run_id="${pair_values[2]}"
  query="$(python3 - "$RELEASE_STARTED_AT" "$thread_id" "$workflow_run_id" <<'PY'
import json
import sys

not_before, thread_id, workflow_run_id = sys.argv[1:]
print(f"""union isfuzzy=true
    (AppRequests | extend telemetryTable = 'AppRequests'),
    (AppDependencies | extend telemetryTable = 'AppDependencies'),
    (AppTraces | extend telemetryTable = 'AppTraces'),
    (AppExceptions | extend telemetryTable = 'AppExceptions')
| where TimeGenerated between (datetime({not_before}) .. now())
| extend properties = column_ifexists('Properties', dynamic({{}}))
| extend threadId = tostring(properties['workflow.thread_id'])
| extend workflowRunId = tostring(properties['workflow.run_id'])
| where threadId == {json.dumps(thread_id)} and workflowRunId == {json.dumps(workflow_run_id)}
| summarize telemetryCount=count(), exceptionCount=countif(telemetryTable == 'AppExceptions'), operationIds=make_set(OperationId, 100)""")
PY
)"
  telemetry_capture_file="$RELEASE_LOGS_DIR/telemetry-$scenario_id.json"
  pair_validated=false
  for (( attempt = 1; attempt <= attempts; attempt++ )); do
    az monitor log-analytics query \
      --workspace "$workspace_id" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --analytics-query "$query" \
      --output json >"$telemetry_capture_file"

    if python3 - "$telemetry_capture_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if isinstance(payload, list):
    # Azure CLI flattens one KQL result row into a list of dictionaries.
    if len(payload) != 1 or not isinstance(payload[0], dict):
        raise SystemExit(1)
    result = payload[0]
    telemetry_count = int(result["telemetryCount"])
    exception_count = int(result["exceptionCount"])
elif isinstance(payload, dict):
    tables = payload.get("tables")
    if not isinstance(tables, list) or len(tables) != 1:
        raise SystemExit(1)
    columns = tables[0].get("columns")
    rows = tables[0].get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list) or len(rows) != 1:
        raise SystemExit(1)
    column_indexes = {
        column.get("name"): index
        for index, column in enumerate(columns)
        if isinstance(column, dict) and isinstance(column.get("name"), str)
    }
    row = rows[0]
    telemetry_count = int(row[column_indexes["telemetryCount"]])
    exception_count = int(row[column_indexes["exceptionCount"]])
else:
    raise SystemExit(1)
if telemetry_count <= 0 or exception_count != 0:
    raise SystemExit(1)
PY
    then
      pair_validated=true
      break
    fi
    if (( attempt < attempts )); then
      sleep "$wait_seconds"
    fi
  done

  if [[ "$pair_validated" != "true" ]]; then
    echo "No fresh non-exception App Insights telemetry was found for scenario $scenario_id." >&2
    exit 1
  fi

  validated_pairs_json="$(python3 - \
    "$validated_pairs_json" \
    "$scenario_id" \
    "$thread_id" \
    "$workflow_run_id" \
    "$RELEASE_STARTED_AT" \
    "$telemetry_capture_file" \
    "logs/$(basename "$telemetry_capture_file")" <<'PY'
import json
import sys
from pathlib import Path

(
    current_json,
    scenario_id,
    thread_id,
    workflow_run_id,
    not_before,
    telemetry_capture_file,
    telemetry_file,
) = sys.argv[1:]
current = json.loads(current_json)
capture_payload = json.loads(Path(telemetry_capture_file).read_text(encoding="utf-8"))

if isinstance(capture_payload, list):
    # Azure CLI flattens one KQL result row into a list of dictionaries.
    result = capture_payload[0]
    telemetry_count = int(result["telemetryCount"])
    exception_count = int(result["exceptionCount"])
elif isinstance(capture_payload, dict):
    tables = capture_payload["tables"]
    columns = tables[0]["columns"]
    rows = tables[0]["rows"]
    column_indexes = {
        column["name"]: index
        for index, column in enumerate(columns)
        if isinstance(column, dict) and isinstance(column.get("name"), str)
    }
    row = rows[0]
    telemetry_count = int(row[column_indexes["telemetryCount"]])
    exception_count = int(row[column_indexes["exceptionCount"]])
else:
    raise SystemExit("Unsupported telemetry query payload.")

current.append(
    {
        "scenario_id": scenario_id,
        "thread_id": thread_id,
        "workflow_run_id": workflow_run_id,
        "not_before": not_before,
        "telemetry_file": telemetry_file,
        "telemetry_count": telemetry_count,
        "exception_count": exception_count,
    }
)
print(json.dumps(current))
PY
)"
done

python3 - "$telemetry_file" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "$environment" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$resource_group" \
  "$location" \
  "$workspace_id" \
  "$validated_pairs_json" \
  "$REQUIRED_DOMAIN_SCENARIOS_JSON" \
  "$attempts" \
  "$wait_seconds" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    output_path,
    release_id,
    release_started_at,
    environment,
    subscription_id,
    resource_group,
    location,
    workspace_id,
    validated_pairs_json,
    required_scenarios_json,
    attempts,
    wait_seconds,
) = sys.argv[1:]
validated_pairs = json.loads(validated_pairs_json)
required_scenarios = json.loads(required_scenarios_json)
payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "artifact_type": "telemetry",
    "status": "passed",
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    "target": {
        "azd_env_name": environment,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
        "workspace_id": workspace_id,
    },
    "attempts": int(attempts),
    "wait_seconds": int(wait_seconds),
    "required_scenarios": required_scenarios,
    "validated_pairs": validated_pairs,
}
Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "Fresh App Insights correlation evidence was captured for all $pair_count domain scenarios."
