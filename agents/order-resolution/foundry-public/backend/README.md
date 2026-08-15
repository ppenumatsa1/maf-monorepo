# Backend - Shared MAF Order Resolution

The local FastAPI host and public Foundry hosted agent invoke the same MAF
business workflow. FastAPI owns the stable API/SSE/UI contract; Foundry uses the
Responses protocol through `foundry/main.py` and `Dockerfile.hosted`.

## Local runtime

```bash
make up
```

Use `STORE_PROVIDER=postgres` for the workflow audit ledger. If Foundry model settings are absent, triage uses
the deterministic summary fallback without bypassing MAF orchestration.
`backend/.env` defaults to `RUNTIME_TARGET=local_maf`. To test the wrapper
locally, explicitly set `RUNTIME_TARGET=responses_wrapper` and the current
`FOUNDRY_RESPONSES_ENDPOINT`; the hosted agent package never copies this local
file.

## Public Foundry runtime

Deploy from the repository root with the authenticated release command:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE=../deployment/profiles/foundry-public.env
make foundry-bootstrap
make foundry-release
```

`infra/foundry-hosted/azure.yaml` deploys a generated `agent/` package that is
refreshed from canonical `backend/` source before every deployment.
The public hosted project uses Microsoft-managed Foundry agent state; PostgreSQL
continues to own the workflow, checkpoint, approval, and audit records.
The default release route is `app_only`: it reuses the selected portable target
and its existing database
and does not automatically provision infrastructure. It validates and deploys
the application legs by immutable digest, securely converges the
`orderresolutionruntimesecrets` project connection, converges the hosted
identity's account-scoped runtime role, verifies exact live state, then runs
hosted smoke/E2E, Foundry evaluation, Application Insights validation, and
aggregate secret-free evidence. The hosted definition and GET metadata contain
only the connection placeholder, never the resolved PostgreSQL URL.
Infrastructure reconciliation is a separate
`make foundry-provision` operation. Bootstrap mode creates the complete lane;
hydration then switches the selected environment to non-mutating reuse mode.
PostgreSQL schema, runtime credential, and readiness steps are explicit and
credentials remain local to the AZD environment. Production runtimes set
`DB_SCHEMA_MANAGED_EXTERNALLY=true`, so startup never attempts DDL with the
least-privilege runtime credential.

The hosted browser path is external frontend Container App -> same-origin
`/api` proxy -> internal FastAPI wrapper -> managed-identity Foundry Responses.
The wrapper creates and persists a Foundry `conv_...` ID before first dispatch,
then uses that ID for the initial turn and checkpoint-keyed HITL resume. It does
not expose Foundry credentials or a direct Foundry endpoint to the browser.
Because the hosted agent is a separate process, wrapper SSE tails persisted
PostgreSQL workflow events. The initial Responses request is non-streaming; the
UI polls the selected run until its durable projection is available.

## Contracts

- API routes and SSE: `app/api/v1/routers/*`
- API schemas: `app/api/v1/schemas/*`
- application service and domain seams: `app/modules/order_resolution/*`
- MAF runtime: `app/maf/*`
- persistence/adapters: `app/infrastructure/*`

Stable event types are `workflow.stage`, `tool.call`, `checkpoint.created`,
`hitl.request`, `hitl.response`, and `workflow.output`. The rich stream is
additive. It preserves the existing native-event envelope and is not the
redacted selected-thread assistant contract.

## Native AG-UI and CopilotKit

`GET /api/chat/stream/{thread_id}/ag-ui` is an additive native AG-UI SSE
projection of one existing workflow thread. `GET /api/copilotkit/info` (and
the `GET /api/copilotkit` alias) returns static CopilotKit discovery metadata
without reading workflow or user data. `POST /api/copilotkit` accepts an
AG-UI/CopilotKit-shaped request solely to select the existing `threadId` and
returns the same read-only projection. Both selected-thread surfaces replay and
tail persisted workflow events, so they work when the wrapper and hosted
workflow run in separate processes.

The bridge neither starts a workflow nor uses supplied `runId`, `messages`,
`state`, `tools`, `context`, or `forwardedProps` values. Its projection is
allowlisted and redacted: it emits lifecycle state, safe step/tool labels,
validated checkpoint IDs and approval decisions, and generic terminal/error
text only. Native payloads, policy and order data, MCP/RAG results, tool
arguments/results, checkpoint state, credentials, and prompts are never
included.

Use the selected-thread routes, not `/api/chat/stream/{thread_id}/rich`, for
any assistant integration. The rich route is an existing native-event
envelope; it is additive to stable SSE but does not supply the selected-thread
redaction guarantee.

HITL pauses when amount/risk is at least `100`, an item is damaged, or policy
requires manual review. `ORD-1001` is low risk; `ORD-1009` requires approval.

## Evaluation and telemetry

- `make eval-backend` runs deterministic contract evaluation.
- `make eval-foundry` judges conversations in hosted E2E evidence only after
  their configured minimum trace age (`90` seconds by default). The evidence
  must contain the fresh ORD-1001 low-risk, ORD-1009 approval/resume, and
  damaged-item approval/resume conversation IDs from one release window.
- The target obtains `FOUNDRY_PROJECTS_ENDPOINT`,
  `FOUNDRY_MODEL_DEPLOYMENT_NAME`, and (when configured) `FOUNDRY_EVAL_MODEL`
  from the selected `infra/foundry-hosted` AZD environment without sourcing or
  displaying its `.env` file. Use `make eval-foundry-config` for a no-evaluation
  configuration check, or set `FOUNDRY_AZD_ENV_NAME` for a one-command,
  non-mutating environment selection.
- `APPLICATIONINSIGHTS_CONNECTION_STRING` enables Azure Monitor export.
- `OTEL_RECORD_CONTENT=false` is the default privacy posture.
- FastAPI health (`/health`, `/api/health`) and chat SSE request spans are
  excluded from request telemetry in the public lane. Foundry readiness,
  invocation, workflow, model, and HITL telemetry remains enabled.

## Container dependency feed

`Dockerfile` and `Dockerfile.hosted` set
`PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`. This is the
approved CFS package feed for release-image Python dependencies; do not replace
or supplement it with an unapproved index.
