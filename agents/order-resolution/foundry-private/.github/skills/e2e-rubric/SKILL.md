---
name: e2e-rubric
description: Preserve the private-lane Order Resolution operator rubric for native SSE, durable HITL resume, optional AG-UI, safe CopilotKit context, privacy, and wrapper boundaries.
---

# E2E Rubric (Order Resolution Private)

Use this skill when editing UI behavior, API responses, workflow events, HITL,
AG-UI, CopilotKit, or selected-thread contracts.

## Rubric sources

- `frontend/tests/e2e/*`
- `backend/tests/test_order_resolution_boundaries.py`
- `backend/tests/test_workflow.py`
- `backend/tests/test_api.py`

## Automated criteria

Keep coverage for:

1. a low-risk `ORD-1001` workflow completing without HITL unless an explicit
   damaged-item or manual-review condition applies;
2. a high-risk `ORD-1009` workflow creating a durable HITL request and
   completing after its checkpoint-keyed approval or rejection;
3. stable native SSE event types, ordering, and durable-history replay;
4. wrapper behavior in which initial dispatch is non-streaming and the browser
   receives state through durable reads and persisted-event SSE;
5. optional AG-UI selected-thread failures that leave the native timeline and
   operator controls available;
6. CopilotKit's selected-thread allowlist and redaction boundary, including no
   browser access to private Foundry, PostgreSQL, MCP/RAG data, credentials, or
   secrets; and
7. correlation identifiers and safe terminal/error-state visibility without
   exposing raw payloads.
8. static, redacted `GET /api/copilotkit/info` discovery and a `POST
   /api/copilotkit` bridge that accepts only an existing selected `threadId` as
   meaningful input; supplied messages, state, tools, context, and forwarded
   props must not affect the workflow.

## Guardrails

- Do not weaken native SSE, durable HITL, or privacy coverage merely because an
  additive AG-UI or CopilotKit surface is unavailable.
- CopilotKit is the selected assistant UI integration, not the GitHub Copilot
  SDK. Test its read-only selected-thread behavior independently of the
  workflow path.
- The private browser topology remains external frontend ACA -> same-origin
  proxy -> internal FastAPI wrapper -> private Foundry and PostgreSQL. Browser
  tests must use the frontend surface, never a direct backend or Foundry URL.
- Do not treat source configuration or local tests as evidence of a private
  deployed endpoint. Use the private runner's existing hosted gate only when
  the task explicitly requires hosted validation.
- If a criterion changes intentionally, update its tests and source-contract
  documentation in the same change.

## Verification

The selected-thread implementation has locally passed 133 tests, a 10/10
deterministic evaluation, seven workflow E2E cases, four selected-thread E2E
cases, and design review. Retain `make test-e2e`, focused selected-thread
Playwright coverage, and `make docker-test` where applicable for future
changes. Local checks do not substitute for protected private-release
evidence. Run `31911162673` is the current hosted deployment, E2E, telemetry,
and strict 3/3 Foundry evaluation authority.
