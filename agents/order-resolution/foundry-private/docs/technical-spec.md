# Technical Specification - Private Order Resolution Agent

> Status: Implemented and release-verified for the private web, Shared Teams
> runtime, secure Adaptive Card approval/rejection, and modernized frontend.
> Related: [functional specification](functional-spec.md),
> [business rules](business-rules.md),
> [architecture](architecture.md), and
> [project structure](projectstructure.md).

## 1. Technology choices

| Area | Choice |
| --- | --- |
| Runtime language | Python 3.13 backend and hosted-agent images |
| API | FastAPI 0.156.3 + Uvicorn 0.54.0 |
| Contracts | Pydantic 2.14.1 |
| Agent orchestration | Microsoft Agent Framework sequential workflow |
| Hosted protocol | Microsoft Foundry dual Responses and Activity hosted agent |
| Foundry SDK/auth | `azure-ai-projects`, `azure-identity`, managed identity |
| Persistence | Azure Database for PostgreSQL Flexible Server, Psycopg 3 |
| Retrieval | PostgreSQL/pgvector-compatible provider; MCP knowledge adapter |
| Frontend | React 19.3, TypeScript 7 typechecker, Vite 8.3 |
| Optional selected-thread UI | AG-UI projection + `@copilotkit/react-core` 1.79 + Zod 4 |
| Hosting | Azure Container Apps + private Foundry hosted agent |
| Images | Private Azure Container Registry |
| Observability | Azure Monitor OpenTelemetry + Application Insights |
| IaC/automation | Bicep, Azure Developer CLI, Make, GitHub Actions |
| Quality | pytest, Ruff, Playwright, deterministic evals, Foundry trace evals |

Pinned package versions are authoritative in `backend/requirements.txt` and
`frontend/package.json`.

## 2. Runtime modes

| Setting | Behavior |
| --- | --- |
| `RUNTIME_TARGET=local_maf` | FastAPI creates the workflow run and invokes the shared MAF workflow in process. |
| `RUNTIME_TARGET=responses_wrapper` | FastAPI records a dispatch, invokes private Foundry Responses with managed identity, and serves PostgreSQL-backed history/SSE. |

Supported provider values are declared in `backend/app/core/config.py`.
Production/private parity currently uses:

```text
WORKFLOW_MODE=maf_sdk
STORE_PROVIDER=postgres
RAG_PROVIDER=pgvector
MEMORY_PROVIDER=postgres
```

Alternative Search/Foundry retrieval and memory values exist as extension
seams; some remain placeholders and are not release-supported.

## 3. Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| React frontend | Workflow composer, history, timeline, output, RAG evidence, metadata, HITL UI, optional selected-thread views | Foundry/database credentials or direct private endpoints |
| FastAPI wrapper | HTTP contracts, dispatch idempotency, private Responses client, durable read models, SSE, HITL forwarding | A separate hosted-only business workflow |
| Shared MAF workflow | Triage, retrieval, deterministic decision, checkpoint creation, approval resume, idempotent completion | Browser rendering or deployment state |
| Foundry hosted entrypoint | Responses parsing, conversation identity, same workflow composition, hosted tracing | Durable application audit authority |
| PostgreSQL adapters | Runs, events, messages, checkpoints, approvals, idempotency, RAG, eval records | Business policy decisions |
| Deployment scripts/IaC | Private topology, runtime secrets, images, hosted versions, release evidence, Bot/Teams resources | Product decisions |

## 4. HTTP API

| Method and path | Contract |
| --- | --- |
| `POST /api/chat/run` | Start/delegate a run. Request: message, optional thread/session/idempotency key, demo customer ID. Response: accepted run/thread IDs. |
| `GET /api/chat/stream/{thread_id}` | Stable native SSE from the live/durable event source. |
| `GET /api/chat/stream/{thread_id}/rich` | Additive rich envelope; not the redacted assistant contract. |
| `GET /api/chat/stream/{thread_id}/ag-ui` | Read-only selected-thread AG-UI projection. |
| `POST /api/hitl/respond` | Resolve one checkpoint with `approve` or `reject`. |
| `GET /api/workflows` | Paginated workflow history. |
| `GET /api/workflows/{thread_id}` | Run, events, pending approvals, latest output, metadata. |
| `GET /api/workflows/{thread_id}/events` | Cursor-paginated events. |
| `GET /api/sessions/{session_id}/messages` | Cursor-paginated transcript. |
| `GET /api/copilotkit[/info]` | Static selected-thread discovery. |
| `POST /api/copilotkit` | Read-only selected-thread bridge. |
| `GET /health`, `GET /api/health` | Runtime/provider health fingerprint. |

The current API has permissive CORS and no application authentication
dependency. See [BR-18](business-rules.md#current-security-limitation).

## 5. Workflow algorithm

1. Persist the user message.
2. Run the MAF sequential triage participant or deterministic fallback.
3. Retrieve order status, policy, RAG evidence, and MCP knowledge.
4. Emit `tool.call` with execution metadata.
5. Select the deterministic action and apply the HITL rule.
6. For low risk, submit once and emit terminal output.
7. For high risk, persist checkpoint + approval and emit
   `checkpoint.created` and `hitl.request`.
8. On approve, atomically resolve the checkpoint, emit `hitl.response`, and
   submit once.
9. On reject, atomically resolve the checkpoint and emit an `escalated`
   terminal output.

Exact rules are in [business-rules.md](business-rules.md).

## 6. Hosted Responses and Activity behavior

- A new browser request creates a Foundry conversation before its first
  Responses invocation.
- The Foundry conversation ID becomes the browser-visible thread ID.
- A Responses decision is accepted only as structured `function_call_output`
  using the checkpoint ID as the call ID; free-form text never becomes an
  approval decision.
- The hosted entrypoint resolves only a pending checkpoint in the same
  conversation.
- Each run persists its server-selected origin channel. Responses cannot
  resolve a Teams Activity checkpoint; Teams approval requires its
  user/conversation-bound card token.
- FastAPI accepts the initial request non-streaming, then the UI polls/replays
  PostgreSQL projections and consumes native SSE.
- Managed identity obtains the `https://ai.azure.com/.default` token; no
  Foundry bearer token is sent to the browser.
- Teams messages enter the native Activity handler in the same process.
- Pending Teams approvals emit an Adaptive Card. Each action carries only an
  opaque random token and returns through an `adaptiveCard/action` invoke.
- The selected action is atomically claimed before workflow resume; competing
  Approve/Reject or replay attempts cannot both proceed.
- Typed Teams decisions do not resolve checkpoints.

## 7. Persistence model

| Table | Purpose |
| --- | --- |
| `workflow_runs` | Status, trusted origin channel, input summary, stage, timing, latest output |
| `responses_dispatches` | Request hash/idempotency and Foundry thread resolution |
| `workflow_events` | Ordered durable native timeline |
| `conversation_messages` | User/assistant transcript |
| `checkpoints` | Durable pause state and trace context |
| `approvals` | Pending/resolved HITL audit |
| `teams_card_actions` | Hashed, expiring, atomically claimed Teams card-action batches bound to checkpoint, user, conversation, and decision |
| `idempotency_keys` | One-time resolution submission |
| `sessions`, `memory_items` | Session association and memory records |
| `documents`, `document_chunks` | Policy knowledge |
| `rag_queries`, `rag_retrieval_results` | Retrieval audit |
| `eval_runs`, `eval_results` | Deterministic evaluation records |

Schema authority: `backend/app/sql/schema.sql`.

## 8. Network and identity

1. Browser -> external frontend Container App over HTTPS.
2. Frontend Nginx -> internal FastAPI Container App through same-origin `/api`.
3. FastAPI -> private Foundry Responses with the runner/backend managed
   identity.
4. Hosted workflow and FastAPI -> private PostgreSQL.
5. Container Apps/hosted service -> private ACR and configured Foundry
   dependencies.
6. Runtime/Foundry telemetry -> Application Insights through Azure Monitor
   ingestion. AMPLS/private monitoring ingestion is not implemented.

The Foundry account keeps public network access disabled for normal
Responses/project/data paths. Teams uses a separate scoped Activity exception.

## 9. Teams integration

- Bot Service and `MsTeamsChannel` are Bicep-managed.
- The active agent endpoint preserves Responses/Entra and adds Activity with
  `BotServiceRbac` for Shared publication.
- Microsoft 365 package/catalog operations are controlled data-plane commands,
  not ARM resources.
- Bot/channel, Activity configuration, Shared publication, authentication, and
  normal Teams invocation are deployed and manually verified.
- Adaptive Card approve/reject handling is deployed and accepted, including
  typed-decision blocking, replay rejection, wrong-conversation isolation, and
  card-action creation.

## 10. Observability and evaluation

- `ENABLE_TELEMETRY=true` by default.
- `OTEL_RECORD_CONTENT=false` by default.
- Business spans include `workflow.run`, stage spans,
  `workflow.hitl_waiting`, `workflow.hitl_resume`, and
  `workflow.resolution_submit`.
- Exact-trace evaluation content is opt-in for marked release requests only.
- Deterministic evals use the local JSONL dataset and an 0.8 pass threshold.
- Private cloud evaluation uses `task_completion` and `coherence`.
- Strict release enforcement checks run-level counts and each evaluator's
  passed/failed/errored/skipped counts.

## 11. Deployment and release

- Fresh bootstrap/reconciliation uses Bicep after reviewed preview evidence.
- Routine app-only release changes existing backend/frontend revisions and the
  hosted-agent version only.
- PostgreSQL readiness, image verification, hosted smoke, HITL E2E, telemetry,
  strict evaluation, and final evidence are required gates.
- The runner requires resource-group `Contributor` plus account-scoped
  `Foundry User`.
- Full Bicep remains blocked while recorded shared-resource drift is
  unresolved.

## 12. Known risks and deferred work

1. Add production API authentication/authorization and trusted reviewer
   identity.
2. Replace synthetic order mapping with a real order service.
3. Remove import-time schema/composition side effects in `core/container.py`.
4. Review and reconcile shared Bicep drift separately.
5. Keep optional provider seams fail-closed until their implementations and
   tests are complete.

## 13. Current verification

The active hosted version and the current Responses, Activity, telemetry,
evaluation, database, and release-budget evidence are recorded in the
[review remediation release](issues-changes-fixes.md#review-remediation-release-2026-10-21).
