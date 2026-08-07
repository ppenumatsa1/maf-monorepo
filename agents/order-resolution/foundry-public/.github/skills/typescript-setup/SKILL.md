---
name: typescript-setup
description: Set up or extend Order Resolution frontend TypeScript surfaces without weakening strictness, durable workflow contracts, or privacy boundaries.
---

# TypeScript Setup (Order Resolution)

Use this skill when adding or restructuring frontend TypeScript files,
components, or configuration.

## Scope

- `frontend/src/**/*`
- `frontend/tsconfig*.json`
- `frontend/eslint.config.js`
- `frontend/tests/e2e/*`

## Invariants

- Preserve strict TypeScript settings. Do not introduce `any`, unsafe casts,
  compiler suppression comments, or weaker `tsconfig` settings to hide
  contract errors.
- Prefer explicit shared types for threads, workflow status, events,
  checkpoints, approvals, and outputs over ad hoc object indexing.
- Keep browser integrations on the public same-origin FastAPI wrapper. No
  frontend type or client may create direct Foundry, PostgreSQL, MCP/RAG, or
  secret-bearing access.
- Preserve native SSE as the stable contract and treat AG-UI types as optional,
  additive selected-thread projections.
- Keep the `frontend/src/copilot.ts` allowlist narrow. The chosen integration
  is CopilotKit, not the GitHub Copilot SDK; do not add or imply a GitHub
  Copilot SDK runtime dependency.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` when UI, API, AG-UI, CopilotKit, or selected-thread behavior changes

