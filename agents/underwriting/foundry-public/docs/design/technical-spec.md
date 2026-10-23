# Technical Specification - Underwriting Foundry Public

> Status: portable implementation contract. Dependency manifests and source
> are authoritative for package versions. The
> [delivery ledger](issues-changes-fixes.md) is authoritative for dated
> deployment and acceptance evidence.
>
> Related: [functional specification](functional-spec.md),
> [business rules](business-rules.md),
> [architecture](architecture.md), and
> [schema, I/O, and telemetry](schema-io-telemetry.md).

## 1. System boundary

The system contains one underwriting workflow and three delivery surfaces:

1. Local CLI/full-stack execution for isolated validation.
2. Public web delivery through an external React/Nginx frontend and internal
   FastAPI adapter.
3. Microsoft Foundry hosted execution through Responses and, for Teams,
   Activity in the same hosted process.

The hosted entrypoint owns production workflow execution. The internal API
relays start/resume operations and serves PostgreSQL-backed projections; it
does not construct a second production orchestration path.

## 2. Technology and runtime surfaces

| Area | Contract |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy/Psycopg |
| Orchestration | Microsoft Agent Framework master workflow with direct executors |
| Hosted protocols | Foundry Responses; additive Activity for Teams in the same process |
| Persistence | PostgreSQL for checkpoints and application/audit projections |
| Frontend | React, TypeScript, Vite, Nginx same-origin proxy |
| Interactive projection | AG-UI plus a selected-run CopilotKit assistant |
| Azure hosting | Container Apps, Foundry hosted agent, Azure Database for PostgreSQL, Application Insights |
| Delivery | Bicep, Azure Developer CLI, Make, protected OIDC workflows, and local authenticated operator equivalents |
| Validation | pytest, Ruff, frontend build/lint, Playwright, hosted smoke/E2E, Foundry evaluation, telemetry verification |

Use `pyproject.toml`, `backend/requirements*.txt`,
`backend/requirements*.lock`, and `frontend/package.json` for exact package
requirements. Do not copy package versions into release records unless needed
to explain a dated change.

## 3. Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| React/Nginx frontend | Operator console, same-origin proxy, durable-run views, safe assistant UI | Foundry/database credentials or direct workflow execution |
| FastAPI adapter | HTTP contracts, hosted relay, durable reads, AG-UI, CopilotKit | A shadow production workflow |
| Shared MAF workflow | Fan-out/fan-in, scoring, checkpoint pause/resume, deterministic recommendation | Browser rendering, publication state, or Azure resource mutation |
| Foundry hosted entrypoint | Responses/Activity parsing, workflow composition, hosted correlation | Durable audit authority outside PostgreSQL |
| PostgreSQL adapters | Runs, state, events, results, checkpoints, approvals, action tokens, idempotency | Score policy |
| Release automation | Profiles, IaC, images, hosted versions, verification, evidence | Product decision semantics |

## 4. HTTP and hosted protocol contract

Current web routes include:

- `POST /api/v1/underwriting/runs`
- `POST /api/v1/underwriting/runs/{run_id}/resume`
- `GET /api/v1/underwriting/runs`
- `GET /api/v1/underwriting/runs/{run_id}`
- `GET /api/v1/underwriting/runs/{run_id}/state`
- `GET /api/v1/underwriting/runs/{run_id}/events`
- `GET /api/v1/underwriting/runs/{run_id}/checkpoints`
- `POST /api/v1/underwriting/ag-ui`
- CopilotKit discovery and selected-run assistant routes under
  `/api/v1/underwriting/copilotkit`

Responses requests carry application data in the request body, never in
metadata. Metadata is limited to safe correlation values. Hosted web and
Responses review mutation is disabled; identity-looking caller headers and
structured or free-form decision input cannot resolve a production checkpoint.
The explicit administrative path is limited to non-hosted local execution,
uses a server-configured actor, and writes administrative audit metadata.

Teams messages enter the Activity handler in the same hosted process. A pending
referral emits a privacy-safe Adaptive Card whose action value is an opaque
token. The token is validated and atomically claimed before the workflow
resumes.

## 5. Workflow and state contract

1. Validate the synthetic application and create the durable run.
2. `init_context` stores required shared state.
3. Fan out risk, credit, medical, and driving requests.
4. Each direct executor emits one idempotent `CheckResult`.
5. `fan_in_aggregator` merges results and emits completion only after all four.
6. `final_decision` computes the deterministic machine recommendation.
7. For a terminal recommendation, persist the result and complete.
8. For `REFER_TO_HUMAN_UNDERWRITER`, persist the immutable recommendation,
   checkpoint, and pending approval, then pause.
9. In production, resume only after a bound Teams card decision; local
   administrative resume is non-hosted and separately audited.
10. Persist reviewer outcome separately and complete without rewriting the
    machine recommendation.

MAF checkpoint state contains executor state, pending messages/requests, and
shared workflow state. Application tables contain queryable run, event,
recommendation, approval, and action-token projections. Neither replaces the
other.

## 6. Persistence contract

| Surface | Purpose |
| --- | --- |
| `workflow_runs` | Run lifecycle, trusted origin, immutable machine recommendation |
| `business_state` | Incremental queryable state |
| `workflow_events` | Append-only operator and telemetry timeline |
| `underwriting_results` | Check outputs and terminal workflow results |
| `maf_checkpoints` | Serialized MAF recovery state |
| `underwriting_approvals` | Pending/completed review and separate reviewer outcome |
| `teams_card_actions` | Hashed, expiring, bound, atomically claimed card actions |
| `idempotency_records` | Replay protection for side effects |

Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`. Runtime startup validates
schema parity but does not create or alter production tables or indexes.
Administrator migration and least-privilege grants must land before a hosted
version that depends on new review tables is activated.

## 7. Teams action lifecycle

1. Generate one random token per `APPROVED`/`DECLINED` action.
2. Store only the token hash with a common action-batch ID and its bindings.
3. Render only the opaque plaintext token into the card action payload.
4. On invoke, validate pending state, expiry, reviewer, conversation,
   checkpoint, requested decision, and Teams origin.
5. Atomically move the selected token to processing and its sibling to
   superseded.
6. Resume the exact workflow checkpoint.
7. Mark the action and approval completed after successful persistence.
8. On a safe retryable failure, release only if the approval is still pending;
   otherwise keep the action consumed.

## 8. Network and identity

1. Browser -> external frontend Container App over HTTPS.
2. Frontend Nginx -> internal FastAPI Container App.
3. FastAPI managed identity -> public Foundry Responses endpoint.
4. Hosted workflow and FastAPI -> PostgreSQL over the configured TLS/public
   firewall posture.
5. Teams -> Azure Bot Service and `MsTeamsChannel` -> Foundry Activity route.
6. Runtime and hosted telemetry -> Application Insights.

The public lane does not require a VNet-connected runner, private endpoint,
private DNS, NAT, or Bastion. The Activity route is additive and must preserve
Responses and Entra authorization while adding `BotServiceRbac`.

## 9. Release contract

- Select an external non-secret runtime profile and verify Azure CLI/AZD
  context before any mutation.
- Use reviewed bootstrap preview for a new environment.
- Use app-only release for normal source changes; do not reconcile shared
  infrastructure during routine deployment.
- Build immutable artifacts, activate the hosted version, then deploy the
  internal backend and external frontend.
- Run smoke, recovery/referral E2E, strict evaluation, telemetry correlation,
  topology verification, Teams acceptance when in scope, and evidence
  aggregation.
- Preserve prior hosted versions and image digests for rollback.
- Record exact release IDs, versions, counts, timings, target identifiers, and
  rollback results only in the ledger and deployment plan.

## 10. Known reconciliation points

Documentation describes the confirmed HITL/Teams contract. Before claiming
implementation or deployment parity, verify that source, administrator schema,
least-privilege grants, Activity/Bot/Teams automation, Make targets, CI checks,
and acceptance harnesses all implement this contract and that fresh evidence
is recorded.
