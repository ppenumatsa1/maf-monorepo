# MAF Order Resolution Agent

Customer-support workflow demonstrating sequential MAF execution, durable
PostgreSQL state, deterministic human-in-the-loop (HITL) approvals, and a React
SSE timeline.

## Runtime model

FastAPI is the only application host for the MAF workflow, locally and in the
Azure Container Apps target. Foundry is limited to model inference and
report-only evaluation; it is not an application host.

The Azure package targets `rg-maf-ora-azure` in North Central US. East US is
excluded because of an Azure PostgreSQL offer restriction. This repository and
its IaC describe **source intent**, not current deployed evidence; record a
new release's non-secret endpoint, smoke, E2E, report-only evaluation, and
telemetry correlation evidence before claiming it is live.

The frontend uses the same-origin `/api` proxy; the FastAPI backend remains the
sole MAF host.

## Quick start

```bash
make bootstrap
make up
```

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health

Model inference is configured with:

- `FOUNDRY_PROJECTS_ENDPOINT`
- `FOUNDRY_MODEL_DEPLOYMENT_NAME`
- `FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME`

When model configuration is absent, the existing deterministic triage summary
is used within the same MAF workflow.

## Contracts

- Low-risk cases complete automatically.
- High-risk cases pause for HITL and resume after an approval decision.
- Native SSE event types remain stable: `workflow.stage`, `tool.call`,
  `checkpoint.created`, `hitl.request`, `hitl.response`, and
  `workflow.output`.
- The rich SSE route is additive.
- `GET /api/chat/stream/{thread_id}/ag-ui` is an additive, read-only,
  redacted projection of one existing durable thread.
- `GET /api/copilotkit/info` (and `GET /api/copilotkit`) is static discovery;
  `POST /api/copilotkit` selects one existing `threadId` and discards standard
  compatibility input. It cannot start, approve, reject, resume, or mutate a
  workflow.

`/rich` preserves its stable native event envelope for compatible consumers.
It is not an assistant contract. The AG-UI/CopilotKit projection never exposes
raw native payloads, order or policy data, tool data, prompts, model output,
checkpoint state, credentials, or secrets.

Baseline scenarios: `ORD-1001` should not require HITL; `ORD-1009` should.

## Validation

```bash
make test
make eval-backend
make eval-foundry   # report-only; requires Foundry configuration
make eval-foundry-deployed  # report-only gate against the selected AZD backend URL
make test-e2e-selected  # focused selected-thread browser contract
make test-e2e           # workflow plus selected-thread browser coverage
make docker-test        # optional local isolated Docker browser coverage
./scripts/skills/design-review-skill.sh
```

The backend test, deterministic evaluation, and local browser targets create a
temporary Compose project with dynamically selected ports, so they do not use a
developer's default PostgreSQL or app ports.

`make docker-test` is intentionally optional for local development because
some managed devices block Docker's npm egress. The **Required cloud Docker
E2E** GitHub Actions job remains the authoritative Docker image/browser gate
for every full-validation change; do not claim Docker E2E evidence until that
job passes.

On a `main` push touching this Azure-hosted path, that job builds the exact
release images, runs Docker E2E against them, deploys their immutable ACR
digests to the existing Container Apps, then performs smoke, hosted browser
E2E, Foundry evaluation, and Application Insights correlation. It is app-only:
the PostgreSQL server/database and all other infrastructure remain untouched.

## Azure release policy

Normal Azure releases are application-only:

```bash
make release-app
```

This deploys backend/frontend revisions, keeps the existing PostgreSQL server
and `maf_workflow` database intact, and gates the release on fresh smoke,
hosted E2E, report-only evaluation, and Application Insights correlation.
Infrastructure reconciliation is exceptional: it requires an owner-reviewed
Bicep preview and explicit non-secret approval reference via
`make release-infra-preview`; it is never selected implicitly by changed files.

## Documentation

- [Architecture](docs/design/architecture.md)
- [User flow and API contracts](docs/design/userflow.md)
- [HITL rules](docs/design/hitl-approval-conditions.md)
- [Engineering operating model](docs/design/engineering-operating-model.md)
- [Azure app-hosted package](infra/azure-apphosted/README.md)
- [Deployment plan](.azure/deployment-plan.md)
