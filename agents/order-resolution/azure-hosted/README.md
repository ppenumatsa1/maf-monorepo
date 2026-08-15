# MAF Order Resolution Agent

Customer-support workflow demonstrating sequential MAF execution, durable
PostgreSQL state, deterministic human-in-the-loop (HITL) approvals, and a React
SSE timeline.

## Runtime model

FastAPI is the only application host for the MAF workflow, locally and in the
Azure Container Apps target. Foundry is limited to model inference and
report-only evaluation; it is not an application host.

The Azure package targets subscription
`7df95e88-701c-4693-af77-3159f83b558d`, `rg-maf-ora-azure`, in North Central
US. East US is excluded because of an Azure PostgreSQL offer restriction.
This repository and its IaC describe **source intent**, not current deployed
evidence.

The frontend uses the same-origin `/api` proxy; the FastAPI backend remains the
sole MAF host.

## Deployment layout

- `deployment/profiles/`: tracked secret-free target profiles and bootstrap
  selection inputs.
- `docs/design/` and `.azure/deployment-plan.md`: tracked deployment contract,
  flow, and recorded evidence guidance.
- `.artifacts/releases/<release-id>/`: generated release bundle for one
  authorized app-only window, including deployment, smoke, hosted browser E2E
  logs, domain E2E, evaluation, telemetry, and final evidence files.

This project owns its deployment contract independently:
`deployment/profiles/azure-hosted.env` is the canonical secret-free target,
`deployment/profile.sh` parses it as data, and `deployment/contracts/` defines
the release evidence envelope. Generated evidence is separated into
`.artifacts/releases/<release-id>/evidence/` and logs into
`.artifacts/releases/<release-id>/logs/`.
The sibling `release.json` records UTC stage intervals, integer millisecond
durations, and the app-only-to-telemetry benchmark under `extensions.azure`.

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
digests to the existing Container Apps, then performs deployment verification,
smoke, hosted browser E2E, the three HTTP domain scenarios, Foundry
evaluation, Application Insights correlation, and final evidence aggregation.
It is app-only: the PostgreSQL server/database and all other infrastructure
remain untouched.

## Azure release policy

Normal Azure releases are application-only:

```bash
make release-app
```

This deploys backend/frontend revisions, keeps the existing PostgreSQL server
and `maf_workflow` database intact, and gates the release on fresh smoke,
hosted browser E2E, the three HTTP domain scenarios, report-only evaluation,
exact Application Insights correlation, and a final evidence bundle under
`.artifacts/releases/<release-id>/`. Report-only evaluation cannot mutate the
application, but the release fails unless the evaluation completes with zero
failed or errored rows.
Infrastructure reconciliation is exceptional and direct invocation is execution
intent. It is never selected implicitly by changed files: `make
release-infra-reconcile` obtains a fresh subscription-scope Bicep what-if in
the same invocation, rejects every PostgreSQL mutation, and applies only after
steady-state what-if excludes PostgreSQL entirely. No separate owner approval,
reference, or caller-supplied preview digest is accepted.

For a fresh target, supply explicit untracked operator IP, image, and Entra
administrator values, then run `make prepare-bootstrap` and review `azd
provision --preview`. After an authorized bootstrap, run `make
prepare-steady-state`; future IaC previews exclude PostgreSQL while routine
releases remain `make release-app`. The transition first deletes and verifies
removal of the exact `allow-bootstrap-runner` firewall rule; it does not switch
modes when cleanup fails. Steady-state IaC also excludes Container App modules,
so reconciliation cannot reset MCP secrets or application configuration.

## Documentation

- [Architecture](docs/design/architecture.md)
- [Deployment flow](docs/design/deployment-flow.md)
- [User flow and API contracts](docs/design/userflow.md)
- [HITL rules](docs/design/hitl-approval-conditions.md)
- [Engineering operating model](docs/design/engineering-operating-model.md)
- [Azure app-hosted package](infra/azure-apphosted/README.md)
- [Deployment plan](.azure/deployment-plan.md)
