# Copilot Instructions

This repository implements a Microsoft Agent Framework (MAF SDK) customer order resolution workflow with HITL checkpoints.

## Primary Goals

- Keep one MAF-based business workflow path (no deterministic fallback path).
- Deterministic triage fallback is allowed only when Foundry Models env vars are
  absent; do not add a separate deterministic fallback orchestration path.
- Preserve the existing sequential `FoundryChatClient` / `SequentialBuilder`
  MAF workflow; do not create a parallel orchestration path in the API wrapper,
  frontend, or an assistant integration.
- Keep Foundry hosting Responses-native through `backend/foundry/main.py` and
  `backend/Dockerfile.hosted`; do not reintroduce legacy invocations adapter paths.
- Keep durable checkpoint-keyed HITL pause/resume behavior deterministic and
  testable.
- Keep PostgreSQL schema DDL administrator-owned. Production runtime
  deployments must set `DB_SCHEMA_MANAGED_EXTERNALLY=true`; never grant schema
  ownership or `CREATE` merely to satisfy application startup.
- Keep API response contracts stable for frontend and Playwright tests.
- Keep the legacy SSE event stream stable; expose richer AG-UI-compatible events only as additive surfaces.
- Treat `/api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` as
  redacted selected-thread projections, not replacements for native SSE or
  `/rich` envelopes.
- Preserve MCP/RAG retrieval and privacy boundaries: the browser must not call
  MCP/RAG services directly. Redact order/policy data, MCP/RAG results, tool
  arguments/results, prompts, model output, checkpoint state, credentials, and
  secrets from selected-thread AG-UI and assistant projections.
- Use CopilotKit (`@copilotkit/react-core`) for the selected-thread assistant
  UI. It is distinct from the GitHub Copilot SDK, which is not this
  application's runtime integration.

## Delivery formalization

- **You provide** architecture intent, business rules, and acceptance criteria.
- **Skills provide** current Microsoft platform and SDK guidance.
- **Copilot provides** implementation, tests, and infra/doc updates.
- **Gates provide** release evidence for correctness, recovery, telemetry, and Foundry parity.

Canonical operating contract: `docs/design/engineering-operating-model.md`.
Canonical deployment stages and command mapping:
`docs/design/deployment-flow.md`.

The portable public Foundry deployment configuration targets subscription
`7df95e88-701c-4693-af77-3159f83b558d`, resource group
`rg-maf-ora-foundry-public`, and `eastus2`; repository configuration is not
evidence of a currently deployed endpoint.
GitHub Actions is credential-free CI only. Use `make foundry-provision` only
for an explicitly approved bootstrap or non-mutating reuse operation; use the
local authenticated `make foundry-release` flow for app-only deployment,
verification, smoke, hosted E2E, evaluation, telemetry, and evidence.
Routine release remains hard `app_only`; any `FOUNDRY_DEPLOY_MODE` override is
an error. Preserve the exact Order Resolution chat/embeddings/evaluator model
set. Model/quota preflight is read-only and must not resize or change live SKUs.
Release images are deployed by immutable digest, the hosted platform identity
receives only account-scoped `Cognitive Services OpenAI User`, and
`make foundry-verify` plus `make foundry-evidence` own live proof and
secret-free release-window aggregation.
Hosted database variables must use the deterministic project `CustomKeys`
connection placeholder; never put the resolved runtime URL in a hosted
definition, agent metadata, deployment metadata, or evidence.

The public UI topology is external frontend ACA -> internal FastAPI wrapper ACA
-> Foundry Responses. Keep browser calls same-origin through the frontend
proxy; only the backend's managed identity may call Foundry, and wrapper SSE
must use persisted workflow events. The initial wrapper dispatch is non-streaming;
the browser obtains live updates by polling durable state and subscribing to SSE.
FastAPI health and SSE request spans are intentionally excluded from Application
Insights request telemetry so workflow/HITL spans remain the operational signal.

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

## Local Validation Commands

- Backend lint + tests: `make test`
- Eval harness: `make eval-backend`
- Foundry evaluator report (hosted/runtime changes): `make eval-foundry`
- Live deployment contract (after deployment): `make foundry-verify`
- Aggregate release evidence (after all hosted gates): `make foundry-evidence`
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
- Use `scripts/skills/deployment-mode-router.sh` to decide quick/full
  validation; automatic releases are always app-only. Provision requires
  an explicit operator command and runs either full bootstrap creation or
  non-mutating reuse from the selected secret-free profile.
- Retain `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple` in
  backend release images; it is the approved CFS package feed.

## Stack Implementation Skills

Load only the relevant implementation skill for the task; these complement
rather than replace the repository workflow skills above:

- `microsoft-foundry`: the selectively vendored complete Foundry lifecycle skill
  for hosted-agent invocation, evaluation, trace analysis, and troubleshooting.
  It is sourced only from
  `microsoft/skills` revision `e58528db9a006528a5fb0a2c029790fa6a9a7c0e`
  (`.github/plugins/azure-skills/skills/microsoft-foundry`); do not install the
  full catalog.
- `agent-framework-foundry-py`: this service's `agent-framework-foundry` integration,
  `FoundryChatClient`, `SequentialBuilder`, middleware, resumable workflows, and
  checkpoint-backed HITL request/response flows.
- `azure-ai-projects-py`: Foundry projects, deployments, and evaluations.
- `azure-identity-py`: Entra authentication and managed identity.
- `azure-monitor-opentelemetry-py`: Application Insights and Azure Monitor telemetry.
- `fastapi-router-py`: FastAPI HTTP routes.
- `pydantic-models-py`: Pydantic v2 schemas.
- `postgres-psycopg-py`: PostgreSQL, Psycopg, and Azure PostgreSQL workflow-audit persistence.
- `ag-ui-streaming-fastapi-py`: additive, redacted AG-UI and CopilotKit
  projections of durable workflow events.
- `ag-ui-react-integration-ts`: React selected-thread UI, additive AG-UI
  consumption, and safe CopilotKit context.
- `typescript-setup`: strict TypeScript boundaries for new frontend surfaces.
- `typescript-update`: strict TypeScript and React updates that preserve
  workflow contracts.
- `e2e-rubric`: operator coverage for native SSE, durable HITL, optional AG-UI,
  CopilotKit safety, and wrapper boundaries.

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
- `docs/design/deployment-flow.md`
- `infra/foundry-hosted/README.md`
- `scripts/README.md`
- `.github/copilot-instructions.md`
- `agents.md`
