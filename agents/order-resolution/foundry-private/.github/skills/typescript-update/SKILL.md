---
name: typescript-update
description: Update private-lane Order Resolution React TypeScript code or dependencies while preserving strictness, stable SSE, safe CopilotKit context, and operator behavior.
---

# TypeScript Update (Order Resolution Private)

Use this skill when modifying existing TypeScript, React components, frontend
dependencies, or their build configuration.

## Invariants

- Keep typecheck, build, and lint clean at each meaningful step. Do not reduce
  strictness, add `@ts-ignore`, or widen types to `any` to silence errors.
- Keep frontend workflow contracts aligned with the same-origin FastAPI wrapper
  and retain native SSE as the stable timeline. AG-UI remains an optional,
  additive selected-thread projection of durable events.
- Preserve the safe selected-thread boundary. CopilotKit is the selected
  runtime integration; the GitHub Copilot SDK is not a substitute or an
  application dependency.
- Do not expose order/customer, policy, MCP/RAG, checkpoint, prompt, model,
  reviewer-comment, credential, or secret data through frontend types, logs,
  errors, or assistant context.
- Preserve the private external frontend -> internal API wrapper topology and
  its non-streaming initial dispatch plus durable-state/SSE update model.

## Verification

The current implementation locally passed 128 tests, a 10/10 deterministic
evaluation, seven workflow E2E cases, four selected-thread E2E cases, and
design review. Continue to run strict type checking, `npm run build`,
`npm run lint`, and `make test-e2e` with focused selected-thread coverage for
user-visible, API, AG-UI, CopilotKit, or selected-thread changes. The protected
`vm-maffnd-runner` deployment, hosted E2E, Foundry evaluation, and telemetry
verification remain outstanding.
