# MAF Order Resolution Agent

## Goal

Build a verifiable customer-support workflow that:

- auto-resolves low-risk cases,
- pauses for human approval on risky cases,
- preserves timeline and audit history end-to-end.

Primary scenarios include delayed delivery, damaged item, and policy-driven compensation decisions.

## Start Here (Self-Serve Onboarding Path)

If someone starts from this README, this path should let them understand and run the system end-to-end:

1. **Product + business intent**
   - PRD: [docs/design/prd.md](docs/design/prd.md)
   - User flow: [docs/design/userflow.md](docs/design/userflow.md)
2. **Architecture + contracts**
   - Architecture: [docs/design/architecture.md](docs/design/architecture.md)
   - HITL decision rules: [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
   - API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
3. **Delivery model (how work is governed)**
   - Canonical contract: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
   - Repo instructions: [.github/copilot-instructions.md](.github/copilot-instructions.md), [agents.md](agents.md)
4. **Agent skill guidance**
   - [AG-UI React integration](.github/skills/ag-ui-react-integration-ts/SKILL.md) and [AG-UI FastAPI streaming](.github/skills/ag-ui-streaming-fastapi-py/SKILL.md)
   - [TypeScript setup](.github/skills/typescript-setup/SKILL.md) and [TypeScript updates](.github/skills/typescript-update/SKILL.md)
   - [E2E operator rubric](.github/skills/e2e-rubric/SKILL.md)
5. **Implementation + repo shape**
   - Backend runtime details: [backend/README.md](backend/README.md)
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
6. **IaC + public hosted deployment**
   - Infra overview: [infra/README.md](infra/README.md)
   - Foundry-hosted lane: [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
   - Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
7. **Validation + operations/SRE**
   - Scripts and validation commands: [scripts/README.md](scripts/README.md)
   - Operational run history and RCA log: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)

## Journey Status

| Stage                | Status      | Runtime path                                                                                                 |
| -------------------- | ----------- | ------------------------------------------------------------------------------------------------------------ |
| Local MAF            | Implemented | Shared MAF workflow (`backend/app/maf/workflows/order_resolution.py`)                                       |
| Foundry hosted agent | Implemented | Shared workflow hosted at `backend/foundry/main.py` with public Responses protocol conversation turns |
| Hosted UI/API wrapper | Implemented in repo | External frontend ACA proxies the stable API/SSE contract to an internal FastAPI ACA, which invokes Foundry Responses |

MAF internals are split for maintainability into `backend/app/maf/prompts`,
`agents`, `tools`, `executors`, `runner`, and `workflows`.

## Agent Skill Guidance

The repository includes task-specific guidance for stable native SSE, additive
AG-UI, durable checkpoint-backed HITL, selected-thread CopilotKit, and strict
frontend TypeScript boundaries. CopilotKit is the selected application
integration; it is not the GitHub Copilot SDK.

The redacted selected-thread contract is intentionally narrower than the
existing workflow streams:

- `GET /api/chat/stream/{thread_id}/ag-ui` projects one existing thread as
  native AG-UI.
- `GET /api/copilotkit/info` (and its `GET /api/copilotkit` alias) returns
  static discovery metadata only; it does not read workflow or user data.
- `POST /api/copilotkit` selects one existing `threadId` and returns the same
  read-only durable-event projection. Standard `runId`, `messages`, `state`,
  `tools`, `context`, and `forwardedProps` fields are accepted only for client
  compatibility and are discarded.

Those selected-thread projections expose only allowlisted lifecycle labels,
safe tool labels, validated checkpoint IDs and approval decisions, and generic
terminal/error text. They never expose order or policy data, MCP/RAG results,
tool arguments or results, prompts, model output, checkpoint state,
credentials, or secrets. The stable native SSE and `/rich` event envelopes
remain separate, existing workflow contracts; do not substitute either for the
redacted assistant projection or create a second workflow path.

These source and local-validation capabilities are not evidence of a currently
deployed public endpoint. See the linked skills in the onboarding path for the
applicable implementation and E2E guidance.

## Hosted deployment boundary

- **Local full stack** owns browser, FastAPI, SSE, and workflow-history testing.
- **Public hosted UI** uses an external frontend ACA and internal FastAPI ACA.
  The browser calls only same-origin `/api` routes; the backend uses managed
  identity to invoke Foundry Responses and PostgreSQL for durable state.
- **Public Foundry** owns hosted Responses-agent deployment, conversation/HITL
  verification, Foundry evaluation, and Application Insights telemetry.
- **Portable target:** subscription
  `7df95e88-701c-4693-af77-3159f83b558d`, resource group
  `rg-maf-ora-foundry-public`, and `eastus2`. Generated resource names and
  endpoints are hydrated into the selected local AZD environment. The backend
  URL remains internal-only and is intentionally not a browser endpoint.
- Evidence is tracked in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md).

## Quick Start (Local)

1. Bootstrap dependencies.

```bash
make bootstrap
```

2. Configure backend environment.

- Copy backend env template and edit values in [backend/.env.example](backend/.env.example) and [backend/.env](backend/.env).
- Core local mode:

```bash
STORE_PROVIDER=postgres
```

3. Start services.

```bash
make up
```

Or run backend/frontend separately:

```bash
make run-backend
make run-frontend
```

4. Open UI and health endpoints.

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health

## Required Validation Gates

Run these before considering a change complete:

```bash
make test
make eval-backend
make eval-foundry   # report-only Foundry evaluator run for hosted/runtime changes
make test-e2e       # workflow suite plus selected-thread integration
make test-e2e-selected-thread  # focused frontend selected-thread integration
./scripts/skills/design-review-skill.sh
```

`make test` and `make eval-backend` now auto-start the local Docker `postgres`
service when `DATABASE_URL` points to localhost and PostgreSQL is not already running.

`make eval-foundry` reads only its non-secret model configuration from the
selected nested `infra/foundry-hosted` AZD environment; it does not source AZD
`.env` files or print values. Run `make eval-foundry-config` to verify this
local configuration without creating an evaluation. To use a non-default local
AZD environment without changing the selected environment, run
`FOUNDRY_AZD_ENV_NAME=<environment> make eval-foundry`.

`make test-e2e` creates its own short-lived Docker Compose project and dynamically
selects host ports for its backend, PostgreSQL, and mock MCP services. It does not
use or stop a process already listening on the normal developer ports (8000, 5432,
or 8011). To reserve known ports for a run, set
`E2E_BACKEND_HOST_PORT`, `E2E_POSTGRES_HOST_PORT`, and
`E2E_MOCK_MCP_HOST_PORT`. `make docker-test` also accepts
`E2E_FRONTEND_HOST_PORT`. The selected-thread integration runs against the same
dynamic Vite URL during `make test-e2e`; when invoked by itself,
`make test-e2e-selected-thread` starts Vite on `127.0.0.1:4175`. Normal
`make up` defaults remain unchanged.

Baseline behavior checks:

- ORD-1001 should usually complete without HITL.
- ORD-1009 should require HITL.
- A damaged-item ORD-1001 message should require HITL even though its amount is low.

## Deploy to Foundry (Hosted Agent)

Select and hydrate a secret-free existing-target profile, then run the
authenticated app-only release sequence:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE=../deployment/profiles/foundry-public.env
make foundry-bootstrap
make foundry-release
```

The shared profile is preferred. The lane-local
`deployment/profiles/foundry-public.env` remains
`legacy_pending_cutover` compatibility and emits a warning when selected.

The default release route is gated `app_only`: it does not automatically
provision infrastructure and reuses the existing PostgreSQL database and
retained public-lane dependencies. It runs the selected validation and Bicep
build, performs a read-only chat/embeddings/evaluator deployment and quota
preflight, then deploys immutable image digests. The hosted identity converges
only the account-scoped `Cognitive Services OpenAI User` role. After PostgreSQL
readiness, the release idempotently stores the runtime URL in the deterministic
project `CustomKeys` connection and gives the hosted definition only
`${{connections.orderresolutionruntimesecrets.credentials.database_url}}`.
Release gates then verify active ACA revisions, topology, same-origin proxy
health, hosted agent version/image and literal connection placeholders, App
Insights, backend database-secret parity, and
`DB_SCHEMA_MANAGED_EXTERNALLY=true` before smoke, three-conversation hosted
E2E, evaluation, telemetry, and one aggregate release-window report.
Future execution writes the v1 authority record to
`.artifacts/releases/<release-id>/release.json`, detailed evidence below
`evidence/`, and logs below `logs/`. This path is
`prepared_not_live_validated`; `deployment-report/` and singular
`.artifacts/release/` remain `legacy_pending_cutover`.
`make foundry-provision` is separate. In bootstrap mode it creates the complete
lane; after output hydration the environment switches to non-mutating reuse
mode. Bootstrap also requires the explicit schema, least-privilege runtime
credential, and readiness sequence documented in
[.azure/deployment-plan.md](.azure/deployment-plan.md). Production runtimes set
`DB_SCHEMA_MANAGED_EXTERNALLY=true`: only the administrator bootstrap applies
DDL, while the runtime credential remains limited to required DML and sequence
usage. To invoke manually
after deployment:

```bash
azd ai agent show order-resolution-hosted --output json
azd ai agent invoke order-resolution-hosted "Resolve delayed order ORD-1001" --protocol responses --conversation-id c1 --no-prompt
azd ai agent invoke order-resolution-hosted "Why was that resolution selected?" --protocol responses --conversation-id c1 --no-prompt
```

For high-risk requests, continue the same conversation with `Approve` or `Reject`.
Run the browser contract suite against the public UI after deployment:

```bash
PLAYWRIGHT_BASE_URL="$(azd env get-value WEB_URL --cwd infra/foundry-hosted)" \
make test-e2e
```

## Environment Model Configuration

For local MAF model-client mode (`maf_sdk` + `foundry_models`), model/deployment
configuration is read from the backend environment:

- FOUNDRY_PROJECTS_ENDPOINT
- FOUNDRY_MODEL_DEPLOYMENT_NAME
- FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME
- FOUNDRY_EVAL_MODEL (the dedicated judge deployment used by `make eval-foundry`)

Portable bootstrap defaults to pinned `gpt-4.1-mini` chat/evaluator deployments
and `text-embedding-3-small` on the `Standard` SKU. SKU, capacities, and
versions remain explicit AZD inputs. `make foundry-model-preflight` records the
live deployment model, version, SKU, capacity, and matching regional quota
without creating, resizing, or changing a deployment.

The release writes generated, gitignored JSON under
`backend/.foundry/results/`. `make foundry-verify` can independently re-run the
live contract checks, and `make foundry-evidence` aggregates the model
preflight, runtime-connection convergence, deployment verification, smoke,
hosted E2E, App Insights connection, telemetry, and Task
Completion/Coherence evaluation artifacts for one release window. These files
must remain secret-free and uncommitted.

Evaluation storage remains private-by-default at the network ACL: Foundry
reaches it only through the Azure trusted-service bypass while all other public
network traffic is denied. Reuse hydration persists the complete non-secret
output contract, including app/environment IDs, PostgreSQL FQDN, monitoring
IDs, and hydrated frontend/backend URLs.

## Foundry-Hosted Wiring

The hosted agent package is rooted at `backend/` and uses:

- `backend/Dockerfile.hosted` (`python -m foundry.main` on port 8088)
- `infra/foundry-hosted/azure.yaml` (Responses protocol and hosted container settings)
- `backend/foundry/main.py` (thin Responses host around the shared workflow)
- `backend/.foundry/agent-metadata.yaml` and `backend/eval.yaml` for hosted eval metadata
- `infra/foundry-hosted/azure.yaml` service project path (`./agent`), generated
  from the canonical `backend/` source before every deployment

Both backend container Dockerfiles install Python dependencies only through the
approved CFS feed
`https://packagefeedproxy.microsoft.io/pypi/simple` (`PIP_INDEX_URL`). Do not
replace it with an unapproved public package index in a release image.

## Troubleshooting

- If parity fails with 429 session_quota_exceeded from Foundry, reduce test concurrency, add case delays, or clear/raise session quota.
- If hosted responses fail, verify the `azure.yaml` Responses protocol and the
  active image/runtime environment, then pass `--protocol responses` on
  `azd ai agent invoke`.

## Documentation Map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- System architecture: [docs/design/architecture.md](docs/design/architecture.md)
- HITL rules and baseline scenarios: [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
- API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery and implementation

- Engineering operating model (intent -> skills -> implementation -> evidence): [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Deployment flow and command-to-stage mapping: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
- Repo structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
- Backend operational details: [backend/README.md](backend/README.md)

### IaC, deployment, and SRE operations

- Infra overview: [infra/README.md](infra/README.md)
- Foundry-hosted IaC/deployment: [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
- Scripts, parity, and E2E usage: [scripts/README.md](scripts/README.md)
- Incident/RCA and execution log: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
