---
name: ag-ui-react-integration-ts
description: Implement and review the private-lane React TypeScript selected-thread experience for Order Resolution's additive AG-UI projection, durable history, and safe CopilotKit assistant context.
---

# AG-UI React Integration (Order Resolution Private)

Use this skill when adding or changing frontend streaming consumption or
operator behavior that depends on workflow events in the private Foundry lane.

## Scope

- `frontend/src/App.tsx`, `frontend/src/main.tsx`, and `frontend/src/config.ts`
- Selected-thread clients and allowlist modules under `frontend/src/`
- `frontend/src/components/studio/*`
- `frontend/tests/e2e/*`

## Invariants

- Native SSE and durable workflow APIs remain the operator source of truth.
  AG-UI is an optional, additive selected-thread view; a connection, parsing,
  or rendering failure must leave the native timeline and HITL controls usable.
- The browser calls only the external frontend's same-origin API proxy. It must
  not call private Foundry, PostgreSQL, MCP/RAG services, or secret-bearing
  endpoints directly.
- The selected assistant integration is CopilotKit
  (`@copilotkit/react-core`), not the GitHub Copilot SDK. Discover it with
  `GET /api/copilotkit/info` (with `GET /api/copilotkit` as an alias), then
  stream one existing selected thread through `POST /api/copilotkit`.
- Keep selected-thread context narrowly allowlisted: opaque thread ID,
  normalized status, safe event metadata, pending-approval count, and output
  presence only. Do not add order/customer details, policy or RAG data, raw
  event payloads, prompts, model output, checkpoint content, reviewer
  comments, credentials, or secrets.
- Preserve the private topology: external frontend ACA -> same-origin proxy ->
  internal FastAPI wrapper ACA -> private Foundry Responses and PostgreSQL.
  The wrapper's initial dispatch is non-streaming; live UI updates come from
  durable reads and persisted-event SSE.
- Send only the selected `threadId` as meaningful bridge input. Compatibility
  fields such as `runId`, `messages`, `state`, `tools`, `context`, and
  `forwardedProps` are intentionally ignored by the backend and must not become
  a prompt, action, or state-mutation channel.
- Keep accessibility and explicit error states for malformed, unavailable, or
  non-JSON optional stream responses.

## Verification

The selected-thread UI and its local frontend gates are implemented. Recorded
local evidence is 133 passing tests, a 10/10 deterministic evaluation, seven
workflow E2E cases, four selected-thread E2E cases, and a passing design
review. Continue to require:

1. strict type checking and `npm run build`;
2. `npm run lint`;
3. the selected-thread Playwright integration and the retained `make test-e2e`
   workflow suite; and
4. a failure-path check proving native SSE and durable history stay usable when
   the optional projection is unavailable.

These local results remain distinct from protected-release evidence. Run
`31911162673` is the current hosted deployment, E2E, telemetry, and strict 3/3
Foundry evaluation authority.
