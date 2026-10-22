# Technical Specification - Azure-Hosted Order Resolution

> Related: [functional specification](functional-spec.md),
> [business rules](business-rules.md), [architecture](architecture.md), and
> [project structure](projectstructure.md).

## 1. Technology choices

| Area | Choice |
| --- | --- |
| Application host | FastAPI + Uvicorn |
| Contracts | Pydantic v2 |
| Agent orchestration | Microsoft Agent Framework sequential workflow |
| Persistence | Azure Database for PostgreSQL Flexible Server + Psycopg |
| Azure database auth | Backend managed identity |
| Retrieval | Local/provider seam plus optional MCP integration |
| Frontend | React + TypeScript + Vite + Nginx |
| Selected-thread UI | Redacted AG-UI projection + CopilotKit React core |
| Hosting | Two Azure Container Apps |
| Observability | Azure Monitor OpenTelemetry + Application Insights |
| Model/evaluation | Optional Foundry model inference + report-only evaluation |
| IaC/automation | Bicep, Azure Developer CLI, Make, GitHub Actions |
| Quality | pytest, Ruff, Playwright, deterministic evals, report-only Foundry evals |

Pinned versions remain authoritative in the package manifests.

## 2. Runtime mode

FastAPI always executes the shared MAF workflow in process. When Foundry model
configuration is absent, deterministic triage remains inside that workflow; it
does not select another orchestrator.

Supported production providers use PostgreSQL for workflow and conversation
state. Foundry is not an application runtime in this lane.

## 3. Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| React frontend | Workflow composer, history, timeline, HITL UI, selected-thread views | Database or Foundry credentials; direct backend endpoint exposure |
| Nginx frontend | Public ingress and same-origin `/api` proxy | Workflow execution |
| FastAPI backend | HTTP contracts, MAF execution, durable read models, SSE, HITL response | A hosted-agent or Responses proxy runtime |
| Shared MAF workflow | Triage, retrieval, decision, checkpoint creation, resume, idempotent completion | Browser rendering or deployment state |
| PostgreSQL adapters | Runs, events, messages, checkpoints, approvals, idempotency, evaluation records | Business policy decisions |
| Release scripts and IaC | Bootstrap, steady state, app release, validation, and evidence | Product decisions |

## 4. HTTP API

| Method and path | Contract |
| --- | --- |
| `POST /api/chat/run` | Start a workflow. |
| `GET /api/chat/stream/{thread_id}` | Stable native SSE. |
| `GET /api/chat/stream/{thread_id}/rich` | Additive native-rich envelope; not assistant input. |
| `GET /api/chat/stream/{thread_id}/ag-ui` | Read-only selected-thread projection. |
| `POST /api/hitl/respond` | Resolve one checkpoint with `approve` or `reject`. |
| `GET /api/workflows` | Paginated workflow history. |
| `GET /api/workflows/{thread_id}` | Run, events, approvals, output, and metadata. |
| `GET /api/workflows/{thread_id}/events` | Cursor-paginated durable events. |
| `GET /api/sessions/{session_id}/messages` | Cursor-paginated transcript. |
| `GET /api/copilotkit[/info]` | Static selected-thread discovery. |
| `POST /api/copilotkit` | Read-only existing-thread bridge. |
| `GET /health`, `GET /api/health` | Runtime/provider health fingerprint. |

## 5. Workflow algorithm

1. Persist the user message.
2. Run the MAF triage participant or its in-workflow deterministic summary.
3. Retrieve order, policy, RAG, and optional MCP evidence.
4. Emit `tool.call` metadata.
5. Select the deterministic action and apply the HITL rule.
6. For low risk, submit once and emit terminal output.
7. For high risk, persist checkpoint and approval before emitting
   `checkpoint.created` and `hitl.request`.
8. On approve, atomically resolve the checkpoint, emit `hitl.response`, and
   submit once.
9. On reject, resolve the checkpoint and emit an `escalated` terminal output.

Exact rules are in [business-rules.md](business-rules.md).

## 6. Persistence model

| Data | Purpose |
| --- | --- |
| Workflow runs | Status, stage, timing, and latest output |
| Workflow events | Ordered durable native timeline |
| Conversation messages | User/assistant transcript |
| Checkpoints | Durable pause state and trace context |
| Approvals | Pending/resolved HITL audit |
| Idempotency keys | One-time resolution submission |
| Sessions and memory | Conversation association |
| Retrieval and evaluation records | Evidence and quality audit |

Schema authority is `backend/app/sql/schema.sql`.

## 7. Network and identity

1. Browser -> external frontend Container App over HTTPS.
2. Frontend Nginx -> internal FastAPI Container App through same-origin `/api`.
3. FastAPI -> Azure PostgreSQL using managed identity.
4. FastAPI -> optional Foundry model deployment using managed identity.
5. Runtime telemetry -> Application Insights.

The browser receives no backend, database, or Foundry credential. Target
selectors and generated endpoints come from an ignored operator profile and
the selected AZD environment, not tracked documentation.

## 8. Observability and evaluation

- Content recording is disabled by default.
- Business spans cover workflow execution, stages, HITL wait/resume, database
  dependencies, model calls, and resolution submission.
- Release telemetry validates the exact thread/workflow pairs produced by the
  release scenarios.
- Deterministic evaluation checks local contracts.
- Foundry evaluation judges captured HTTP results only. It cannot invoke,
  resume, approve, reject, or otherwise mutate a workflow.
- Every configured evaluator must report zero failed and zero errored rows.

## 9. Deployment and release

- **Fresh bootstrap** creates a new profile-selected platform and establishes
  managed-identity PostgreSQL access.
- **Steady state** retains PostgreSQL and limits infrastructure reconciliation
  to an explicit, reviewed operation.
- **App-only release** updates the backend and frontend revisions, then runs
  verification, smoke, browser/domain E2E, telemetry, report-only evaluation,
  and final evidence.
- The backend remains internal and the frontend remains external.
- Generated evidence is stored under
  `.artifacts/releases/<release-id>/`; logs remain in the sibling `logs/`
  directory.

## 10. Known risks and deferred work

1. Add production authentication, authorization, and trusted reviewer identity.
2. Replace synthetic order mapping with a real order service.
3. Keep optional provider seams fail-closed until implemented and tested.
4. Treat infrastructure drift separately from application release.
