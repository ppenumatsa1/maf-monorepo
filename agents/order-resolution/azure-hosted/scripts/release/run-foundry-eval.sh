#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

report_file="${FOUNDRY_EVAL_OUTPUT_FILE:-}"
max_attempts="${FOUNDRY_EVAL_ERROR_RETRY_ATTEMPTS:-3}"
retry_seconds="${FOUNDRY_EVAL_ERROR_RETRY_SECONDS:-15}"

[[ -n "$report_file" ]] || {
  echo "FOUNDRY_EVAL_OUTPUT_FILE is required for the release evaluation." >&2
  exit 1
}
[[ "$max_attempts" =~ ^[1-5]$ ]] || {
  echo "FOUNDRY_EVAL_ERROR_RETRY_ATTEMPTS must be between 1 and 5." >&2
  exit 1
}
[[ "$retry_seconds" =~ ^[0-9]+$ ]] && (( retry_seconds <= 300 )) || {
  echo "FOUNDRY_EVAL_ERROR_RETRY_SECONDS must be between 0 and 300." >&2
  exit 1
}

retryable_evaluator_error_only() {
  python3 - "$report_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file() or path.is_symlink():
    raise SystemExit(1)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

result_counts = payload.get("result_counts")
run_details = payload.get("run_details")
criteria = (
    run_details.get("per_testing_criteria_results")
    if isinstance(run_details, dict)
    else None
)
if not isinstance(result_counts, dict) or not isinstance(criteria, list) or not criteria:
    raise SystemExit(1)
if int(result_counts.get("failed", 0)) != 0:
    raise SystemExit(1)

errors = 0
for result in criteria:
    if not isinstance(result, dict):
        raise SystemExit(1)
    if any(int(result.get(name, 0)) != 0 for name in ("failed", "skipped", "expected")):
        raise SystemExit(1)
    errors += int(result.get("errored", 0))
raise SystemExit(0 if errors > 0 else 1)
PY
}

for ((attempt = 1; attempt <= max_attempts; attempt += 1)); do
  set +e
  make --no-print-directory eval-foundry-deployed
  result=$?
  set -e
  (( result == 0 )) && exit 0

  if (( attempt < max_attempts )) && retryable_evaluator_error_only; then
    echo "Foundry evaluation had evaluator errors but no quality failures; retrying ($attempt/$max_attempts)."
    sleep "$retry_seconds"
    continue
  fi
  exit "$result"
done

exit 1
