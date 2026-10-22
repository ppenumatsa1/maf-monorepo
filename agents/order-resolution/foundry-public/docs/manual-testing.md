# Manual Testing Guide

## Local full-stack workflow

```bash
make up
```

Open `http://localhost:5173`, submit a case, and verify the local FastAPI/SSE
timeline. Every run should include the expected `workflow.stage`, `tool.call`,
and terminal `workflow.output` events.

| Scenario | Prompt | Expected result |
| --- | --- | --- |
| Low risk | `Order ORD-1001 arrived late by 1 day.` | `completed`; no `hitl.request` |
| High value | `Order ORD-1009 is delayed by 5 days.` | `waiting_approval`, then `completed` after approval |
| Damaged reject | `Order ORD-1001 arrived damaged and broken.` | `waiting_approval`, then `escalated` after rejection |

For a broader local matrix:

```bash
make manual-matrix
```

Verify history through `GET /api/workflows/{thread_id}` and
`GET /api/workflows/{thread_id}/events`. The persisted tables are
`workflow_runs`, `workflow_events`, `conversation_messages`, `checkpoints`, and
`approvals`.

## Optional selected-thread projections

After selecting an existing workflow thread in the UI:

1. Connect **AG-UI Selected Thread**. It uses
   `GET /api/chat/stream/{thread_id}/ag-ui` and must show only generic
   lifecycle, approval, and terminal-status frames.
2. Load **Selected Thread Assistant**. The CopilotKit bridge posts only the
   selected thread ID to `POST /api/copilotkit` and returns the same redacted,
   read-only durable-event view.
3. Confirm neither surface can start a run or approve/reject a request, and
   neither shows order/customer details, policy or retrieval evidence, MCP/RAG
   content, prompts, raw model output, checkpoint state, credentials, or
   secrets.
4. Make the optional AG-UI endpoint unavailable (or use a test stub returning
   `404`) and confirm that the selected-thread controls and native SSE timeline
   still work.

The AG-UI and CopilotKit panels are optional views, not a replacement for
native SSE or durable workflow history. CopilotKit means
`@copilotkit/react-core` here, not the GitHub Copilot SDK.

## Public Foundry hosted workflow and browser

The hosted agent uses the Responses protocol rather than the FastAPI/SSE UI.
Run the authenticated release sequence:

```bash
make foundry-release
```

It covers ORD-1001, ORD-1009 approval, damaged-item approval/resume, and
duplicate HITL response behavior. Conversation evidence is written to
`backend/.foundry/results/hosted-e2e-evidence.json`.

Historical release entries remain in
[issues-changes-fixes.md](design/issues-changes-fixes.md). They do not validate
the current parity source. Run the complete live gate chain again after the
reviewed infrastructure/app deployment.

Verify the configured deployed frontend uses the same-origin API proxy and
validates the complete UI contract with:

```bash
PLAYWRIGHT_BASE_URL="<public-frontend-url>" \
make test-e2e
```

The backend Container App is internal-only. Do not configure a browser to call
the Foundry Responses endpoint or backend FQDN directly. Before invoking an
authenticated release, follow the existing-resource, app-only safety checks in
[deployment-plan.md](../.azure/deployment-plan.md); do not infer a current
endpoint from repository configuration alone.

For Teams, credential-free tests can validate endpoint merge behavior,
publication/package structure, Bot/Teams Bicep shape, Adaptive Card
approve/reject, wrong-user/conversation, replay, resolved-card replacement,
and atomic competing claims. Live testing additionally requires the reviewed
Bot deployment, Activity reconciliation, Shared publication, authorized and
unauthorized invocations, diagnostics, and rollback review. Do not record
tenant, user, subscription, resource, endpoint, token, or customer identifiers
in tracked documentation.
