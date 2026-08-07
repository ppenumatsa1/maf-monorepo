---
name: typescript-setup
description: Set up or extend private-lane Order Resolution frontend TypeScript surfaces without weakening strictness, durable workflow contracts, or privacy boundaries.
---

# TypeScript Setup (Order Resolution Private)

Use this skill when adding or restructuring frontend TypeScript files,
components, configuration, or selected-thread tests.

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
- Keep browser integrations on the public same-origin API proxy exposed by the
  private frontend. No frontend type or client may create direct private
  Foundry, PostgreSQL, MCP/RAG, or secret-bearing access.
- Preserve native SSE as the stable contract and treat AG-UI types as optional,
  additive selected-thread projections.
- Keep selected-thread context narrow. The chosen integration is CopilotKit,
  not the GitHub Copilot SDK; do not add or imply a GitHub Copilot SDK runtime
  dependency.
- Preserve the VNet-isolated private topology: only the external frontend has
  public ingress; the FastAPI wrapper, Foundry, ACR, and PostgreSQL remain on
  private paths.

## Verification

The private frontend now provides the modern strict TypeScript/frontend gates.
The selected-thread implementation locally passed 128 tests, a 10/10
deterministic evaluation, seven workflow E2E cases, four selected-thread E2E
cases, and design review. Retain strict type checking, `npm run build`,
`npm run lint`, and focused selected-thread Playwright coverage for future
changes. The protected `vm-maffnd-runner` deployment, hosted E2E, Foundry
evaluation, and telemetry verification remain outstanding.
