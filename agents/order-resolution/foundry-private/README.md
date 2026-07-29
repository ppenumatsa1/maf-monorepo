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
4. **Implementation + repo shape**
   - Backend runtime details: [backend/README.md](backend/README.md)
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
5. **IaC + deployment lane**
   - Infra overview: [infra/README.md](infra/README.md)
   - Foundry-hosted private VNet lane: [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
6. **Validation + operations/SRE**
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
- Private release and database lockdown remain gated by a fresh ACA and
  hosted-agent connectivity proof for the canonical PostgreSQL FQDN.
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

PR validation remains credential-free. Protected manual workflows
`order-resolution-private-provision.yml` and
`order-resolution-private-deploy.yml` run only on the
`foundry-private-v2` self-hosted runner in `foundry-private-env`, using Azure
OIDC and the runner's retained private AZD environment. Provision, deploy, and
observability dispatches share one release concurrency group. A deploy dispatch
requires both `confirmation=deploy` and
`postgres_lockdown_confirmation=lockdown`; this is the explicit workflow
confirmation for the irreversible database cutover. The release sequence always
deploys backend, frontend, and the hosted agent, generates a fresh
connectivity proof, performs the confirmed lockdown, then runs hosted E2E,
enforced Foundry evaluation, and telemetry evidence. It has no password-repair,
public-access, firewall, or administrator-user bypass.

The same source-of-truth target is available only from the private runner:

```bash
make foundry-provision-preview
make foundry-release
```

`foundry-release` records ACA and hosted-agent connectivity in
`backend/.foundry/results/private-connectivity-proof.json` before it disables
PostgreSQL public access and removes the temporary Azure-services firewall rule.
For a manual staged run, execute `make foundry-connectivity-proof` before
`make foundry-postgres-lockdown`; the lockdown target rejects missing, stale, or
mismatched proof for the canonical `POSTGRES_SERVER_NAME` FQDN. The current
recorded target is
`maffndpgv20722.postgres.database.azure.com`; preflight is authoritative if
the AZD environment changes.

The intentional private-lane teardown left the original Foundry account
soft-deleted. `RESTORE_FOUNDRY_ACCOUNT` therefore defaults to `true` and is
passed to the account resource during clean-room recovery. Set it to `false`
only after that account name has been purged from Azure.

Clean provisioning is staged: `make foundry-provision` creates the private
account, project, identities, and RBAC without storing Foundry connection
secrets. After the project identity has propagated, run
`make foundry-project-connections`; the protected deploy workflow performs this
stage before application deployment. If Azure reports that a private endpoint
is still deleting, wait for that operation to finish and retry the same stage;
do not open public access or remove the connection.

### Private runner recovery

If the private runner VM or its GitHub registration is gone, an authorized
management-plane operator must recreate the in-VNet runner before dispatching
any release workflow:

```bash
RUNNER_SSH_PUBKEY_PATH=/secure/path/id_ed25519.pub make foundry-access-path
```

The target rejects an absent, missing, or empty public-key file. It selects the
retained `foundry-private-env`, validates its existing private target, enables
the existing `main.bicep` private-runner/VM parameters, and provisions that
same resource group; it does not use a separate access resource group or
public ACR/firewall exception. Connect to the recreated VM through Bastion,
then run `scripts/github/bootstrap_vm_runner_host.sh` and
`scripts/github/register_vm_runner.sh`. Registration defaults to the required
`foundry-private-v2` label. Only after GitHub reports that label online may a
private release be dispatched.

If the source-controlled VM and registration remain intact but the VM is
deallocated, dispatch **Order Resolution Private Runner Start** with
`confirmation=start`. It starts only `vm-maffnd-runner` through the existing
environment-scoped OIDC identity, waits for `PowerState/running`, then waits
for the existing `foundry-private-v2` GitHub runner registration to be online.
It does not create or modify RBAC, OIDC, networking, secrets, or VM extensions.

For release automation changes, the only local private validation is:

```bash
make test
```

Foundry evaluation runs only as the enforced hosted release-evidence step,
after hosted E2E; do not run a local evaluation as a substitute.

2. Configure backend environment.

- Copy backend env template and edit values in [backend/.env.example](backend/.env.example) and [backend/.env](backend/.env).
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
