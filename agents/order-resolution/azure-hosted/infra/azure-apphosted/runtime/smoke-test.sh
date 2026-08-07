#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
FRONTEND_URL="${2:-}"
RELEASE_RUN_ID="${RELEASE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RELEASE_E2E_STARTED_AT="${RELEASE_E2E_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
LOW_RISK_THREAD_ID="smoke-apphosted-${RELEASE_RUN_ID}-ord1001"
HIGH_RISK_THREAD_ID="smoke-apphosted-${RELEASE_RUN_ID}-ord1009"

curl --fail --silent "$BASE_URL/api/health" >/dev/null
if [[ -n "$FRONTEND_URL" ]]; then
  curl --fail --silent "$FRONTEND_URL/health" >/dev/null
  curl --fail --silent "$FRONTEND_URL/api/health" >/dev/null
fi

RUN_RESPONSE="$(curl --silent --show-error -X POST "$BASE_URL/api/chat/run" \
  -H 'Content-Type: application/json' \
  -d "{\"thread_id\":\"${LOW_RISK_THREAD_ID}\",\"message\":\"ORD-1001 late delivery\"}")"

HITL_RESPONSE="$(curl --silent --show-error -X POST "$BASE_URL/api/chat/run" \
  -H 'Content-Type: application/json' \
  -d "{\"thread_id\":\"${HIGH_RISK_THREAD_ID}\",\"message\":\"ORD-1009 is delayed by 5 days. I need compensation.\"}")"

python3 - <<'PY' \
  "$RUN_RESPONSE" \
  "$HITL_RESPONSE" \
  "$BASE_URL" \
  "$LOW_RISK_THREAD_ID" \
  "$HIGH_RISK_THREAD_ID" \
  "$RELEASE_RUN_ID" \
  "$RELEASE_E2E_STARTED_AT" \
  "${SMOKE_EVIDENCE_FILE:-}"
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

payload = json.loads(sys.argv[1])
hitl_payload = json.loads(sys.argv[2])
base_url = sys.argv[3]
low_risk_thread_id = sys.argv[4]
high_risk_thread_id = sys.argv[5]
release_run_id = sys.argv[6]
release_started_at = sys.argv[7]
evidence_file = sys.argv[8]
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

events = []
hitl_events = []
for _ in range(20):
    events = events_for(thread_id)
    hitl_events = events_for(hitl_thread_id)
    types = [item.get("type") for item in events]
    hitl_types = [item.get("type") for item in hitl_events]
    if "workflow.output" in types and "hitl.request" in hitl_types:
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

if evidence_file:
    workflow_run_ids = sorted(
        {
            str(event.get("payload", {}).get("workflow_run_id"))
            for event in events + hitl_events
            if event.get("payload", {}).get("workflow_run_id")
        }
    )
    evidence = {
        "release_run_id": release_run_id,
        "release_started_at": release_started_at,
        "thread_ids": [low_risk_thread_id, high_risk_thread_id],
        "workflow_run_ids": workflow_run_ids,
    }
    path = Path(evidence_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("azure-apphosted smoke test passed")
PY
