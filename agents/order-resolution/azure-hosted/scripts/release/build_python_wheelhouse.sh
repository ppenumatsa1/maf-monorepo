#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
BACKEND_DIR="$ROOT_DIR/backend"
LOCK_FILE="$BACKEND_DIR/requirements.lock"
WHEELHOUSE_DIR="$BACKEND_DIR/.wheels"
VALIDATOR="$ROOT_DIR/scripts/release/validate_python_wheelhouse.py"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"
EXTRA_INDEX_URL="https://pypi.org/simple"
CONTRACT_FILE="$WHEELHOUSE_DIR/.wheelhouse-contract.json"

if [[ ! -f "$LOCK_FILE" ]]; then
  echo "Runtime dependency lock is missing: $LOCK_FILE" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c \
  'import sys; raise SystemExit(sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 13))'; then
  echo "Wheelhouse generation requires CPython 3.13: $PYTHON_BIN" >&2
  exit 1
fi

requirements_hash="$(
  {
    sha256sum "$LOCK_FILE" | awk '{print $1}'
    printf '%s\n' 'manylinux2014_x86_64|cp|3.13|cp313'
    printf '%s\n' "$INDEX_URL"
    printf '%s\n' "$EXTRA_INDEX_URL"
  } | sha256sum | awk '{print $1}'
)"

if [[ -f "$CONTRACT_FILE" ]] &&
  "$PYTHON_BIN" "$VALIDATOR" "$WHEELHOUSE_DIR" "$LOCK_FILE" >/dev/null &&
  [[ "$("$PYTHON_BIN" -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["contract_hash"])' \
    "$CONTRACT_FILE")" == "$requirements_hash" ]]; then
  wheel_count="$(find "$WHEELHOUSE_DIR" -maxdepth 1 -type f -name '*.whl' | wc -l)"
  echo "Reusing ${wheel_count} validated CPython 3.13 Linux AMD64 wheels."
  exit 0
fi

find "$WHEELHOUSE_DIR" -mindepth 1 ! -name .gitkeep -delete

"$PYTHON_BIN" -m pip download \
  --disable-pip-version-check \
  --index-url "$INDEX_URL" \
  --extra-index-url "$EXTRA_INDEX_URL" \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --python-version 3.13 \
  --implementation cp \
  --abi cp313 \
  --require-hashes \
  --dest "$WHEELHOUSE_DIR" \
  -r "$LOCK_FILE"

"$PYTHON_BIN" "$VALIDATOR" \
  "$WHEELHOUSE_DIR" \
  "$LOCK_FILE" \
  --write-contract \
  --contract-hash "$requirements_hash" \
  --index-url "$INDEX_URL"

wheel_count="$(find "$WHEELHOUSE_DIR" -maxdepth 1 -type f -name '*.whl' | wc -l)"
echo "Prepared ${wheel_count} hash-verified CPython 3.13 Linux AMD64 wheels."
