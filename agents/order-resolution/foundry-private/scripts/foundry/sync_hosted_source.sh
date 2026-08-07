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
tar --exclude='.env' --exclude='.venv' --exclude='tests' --exclude='.pytest_cache' --exclude='__pycache__' --exclude='*/__pycache__' \
  --exclude='.foundry/checkpoints' --exclude='.foundry/memory' --exclude='.foundry/results' \
  -C "${SRC_DIR}" -cf - . | tar -C "${DST_DIR}" -xf -
cp "${SRC_DIR}/Dockerfile.hosted" "${DST_DIR}/Dockerfile"

if [[ ! -f "${DST_DIR}/Dockerfile" || ! -f "${DST_DIR}/foundry/main.py" ]]; then
  echo "Hosted source sync did not produce the required Dockerfile and entrypoint." >&2
  exit 1
fi
if ! cmp -s "${SRC_DIR}/Dockerfile.hosted" "${DST_DIR}/Dockerfile"; then
  echo "Hosted source sync produced a Dockerfile that differs from Dockerfile.hosted." >&2
  exit 1
fi
if find "${DST_DIR}" -type d -name '__pycache__' -print -quit | grep -q .; then
  echo "Hosted source sync retained a nested __pycache__ directory." >&2
  exit 1
fi
