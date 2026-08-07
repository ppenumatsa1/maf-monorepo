---
name: typescript-update
description: Update Order Resolution React TypeScript code or dependencies while preserving strictness, stable SSE, safe CopilotKit context, and operator behavior.
---

# TypeScript Update (Order Resolution)

Use this skill when modifying existing TypeScript, React components, frontend
dependencies, or their build configuration.

## Invariants

- Keep typecheck, build, and lint clean at each meaningful step. Do not reduce
  strictness, add `@ts-ignore`, or widen types to `any` to silence errors.
- Keep frontend workflow contracts aligned with the public FastAPI wrapper and
  retain native SSE as the stable timeline. AG-UI remains an optional additive
  projection of durable events.
- Preserve the safe selected-thread boundary in `frontend/src/copilot.ts`.
  CopilotKit is the selected runtime integration; GitHub Copilot SDK is not a
  substitute or an application dependency.
- Do not expose order, policy, MCP/RAG, checkpoint, prompt, model, credential,
  or secret data through frontend types, logs, errors, or assistant context.
- Preserve the external frontend -> internal API wrapper topology and its
  non-streaming initial dispatch plus durable-state/SSE update model.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` for user-visible, API, AG-UI, CopilotKit, or selected-thread changes

