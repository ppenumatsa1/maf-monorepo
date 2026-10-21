#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
WHEELHOUSE_DIR="${BACKEND_DIR}/.wheels"
PYTHON_BIN="${PYTHON_BIN:-${BACKEND_DIR}/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment is missing: ${PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${BACKEND_DIR}/requirements.lock" ]]; then
  echo "Runtime dependency lock is missing: backend/requirements.lock" >&2
  exit 1
fi

rm -rf "$WHEELHOUSE_DIR"
mkdir -p "$WHEELHOUSE_DIR"

"$PYTHON_BIN" -m pip download \
  --disable-pip-version-check \
  --index-url "https://packagefeedproxy.microsoft.io/pypi/simple" \
  --extra-index-url "https://pypi.org/simple" \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --python-version 3.13 \
  --implementation cp \
  --abi cp313 \
  --require-hashes \
  --dest "$WHEELHOUSE_DIR" \
  -r "${BACKEND_DIR}/requirements.lock"

wheel_count="$(find "$WHEELHOUSE_DIR" -maxdepth 1 -type f -name '*.whl' | wc -l)"
if [[ "$wheel_count" -eq 0 ]]; then
  echo "Runtime wheelhouse is empty." >&2
  exit 1
fi
echo "Prepared ${wheel_count} hash-verified Python 3.13 Linux AMD64 wheels."
