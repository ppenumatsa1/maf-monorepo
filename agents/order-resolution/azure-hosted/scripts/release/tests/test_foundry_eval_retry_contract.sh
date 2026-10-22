#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scratch="$ROOT_DIR/.artifacts/foundry-eval-retry-contract-$$"
fake_bin="$scratch/bin"
report="$scratch/evaluation.json"
counter="$scratch/count"
mkdir -p "$fake_bin"
trap 'rm -rf "$scratch"' EXIT

cat >"$fake_bin/make" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
count=0
[[ ! -f "$TEST_COUNTER" ]] || count="$(cat "$TEST_COUNTER")"
count=$((count + 1))
printf '%s\n' "$count" >"$TEST_COUNTER"

failed=0
errored=0
exit_code=0
if [[ "$TEST_MODE" == "evaluator-error" && "$count" -eq 1 ]]; then
  errored=1
  exit_code=1
elif [[ "$TEST_MODE" == "quality-failure" ]]; then
  failed=1
  exit_code=1
fi

python3 - "$FOUNDRY_EVAL_OUTPUT_FILE" "$failed" "$errored" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
failed = int(sys.argv[2])
errored = int(sys.argv[3])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    json.dumps(
        {
            "result_counts": {"failed": failed, "errored": errored},
            "run_details": {
                "per_testing_criteria_results": [
                    {
                        "testing_criteria": "task_completion",
                        "passed": 3 - failed - errored,
                        "failed": failed,
                        "errored": errored,
                        "skipped": 0,
                        "expected": 0,
                    },
                    {
                        "testing_criteria": "coherence",
                        "passed": 3,
                        "failed": 0,
                        "errored": 0,
                        "skipped": 0,
                        "expected": 0,
                    },
                ]
            },
        }
    )
    + "\n",
    encoding="utf-8",
)
PY
exit "$exit_code"
SH
chmod +x "$fake_bin/make"

run_case() {
  local mode="$1"
  rm -f "$counter"
  rm -f "$report"
  PATH="$fake_bin:$PATH" \
    TEST_MODE="$mode" \
    TEST_COUNTER="$counter" \
    FOUNDRY_EVAL_OUTPUT_FILE="$report" \
    FOUNDRY_EVAL_ERROR_RETRY_ATTEMPTS=3 \
    FOUNDRY_EVAL_ERROR_RETRY_SECONDS=0 \
    "$ROOT_DIR/scripts/release/run-foundry-eval.sh"
}

run_case evaluator-error
[[ "$(cat "$counter")" == "2" ]] || {
  echo "Evaluator-error-only result was not retried exactly once." >&2
  exit 1
}

set +e
run_case quality-failure
quality_status=$?
set -e
[[ "$quality_status" -ne 0 ]] || {
  echo "Quality failure was incorrectly accepted." >&2
  exit 1
}
[[ "$(cat "$counter")" == "1" ]] || {
  echo "Quality failure was incorrectly retried." >&2
  exit 1
}

echo "Foundry evaluator retry contract passed."
