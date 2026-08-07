---
name: typescript-setup
description: Set up or extend Azure app-hosted Order Resolution frontend TypeScript without weakening strictness, workflow contracts, or privacy boundaries.
---

# TypeScript Setup

Use this skill for new or restructured frontend TypeScript surfaces.

## Invariants

- Preserve strict TypeScript and ESLint settings. Do not use `any`,
  suppression comments, unsafe broad casts, or weaker compiler settings to
  hide contract errors.
- Model workflow threads, statuses, events, approvals, and outputs explicitly.
  AG-UI types are optional redacted selected-thread projections; native SSE
  remains the stable contract.
- Keep public browser clients same-origin and runtime-configured. No frontend
  type or client may directly access Foundry, PostgreSQL, MCP/RAG, credentials,
  or secrets.
- Keep `frontend/src/copilot.ts` narrow and redacted. The integration is
  CopilotKit, not the GitHub Copilot SDK, and its inspector stays disabled.

## Verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. Run the applicable existing Playwright target.
