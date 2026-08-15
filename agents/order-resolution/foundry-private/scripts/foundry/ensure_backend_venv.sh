#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
STAMP_FILE="${VENV_DIR}/.requirements.sha256"

requirements_hash="$(
  sha256sum \
    "${BACKEND_DIR}/requirements.txt" \
    "${BACKEND_DIR}/requirements-dev.txt" |
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
python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check \
  -r "${BACKEND_DIR}/requirements-dev.txt"
printf '%s\n' "$requirements_hash" >"$STAMP_FILE"
echo "Prepared backend virtual environment for requirements ${requirements_hash:0:12}."
