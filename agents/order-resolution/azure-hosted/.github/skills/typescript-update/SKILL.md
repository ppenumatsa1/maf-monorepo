---
name: typescript-update
description: Update Azure app-hosted Order Resolution React TypeScript code or dependencies while preserving strictness, native SSE, redaction, and operator behavior.
---

# TypeScript Update

Use this skill for existing TypeScript, React, dependency, or frontend build
configuration changes.

## Invariants

- Keep typecheck, build, and lint clean without reducing strictness.
- Preserve FastAPI as the sole MAF host and native SSE as the stable timeline.
  AG-UI/CopilotKit remain optional redacted durable-event projections.
- Preserve runtime endpoint precedence: injected `window.__APP_CONFIG__`, then
  Vite values, then same-origin API defaults.
- Do not expose order, policy, MCP, prompt, model, checkpoint, credential, or
  secret data in UI types, errors, logs, raw-event panels, or assistant
  context. Keep the CopilotKit inspector disabled.

## Verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e-selected` for selected-thread changes; otherwise run the
   smallest applicable existing Playwright target.
