#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AGENT_DIR="$ROOT_DIR/infra/foundry-hosted/agent"

rm -rf "$AGENT_DIR"
mkdir -p "$AGENT_DIR"

cp "$ROOT_DIR/pyproject.toml" "$AGENT_DIR/"
cp "$ROOT_DIR/backend/Dockerfile.hosted" "$AGENT_DIR/Dockerfile"
tar \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.foundry/results' \
  -C "$ROOT_DIR" \
  -cf - backend | tar -C "$AGENT_DIR" -xf -
cp "$ROOT_DIR/backend/eval.yaml" "$AGENT_DIR/eval.yaml"
cp -R "$ROOT_DIR/backend/.foundry" "$AGENT_DIR/.foundry"
