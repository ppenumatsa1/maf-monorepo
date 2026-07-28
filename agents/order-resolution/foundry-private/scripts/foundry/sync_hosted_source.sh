#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${ROOT_DIR}/backend"
DST_DIR="${ROOT_DIR}/infra/foundry-hosted/agent"

if [[ ! -f "${SRC_DIR}/Dockerfile.hosted" || ! -f "${SRC_DIR}/foundry/main.py" ]]; then
  echo "Hosted source validation failed: backend/Dockerfile.hosted and backend/foundry/main.py are required."
  exit 1
fi

rm -rf "${DST_DIR}"
mkdir -p "${DST_DIR}"
tar --exclude='.env' --exclude='.venv' --exclude='tests' --exclude='.pytest_cache' --exclude='__pycache__' \
  --exclude='.foundry/checkpoints' --exclude='.foundry/memory' --exclude='.foundry/results' \
  -C "${SRC_DIR}" -cf - . | tar -C "${DST_DIR}" -xf -
cp "${SRC_DIR}/Dockerfile.hosted" "${DST_DIR}/Dockerfile"
