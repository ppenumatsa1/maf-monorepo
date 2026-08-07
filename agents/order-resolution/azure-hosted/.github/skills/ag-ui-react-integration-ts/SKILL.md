---
name: ag-ui-react-integration-ts
description: Implement or review the Azure app-hosted React selected-thread AG-UI and CopilotKit experience without weakening workflow or privacy contracts.
---

# AG-UI React Integration

Use this skill when changing frontend stream consumption, selected-thread UI,
CopilotKit context, or operator behavior based on workflow events.

## Scope

- `frontend/src/App.tsx`, `main.tsx`, `config.ts`, and `copilot.ts`
- `frontend/src/lib/*` and `frontend/src/components/studio/*`
- `frontend/tests/e2e/*`

## Invariants

- Native SSE, durable workflow reads, and HITL controls are the operator source
  of truth. AG-UI and CopilotKit are optional selected-thread displays; a
  parsing, connection, or endpoint failure must not disable the native UI.
- The browser uses same-origin FastAPI APIs through Nginx only. It must not
  call Foundry, PostgreSQL, MCP/RAG, or secret-bearing services directly.
- Resolve endpoints at runtime from `window.__APP_CONFIG__` (`API_BASE`,
  `AG_UI_URL`, `COPILOTKIT_URL`) before Vite build-time fallback values. The
  safe defaults are `/api/chat/stream/{threadId}/ag-ui` and
  `/api/copilotkit`.
- CopilotKit is not GitHub Copilot. Its context remains allowlisted to opaque
  thread ID, normalized status, safe event metadata, pending-approval count,
  and output presence. Do not add raw events or business/content data.
- The CopilotKit inspector remains disabled. The selected-thread panel may
  request a redacted durable projection only; it may not start, approve,
  reject, resume, or otherwise alter the workflow.

## Verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e-selected` for selected-thread changes and `make test-e2e`
   when broader workflow UI behavior changes.
