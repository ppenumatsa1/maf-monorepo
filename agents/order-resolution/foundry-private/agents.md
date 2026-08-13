# Agents Guide

This file describes expected behavior for coding agents working in this repository.

## Project Context

- Backend: FastAPI + MAF SDK workflow path (single primary workflow story).
- Foundry hosted entrypoint: `backend/foundry/main.py` (Responses protocol in the ACR-built `backend/Dockerfile.hosted` image).
- Current hosted gate posture is private-lane-first; use private Foundry for hosted validation/deployment unless the canonical operating model is explicitly revised.
- Frontend: React + Vite, consumes stable native SSE workflow events. The
  approved selected-thread AG-UI/CopilotKit surface is optional and read-only;
  its frontend implementation and focused modern frontend gates are complete
  and locally validated. Protected deployment, hosted E2E, Foundry evaluation,
  and telemetry evidence are recorded in
  `docs/design/issues-changes-fixes.md`.
- CopilotKit means `@copilotkit/react-core`, not the GitHub Copilot SDK.
  `GET /api/copilotkit/info` (or `GET /api/copilotkit`) is static discovery.
  `POST /api/copilotkit` selects one existing `threadId` and ignores compatible
  `runId`, `messages`, `state`, `tools`, `context`, and `forwardedProps`
  values.
- Private browser delivery: external frontend ACA proxies same-origin `/api` to
  internal FastAPI ACA; the backend reaches private Foundry Responses and
  PostgreSQL through the VNet. Do not expose a backend ingress or browser
  credentials, and do not reuse the Foundry agent-host subnet for ACA.
- PostgreSQL public access and the Azure-services firewall rule remain in place
  until the canonical server's private endpoint/DNS path has explicit ACA and
  hosted-agent connectivity proof. `POSTGRES_SERVER_NAME` and
  `RUNTIME_DATABASE_URL` must identify that same FQDN; only the generated,
  current connectivity-proof artifact can authorize lockdown.
- Private provision, reconciliation, app-release, and observability workflows
  share one serialized release group on `foundry-private-v2`. Classify the
  operation before dispatch: a routine app-only release changes only existing
  ACA revisions and the existing hosted agent, and validates existing
  dependencies; it must not invoke full Bicep or change PostgreSQL access.
  Bootstrap/reconciliation is a separately approved full-Bicep operation.
  PostgreSQL lockdown is a separate explicitly confirmed, proof-gated
  operation, never an app-only release side effect. Do not add optional
  agent-refresh, administrator-password, public-access, or firewall bypasses.
- Preview run `31198356080` found shared authoritative drift in the VNet and
  subnets, ACA environment, Foundry account/project/models, ACR, Cosmos,
  Application Insights, and Search. Do not apply or normalize that drift during
  a routine application release and do not claim deployment success from the
  preview. Full Bicep remains blocked pending reviewed, explicit reconciliation
  approval.
- Core provisioning stages Foundry connections until the project managed
  identity and service RBAC exist. The later private deploy stage enables those
  connections; identity propagation and private-endpoint deletion failures
  require a retry after Azure completes, never a security workaround.
- Workflow checkpointing: Postgres-backed checkpoint storage via repository-pattern adapters.
- Event streaming: native SSE remains the stable contract; rich events and the
  approved selected-thread AG-UI projection are additive and do not replace it.
  The selected-thread projection must allowlist only generic lifecycle/tool
  labels, validated checkpoint IDs and approval decisions, and generic
  terminal/error text. It must never expose order/customer or policy data,
  MCP/RAG content, tool arguments/results, prompts, model output, checkpoint
  payloads, reviewer comments, credentials, or secrets.
- Backend package boundaries:
  - `backend/app/api/v1/routers/*` owns HTTP/SSE routes.
  - `backend/app/api/v1/schemas/*` owns API contracts.
  - `backend/app/modules/order_resolution/*` owns the application service, internal workflow models, ports, and event projection.
  - `backend/app/core/*` owns config, database, telemetry, and composition.
  - `backend/app/infrastructure/*` is the repository-pattern/adapters namespace.
  - `backend/app/maf/*` owns the MAF runtime namespace.
  - Keep MAF internals modular: `prompts/`, `agents/`, `tools/`, `executors/`,
    `runner.py`, and `workflows/` should remain separate concerns.

## Agent Change Policy

1. Keep changes minimal and focused on user request.
2. Use one MAF-based workflow path; do not introduce or retain deterministic fallback orchestration. The deterministic triage fallback is permitted only when Foundry Models env vars are absent and must not bypass MAF execution.
3. If API/event contracts intentionally change, update frontend, tests, and docs in the same change set.
4. If HITL logic changes, update docs and tests in the same change set.
5. Follow sample-derived implementation guardrails:

- intermediate executors use `ctx.send_message(...)`
- terminal executors use `ctx.yield_output(...)`
- approval flow uses explicit request/response handling keyed by request id
- retries are allowed only for read/model operations; side-effecting writes must be idempotent
- per-agent kwargs/config must remain scoped to that agent
- executor invocation/completion/output signals must stay observable and correlated
- MAF telemetry should observe streamed `executor_invoked`, `executor_completed`, and `output` events
- MAF middleware should centralize cross-cutting runtime behavior such as correlation, redaction/enrichment, usage/event observation, and explicit failure events
- HITL telemetry must preserve checkpoint trace context so approval/resume spans stay correlated with the original workflow operation
- additive rich event streams must preserve the native event payload and must not replace or rename stable SSE event types
- an AG-UI or CopilotKit failure must leave native SSE, durable history, and
  checkpoint-keyed HITL controls usable
- selected-thread requests are read-only: they cannot start, resume, approve,
  reject, or otherwise mutate a workflow

6. Never remove coverage for:

- low-risk no-HITL flow
- high-risk HITL flow and resume flow

## Required Verification Before Completing Work

Run and report:

- `make test`
- `make eval-backend`
- `make eval-foundry` (report-only by default; the private release workflow
  enforces judgement over the current hosted E2E conversation traces)
- `make test-e2e`
- `./scripts/skills/design-review-skill.sh` (consolidated deterministic review/test gate)

If a suite cannot run because of missing runtime dependencies (for example browser binaries), report the blocker and the exact command needed to unblock.

## Repository Skills

Use focused skills instead of one broad agent pass:

- `design-review`: final deterministic local review/test gate.
- `docs-sync`: update affected docs after code, IaC, script, or behavior changes.
- `backend-boundary-review`: check API/application/core/infrastructure/MAF separation and shim import safety.
- `local-validation`: run local unit/integration/e2e gates.
- `quick-validation`: run fast validation for app-only redeployments.
- `iac-review`: review Azure/Foundry IaC and deployment assets without deploying.
- `azure-validation`: validate Azure readiness or live endpoints without deployment.
- `azure-deployment`: deploy only after Azure validation has passed.
- `azure-telemetry-validation`: run hosted workflow stimulus and KQL checks against Application Insights after deployment.
- `release-readiness`: orchestrate relevant focused skills for PR/release handoff.

Use `scripts/skills/deployment-mode-router.sh` to route quick-vs-full validation and app-only-vs-full deployment for release work.

## Stack Implementation Skills

Load only the relevant implementation skill for the task; these complement rather than replace the
repository workflow skills above. The baseline includes seven vendored Microsoft skills and
repository-owned workflow/frontend-boundary skills:

- `agent-framework-foundry-py`: this service's `agent-framework-foundry` integration,
  `FoundryChatClient`, `SequentialBuilder`, middleware, resumable workflows, and
  checkpoint-backed HITL request/response flows.
- `azure-ai-projects-py`: Foundry projects, deployments, and evaluations.
- `azure-identity-py`: Entra authentication and managed identity.
- `azure-monitor-opentelemetry-py`: Application Insights and Azure Monitor telemetry.
- `azure-monitor-query-py`: read-only Azure Monitor Logs queries, including the
  `LogsQueryClient` telemetry correlation in `backend/evals/verify_telemetry.py`.
- `microsoft-foundry`: hosted-agent, evaluation, and Foundry observability guidance.
- `fastapi-router-py`: FastAPI HTTP routes.
- `pydantic-models-py`: Pydantic v2 schemas.
- `postgres-psycopg-py`: PostgreSQL, Psycopg, pgvector, and Azure PostgreSQL persistence.
- `ag-ui-streaming-fastapi-py`: additive, redacted AG-UI and CopilotKit
  projections of durable workflow events in the private wrapper topology.
- `ag-ui-react-integration-ts`: React selected-thread UI, additive AG-UI
  consumption, and safe CopilotKit context.
- `typescript-setup`: strict TypeScript boundaries for new frontend surfaces.
- `typescript-update`: strict TypeScript and React updates that preserve
  workflow contracts.
- `e2e-rubric`: operator coverage for native SSE, durable HITL, optional
  AG-UI, CopilotKit safety, and private wrapper boundaries.

`microsoft-foundry` and `azure-monitor-query-py` were selectively vendored
(not as a full catalog install) from `microsoft/skills` revision
`e58528db9a006528a5fb0a2c029790fa6a9a7c0e`; see
`docs/design/techstack.md` for their exact upstream paths.

Legacy shim paths have been removed. Do not add code that imports or recreates `app/models.py`, `app/config.py`, `app/db.py`, `app/state.py`, `app/workflow_run_repository.py`, `app/rag_repository.py`, `workflows/*`, `tools/*`, or root `app/api/*` router shims.
Also do not reintroduce removed Foundry adapter/proxy surfaces such as `/api/foundry*` or `backend/app/foundry/*`.

## HITL Testing Baseline

Use these baseline scenarios:

- `ORD-1009` delayed -> expect `hitl.request`
- `ORD-1001` late delivery -> expect no `hitl.request`
- damaged item message -> expect `hitl.request`

Reference details:

- `docs/design/hitl-approval-conditions.md`

## Documentation Update Contract

When architecture or execution policies change, update these instruction files in the same PR:

- `.github/copilot-instructions.md`
- `agents.md`
- `docs/design/engineering-operating-model.md`

The selected-thread implementation includes strict type checking, frontend
build/lint, focused Playwright coverage, and the retained `make test-e2e`
suite. Recorded local evidence is 128 passing tests, a 10/10 deterministic
evaluation, seven workflow E2E cases, four selected-thread E2E cases, and a
passing design review. The protected release evidence is recorded in
`docs/design/issues-changes-fixes.md`; do not infer future release results
from local evidence alone.
