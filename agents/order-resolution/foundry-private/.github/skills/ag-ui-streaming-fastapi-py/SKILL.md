---
name: ag-ui-streaming-fastapi-py
description: Implement and review the private-lane FastAPI AG-UI and CopilotKit projections of durable workflow events without changing the stable SSE contract.
---

# AG-UI Streaming for FastAPI (Order Resolution Private)

Use this skill when changing streaming APIs, event envelopes, the
selected-thread assistant bridge, or backend-to-frontend event projection in
the private Foundry lane.

## Scope

- Stable and additive route entrypoints: `backend/app/api/v1/routers/*`
- Stream and bridge schemas: `backend/app/api/v1/schemas/*`
- Safe projection and durable-tail helpers:
  `backend/app/modules/order_resolution/agui.py` and
  `backend/app/modules/order_resolution/durable_events.py`
- Boundary coverage: `backend/tests/test_order_resolution_boundaries.py`

## Invariants

- Native workflow events and durable PostgreSQL projections remain the source
  of truth. AG-UI and CopilotKit frames are additive views, never a replacement
  for the stable native SSE contract.
- Preserve stable event types and their consumer behavior:
  `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
  `hitl.response`, and `workflow.output`.
- Retain the one sequential MAF path based on `FoundryChatClient` and
  `SequentialBuilder`. The HTTP wrapper projects or relays durable state; it
  must not create a second orchestration path.
- Preserve durable checkpoint-keyed HITL pause/resume and event ordering. The
  external frontend receives a non-streaming initial wrapper dispatch, then
  polls durable state and subscribes to persisted-event SSE.
- CopilotKit is the selected read-only assistant integration; it is not the
  GitHub Copilot SDK. `GET /api/copilotkit/info` (and `GET /api/copilotkit`)
  returns static discovery only. `POST /api/copilotkit` may select one existing
  `threadId` and expose only the allowlisted, redacted projection; it must not
  start work or honor supplied `runId`, messages, state, tools, context,
  forwarded props, credentials, or arbitrary thread data.
- Never project raw order/customer or policy data, MCP/RAG results, tool
  arguments/results, prompts, model output, checkpoint payloads, reviewer
  comments, credentials, or secrets. Preserve the private external-browser ->
  internal-wrapper boundary; only the wrapper and hosted agent use private
  Foundry and PostgreSQL paths.
- The selected-thread projection may emit only `RUN_STARTED`, safe
  `STEP_*`/`TOOL_CALL_*` frames, CUSTOM checkpoint/approval summaries with
  validated UUIDs and approved/rejected decisions, generic terminal/error
  text, and `RUN_FINISHED`. Do not use the existing `/rich` native-event
  envelope as a redacted assistant stream.

## Verification

The current selected-thread implementation has local evidence of 128 passing
tests, a 10/10 deterministic evaluation, seven workflow E2E cases, four
selected-thread E2E cases, and a passing design review. When a projection or
bridge implementation changes:

1. run focused projection and boundary tests, including
   `backend/tests/test_order_resolution_boundaries.py`;
2. verify static `GET /api/copilotkit/info` discovery and that standard
   CopilotKit input is discarded rather than acted upon;
3. run the browser suite, including selected-thread coverage, when a
   browser-visible stream or bridge contract changes; and
4. prove an optional AG-UI/CopilotKit failure does not break native SSE or
   durable-history behavior.

The local evidence is distinct from protected-release evidence. The
`vm-maffnd-runner` deployment, hosted E2E, Foundry evaluation, and telemetry
record are documented in `docs/design/issues-changes-fixes.md`.
