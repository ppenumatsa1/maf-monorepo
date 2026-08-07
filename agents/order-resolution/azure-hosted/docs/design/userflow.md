# User Flow

## Current contract

The React UI submits requests to the FastAPI MAF application and consumes the
native SSE stream. The same application contract is used locally and by the
planned Container Apps deployment.

1. An operator submits an order issue with `POST /api/chat/run`.
2. The UI subscribes to `GET /api/chat/stream/{thread_id}`.
3. The MAF workflow performs triage, policy retrieval, and resolution.
4. A low-risk case emits `workflow.output`.
5. A risky case emits `checkpoint.created` and `hitl.request`.
6. The operator sends an approval or rejection to `POST /api/hitl/respond`.
7. The workflow resumes and emits `hitl.response` plus terminal
   `workflow.output`.

Repeated responses for the same checkpoint are idempotent and must not create
duplicate terminal events.

## Read and stream endpoints

- `GET /api/chat/stream/{thread_id}/rich` is an additive native-rich stream.
- `GET /api/chat/stream/{thread_id}/ag-ui` is an additive redacted projection
  of an existing durable thread.
- `GET /api/copilotkit/info` (and `GET /api/copilotkit`) returns static
  discovery with inspector/list/mutation endpoints disabled.
- `POST /api/copilotkit` selects one existing `threadId`; compatibility fields
  are discarded and the request cannot mutate a workflow.
- `GET /api/workflows`
- `GET /api/workflows/{thread_id}`
- `GET /api/workflows/{thread_id}/events`
- `GET /api/sessions/{session_id}/messages`

## Stable events

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

The native stream remains the source of truth. The rich stream must not rename
or replace it and remains a native-payload contract. The assistant projections
are deliberately separate: they expose only safe labels, validated
checkpoint/decision summaries, and generic terminal/error text. They never
surface raw native payloads, order/policy/MCP data, tool data, prompts, model
output, checkpoint state, credentials, or secrets.

The React image may configure the same endpoints at runtime through
`window.__APP_CONFIG__` (`API_BASE`, `AG_UI_URL`, and `COPILOTKIT_URL`), before
Vite fallback values. The CopilotKit inspector remains disabled; an optional
AG-UI/CopilotKit failure must not block native timeline, history, or HITL UI.

## Baselines

- `ORD-1001` late delivery: no HITL expected.
- `ORD-1009` delayed/high amount: HITL expected.
- Damaged item: HITL expected.

See [HITL approval conditions](hitl-approval-conditions.md) for exact rules.
