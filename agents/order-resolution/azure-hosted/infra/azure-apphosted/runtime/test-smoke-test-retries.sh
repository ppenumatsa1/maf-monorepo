#!/bin/bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
SMOKE_TEST="$ROOT_DIR/infra/azure-apphosted/runtime/smoke-test.sh"
TEST_DIR="$ROOT_DIR/.artifacts/smoke-retry-test-$$-$RANDOM"
FAKE_BIN="$TEST_DIR/bin"

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/curl" <<'EOF'
#!/bin/bash
set -euo pipefail

for argument in "$@"; do
  if [[ "$argument" == */api/chat/run ]]; then
    attempt="$(($(cat "$FAKE_REQUEST_COUNT" 2>/dev/null || echo 0) + 1))"
    printf '%s\n' "$attempt" >"$FAKE_REQUEST_COUNT"
    case "$FAKE_SCENARIO:$attempt" in
      recover:1) exit 0 ;;
      recover:2) exit 22 ;;
      recover:3) printf '%s' '{"thread_id":"recovered-low-risk"}' ;;
      recover:4) printf '%s' '{"thread_id":"recovered-high-risk"}' ;;
      exhaust:*) exit 22 ;;
      *) echo "unexpected /api/chat/run attempt: $FAKE_SCENARIO:$attempt" >&2; exit 99 ;;
    esac
    exit 0
  fi
done
EOF

cat >"$FAKE_BIN/sleep" <<'EOF'
#!/bin/bash
set -euo pipefail
:
EOF

cat >"$FAKE_BIN/python3" <<'EOF'
#!/bin/bash
set -euo pipefail
[[ "$1" == "-" ]]
[[ "$2" == '{"thread_id":"recovered-low-risk"}' ]]
[[ "$3" == '{"thread_id":"recovered-high-risk"}' ]]
printf '%s\n' "azure-apphosted smoke test passed"
EOF
chmod 700 "$FAKE_BIN"/*

run_smoke() {
  local scenario="$1"
  local count_file="$TEST_DIR/$scenario-request-count"

  /usr/bin/env -u BASH_ENV -u ENV \
    PATH="$FAKE_BIN:$PATH" \
    FAKE_SCENARIO="$scenario" \
    FAKE_REQUEST_COUNT="$count_file" \
    "$SMOKE_TEST" "https://smoke-test.invalid"
}

run_smoke recover
[[ "$(<"$TEST_DIR/recover-request-count")" == "4" ]] || {
  echo "Transient empty and failed /api/chat/run responses did not recover as expected." >&2
  exit 1
}

if exhaustion_output="$(run_smoke exhaust 2>&1)"; then
  echo "Exhausted /api/chat/run retries unexpectedly succeeded." >&2
  exit 1
fi
[[ "$(<"$TEST_DIR/exhaust-request-count")" == "10" ]] || {
  echo "Expected ten bounded /api/chat/run retry attempts after exhaustion." >&2
  exit 1
}
[[ "$exhaustion_output" == *"Timed out waiting for a non-empty /api/chat/run response"* ]] || {
  echo "Exhausted /api/chat/run retries did not emit the explicit timeout failure." >&2
  printf '%s\n' "$exhaustion_output" >&2
  exit 1
}

echo "Azure-hosted smoke retry contract passed"
