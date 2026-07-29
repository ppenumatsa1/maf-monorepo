#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${ROOT_DIR}/backend/.venv/bin/python"

[[ -x "$PYTHON" ]] || {
  echo "Private telemetry verification requires the backend virtual environment."
  exit 1
}

exec "$PYTHON" -m evals.verify_telemetry
