# Order Resolution - Foundry Private

## Goal

Run one explainable Microsoft Agent Framework order-resolution workflow in a
private Microsoft Foundry environment:

- low-risk synthetic cases complete automatically;
- high-risk or damaged-item cases pause for human approval;
- workflow state, checkpoints, approvals, and history remain durable in
  PostgreSQL;
- the same hosted workflow supports the private web application and Microsoft
  Teams;
- release evidence is correlated in Application Insights and evaluated against
  the exact hosted conversations.

This project uses synthetic data only. Do not commit customer information,
tenant or subscription identifiers, live endpoints, credentials, generated
Teams packages, or release artifacts.

## Choose a path

| Goal | Start here |
| --- | --- |
| Install and run locally | [Local development](#local-development) |
| Deploy application changes to an existing environment | [Routine app-only Azure release](#routine-app-only-azure-release) |
| Create or reconcile the private Azure environment | [Bootstrap or infrastructure reconciliation](#bootstrap-or-infrastructure-reconciliation) |
| Publish or validate the agent in Teams | [Teams publication](#teams-publication) |
| Understand GitHub automation | [CI/CD](#cicd) |
| Operate an existing deployment | [Operations](#operations) |
| Recover from a failure | [Troubleshooting](#troubleshooting) |

## Architecture at a glance

1. The browser calls only the external frontend Container App.
2. Frontend Nginx proxies same-origin `/api` traffic to the internal FastAPI
   Container App.
3. FastAPI invokes the private Foundry Responses endpoint with managed
   identity.
4. The hosted agent and FastAPI share the same MAF workflow and private
   PostgreSQL state.
5. Microsoft Teams uses the separately authorized Foundry Activity route
   through Azure Bot Service.
6. Application Insights receives correlated runtime, model, HITL, and
   evaluation telemetry.

Normal Foundry project, model, storage, registry, PostgreSQL, backend, and
Responses paths remain private. The Teams Activity route is a separate,
source-filtered and Bot-authorized exception; it does not make the normal data
plane public.

See [architecture](docs/architecture.md) for the complete component, network,
identity, and trust boundaries.

## Prerequisites

### Local development

- Git
- Make
- Python 3.13
- Node.js and npm compatible with `frontend/package.json`
- Docker with Docker Compose

### Azure and private Foundry operations

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- Docker
- Access to the selected Azure subscription
- A VNet-connected private runner for private Foundry data-plane operations
- GitHub CLI (`gh`) only when dispatching workflows from a terminal

Foundry deployment commands must run with
`AZURE_DEV_USER_AGENT=microsoft_foundry_skill`; repository Make targets and
scripts set it where required.

## Local development

### 1. Configure the backend

From this project directory:

```bash
cp backend/.env.example backend/.env
```

The default local path uses the shared MAF workflow in FastAPI. Confirm the
following values in `backend/.env`:

```dotenv
RUNTIME_TARGET=local_maf
STORE_PROVIDER=postgres
RAG_PROVIDER=pgvector
MEMORY_PROVIDER=postgres
```

Foundry model variables are optional locally. When they are absent, the
workflow retains its MAF execution path and uses the supported deterministic
triage fallback.

### 2. Install dependencies

```bash
make bootstrap
```

This creates the backend virtual environment, installs the locked Python
development dependencies, and installs the frontend packages.

### 3. Start the application

```bash
make up
```

Or start each development server separately:

```bash
make run-backend
make run-frontend
```

Open:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`

### 4. Verify the workflow

Baseline scenarios:

- `ORD-1001`: low risk; normally completes without HITL.
- `ORD-1009`: high value; requires HITL.
- A damaged-item request requires HITL regardless of amount.

Run the private local gate:

```bash
make test
```

View or stop the local stack:

```bash
make logs
make down
```

## Configure an Azure target

Azure target values belong in an ignored local profile, not in tracked files.

### 1. Create the local profile

```bash
cp ../deployment/profiles/foundry-private.local.env.example \
  ../deployment/profiles/foundry-private.local.env
chmod 600 ../deployment/profiles/foundry-private.local.env

export DEPLOYMENT_PROFILE_FILE="$PWD/../deployment/profiles/foundry-private.local.env"
export PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

Replace every placeholder locally. Keep passwords, SSH private keys, user
identity, endpoints, and generated resource identifiers out of the profile and
out of Git.

Validate and apply the profile without printing its values:

```bash
source ../deployment/profile.sh
deployment_profile_load "$DEPLOYMENT_PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

make foundry-profile
```

### 2. Authenticate and verify context

```bash
az login --tenant "$AZURE_TENANT_ID" --use-device-code \
  --only-show-errors --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

actual_tenant="$(az account show --query tenantId --output tsv)"
actual_subscription="$(az account show --query id --output tsv)"

if [[ "$actual_tenant" != "$AZURE_TENANT_ID" ||
      "$actual_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "STOP: Azure CLI does not match the selected deployment profile." >&2
  exit 1
fi

unset actual_tenant actual_subscription
```

Do not copy `az account show` output into documentation or release evidence.

### 3. Run preflight

```bash
make foundry-preflight
```

Preflight validates provider registration, regions, the configured runner VM
SKU, compute quota, Container Apps quota, AI Services, Search, PostgreSQL, and
model deployment capacity.

Stop on any target mismatch, unavailable SKU, provider failure, quota failure,
or unsupported region. Do not silently switch regions, reduce required
capacity, or weaken private networking.

## Routine app-only Azure release

Use this path for normal backend, frontend, hosted-agent, dependency, or
release-automation changes against an existing private environment.

Run from the VNet-connected private runner:

```bash
make foundry-app-only-preflight
make foundry-app-only-release
make foundry-evidence
```

`foundry-app-only-release`:

- validates the selected target and existing private dependencies;
- verifies private PostgreSQL readiness;
- builds and deploys backend/frontend revisions;
- builds and activates one immutable hosted-agent version;
- verifies deployed image provenance.

`foundry-evidence` then runs hosted HITL E2E, Application Insights
correlation, strict Foundry evaluation, and final evidence aggregation.

An app-only release must not:

- run full Bicep reconciliation;
- create, replace, resize, or delete shared infrastructure;
- change PostgreSQL networking or administrator access;
- normalize unrelated drift;
- claim success without fresh evidence from the same release window.

## Bootstrap or infrastructure reconciliation

Use this path only for a fresh environment or an explicitly reviewed
infrastructure reconciliation.

### 1. Validate and preview

```bash
make test
make foundry-release-preflight
make foundry-provision-preview
```

The preview is not deployment proof. Stop if it proposes an unexpected
PostgreSQL mutation, public access, firewall creation, private-endpoint
deletion, DNS weakening, network replacement, or target mismatch.

### 2. Apply the reviewed release

```bash
make foundry-release
```

The full target runs:

1. local tests;
2. release and Bicep preflight;
3. infrastructure preview;
4. private infrastructure provisioning;
5. PostgreSQL schema/runtime-role bootstrap and readiness;
6. Foundry project connections;
7. app-only application deployment;
8. hosted E2E, telemetry, strict evaluation, and final evidence.

Private endpoint deletion or identity propagation can take time. Wait and retry
the same stage; never use public access, firewall, administrator, or alternate
connection bypasses.

The complete clean-room procedure, including Bastion and private-runner setup,
is in the [operator runbook](docs/customer-demo-runbook.md).

## Teams publication

Shared publication requires an interactive user login on the private runner.
GitHub OIDC, service principals, and managed identities cannot perform the
user-scoped Shared catalog operation.

Verify private Responses first:

```bash
make foundry-smoke SMOKE_MESSAGE="Resolve delayed order ORD-1001"
```

Then plan and build the Teams integration:

```bash
make foundry-teams-plan
make foundry-teams-deploy-bot
make foundry-teams-package
```

The package command preserves Responses and Entra authorization while applying
the controlled Activity state. Inspect the ignored package locally; do not
attach it or its raw manifest to release evidence.

Publish and verify:

```bash
make foundry-teams-publish
make foundry-teams-verify-local-state
```

Teams acceptance must verify:

1. low-risk invocation completes;
2. high-risk and damaged-item requests display an Adaptive Card;
3. Approve resumes the exact checkpoint;
4. Reject escalates the exact checkpoint;
5. typed `Approve` or `Reject` does not resolve a Teams checkpoint;
6. replay is rejected;
7. a card cannot be used from another user or conversation.

For package inspection, interactive login, acquisition links, tenant policy,
and acceptance steps, use the
[Teams operator procedure](docs/customer-demo-runbook.md#8-plan-deploy-botchannel-inspect-and-publish-shared).

## CI/CD

### Automatic pull-request and `main` validation

| Workflow | Responsibility |
| --- | --- |
| `order-resolution-private-ci.yml` | Operating-model routing, backend lint/tests/evals, frontend build, Docker E2E, design review, and quick validation |
| `order-resolution-private-validation.yml` | Credential-free workflow contracts, deployment-profile checks, portability contracts, JSON validation, and Bicep compilation |

These workflows must not require live Azure credentials for pull-request
validation.

### Protected manual workflows

| Workflow | When to use it |
| --- | --- |
| `order-resolution-private-runner-start.yml` | Start the existing deallocated private runner VM |
| `order-resolution-private-provision.yml` | Preview or apply private infrastructure bootstrap/reconciliation |
| `order-resolution-private-deploy.yml` | Routine app-only release; evidence runs by default |
| `order-resolution-private-evidence.yml` | Retry evidence for the same deployed release without redeploying |
| `order-resolution-private-observability.yml` | Run private diagnostics without deploying |
| `order-resolution-private-package-validation.yml` | Validate private release packaging on the VNet runner |

Protected workflows use:

- GitHub OIDC;
- repository variables for non-secret target selection;
- GitHub secrets for credentials such as the PostgreSQL administrator password;
- the self-hosted runner label from repository configuration;
- one serialized `order-resolution-private-release` concurrency group.

The deploy workflow retains the private AZD environment, performs app-only
deployment, and collects evidence unless `collect_evidence` is intentionally
disabled. The standalone evidence workflow is a retry path, not a substitute
for a failed release.

## Operations

### Start a stopped private runner

Dispatch **Order Resolution Private Runner Start** from GitHub Actions. It
starts only the configured existing VM and waits for `PowerState/running`.

If the VM or GitHub runner registration no longer exists, follow
[private runner recovery](infra/foundry-hosted/README.md#private-runner-recovery).
Do not create a public IP or alternate public runner.

### Start or verify PostgreSQL

If Azure PostgreSQL is stopped, start the existing server through an approved
Azure operation, then run:

```bash
make foundry-postgres-readiness
```

Readiness verifies:

- public access remains disabled;
- the private endpoint is approved;
- private DNS resolves correctly from the runner;
- the expected schema exists;
- the runtime role retains only the required DML and sequence permissions.

Do not add a public firewall rule or use the administrator connection as a
runtime workaround.

### Verify the active application

```bash
make foundry-smoke SMOKE_MESSAGE="Resolve delayed order ORD-1001"
make foundry-app-images-verify
make foundry-teams-verify-local-state
```

### Retry release evidence

```bash
make foundry-evidence
```

Use this only for the same source and deployed release context. A new release
requires a new complete evidence window.

### Find release authority

- Current committed deployment status:
  [`.azure/deployment-plan.md`](.azure/deployment-plan.md)
- Dated deployment, incident, and acceptance history:
  [docs/issues-changes-fixes.md](docs/issues-changes-fixes.md)
- Generated release state:
  `.artifacts/releases/<release-id>/release.json`
- Ignored detailed evidence:
  `.artifacts/releases/<release-id>/evidence/`
- Ignored logs:
  `.artifacts/releases/<release-id>/logs/`

Successful finalization rejects an app-only-start-to-telemetry-success interval
above 15 minutes.

### Roll back Teams without harming Responses

1. Remove the Shared catalog entry through Microsoft 365 governance.
2. Review:

   ```bash
   make foundry-teams-rollback-plan
   ```

3. Remove Activity/Bot authorization while preserving Responses and Entra:

   ```bash
   make foundry-activity-rollback
   ```

4. Re-run private Responses:

   ```bash
   make foundry-smoke SMOKE_MESSAGE="Resolve delayed order ORD-1001"
   ```

Bot Service deletion is a separate reviewed ARM/Bicep lifecycle action. Teams
rollback must not delete the Foundry project, Responses protocol, PostgreSQL,
private dependencies, or durable workflow data.

## Troubleshooting

### Local development

| Symptom | Action |
| --- | --- |
| `python3` or virtual-environment creation fails | Install Python 3.13 and recreate `backend/.venv`; do not reuse an incompatible system-Python environment. |
| Python dependency or Docker wheel installation fails | Run `make foundry-python-wheelhouse`; confirm the hash-locked Linux AMD64 wheelhouse completes without missing packages. |
| Frontend install or build fails | Remove only local generated frontend state, rerun `make bootstrap`, then run `npm run build` from `frontend/`. Do not edit the lockfile manually. |
| Local PostgreSQL is unavailable | Run `make up` or `make test`; the local targets start the Compose PostgreSQL service when the configured URL points to localhost. |
| Local ports are already used | Stop the conflicting local process or use the project Docker Compose stack; do not connect tests to a developer's unrelated database. |
| Workflow behaves differently from hosted | Confirm local providers use PostgreSQL/pgvector and that the same MAF workflow path is active. |

### Azure, networking, and deployment

| Symptom | Action |
| --- | --- |
| Wrong tenant or subscription | Stop, reload the ignored local profile, log in again, set the subscription, and repeat the non-printing comparison. |
| Profile validation fails | Compare the local file with `foundry-private.local.env.example`; verify every required value and explicit runner SKU. |
| Capacity preflight fails | Resolve provider, region, service/SKU, model-capacity, or quota problems and rerun. Do not silently switch region or SKU. |
| Private runner is offline | Dispatch **Order Resolution Private Runner Start**. If registration is gone, use the documented Bastion recovery path. |
| Foundry data-plane call times out or reports public access disabled | Run from the VNet-connected runner and verify private DNS and approved endpoints. Do not enable general public access. |
| PostgreSQL readiness fails | Check server state, private endpoint, DNS, canonical FQDN, schema, and runtime grants. Never add a public firewall bypass. |
| Image deployment fails | Verify ACR reachability, managed-identity `AcrPull`, immutable image digests, and the existing Container Apps environment. |
| Infrastructure preview shows shared drift | Stop the routine release. Review the full reconciliation separately; do not apply Bicep from the app-only path. |
| Hosted invocation returns a transient `404`, `409`, `429`, or `5xx` | Retry through `make foundry-smoke`; it has bounded retries for known transient readiness failures. |
| Foundry session quota returns `429` | Reduce synthetic test concurrency, allow sessions to retire, or resolve quota before retrying. |

### Responses, evidence, and observability

| Symptom | Action |
| --- | --- |
| Plain hosted Responses invocation fails | Verify the active hosted version and invoke with `--protocol responses` from the private runner. |
| Structured approval is treated as text | Do not send Responses JSON through AZD `--input-file`; the E2E harness uses an authenticated structured Responses POST for `function_call_output`. |
| Approval updates the wrong or no workflow | Verify the checkpoint belongs to a pending Responses-origin workflow in the same conversation. Teams checkpoints require the card action. |
| Telemetry is not visible immediately | Allow bounded ingestion time, then rerun `make foundry-evidence` for the same release. Do not redeploy merely to wait for ingestion. |
| Evaluation reports zero rows | Confirm telemetry correlation succeeded and retry only the bounded zero-row, error-free ingestion case. |
| An evaluator fails, errors, or skips | Treat the release as failed. A run-level summary cannot override an individual evaluator result. |
| Evidence exceeds 15 minutes | Treat finalization as failed and investigate deployment, ingestion, or evaluation timing before another release. |

### Teams and Adaptive Cards

| Symptom | Action |
| --- | --- |
| Shared publication rejects the identity | Confirm `az account show --query user.type` returns `user`; OIDC, service-principal, and managed-identity contexts cannot publish Shared. |
| Bot or Teams channel deployment fails | Review the Bicep error and local identity/tenant inputs. Do not print Bot or resource IDs into evidence. |
| Package or version is rejected | Increment `appVersion` intentionally; never reuse or decrease a published version. Re-run the plan before package/publish. |
| App cannot be installed | Check Teams custom-app and app-permission policies for the publishing user. Do not promote to Tenant as a workaround. |
| Manifest-ID link cannot find the app | Use the Teams v2 launcher created from the sensitive Shared publication title ID, not the package manifest ID. |
| Sign-in code was already redeemed | Stop the waiting turn, send a new message, and open the newly generated one-time sign-in URL once. |
| Teams uses older behavior | Inspect the session version. Completed disposable sessions can remain pinned to the version selected at creation; start a fresh session after approved cleanup. |
| Adaptive Card returns `409` | The action was already used, replaced, expired, or the checkpoint is no longer pending. Use the current pending card. |
| Adaptive Card returns `403` | The card belongs to another user or conversation. Use it only where it was issued. |
| Typed `Approve` or `Reject` does nothing | Expected. Teams approvals must use the bound Adaptive Card action. |
| Teams does not stream tokens | Expected for the current direct Activity handler. |

For uncommon recovery steps and complete Teams rollback, use
[docs/customer-demo-runbook.md](docs/customer-demo-runbook.md). For prior
root causes and exact remediations, use
[docs/issues-changes-fixes.md](docs/issues-changes-fixes.md).

## Project map

| Path | Responsibility |
| --- | --- |
| `backend/` | FastAPI wrapper, shared MAF workflow, hosted Responses/Activity entrypoint, persistence, tests, and evaluations |
| `frontend/` | React/Vite workflow UI and optional read-only selected-thread experience |
| `infra/foundry-hosted/` | Private Foundry, Container Apps, Bot/Teams, and AZD/Bicep deployment assets |
| `scripts/` | Private-runner deployment, release, Teams, E2E, telemetry, and evidence automation |
| `docs/` | Specifications, architecture, operating model, runbooks, and release history |
| `agents.md` | Coding-agent boundaries and required verification |

## Detailed documentation

| Need | Read |
| --- | --- |
| Product behavior and acceptance criteria | [Functional specification](docs/functional-spec.md) |
| Resolution and HITL rules | [Business rules](docs/business-rules.md) |
| Runtime, API, persistence, and deployment contract | [Technical specification](docs/technical-spec.md) |
| Network and component boundaries | [Architecture](docs/architecture.md) |
| Complete documentation map | [Documentation index](docs/README.md) |
| Private deployment and Teams demo operations | [Operator runbook](docs/customer-demo-runbook.md) |
| Current deployment and validation evidence | [Evidence ledger](docs/issues-changes-fixes.md) |
| Instructions for coding agents | [Agents guide](agents.md) |

Read [agents.md](agents.md) before changing this project. It defines package
boundaries, security and HITL invariants, stable API/event contracts, required
documentation updates, and verification expectations.
