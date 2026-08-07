#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

environment="${AZURE_ENV_NAME:-maf-ora-azure}"
evidence_file="${E2E_EVIDENCE_FILE:?E2E_EVIDENCE_FILE is required}"
release_started_at="${RELEASE_E2E_STARTED_AT:?RELEASE_E2E_STARTED_AT is required}"
release_run_id="${RELEASE_RUN_ID:?RELEASE_RUN_ID is required}"
attempts="${TELEMETRY_MAX_ATTEMPTS:-8}"
wait_seconds="${TELEMETRY_WAIT_SECONDS:-15}"

[[ -f "$evidence_file" ]] || {
  echo "Hosted E2E evidence file is missing: $evidence_file" >&2
  exit 1
}
[[ "$attempts" =~ ^[1-9][0-9]*$ && "$wait_seconds" =~ ^[0-9]+$ ]] || {
  echo "TELEMETRY_MAX_ATTEMPTS must be positive and TELEMETRY_WAIT_SECONDS must be non-negative integers." >&2
  exit 1
}

get_azd_output() {
  local name="$1"
  azd env get-value "$name" --environment "$environment" 2>/dev/null
}

azd_subscription_id="$(get_azd_output AZURE_SUBSCRIPTION_ID)"
if [[ ! "$azd_subscription_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
  echo "The selected AZD environment must define AZURE_SUBSCRIPTION_ID as a subscription ID." >&2
  exit 1
fi
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" && "$AZURE_SUBSCRIPTION_ID" != "$azd_subscription_id" ]]; then
  echo "AZURE_SUBSCRIPTION_ID does not match the selected AZD environment." >&2
  exit 1
fi
export AZURE_SUBSCRIPTION_ID="$azd_subscription_id"

resolved_subscription_id="$(az account show \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query id \
  --output tsv)"
if [[ "$resolved_subscription_id" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI could not resolve the selected AZD environment subscription ID." >&2
  exit 1
fi

resource_group="$(get_azd_output AZURE_RESOURCE_GROUP)"
workspace_resource_id="$(get_azd_output AZURE_LOG_ANALYTICS_WORKSPACE_ID)"
if [[ -z "$resource_group" || -z "$workspace_resource_id" ]]; then
  echo "Selected AZD environment is missing monitoring output references." >&2
  exit 1
fi
if [[ "$resource_group" != "rg-$environment" ]]; then
  echo "Selected AZD resource group does not match the deterministic Bicep resource group for this environment." >&2
  exit 1
fi
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

pairs_file="$(dirname "$evidence_file")/app-insights-$release_run_id-pairs.json"
python3 - "$evidence_file" "$pairs_file" "$release_run_id" "$release_started_at" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

evidence_path, pairs_path, release_run_id, release_started_at = sys.argv[1:]
try:
    not_before = datetime.fromisoformat(release_started_at.replace("Z", "+00:00"))
except ValueError as error:
    raise SystemExit(f"RELEASE_E2E_STARTED_AT must be an ISO-8601 timestamp: {error}")
if not_before.tzinfo is None:
    raise SystemExit("RELEASE_E2E_STARTED_AT must include a timezone.")

evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
if evidence.get("release_run_id") != release_run_id:
    raise SystemExit("Evidence release_run_id does not match RELEASE_RUN_ID.")
if evidence.get("release_started_at") != release_started_at:
    raise SystemExit("Evidence release_started_at does not match the fresh release timestamp.")

pairs = evidence.get("correlations")
if not isinstance(pairs, list) or not pairs:
    raise SystemExit(
        "Hosted E2E evidence must contain a non-empty correlations list of exact "
        "thread_id/workflow_run_id pairs."
    )

identifier = re.compile(r"^[A-Za-z0-9._:-]+$")
seen_threads: set[str] = set()
seen_pairs: set[tuple[str, str]] = set()
validated_pairs: list[dict[str, str]] = []
for pair in pairs:
    if not isinstance(pair, dict):
        raise SystemExit("Each correlation evidence entry must be an object.")
    thread_id = pair.get("thread_id")
    workflow_run_id = pair.get("workflow_run_id")
    if not isinstance(thread_id, str) or not isinstance(workflow_run_id, str):
        raise SystemExit("Each correlation evidence entry requires string thread_id and workflow_run_id.")
    if not identifier.fullmatch(thread_id) or not identifier.fullmatch(workflow_run_id):
        raise SystemExit("Correlation identifiers contain unsupported characters.")
    if not thread_id.startswith(f"smoke-apphosted-{release_run_id}-"):
        raise SystemExit("Correlation evidence includes a thread outside this release run.")
    if thread_id in seen_threads or (thread_id, workflow_run_id) in seen_pairs:
        raise SystemExit("Correlation evidence must contain exactly one workflow run for each fresh thread.")
    seen_threads.add(thread_id)
    seen_pairs.add((thread_id, workflow_run_id))
    validated_pairs.append({"thread_id": thread_id, "workflow_run_id": workflow_run_id})

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

for (( pair_index = 0; pair_index < pair_count; pair_index++ )); do
  readarray -t pair_values < <(python3 - "$pairs_file" "$pair_index" <<'PY'
import json
import sys

pairs = json.load(open(sys.argv[1], encoding="utf-8"))
pair = pairs[int(sys.argv[2])]
print(pair["thread_id"])
print(pair["workflow_run_id"])
PY
)
  thread_id="${pair_values[0]}"
  workflow_run_id="${pair_values[1]}"
  query="$(python3 - "$release_started_at" "$thread_id" "$workflow_run_id" <<'PY'
import json
import sys

not_before, thread_id, workflow_run_id = sys.argv[1:]
print(f"""union isfuzzy=true
    (AppRequests | extend telemetryTable = 'AppRequests'),
    (AppDependencies | extend telemetryTable = 'AppDependencies'),
    (AppTraces | extend telemetryTable = 'AppTraces'),
    (AppExceptions | extend telemetryTable = 'AppExceptions')
| where TimeGenerated >= datetime({not_before})
| extend properties = column_ifexists('Properties', dynamic({{}}))
| extend threadId = tostring(properties['workflow.thread_id'])
| extend workflowRunId = tostring(properties['workflow.run_id'])
| where threadId == {json.dumps(thread_id)} and workflowRunId == {json.dumps(workflow_run_id)}
| summarize telemetryCount=count(), exceptionCount=countif(telemetryTable == 'AppExceptions'), operationIds=make_set(OperationId, 100)""")
PY
)"
  telemetry_file="$(dirname "$evidence_file")/app-insights-$release_run_id-pair-$pair_index.json"

  pair_validated=false
  for (( attempt = 1; attempt <= attempts; attempt++ )); do
    az monitor log-analytics query \
      --workspace "$workspace_id" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --analytics-query "$query" \
      --output json >"$telemetry_file"

    if python3 - "$telemetry_file" "$evidence_file" "$pair_index" "$thread_id" "$workflow_run_id" "$release_started_at" <<'PY'
import json
import sys
from pathlib import Path

(
    telemetry_path,
    evidence_path,
    pair_index,
    expected_thread_id,
    expected_workflow_run_id,
    not_before,
) = sys.argv[1:]
payload = json.loads(Path(telemetry_path).read_text(encoding="utf-8"))
if isinstance(payload, list):
    # Azure CLI flattens one KQL result row into a list of dictionaries.
    if len(payload) != 1 or not isinstance(payload[0], dict):
        raise SystemExit(1)
    result = payload[0]
    try:
        telemetry_count = int(result["telemetryCount"])
        exception_count = int(result["exceptionCount"])
    except (KeyError, TypeError, ValueError):
        raise SystemExit(1)
elif isinstance(payload, dict):
    # Keep accepting the Log Analytics REST API table-and-row response shape.
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
    if not {"telemetryCount", "exceptionCount", "operationIds"} <= column_indexes.keys():
        raise SystemExit(1)
    row = rows[0]
    if not isinstance(row, list):
        raise SystemExit(1)
    try:
        telemetry_count = int(row[column_indexes["telemetryCount"]])
        exception_count = int(row[column_indexes["exceptionCount"]])
    except (TypeError, ValueError, IndexError):
        raise SystemExit(1)
else:
    raise SystemExit(1)
if telemetry_count <= 0 or exception_count != 0:
    raise SystemExit(1)

evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
app_insights = evidence.setdefault("app_insights", {})
if not isinstance(app_insights, dict):
    raise SystemExit("Evidence app_insights entry is malformed.")
correlations = app_insights.setdefault("correlations", [])
if not isinstance(correlations, list):
    raise SystemExit("Evidence app_insights correlations entry is malformed.")
entry = {
    "thread_id": expected_thread_id,
    "workflow_run_id": expected_workflow_run_id,
    "not_before": not_before,
    "telemetry_file": telemetry_path,
    "telemetry_count": telemetry_count,
    "exception_count": exception_count,
}
if len(correlations) == int(pair_index):
    correlations.append(entry)
elif len(correlations) > int(pair_index):
    correlations[int(pair_index)] = entry
else:
    raise SystemExit("Telemetry correlation evidence is out of order.")
app_insights["validated"] = False
Path(evidence_path).write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
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
    echo "No fresh non-exception App Insights telemetry was found for exact pair $((pair_index + 1))/$pair_count." >&2
    exit 1
  fi
done

python3 - "$evidence_file" "$pair_count" "$release_started_at" <<'PY'
import json
import sys
from pathlib import Path

evidence_path, expected_count, not_before = sys.argv[1:]
evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
app_insights = evidence.get("app_insights")
if not isinstance(app_insights, dict):
    raise SystemExit("App Insights evidence is missing.")
correlations = app_insights.get("correlations")
if not isinstance(correlations, list) or len(correlations) != int(expected_count):
    raise SystemExit("App Insights evidence does not cover every exact correlation pair.")
if any(item.get("not_before") != not_before for item in correlations if isinstance(item, dict)):
    raise SystemExit("App Insights evidence did not retain the release not-before timestamp.")
app_insights["validated"] = True
Path(evidence_path).write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

echo "Fresh App Insights correlation evidence was captured for all $pair_count exact release pairs."
