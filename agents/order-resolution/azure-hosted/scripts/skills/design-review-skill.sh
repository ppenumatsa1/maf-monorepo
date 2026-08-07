#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REPORT_FILE="backend/.foundry/results/report.json"
CAPTURE_FILE="backend/.foundry/results/contract_capture.json"
REPORT_BACKUP="$(git rev-parse --git-path .design-review-report.backup.json)"
CAPTURE_BACKUP="$(git rev-parse --git-path .design-review-capture.backup.json)"
restore_report=0
restore_capture=0

cleanup() {
  if [[ "$restore_report" -eq 1 && -f "$REPORT_BACKUP" ]]; then
    mv "$REPORT_BACKUP" "$REPORT_FILE"
  fi
  if [[ "$restore_capture" -eq 1 && -f "$CAPTURE_BACKUP" ]]; then
    mv "$CAPTURE_BACKUP" "$CAPTURE_FILE"
  fi
}
trap cleanup EXIT

step() {
  echo
  echo "==> $1"
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if ! grep -Fq "$pattern" "$file"; then
    echo "[FAIL] Missing rubric/test requirement: $label"
    echo "  file: $file"
    echo "  expected text: $pattern"
    exit 1
  fi
}

step "Scope guard (avoid broad refactors)"
changed_files_count="$(git diff --name-only HEAD -- | wc -l | tr -d ' ')"
if [[ "$changed_files_count" -gt 20 ]]; then
  echo "[WARN] $changed_files_count files changed (review threshold: 20)."
  echo "Avoid broad refactors in this review skill unless explicitly required."
else
  echo "[PASS] Changed files: $changed_files_count"
fi

step "Backend formatting"
make format-check

step "Backend lint"
make lint

step "Backend tests"
make test-backend

step "Backend eval harness"
if [[ -f "$REPORT_FILE" ]]; then
  cp "$REPORT_FILE" "$REPORT_BACKUP"
  restore_report=1
fi
if [[ -f "$CAPTURE_FILE" ]]; then
  cp "$CAPTURE_FILE" "$CAPTURE_BACKUP"
  restore_capture=1
fi

make eval-backend

if [[ "$restore_report" -eq 1 ]]; then
  mv "$REPORT_BACKUP" "$REPORT_FILE"
fi
if [[ "$restore_capture" -eq 1 ]]; then
  mv "$CAPTURE_BACKUP" "$CAPTURE_FILE"
fi

step "Rubric validation"
RUBRIC_FILE="scripts/rubric/e2e-rubric.md"
E2E_SPEC_FILE="scripts/playwright/tests/workflow.e2e.spec.ts"
SELECTED_THREAD_SPEC_FILE="frontend/tests/e2e/selected-thread-integrations.spec.ts"
EVAL_CASES_FILE="backend/.foundry/datasets/order-resolution-hosted-cases.jsonl"
EVAL_RUNNER_FILE="backend/evals/eval_runner.py"
WORKFLOW_TEST_FILE="backend/tests/test_workflow.py"
PERSISTENCE_TEST_FILE="backend/tests/test_persistence_reload.py"

assert_contains "$RUBRIC_FILE" "Minimum 10/12 on automated runs." "rubric pass threshold"
assert_contains "$RUBRIC_FILE" "Any score 0 in criteria 1, 3, or 4 is automatic fail." "rubric critical fail clause"
assert_contains "$RUBRIC_FILE" "final output includes action and status and references order id." "output quality requirement"
assert_contains "$RUBRIC_FILE" "## Required gate coverage" "required baseline coverage section"
assert_contains "$EVAL_RUNNER_FILE" "if case.expected_action:" "deterministic action assertion"
assert_contains "$EVAL_RUNNER_FILE" "prohibited claim detected" "deterministic unsafe-claim assertion"
assert_contains "$EVAL_CASES_FILE" "\"id\":\"ord-1001-low-risk-late\"" "baseline low-risk eval case"
assert_contains "$EVAL_CASES_FILE" "\"id\":\"ord-1009-high-amount\"" "baseline high-risk eval case"
assert_contains "$EVAL_CASES_FILE" "\"id\":\"ord-1005-broken-reject-manual\"" "baseline rejection eval case"
assert_contains "$EVAL_CASES_FILE" "\"id\":\"ord-1008-damaged-pause-resume\"" "baseline durable resume eval case"
assert_contains "$EVAL_CASES_FILE" "\"assert_duplicate_hitl_response\":true" "baseline duplicate response eval case"
assert_contains "$E2E_SPEC_FILE" "high-risk request triggers HITL and approve path completes" "happy + HITL approve flow"
assert_contains "$E2E_SPEC_FILE" "low-risk request completes without HITL" "happy no-HITL flow"
assert_contains "$E2E_SPEC_FILE" "reject decision escalates workflow" "exception/escalation flow"
assert_contains "$E2E_SPEC_FILE" "openStudioWithHealthyHistory" "Workflow History API health check"
assert_contains "$E2E_SPEC_FILE" "workflow history status filter loads JSON without fallback HTML" "Workflow History status-filter API health check"
assert_contains "$E2E_SPEC_FILE" "not valid JSON" "HTML-as-JSON UI regression guard"
assert_contains "$WORKFLOW_TEST_FILE" "test_high_risk_flow_requests_hitl_then_resumes" "durable HITL resume test"
assert_contains "$WORKFLOW_TEST_FILE" "test_submit_resolution_is_idempotent_for_duplicate_approval" "duplicate approval response test"
assert_contains "$PERSISTENCE_TEST_FILE" "test_persists_and_reloads_after_store_reinit" "durable store reload test"
assert_contains "$SELECTED_THREAD_SPEC_FILE" "durable AG-UI view uses the selected thread GET stream" "selected-thread GET coverage"
assert_contains "$SELECTED_THREAD_SPEC_FILE" "CopilotKit bridge posts selected-thread AG-UI input to the root endpoint" "CopilotKit selection-only coverage"
assert_contains "$SELECTED_THREAD_SPEC_FILE" "optional AG-UI failure leaves selected-thread controls and native timeline available" "selected-thread fallback coverage"
assert_contains "$SELECTED_THREAD_SPEC_FILE" "cpk-web-inspector" "selected-thread inspector exclusion"

echo "[PASS] Rubric and required flow coverage checks succeeded"

step "Playwright E2E"
if [[ ! -f backend/.env && -f backend/.env.example ]]; then
  cp backend/.env.example backend/.env
fi

if [[ ! -d scripts/playwright/node_modules ]]; then
  (cd scripts/playwright && npm ci)
fi

if [[ ! -x scripts/playwright/node_modules/.bin/playwright ]]; then
  (cd scripts/playwright && npm ci)
fi

(cd scripts/playwright && npx playwright install chromium)

if ! make test-e2e-selected; then
  echo "[FAIL] Focused selected-thread E2E validation failed."
  echo "If selected-thread UI integration is still in progress, complete its documented browser contract first."
  exit 1
fi

if ! make test-e2e; then
  echo "[FAIL] Full workflow and selected-thread E2E validation failed."
  echo "If this is an environment/runtime blocker, run:"
  echo "  make up && make test-e2e"
  echo "Or run containerized E2E:"
  echo "  make docker-test"
  exit 1
fi

echo "[PASS] E2E validation succeeded"

echo
echo "All design-review skill checks passed."
