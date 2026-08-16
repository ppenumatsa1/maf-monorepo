#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-}"
RELEASE_ID="${RELEASE_ID:-${RELEASE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}}"
SMOKE_ATTEMPT_ID="${SMOKE_ATTEMPT_ID:-$(date -u +%s%N)-$$}"
RELEASE_STARTED_AT="${RELEASE_STARTED_AT:-${RELEASE_E2E_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}}"
LOW_RISK_THREAD_ID="smoke-apphosted-${RELEASE_ID}-ord1001-${SMOKE_ATTEMPT_ID}"
HIGH_RISK_THREAD_ID="smoke-apphosted-${RELEASE_ID}-ord1009-${SMOKE_ATTEMPT_ID}"

curl --fail --silent "$BASE_URL/api/health" >/dev/null
if [[ -n "$FRONTEND_URL" ]]; then
  curl --fail --silent "$FRONTEND_URL/health" >/dev/null
  curl --fail --silent "$FRONTEND_URL/api/health" >/dev/null
fi

run_chat() {
  local thread_id="$1"
  local message="$2"
  local response=""
  local attempt

  for attempt in {1..10}; do
    if response="$(curl --fail --silent --show-error -X POST "$BASE_URL/api/chat/run" \
      -H 'Content-Type: application/json' \
      -d "{\"thread_id\":\"${thread_id}\",\"message\":\"${message}\"}")" &&
      [[ -n "$response" ]]; then
      printf '%s' "$response"
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for a non-empty /api/chat/run response for ${thread_id}." >&2
  return 1
}

RUN_RESPONSE="$(run_chat "$LOW_RISK_THREAD_ID" "ORD-1001 late delivery")"
HITL_RESPONSE="$(run_chat "$HIGH_RISK_THREAD_ID" "ORD-1009 is delayed by 5 days. I need compensation.")"

python3 - <<'PY' \
  "$RUN_RESPONSE" \
  "$HITL_RESPONSE" \
  "$BASE_URL" \
  "$FRONTEND_URL" \
  "$LOW_RISK_THREAD_ID" \
  "$HIGH_RISK_THREAD_ID" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "${SMOKE_EVIDENCE_FILE:-}"
import json
import os
import sys
import time
from datetime import UTC, datetime
import urllib.request
from pathlib import Path

payload = json.loads(sys.argv[1])
hitl_payload = json.loads(sys.argv[2])
base_url = sys.argv[3]
frontend_url = sys.argv[4]
low_risk_thread_id = sys.argv[5]
high_risk_thread_id = sys.argv[6]
release_id = sys.argv[7]
release_started_at = sys.argv[8]
evidence_file = sys.argv[9]
thread_id = payload.get("thread_id")
if not thread_id:
    raise SystemExit("thread_id missing in /api/chat/run response")
hitl_thread_id = hitl_payload.get("thread_id")
if not hitl_thread_id:
    raise SystemExit("thread_id missing in high-risk /api/chat/run response")

def events_for(run_thread_id: str) -> list[dict[str, object]]:
    with urllib.request.urlopen(f"{base_url}/api/workflows/{run_thread_id}/events?limit=100") as response:
        events_payload = json.loads(response.read().decode("utf-8"))
    return events_payload.get("items", [])

def details_for(run_thread_id: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{base_url}/api/workflows/{run_thread_id}") as response:
        return json.loads(response.read().decode("utf-8"))

events = []
hitl_events = []
details = {}
hitl_details = {}
for _ in range(20):
    events = events_for(thread_id)
    hitl_events = events_for(hitl_thread_id)
    details = details_for(thread_id)
    hitl_details = details_for(hitl_thread_id)
    types = [item.get("type") for item in events]
    hitl_types = [item.get("type") for item in hitl_events]
    approvals = hitl_details.get("pending_approvals") or []
    if "workflow.output" in types and "hitl.request" in hitl_types and approvals:
        break
    time.sleep(1)

if "workflow.output" not in types:
    raise SystemExit("workflow.output not emitted for ORD-1001")
if "hitl.request" in types:
    raise SystemExit("unexpected hitl.request for low-risk ORD-1001 flow")
if "hitl.request" not in hitl_types:
    raise SystemExit("hitl.request not emitted for high-risk ORD-1009 flow")

expected_triage_mode = os.getenv("EXPECT_TRIAGE_MODE")
if expected_triage_mode:
    triage_modes = [
        item.get("payload", {}).get("triage_mode", {}).get("mode")
        for item in events + hitl_events
        if item.get("type") == "workflow.stage"
        and item.get("payload", {}).get("agent") == "triage"
    ]
    if expected_triage_mode not in triage_modes:
        raise SystemExit(
            f"expected triage mode {expected_triage_mode!r}, observed {triage_modes!r}"
        )

def workflow_run_id(history: list[dict[str, object]]) -> str:
    workflow_run_ids = sorted(
        {
            str(event.get("payload", {}).get("workflow_run_id"))
            for event in history
            if event.get("payload", {}).get("workflow_run_id")
        }
    )
    if len(workflow_run_ids) != 1:
        raise SystemExit(
            f"Smoke evidence requires exactly one workflow_run_id; found {workflow_run_ids!r}."
        )
    return workflow_run_ids[0]

if evidence_file:
    low_risk_workflow_run_id = workflow_run_id(events)
    high_risk_workflow_run_id = workflow_run_id(hitl_events)
    evidence = {
        "schema_version": 1,
        "contract": "azure-hosted-release/v1",
        "lane": "azure-hosted",
        "artifact_type": "smoke",
        "status": "passed",
        "release_id": release_id,
        "release_started_at": release_started_at,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "target": {
            "api_url": base_url,
            "web_url": frontend_url or None,
        },
        "scenarios": [
            {
                "scenario_id": "low-risk-no-hitl",
                "status": "passed",
                "thread_id": low_risk_thread_id,
                "workflow_run_id": low_risk_workflow_run_id,
                "expected_hitl": False,
                "observed_hitl": False,
                "terminal_status": (details.get("latest_output") or {}).get("status"),
            },
            {
                "scenario_id": "high-risk-hitl-request",
                "status": "passed",
                "thread_id": high_risk_thread_id,
                "workflow_run_id": high_risk_workflow_run_id,
                "expected_hitl": True,
                "observed_hitl": True,
                "terminal_status": hitl_details.get("status"),
                "checkpoint_id": ((hitl_details.get("pending_approvals") or [{}])[0]).get(
                    "checkpoint_id"
                ),
            },
        ],
        "correlations": [
            {"thread_id": low_risk_thread_id, "workflow_run_id": low_risk_workflow_run_id},
            {"thread_id": high_risk_thread_id, "workflow_run_id": high_risk_workflow_run_id},
        ],
    }
    path = Path(evidence_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("azure-apphosted smoke test passed")
PY
