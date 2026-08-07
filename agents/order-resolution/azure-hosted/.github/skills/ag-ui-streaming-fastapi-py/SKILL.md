---
name: ag-ui-streaming-fastapi-py
description: Implement or review the Azure app-hosted Order Resolution additive FastAPI AG-UI and CopilotKit projections without changing native SSE.
---

# AG-UI Streaming for FastAPI

Use this skill for streaming routes, event projections, or the selected-thread
assistant bridge.

## Scope

- `backend/app/api/v1/routers/chat.py` and `copilotkit.py`
- `backend/app/api/v1/schemas/copilotkit.py`
- `backend/app/modules/order_resolution/agui.py` and durable-event helpers
- projection/boundary tests

## Invariants

- FastAPI is the sole sequential MAF application host. Foundry supplies model
  inference and report-only evaluation only; do not add another application
  host, proxy, or orchestration path.
- Native persisted workflow events and native SSE remain the source of truth.
  Preserve `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
  `hitl.response`, and `workflow.output`.
- `/api/chat/stream/{thread_id}/rich` is an existing native-rich envelope.
  Keep its contract stable, but never use its raw event or payload as an
  assistant surface.
- `GET /api/chat/stream/{thread_id}/ag-ui` may project one already durable,
  safe thread only. It must use the allowlisted redacted projection, durable
  event tail, and heartbeat behavior; it cannot create, resume, or mutate work.
- `GET /api/copilotkit/info` and its `GET /api/copilotkit` alias return static
  redacted discovery. `POST /api/copilotkit` only selects an existing
  `threadId`; ignore compatibility input (`runId`, messages, state, tools,
  context, and `forwardedProps`).
- Emit only safe lifecycle/tool labels, validated checkpoint IDs and
  approve/reject decisions, and generic terminal/error text. Never expose raw
  native payloads, orders, policy/MCP results, tool arguments/results, prompts,
  model output, checkpoint state, credentials, or secrets.
- CopilotKit is the selected assistant integration, not the GitHub Copilot SDK.

## Verification

1. Run affected backend projection and boundary tests.
2. Assert missing/invalid thread IDs fail and discovery is static.
3. Assert compatibility fields cannot influence the selected workflow.
4. Run `make test-e2e-selected` for browser-visible bridge changes; optional
   projection failure must leave native SSE, history, and HITL controls usable.
