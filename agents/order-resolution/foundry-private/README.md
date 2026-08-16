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
4. **Approved selected-thread guidance**
   - [AG-UI React integration](.github/skills/ag-ui-react-integration-ts/SKILL.md)
   - [AG-UI FastAPI streaming](.github/skills/ag-ui-streaming-fastapi-py/SKILL.md)
   - [TypeScript setup](.github/skills/typescript-setup/SKILL.md),
     [TypeScript updates](.github/skills/typescript-update/SKILL.md), and the
     [E2E operator rubric](.github/skills/e2e-rubric/SKILL.md)
5. **Implementation + repo shape**
   - Backend runtime details: [backend/README.md](backend/README.md)
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
6. **IaC + deployment lane**
   - Infra overview: [infra/README.md](infra/README.md)
   - Foundry-hosted private VNet lane: [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
7. **Validation + operations/SRE**
   - Scripts and validation commands: [scripts/README.md](scripts/README.md)
   - Operational run history and RCA log: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)

## Journey Status

| Stage                | Status      | Runtime path                                                                                                 |
| -------------------- | ----------- | ------------------------------------------------------------------------------------------------------------ |
| Local MAF            | Implemented | Shared MAF workflow (`backend/app/maf/workflows/order_resolution.py`)                                       |
| Foundry hosted agent | Implemented (private VNet lane retained) | Shared workflow hosted at `backend/foundry/main.py` with Responses protocol conversation turns in an ACR-built hosted image |
| Private web delivery | Requires fresh redeployment | External frontend ACA proxies same-origin `/api` and SSE to an internal FastAPI ACA, which calls private Foundry Responses and PostgreSQL. |

MAF internals are split for maintainability into `backend/app/maf/prompts`,
`agents`, `tools`, `executors`, `runner`, and `workflows`.

## Approved Selected-Thread Alignment

The approved private-lane design adds an **optional, read-only** selected-thread
experience. It does not alter the native SSE timeline, durable history, one MAF
workflow path, or checkpoint-keyed HITL:

- `GET /api/chat/stream/{thread_id}/ag-ui` is the additive native AG-UI
  projection for one existing thread.
- `GET /api/copilotkit/info` (and `GET /api/copilotkit`) is static, redacted
  discovery. `POST /api/copilotkit` selects one existing `threadId`; compatible
  `runId`, `messages`, `state`, `tools`, `context`, and `forwardedProps`
  values are discarded.
- CopilotKit means `@copilotkit/react-core`, not the GitHub Copilot SDK. Its
  approved context is limited to opaque thread identity, normalized status,
  safe event metadata, pending-approval count, and output presence.
- These projections may expose only safe lifecycle/tool labels, validated
  checkpoint IDs and approval decisions, and generic terminal/error text.
  Order/customer and policy data, MCP/RAG content, tool inputs/results,
  prompts, raw model output, checkpoint payloads, reviewer comments,
  credentials, and secrets remain private backend concerns.

The private frontend integration, strict TypeScript/lint scripts, and focused
selected-thread browser coverage are implemented and locally validated. The
current backend suite has 133 passing tests. Protected run `31911162673`
deployed hosted-agent version 6 and passed all three HITL scenarios, telemetry
correlation, and strict 3/3 Foundry evaluation.

## Historical Foundry trace evidence (2026-07-27)

- The private Foundry resources were intentionally deleted on 2026-07-28. The
  following hosted E2E and telemetry record is historical only; a clean release
  must produce fresh evidence before any deployment is claimed.
- The private Foundry workflow, PostgreSQL state, and HITL behavior had hosted
  E2E and correlated Application Insights evidence.
- Hosted monitoring uses the private project-level `ApplicationInsights`
  connection and Foundry's native
  `APPLICATIONINSIGHTS_CONNECTION_STRING` injection; do not add runtime
  connection-string aliases or instrumentation-key fallbacks.
- Private releases retain a private PostgreSQL readiness gate that verifies the
  canonical FQDN, private endpoint, DNS, and least-privilege runtime role before
  application deployment.
- Current private telemetry RCA and run evidence are tracked in:
  - [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)

## Quick Start (Local)

1. Bootstrap dependencies.

```bash
make bootstrap
```

## Private VNet web release

The private deployment exposes only the frontend Container App. The browser never
receives a Foundry or database credential: Nginx proxies `/api` to the
internal-ingress FastAPI Container App, and the backend uses managed identity
for the private Foundry Responses endpoint.

### Safe release boundaries (effective 2026-08-07)

Classify every protected operation before it starts. These are separate
operations, not interchangeable steps of one routine release:

| Operation | Permitted scope | Required decision and evidence |
| --- | --- | --- |
| Routine app-only release | Existing ACA backend/frontend revisions and the existing hosted agent only. | Validate the existing private dependencies and release the application artifacts. Do not run full Bicep, reconcile shared resources, or change PostgreSQL access. |
| Bootstrap or reconciliation | Full Bicep management-plane scope. | First capture a current preview and record review evidence for every shared-resource change. Dispatch starts the validated operation. |
| PostgreSQL initialization/readiness | The canonical private-only PostgreSQL server, schema, and least-privilege runtime role. | Runs from the VNet runner before application deployment. Public access and firewall bypasses are unsupported. |

IaC preview run `31198356080` detected shared authoritative drift in the VNet
and subnets, ACA environment, Foundry account/project/models, ACR, Cosmos,
Application Insights, and Search. This is a no-go for full Bicep application
until a reconciliation plan and current validation evidence establish the
intended state. The preview is
evidence only: it does not establish that an application was deployed or that
any dependency is healthy.

PR validation remains credential-free. Protected dispatch workflows
`order-resolution-private-provision.yml` and
`order-resolution-private-deploy.yml` run only on the
`foundry-private-ora` self-hosted runner, using repository-scoped Azure OIDC
variables and the runner's retained private AZD environment. Invoking a
validated workflow starts it: no confirmation input, environment approval, or
owner approval gate is allowed. Provision,
reconciliation, application release, and observability dispatches share one
release concurrency group. A routine app-only release is restricted to the
existing ACA revisions and hosted agent and validates its existing
dependencies. It must not accept or repair the previewed shared-resource drift.
By default, the deploy workflow continues directly into HITL E2E, telemetry,
and strict exact-trace evaluation. It preserves a requirements-hash-validated
backend virtual environment and overlaps hosted-image construction with ACA
deployment. The standalone evidence workflow remains the retry path.
Bootstrap/reconciliation remains a separate full-Bicep operation. PostgreSQL
is private-only from creation, and app-only deployment runs the read-only
private readiness gate before activating artifacts. No operation may use
password-repair, public-access, firewall, or administrator-user bypasses.

Release authority is prepared under `.artifacts/releases/<release-id>/`.
Sanitized `release.json` and provenance are retainable; detailed evidence is
written under `evidence/` and logs under `logs/`, both ignored by Git. The
standalone evidence retry attaches only to the same running source/release
context. The lane-local `extensions.timing` object records UTC millisecond
start/end timestamps, durations, retry attempts, overlap, and total
app-only-start-to-telemetry-success elapsed time for every deployment and
evidence stage. Workflow `31922650130` live-validated this path at 6m 36.8s
to telemetry and 6m 57.8s through strict evaluation. Finalization rejects an
app-only-to-telemetry interval above 15 minutes. Singular
`.artifacts/release/` and historical `backend/.foundry/results/` release output
are historical inventory; migration tooling is dry-run only and never
copies or deletes history.

The same source-of-truth target is available only from the private runner:

```bash
make foundry-provision-preview
make foundry-release
```

`make foundry-provision-preview` provides the required
bootstrap/reconciliation evidence and must not be treated as an app-only
preflight. `make foundry-app-only-release` is the routine application deployment command;
`make foundry-evidence` completes its hosted evidence gates.
`make foundry-release` is the full bootstrap/reconciliation-plus-release path
and must not be used for routine app-only changes. Fresh bootstrap initializes the
schema and runtime role from the private runner, then
`make foundry-postgres-readiness` verifies public access is disabled, the
private endpoint and DNS are authoritative, and the runtime role remains
least privilege before application deployment.

The intentional private-lane teardown left the original Foundry account
soft-deleted. `RESTORE_FOUNDRY_ACCOUNT` therefore defaults to `true` and is
passed to the account resource during clean-room recovery. Set it to `false`
only after that account name has been purged from Azure.

Clean provisioning is staged: `make foundry-provision` creates the private
account, project, identities, and RBAC without storing Foundry connection
secrets. After the project identity has propagated, run
`make foundry-project-connections` only in the separate
bootstrap/reconciliation operation. A routine app-only release validates those
existing connections read-only and does not recreate them. If Azure reports
that a private endpoint is still deleting, wait for that operation to finish
and retry the same provisioning stage; do not open public access or remove
the connection.

### Private runner recovery

If the private runner VM or its GitHub registration is gone, an authorized
management-plane operator must recreate the in-VNet runner before dispatching
any release workflow:

```bash
RUNNER_SSH_PUBKEY_PATH=/secure/path/id_ed25519.pub make foundry-access-path
```

The target rejects an absent, missing, or empty public-key file. It selects the
retained `ora-foundry-private` environment, validates its existing private target, enables
the existing `main.bicep` private-runner/VM parameters, and provisions that
same resource group; it does not use a separate access resource group or
public ACR/firewall exception. Connect to the recreated VM through Bastion,
then run `scripts/github/bootstrap_vm_runner_host.sh` and
`scripts/github/register_vm_runner.sh`. Registration defaults to the required
`foundry-private-ora` label. Only after GitHub reports that label online may a
private release be dispatched.

If the source-controlled VM and registration remain intact but the VM is
deallocated, dispatch **Order Resolution Private Runner Start**. It starts
immediately and starts only `maforapriv-runner-4u2gr5q5plofy` through the existing
repository-scoped OIDC identity, then waits for `PowerState/running`. The
subsequent protected release job is the GitHub registration readiness proof;
the workflow token intentionally lacks runner-administration permission.
It does not create or modify RBAC, OIDC, networking, secrets, or VM extensions.

For release automation changes, the only local private validation is:

```bash
make test
```

Foundry evaluation runs only as the enforced hosted release-evidence step,
after hosted E2E; do not run a local evaluation as a substitute.

2. Configure backend environment.

- Copy [backend/.env.example](backend/.env.example) to `backend/.env` and edit
  its values.
- Core local mode:

```bash
STORE_PROVIDER=postgres
RAG_PROVIDER=pgvector
MEMORY_PROVIDER=postgres
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

For private release-automation changes, run the sole local gate:

```bash
make test
```

`make test` auto-starts local Docker `postgres` when `DATABASE_URL` points to
localhost and PostgreSQL is not already running. Hosted E2E, enforced Foundry
evaluation, and telemetry are collected only from the private runner after
deployment.

Cross-target parity gate (requires endpoint matrix env vars):

```bash
make parity-all
```

POC parity is intentionally fast while still covering both targets (local + Foundry):

- manual baseline cases: ORD-1001 and ORD-1009
- event contract checks: all contract cases
- UI smoke checks: low-risk complete, high-risk approve, high-risk reject

Baseline behavior checks:

- ORD-1001 should usually complete without HITL.
- ORD-1009 should require HITL.

### Selected-thread frontend local evidence

The implemented selected-thread UI passed its strict TypeScript/frontend gates,
133 tests, a 10/10 deterministic evaluation, seven workflow E2E cases, four
selected-thread E2E cases, and the design-review gate. This is local evidence
only. Protected run `31911162673` is the current deployment, hosted E2E,
telemetry, and strict evaluation authority.

## Deploy to Foundry (Hosted Agent)

Deploy hosted agent package:

```bash
azd deploy order-resolution-hosted --no-prompt
```

Verify and invoke:

```bash
azd ai agent show order-resolution-hosted --output json
azd ai agent invoke order-resolution-hosted "Resolve delayed order ORD-1001" --protocol responses --conversation-id c1 --no-prompt
azd ai agent invoke order-resolution-hosted "Why was that resolution selected?" --protocol responses --conversation-id c1 --no-prompt
```

For high-risk requests, continue the same conversation with `Approve` or `Reject`.

## Environment Model Configuration

For hosted model client mode (`maf_sdk` + `foundry_models`), model/deployment config is read from backend environment:

- FOUNDRY_PROJECTS_ENDPOINT
- FOUNDRY_MODEL_DEPLOYMENT_NAME
- FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME

Current default examples in checked-in templates use gpt-4.1-mini for chat deployment.

## Foundry-Hosted Wiring

The hosted agent package is rooted at `backend/` and uses:

- `backend/Dockerfile.hosted` (Responses image entrypoint)
- `backend/foundry/main.py` (thin Responses host around the shared workflow)
- `backend/.foundry/agent-metadata.yaml` and `backend/eval.yaml` for hosted eval metadata
- `infra/foundry-hosted/azure.yaml` service project path (`./agent`) generated from `backend/` via `scripts/foundry/sync_hosted_source.sh`

`infra/foundry-hosted/azure.yaml` is the only supported AZD project for this
lane. Use `make foundry-deploy`; it builds from the VNet runner and registers
the tagged private-ACR image through the Foundry SDK rather than invoking
Foundry's broken source builder.

## Troubleshooting

- If parity fails with 429 session_quota_exceeded from Foundry, reduce test concurrency, add case delays, or clear/raise session quota.
- If hosted responses fail, verify the active image version uses the Responses protocol and pass `--protocol responses` on `azd ai agent invoke`.

## Documentation Map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- System architecture: [docs/design/architecture.md](docs/design/architecture.md)
- HITL rules and baseline scenarios: [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
- API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery, implementation, and decisions

- Engineering operating model (intent -> skills -> implementation -> evidence): [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Project phases and milestone history: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)
- Repo structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
- Backend operational details: [backend/README.md](backend/README.md)

### IaC, deployment, and SRE operations

- Infra overview: [infra/README.md](infra/README.md)
- Foundry-hosted IaC/deployment: [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
- Scripts, parity, and E2E usage: [scripts/README.md](scripts/README.md)
- Incident/RCA and execution log: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
