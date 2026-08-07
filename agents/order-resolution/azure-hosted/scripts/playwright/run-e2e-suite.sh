#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
base_url="${1:?Usage: $0 <base-url> [all|selected-thread]}"
suite="${2:-all}"

run_workflow_suite() {
  (
    cd "$ROOT_DIR/scripts/playwright"
    PLAYWRIGHT_BASE_URL="$base_url" npm run test:e2e
  )
}

run_selected_thread_suite() {
  (
    cd "$ROOT_DIR/frontend"
    PLAYWRIGHT_BASE_URL="$base_url" npm run test:e2e
  )
}

case "$suite" in
  all)
    run_workflow_suite
    run_selected_thread_suite
    ;;
  selected-thread)
    run_selected_thread_suite
    ;;
  *)
    echo "Unknown E2E suite '$suite'; expected all or selected-thread." >&2
    exit 2
    ;;
esac
