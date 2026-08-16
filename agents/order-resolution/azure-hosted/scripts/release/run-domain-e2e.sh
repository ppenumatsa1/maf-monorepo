#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

get_azd_output() {
  azd env get-value "$1" --environment "$environment" 2>/dev/null
}

write_release_context \
  "$environment" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"

api_url="${RELEASE_API_BASE_URL:-${WEB_URL:-$(get_azd_output WEB_URL)}}"

if [[ ! "$api_url" =~ ^https?:// ]]; then
  echo "Selected AZD environment does not contain a valid same-origin WEB_URL output." >&2
  exit 1
fi

domain_e2e_file="$(release_artifact_path domain-e2e.json)"
http_log="$RELEASE_LOGS_DIR/domain-e2e-http.log"

http_status=0
python3 - "$domain_e2e_file" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "$environment" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION" \
  "$api_url" >"$http_log" 2>&1 <<'PY' || http_status=$?
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
    api_url,
) = sys.argv[1:]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def list_events(thread_id: str) -> list[dict[str, object]]:
    encoded = urllib.parse.quote(thread_id, safe="")
    payload = request_json("GET", f"{api_url}/api/workflows/{encoded}/events?limit=100")
    return payload.get("items", []) if isinstance(payload, dict) else []


def workflow_details(thread_id: str) -> dict[str, object]:
    encoded = urllib.parse.quote(thread_id, safe="")
    return request_json("GET", f"{api_url}/api/workflows/{encoded}")


def wait_for(
    thread_id: str,
    *,
    require_hitl: bool = False,
    require_output: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    last_details: dict[str, object] = {}
    last_events: list[dict[str, object]] = []
    for _ in range(90):
        last_details = workflow_details(thread_id)
        last_events = list_events(thread_id)
        event_types = [str(item.get("type")) for item in last_events]
        if require_output and "workflow.output" not in event_types:
            time.sleep(1)
            continue
        if require_hitl and "hitl.request" not in event_types:
            time.sleep(1)
            continue
        if require_hitl:
            approvals = last_details.get("pending_approvals") or []
            if last_details.get("status") == "waiting_approval" and approvals:
                return last_details, last_events
            if last_details.get("status") == "failed":
                raise RuntimeError(f"{thread_id} failed before approval was available.")
            time.sleep(1)
            continue
        if last_details.get("status") in {"completed", "escalated"}:
            return last_details, last_events
        if last_details.get("status") == "failed":
            raise RuntimeError(f"{thread_id} failed before completing.")
        time.sleep(1)
    raise TimeoutError(f"{thread_id} did not reach the expected state in time.")


def workflow_run_id(events: list[dict[str, object]]) -> str:
    workflow_run_ids = sorted(
        {
            str(event.get("payload", {}).get("workflow_run_id"))
            for event in events
            if isinstance(event, dict)
            and isinstance(event.get("payload"), dict)
            and event.get("payload", {}).get("workflow_run_id")
        }
    )
    if len(workflow_run_ids) != 1:
        raise RuntimeError(
            f"Expected exactly one workflow_run_id, found {workflow_run_ids!r}."
        )
    return workflow_run_ids[0]


def scenario(
    *,
    scenario_id: str,
    order_id: str,
    message: str,
    expected_hitl: bool,
    decision: str | None = None,
) -> dict[str, object]:
    thread_id = f"domain-e2e-{release_id}-{scenario_id}"
    request_json(
        "POST",
        f"{api_url}/api/chat/run",
        {"thread_id": thread_id, "message": message},
    )
    if expected_hitl:
        details, events = wait_for(thread_id, require_hitl=True)
        approvals = details.get("pending_approvals") or []
        checkpoint_id = str(approvals[0]["checkpoint_id"])
        request_json(
            "POST",
            f"{api_url}/api/hitl/respond",
            {
                "checkpoint_id": checkpoint_id,
                "decision": decision or "approve",
                "reviewer": "release-domain-e2e",
                "comments": f"{scenario_id}:{decision or 'approve'}",
            },
        )
        details, events = wait_for(thread_id, require_output=True)
        event_types = [str(item.get("type")) for item in events]
        for expected in ("checkpoint.created", "hitl.request", "hitl.response", "workflow.output"):
            if expected not in event_types:
                raise RuntimeError(f"{scenario_id} missing {expected}.")
        output = details.get("latest_output") or {}
        if output.get("status") != "completed":
            raise RuntimeError(f"{scenario_id} did not complete after approval.")
        return {
            "scenario_id": scenario_id,
            "order_id": order_id,
            "transport": "http",
            "status": "passed",
            "thread_id": thread_id,
            "workflow_run_id": workflow_run_id(events),
            "checkpoint_id": checkpoint_id,
            "expected_hitl": True,
            "observed_hitl": True,
            "decision": decision or "approve",
            "terminal_status": output.get("status"),
        }

    details, events = wait_for(thread_id, require_output=True)
    event_types = [str(item.get("type")) for item in events]
    if "hitl.request" in event_types:
        raise RuntimeError(f"{scenario_id} unexpectedly requested HITL.")
    output = details.get("latest_output") or {}
    if output.get("status") != "completed":
        raise RuntimeError(f"{scenario_id} did not finish with completed status.")
    return {
        "scenario_id": scenario_id,
        "order_id": order_id,
        "transport": "http",
        "status": "passed",
        "thread_id": thread_id,
        "workflow_run_id": workflow_run_id(events),
        "expected_hitl": False,
        "observed_hitl": False,
        "terminal_status": output.get("status"),
    }


payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "artifact_type": "domain_e2e",
    "status": "failed",
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": now_iso(),
    "target": {
        "azd_env_name": environment,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
        "api_url": api_url,
    },
    "scenarios": [],
    "correlations": [],
}

try:
    scenarios = [
        scenario(
            scenario_id="low-risk-no-hitl",
            order_id="ORD-1001",
            message="Order ORD-1001 arrived late by 1 day. What can you do?",
            expected_hitl=False,
        ),
        scenario(
            scenario_id="high-risk-approval-resume",
            order_id="ORD-1009",
            message="Order ORD-1009 is delayed by 5 days. I need compensation.",
            expected_hitl=True,
            decision="approve",
        ),
        scenario(
            scenario_id="damaged-item-approval-resume",
            order_id="ORD-1001",
            message="Order ORD-1001 arrived damaged and broken.",
            expected_hitl=True,
            decision="approve",
        ),
    ]
    payload["scenarios"] = scenarios
    payload["correlations"] = [
        {
            "thread_id": item["thread_id"],
            "workflow_run_id": item["workflow_run_id"],
        }
        for item in scenarios
        if item["transport"] == "http"
    ]
    payload["status"] = "passed"
except Exception as exc:  # noqa: BLE001
    payload["error"] = str(exc)
    Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise

Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("Azure-hosted domain HTTP scenarios passed")
PY

(( http_status == 0 ))
