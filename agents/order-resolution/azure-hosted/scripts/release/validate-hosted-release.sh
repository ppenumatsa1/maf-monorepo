#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

environment="${AZURE_ENV_NAME:-maf-ora-azure}"
release_run_id="${RELEASE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
release_started_at="${RELEASE_E2E_STARTED_AT:-$(python3 - <<'PY'
from datetime import UTC, datetime
print(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
PY
)}"
artifacts_dir="$ROOT_DIR/.artifacts/release/$release_run_id"
evidence_file="$artifacts_dir/hosted-e2e-evidence.json"
dry_run="${RELEASE_DRY_RUN:-false}"

if [[ "$dry_run" == "true" ]]; then
  cat <<EOF
Hosted release validation dry run:
  resolve API_URL and WEB_URL from AZD environment $environment
  smoke the backend and frontend before hosted E2E/eval
  run hosted Playwright E2E and Foundry evaluation
  query fresh App Insights evidence since $release_started_at
EOF
  exit 0
fi

get_azd_output() {
  local name="$1"
  azd env get-value "$name" --environment "$environment" 2>/dev/null
}

api_url="${API_URL:-$(get_azd_output API_URL)}"
web_url="${WEB_URL:-$(get_azd_output WEB_URL)}"

if [[ ! "$api_url" =~ ^https?:// || ! "$web_url" =~ ^https?:// ]]; then
  echo "Selected AZD environment does not contain valid API_URL and WEB_URL outputs." >&2
  exit 1
fi

mkdir -p "$artifacts_dir"

RELEASE_RUN_ID="$release_run_id" \
RELEASE_E2E_STARTED_AT="$release_started_at" \
SMOKE_EVIDENCE_FILE="$evidence_file" \
infra/azure-apphosted/runtime/smoke-test.sh "$api_url" "$web_url"

python3 - "$evidence_file" "$api_url" "$release_run_id" "$release_started_at" <<'PY'
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

evidence_path, api_url, release_run_id, release_started_at = sys.argv[1:]
evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
if evidence.get("release_run_id") != release_run_id:
    raise SystemExit("Smoke evidence release_run_id does not match this release.")
if evidence.get("release_started_at") != release_started_at:
    raise SystemExit("Smoke evidence release_started_at does not match this release.")
thread_ids = evidence.get("thread_ids")
if not isinstance(thread_ids, list) or not thread_ids:
    raise SystemExit("Smoke evidence contains no thread IDs.")

correlations: list[dict[str, str]] = []
for thread_id in thread_ids:
    if not isinstance(thread_id, str) or not thread_id.startswith(f"smoke-apphosted-{release_run_id}-"):
        raise SystemExit("Smoke evidence contains a thread outside this release.")
    workflow_run_ids: set[str] = set()
    for _ in range(20):
        thread_url = urllib.parse.quote(thread_id, safe="")
        with urllib.request.urlopen(f"{api_url}/api/workflows/{thread_url}/events?limit=100") as response:
            events = json.loads(response.read().decode("utf-8")).get("items", [])
        workflow_run_ids = {
            str(event.get("payload", {}).get("workflow_run_id"))
            for event in events
            if isinstance(event, dict) and event.get("payload", {}).get("workflow_run_id")
        }
        if workflow_run_ids:
            break
        time.sleep(1)
    if len(workflow_run_ids) != 1:
        raise SystemExit(
            f"Smoke evidence requires exactly one workflow_run_id for fresh thread {thread_id!r}; "
            f"found {sorted(workflow_run_ids)!r}."
        )
    correlations.append(
        {"thread_id": thread_id, "workflow_run_id": next(iter(workflow_run_ids))}
    )

if len({pair["thread_id"] for pair in correlations}) != len(correlations):
    raise SystemExit("Smoke evidence contains duplicate threads.")
evidence["correlations"] = correlations
Path(evidence_path).write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

PLAYWRIGHT_BASE_URL="$web_url" \
PLAYWRIGHT_ARTIFACTS_DIR="$artifacts_dir/playwright" \
make --no-print-directory test-e2e

AZURE_ENV_NAME="$environment" make --no-print-directory eval-foundry-deployed

AZURE_ENV_NAME="$environment" \
RELEASE_RUN_ID="$release_run_id" \
RELEASE_E2E_STARTED_AT="$release_started_at" \
E2E_EVIDENCE_FILE="$evidence_file" \
./scripts/release/verify-app-insights-correlation.sh
