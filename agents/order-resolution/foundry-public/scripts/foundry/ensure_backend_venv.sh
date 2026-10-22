#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
STAMP_FILE="${VENV_DIR}/.requirements.sha256"

select_python() {
  local candidate

  if [[ -n "${BACKEND_PYTHON_BIN:-}" ]]; then
    printf '%s' "$BACKEND_PYTHON_BIN"
    return
  fi
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done
  for candidate in \
    "$HOME/.local/bin/python3.13" \
    "$HOME/.local/bin/python3.12" \
    "$HOME/.local/bin/python3.11"; do
    if [[ -x "$candidate" ]]; then
      printf '%s' "$candidate"
      return
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "Python 3.11 or newer is required for backend tooling." >&2
  return 1
}

PYTHON_BIN="$(select_python)"
"$PYTHON_BIN" -c '
import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        "Backend dependencies require Python 3.11 or newer. "
        "Set BACKEND_PYTHON_BIN to Python 3.13, 3.12, or 3.11."
    )
'

requirements_hash="$(
  sha256sum \
    "${BACKEND_DIR}/requirements.txt" \
    "${BACKEND_DIR}/requirements.lock" \
    "${BACKEND_DIR}/requirements-dev.txt" \
    "${BACKEND_DIR}/requirements-dev.lock" |
    sha256sum |
    awk '{print $1}'
)"

if [[ "${FORCE_BACKEND_VENV_REFRESH:-false}" != "true" &&
  -x "${VENV_DIR}/bin/python" &&
  -f "$STAMP_FILE" &&
  "$(cat "$STAMP_FILE")" == "$requirements_hash" ]] &&
  "${VENV_DIR}/bin/python" -c "import azure.ai.projects, pytest" >/dev/null 2>&1; then
  echo "Reusing backend virtual environment for requirements ${requirements_hash:0:12}."
  exit 0
fi

rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check \
  --index-url "https://packagefeedproxy.microsoft.io/pypi/simple" \
  --extra-index-url "https://pypi.org/simple" \
  --require-hashes \
  -r "${BACKEND_DIR}/requirements-dev.lock"
printf '%s\n' "$requirements_hash" >"$STAMP_FILE"
echo "Prepared backend virtual environment for requirements ${requirements_hash:0:12}."
