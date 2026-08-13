# Copilot Instructions

This repository implements a Microsoft Agent Framework (MAF SDK) customer order resolution workflow with HITL checkpoints.

## Primary Goals

- Keep one MAF-based business workflow path (no deterministic fallback path).
- Deterministic triage fallback is allowed only when Foundry Models env vars are
  absent; do not add a separate deterministic fallback orchestration path.
- Keep Foundry hosting Responses-native through `backend/foundry/main.py` and
  the ACR-built `backend/Dockerfile.hosted` image; do not reintroduce legacy
  invocations adapter paths.
- Keep HITL behavior deterministic and testable.
- Keep API response contracts stable for frontend and Playwright tests.
- Keep the legacy SSE event stream stable; expose richer AG-UI-compatible events only as additive surfaces.
- Treat `/api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` as
  redacted selected-thread projections, not replacements for native SSE or
  `/rich` envelopes.
- Preserve private data boundaries: the browser must not call private Foundry,
  PostgreSQL, or MCP/RAG services directly. Redact order/customer and policy
  data, MCP/RAG results, tool arguments/results, prompts, model output,
  checkpoint state, reviewer comments, credentials, and secrets from
  selected-thread AG-UI and assistant projections.
- Use CopilotKit (`@copilotkit/react-core`) for the approved selected-thread
  assistant UI. It is distinct from the GitHub Copilot SDK, which is not this
  application's runtime integration.

## Delivery formalization

- **You provide** architecture intent, business rules, and acceptance criteria.
- **Skills provide** current Microsoft platform and SDK guidance.
- **Copilot provides** implementation, tests, and infra/doc updates.
- **Gates provide** release evidence for correctness, recovery, telemetry, and Foundry parity.

Canonical contract: `docs/design/engineering-operating-model.md`.

Current hosted gate posture uses private Foundry for all hosted validation and
deployment. Do not introduce an additional hosted deployment path without a
documented contract update.

The private browser topology is external frontend ACA -> same-origin proxy ->
internal FastAPI ACA -> private Foundry Responses -> private PostgreSQL. Only
the frontend has external ingress. Keep the ACA environment VNet-integrated on
a dedicated subnet; do not reuse the Foundry agent-host subnet. The backend
uses managed identity, persisted workflow events, and stable native SSE types.
For PostgreSQL privatization, use the canonical server FQDN and private DNS
output contract. `POSTGRES_SERVER_NAME` and `RUNTIME_DATABASE_URL` must name
the same FQDN; public access and the Azure-services firewall rule may be
removed only after fresh explicit ACA and hosted-agent connectivity proof.
Only the generated proof artifact may authorize lockdown; it must not be
replaced by a manual environment flag.

Private provision, reconciliation, app-release, and observability workflows
must serialize on the same release group and run only on `foundry-private-v2`.
Classify the operation first: a routine app-only release changes only existing
ACA revisions and the existing hosted agent, then validates existing
dependencies. It must not run full Bicep, reconcile shared resources, or change
PostgreSQL access. Bootstrap/reconciliation is a separately approved
full-Bicep operation. PostgreSQL lockdown is a separate explicitly confirmed,
generated-proof-gated operation and is never implied by an app-only release.
Do not add optional refresh, administrator-password, public-access, or
firewall bypasses to any path.

Preview run `31198356080` found shared authoritative drift in the VNet and
subnets, ACA environment, Foundry account/project/models, ACR, Cosmos,
Application Insights, and Search. Do not apply or normalize this drift during
an app-only release, and do not claim deployment success from the preview. Full
Bicep remains blocked until a reviewed reconciliation plan is explicitly
approved.

Clean private provisioning stages Foundry project connections behind
`MANAGE_PROJECT_CONNECTIONS=false` until the project identity and required RBAC
exist. Enable connections only in the later private deploy stage; on identity
or private-endpoint deletion timing failures, retry after propagation rather
than removing a connection or weakening network security.

`GET /api/copilotkit/info` (with `GET /api/copilotkit` as an alias) returns
static, redacted runtime discovery only. `POST /api/copilotkit` verifies and
selects an existing `threadId`; compatible `runId`, `messages`, `state`,
`tools`, `context`, and `forwardedProps` inputs are discarded. Its output may
contain only safe lifecycle/tool labels, validated checkpoint IDs and approval
decisions, and generic terminal/error text. It must never start, resume, or
alter a workflow.

## Workflow Guardrails

- Keep API, application service, MAF runtime, and infrastructure concerns separated:
  - `backend/app/api/v1/routers/*` owns HTTP/SSE routes.
  - `backend/app/api/v1/schemas/*` owns API contracts.
  - `backend/app/modules/order_resolution/*` owns service/domain seams, ports, workflow context/events, and projection logic.
  - `backend/app/core/*` owns config, database, telemetry, and runtime composition.
  - `backend/app/infrastructure/*` is the repository-pattern/adapters namespace.
  - `backend/app/maf/*` owns the MAF runtime namespace.
  - Within `backend/app/maf/*`, keep prompts/agents/tools/executors/runner/workflow
    separated; avoid reintroducing monolithic workflow-stage logic.
- Do not add back removed legacy routes/modules such as `/api/foundry*` or
  `backend/app/foundry/*`.
- Any change to HITL decision logic must update:
  - `docs/design/hitl-approval-conditions.md`
  - tests in `backend/tests/test_workflow.py` and/or eval cases in `backend/.foundry/datasets/order-resolution-hosted-cases.jsonl`
- Do not remove or rename emitted event types without updating frontend/event consumers:
  - `workflow.stage`
  - `tool.call`
  - `checkpoint.created`
  - `hitl.request`
  - `hitl.response`
  - `workflow.output`
- Follow sample-derived MAF execution patterns:
  - Intermediate executors use `ctx.send_message(...)`; terminal executors use `ctx.yield_output(...)`.
  - Treat workflow runs as resumable across multiple `run(...)` calls.
  - Handle approvals via explicit request/response objects keyed by request id.
  - Do not blindly retry side-effecting tools; enforce idempotency keys for write operations.
  - Keep per-agent context/config scoped by agent identity.
  - Observe MAF executor telemetry from streamed `executor_invoked`,
    `executor_completed`, and `output` events.
  - Preserve checkpoint trace context for HITL pause/resume telemetry so
    approval spans remain correlated with the original workflow operation.
  - Emit and persist correlated execution identifiers (`workflow_run_id`, `session_id`, `thread_id`, `event_id`).
  - Keep MAF middleware responsible for cross-cutting runtime behavior such as
    correlation, safe event enrichment/redaction, usage/event observation, and
    explicit failure event emission.
  - Do not replace stable native SSE events with rich/AG-UI events; expose rich
    events through additive routes/adapters.
  - Keep AG-UI and CopilotKit selected-thread views optional; their failure
    must not make native SSE, durable workflow reads, or HITL controls
    unavailable.

## Local Validation Commands

- Backend lint + tests: `make test`
- Eval harness: `make eval-backend`
- Foundry evaluator report (hosted/runtime changes): `make eval-foundry`
  (report-only by default; the private release workflow enforces judgement over
  the current hosted E2E conversation traces)
- Playwright E2E: `make test-e2e`
- Docker E2E profile: `make docker-test`
- Deterministic review/test gate: `./scripts/skills/design-review-skill.sh`

## Repository Skills

- Use `design-review` as the final deterministic local gate.
- Use `docs-sync` for documentation updates after code, IaC, script, or behavior changes.
- Use `backend-boundary-review` for API/modules/core/infrastructure/MAF separation and shim import safety.
- Use `local-validation` for local unit/integration/e2e checks.
- Use `quick-validation` for low-risk app-only redeployments.
- Use `iac-review` for Azure/Foundry IaC, Docker, AZD, RBAC, secret, smoke, and security review without deployment.
- Use `azure-validation` for Azure readiness/live endpoint checks without deployment.
- Use `azure-deployment` only after Azure validation passes.
- Use `azure-telemetry-validation` after hosted deployment to verify App Insights request, dependency, trace, HITL correlation, and exception data.
- Use `release-readiness` to orchestrate the focused skills for PR/release handoff.
- Use `scripts/skills/deployment-mode-router.sh` to decide quick/full validation and app-only/full deployment from changed files.

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
  projections of durable workflow events.
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

## Baseline Test Inputs

- `ORD-1009` -> high amount (`185.0`) -> typically HITL.
- `ORD-1001` -> low amount (`79.0`) -> no HITL unless damaged/manual review rule applies.

## Documentation Contract

When behavior changes, update these docs in the same PR:

- `README.md`
- `backend/README.md`
- `docs/design/userflow.md`
- `docs/design/hitl-approval-conditions.md`
- `docs/design/engineering-operating-model.md`
- `.github/copilot-instructions.md`
- `agents.md`

The selected-thread frontend, strict TypeScript/lint scripts, and focused
browser coverage are implemented and locally validated: 128 tests passed, the
deterministic evaluation is 10/10, seven workflow and four selected-thread E2E
cases passed, and design review passed. Protected-release evidence from
`vm-maffnd-runner` is recorded in
`docs/design/issues-changes-fixes.md`; do not infer future release results
from local evidence alone.
