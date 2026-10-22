# Order Resolution - Foundry Public

## Why this lane exists

This project is the portable **public Microsoft Foundry** reference lane for
the Order Resolution workflow. It demonstrates how to:

- run one sequential Microsoft Agent Framework (MAF) workflow locally and as a
  Foundry-hosted agent;
- auto-resolve low-risk synthetic order cases and pause risky or damaged-item
  cases at a durable human-in-the-loop (HITL) checkpoint;
- expose the hosted workflow through Responses for the web application and
  through additive Activity handling for Microsoft Teams;
- keep the browser on a same-origin path through an external frontend
  Container App and an internal FastAPI wrapper Container App;
- persist workflow runs, messages, events, checkpoints, approvals, and Teams
  card actions in PostgreSQL;
- deploy a target-agnostic public Azure topology from an ignored external
  profile; and
- require fresh smoke, E2E, evaluation, telemetry, and aggregate evidence
  before claiming a release.

This lane intentionally differs from the private Foundry lane. It creates no
VNet, private endpoint, private runner, private DNS, or capability host.
Public service access is still constrained by identity, TLS, scoped firewall
rules, least-privilege PostgreSQL credentials, managed identity, and
resource-scoped Azure RBAC. The FastAPI backend remains internal to the
Container Apps environment and is not a browser endpoint.

The project uses synthetic data only. Do not commit tenant, subscription, user,
resource, region, or endpoint identifiers; credentials or connection strings;
generated Teams packages; populated deployment profiles; or release artifacts.

> Source, infrastructure definitions, and local tests describe the supported
> implementation. They do not prove that the current source is deployed.
> Consult the evidence authorities in [Operations](#operations) before making
> any live-state claim.

## Choose a path

| Goal | Start here |
| --- | --- |
| Understand the runtime and trust boundaries | [Architecture at a glance](#architecture-at-a-glance) |
| Install and run locally | [Local development](#local-development) |
| Configure a portable Azure target | [Configure an Azure target](#configure-an-azure-target) |
| Release application changes to existing resources | [Routine app-only Azure release](#routine-app-only-azure-release) |
| Create or reconcile the public Azure environment | [Bootstrap or infrastructure reconciliation](#bootstrap-or-infrastructure-reconciliation) |
| Publish or validate the agent in Teams | [Teams Shared publication](#teams-shared-publication) |
| Understand automation and deployment ownership | [CI/CD and operation ownership](#cicd-and-operation-ownership) |
| Verify, observe, or roll back a release | [Operations](#operations) |
| Diagnose a failure | [Troubleshooting](#troubleshooting) |
| Find source or detailed documentation | [Project map](#project-map) and [Documentation map](#documentation-map) |

## Architecture at a glance

1. The browser calls only the external React/Nginx frontend Container App.
2. Frontend Nginx proxies same-origin `/api` traffic to the internal FastAPI
   Container App.
3. FastAPI uses managed identity to invoke the Foundry Responses endpoint.
4. The Foundry-hosted process and local FastAPI runtime call the same
   sequential MAF order-resolution workflow.
5. PostgreSQL is the application-owned durable authority for workflow state,
   events, conversation memory, checkpoints, approvals, idempotency, and Teams
   card actions.
6. Azure Bot Service and `MsTeamsChannel` route Teams messages to the additive
   Foundry Activity endpoint in the same hosted process; Activity does not
   replace Responses.
7. Application Insights receives correlated Foundry invocation, workflow,
   model, HITL, and evaluation telemetry.

```text
Browser
  -> external frontend Container App
  -> same-origin /api proxy
  -> internal FastAPI Container App
  -> managed-identity Foundry Responses endpoint
  -> shared MAF workflow
  -> PostgreSQL

Teams
  -> Azure Bot Service / MsTeamsChannel
  -> Foundry Activity endpoint
  -> the same hosted process and MAF workflow
  -> PostgreSQL
```

The hosted process exposes Responses 2.0 and Activity 2.0 additively. The
browser never receives a Foundry credential, PostgreSQL URL, or direct backend
address. Native SSE and durable workflow APIs remain the web operator
contract. AG-UI and CopilotKit are optional, read-only selected-thread
projections and cannot start, approve, reject, or resume a workflow.

The public resource graph includes the Foundry account/project and chat,
embeddings, and evaluator deployments; Azure Container Registry; Log Analytics
and Application Insights; the Container Apps environment and apps; PostgreSQL;
evaluation storage; Azure AI Search; managed identities; scoped role
assignments; and, when separately authorized, Azure Bot Service and
`MsTeamsChannel`.

See the detailed
[architecture](docs/design/architecture.md),
[deployment flow](docs/design/deployment-flow.md), and
[Teams integration contract](docs/design/teams-foundry-integration.md).

## Source capability status

| Surface | Source status | Live-state rule |
| --- | --- | --- |
| Local MAF workflow | Implemented | Prove locally with the commands in this guide. |
| Public Foundry Responses host | Implemented in source | Requires a fresh reviewed deployment and Responses evidence. |
| External frontend and internal FastAPI wrapper | Implemented in source | Requires exact active-revision, image, topology, and same-origin verification. |
| Teams Activity and Adaptive Card approval | Implemented in source | Requires reviewed Bot/channel deployment, Shared publication, live acceptance, and rollback evidence. |
| Evaluation and telemetry gates | Implemented in source | A current release must produce fresh same-window evaluation and Application Insights evidence. |

The current implementation baseline uses Python 3.13 for both backend images
and installs hash-locked CPython 3.13 Linux AMD64 wheels offline. The frontend
baseline is React 19.3, CopilotKit 1.79, Zod 4.6, Vite 8.3, Playwright 1.64,
ESLint 10.12, and the documented TypeScript 7 executable/TypeScript 6 compiler
API compatibility arrangement.

### Runtime and projection invariants

- One `FoundryChatClient` / `SequentialBuilder` MAF workflow owns triage,
  policy retrieval, resolution, checkpointing, and resume. Responses, Activity,
  FastAPI, native SSE, AG-UI, and CopilotKit do not create alternate business
  workflows.
- `GET /api/chat/stream/{thread_id}/ag-ui` is an additive redacted projection
  of one existing durable thread.
- `GET /api/copilotkit/info` and its `GET /api/copilotkit` alias return static
  discovery metadata. `POST /api/copilotkit` selects one existing `threadId`;
  compatible `runId`, `messages`, `state`, `tools`, `context`, and
  `forwardedProps` values are discarded.
- Selected-thread projections may expose only safe lifecycle/tool labels,
  validated checkpoint IDs and approval state, and generic terminal/error
  text. They never expose order or policy data, MCP/RAG content, tool
  arguments/results, prompts, model output, checkpoint state, credentials, or
  secrets.
- Evaluation storage denies general public traffic; Foundry reaches it through
  the configured Azure trusted-service bypass. Blob public access and shared
  key authorization remain disabled.

## Prerequisites

### Developer workstation

- Git
- GNU Make and Bash
- Python 3.13 with `venv`
- Node.js 20 and npm
- Docker with Docker Compose
- `curl`

Local PostgreSQL and the mock MCP service run through Docker Compose. A
Foundry account is not required for the default local workflow because model
configuration is optional; when model variables are absent, deterministic
triage remains inside the same MAF workflow rather than selecting a second
orchestration path.

### Azure and release operations

- Azure CLI (`az`) with the Bicep command available
- Azure Developer CLI (`azd`)
- Docker
- Python 3.13
- `jq`, `curl`, and PostgreSQL `psql`
- An interactive operator identity with access to the selected subscription,
  resource group, Foundry project data plane, ACR, Container Apps,
  PostgreSQL, monitoring, and any separately authorized Teams resources
- Sufficient regional service availability, model capacity, and quota for the
  exact profile
- A public operator IPv4 address when the PostgreSQL operator firewall rule is
  created or validated

Azure mutation and live validation run from the authenticated operator
workstation. This public lane does not use a private runner or a GitHub
deployment identity.

Foundry commands must carry
`AZURE_DEV_USER_AGENT=microsoft_foundry_skill`; the repository Make targets and
scripts set it where required.

### Teams publication prerequisites

- A successfully activated Teams-capable hosted-agent version
- Azure Bot Service and `MsTeamsChannel` values in the external profile
- An **interactive Azure CLI user** login; service principals, managed
  identities, and GitHub OIDC cannot publish to the Shared catalog
- Permission to deploy or use the selected Bot resource
- Microsoft Teams custom-app and app-permission policies that allow the
  publishing user to acquire and run the Shared app
- Reviewed metadata and an intentionally incremented semantic `appVersion` in
  `infra/foundry-hosted/teams-publication.json`

The tracked publication manifest contains example organization URLs. Replace
them with approved external metadata before a real publication without adding
customer or tenant identifiers to this README.

## Local development

Run all commands in this project directory:

```bash
cd agents/order-resolution/foundry-public
```

### 1. Configure the backend

```bash
cp backend/.env.example backend/.env
```

The default local configuration should retain:

```dotenv
APP_ENV=local
STORE_PROVIDER=postgres
RUNTIME_TARGET=local_maf
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/maf_workflow?sslmode=disable
FRONTEND_ORIGIN=http://localhost:5173
```

Do not put a production PostgreSQL URL or Azure credential in `backend/.env`.
Optional Foundry model variables, telemetry, and MCP settings are documented
as comments in [backend/.env.example](backend/.env.example).

### 2. Install dependencies

```bash
make bootstrap
```

This creates or refreshes `backend/.venv`, installs the locked Python
development dependencies, and installs frontend and Playwright npm
dependencies.

If host Playwright browsers are not already installed:

```bash
cd scripts/playwright
npx playwright install --with-deps chromium
cd ../..
```

### 3. Start the application

Start the complete Compose stack:

```bash
make up
```

Open:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`

Or run the backend and frontend development servers in separate terminals:

```bash
make run-backend
```

```bash
make run-frontend
```

Use `make run-mock-mcp` in another terminal when testing the local MCP
integration outside Compose.

### 4. Exercise the workflow

Baseline scenarios:

| Scenario | Prompt | Expected result |
| --- | --- | --- |
| Low risk | `Order ORD-1001 arrived late by 1 day.` | Completes without `hitl.request`. |
| High value | `Order ORD-1009 is delayed by 5 days.` | Pauses for approval, then completes after approval or escalates after rejection. |
| Damaged item | `Order ORD-1001 arrived damaged and broken.` | Pauses for approval regardless of the low amount. |

The stable event sequence uses `workflow.stage`, `tool.call`,
`checkpoint.created`, `hitl.request`, `hitl.response`, and
`workflow.output`.

Run the broader manual matrix:

```bash
make manual-matrix
```

### 5. Run local validation

Focused backend and deterministic evaluation:

```bash
make test
make eval-backend
```

Browser workflow and selected-thread integration:

```bash
make test-e2e
```

Docker-contained browser validation:

```bash
make docker-test
```

Complete deterministic local gate:

```bash
make validate-full
```

Hosted `make eval-foundry` is report-only and requires a selected nested AZD
environment with evaluator configuration. Verify configuration without
creating an evaluation:

```bash
make eval-foundry-config
```

Do not treat a local or report-only evaluator run as Azure release evidence.

### 6. Inspect or stop the stack

```bash
make ps
make logs
make down
```

`make test` and `make eval-backend` start the local PostgreSQL service when the
configured database URL points to localhost. `make test-e2e` creates an
isolated Compose project and dynamically selects backend, PostgreSQL, mock MCP,
and frontend ports; it does not take over the normal developer ports.

## Configure an Azure target

The public target is supplied through a populated, ignored profile. Never edit
the tracked example into a real target and never commit the copied profile.

### 1. Create the ignored profile

```bash
cp deployment/profiles/foundry-public.env.example \
  deployment/profiles/foundry-public.env
chmod 600 deployment/profiles/foundry-public.env

export FOUNDRY_DEPLOYMENT_PROFILE="$PWD/deployment/profiles/foundry-public.env"
```

Replace every placeholder in the ignored file. The profile contains only
target selectors and desired non-secret configuration:

- subscription, resource group, Azure/AZD environment, and regions;
- deterministic resource names;
- chat, embeddings, and evaluator model identities, versions, SKUs, and
  capacities;
- PostgreSQL, Search, ACR, Container Apps, monitoring, image-repository, and
  Bot settings; and
- `INFRASTRUCTURE_MODE=reuse` for an existing target or `bootstrap` for a
  separately authorized creation.

Do not add a tenant ID, user ID, password, connection string, endpoint,
generated resource ID, image digest, or access token to the profile.

Validate it as data rather than sourcing it:

```bash
bash deployment/profile.sh validate "$FOUNDRY_DEPLOYMENT_PROFILE"
make test-deployment-profile
```

### 2. Authenticate and verify the selected subscription

```bash
az login --use-device-code
azd auth login

source deployment/profile.sh
deployment_profile_load "$FOUNDRY_DEPLOYMENT_PROFILE"
deployment_profile_validate
deployment_profile_export

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

actual_subscription="$(az account show --query id --output tsv)"
if [[ "$actual_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "STOP: Azure CLI does not match the selected profile." >&2
  exit 1
fi
unset actual_subscription
```

Do not paste `az account show`, `azd env get-values`, or populated profile
output into issues, documentation, chat, or release evidence.

### 3. Apply the profile

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
```

For an existing target with `INFRASTRUCTURE_MODE=reuse`, hydrate the selected
local AZD environment:

```bash
make foundry-bootstrap
```

The hydrated local AZD environment contains generated outputs and secrets and
must remain ignored. Confirm configuration without printing values:

```bash
make foundry-iac-build
make foundry-release-preflight
```

Stop on a subscription, resource group, region, AZD environment, resource,
model, SKU, capacity, PostgreSQL, runtime-connection, or preview mismatch. Do
not silently rename resources, move regions, reduce capacity, broaden access,
or convert a reuse operation into bootstrap.

## Routine app-only Azure release

Use this path for normal backend, frontend, hosted-agent, dependency, or
release-automation changes against an existing public environment.

The profile must use:

```dotenv
INFRASTRUCTURE_MODE=reuse
```

Run:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap
make foundry-release
```

`make foundry-release` is the only routine release command. It is hard
`app_only`; `FOUNDRY_DEPLOY_MODE` overrides are rejected. The release:

1. validates the profile and selected Azure/AZD context;
2. routes quick or full **local validation** without changing deployment
   authority;
3. compiles Bicep and requires a fresh zero-mutation reuse preview;
4. validates exact retained resources and zero incremental model/service
   growth;
5. verifies PostgreSQL readiness, the existing project `CustomKeys` runtime
   connection, and required hosted identity state without mutation;
6. packages a fresh offline wheelhouse and synchronized hosted source;
7. builds and deploys the hosted agent, internal backend, and external
   frontend concurrently by immutable digest;
9. verifies active revisions, ingress topology, same-origin health, hosted
   version/image/placeholders, Application Insights, PostgreSQL secret parity,
   and `DB_SCHEMA_MANAGED_EXTERNALLY=true`;
10. runs Responses smoke, three fresh hosted conversations, strict Foundry
    evaluation, correlated telemetry, and secret-free final evidence.

The three hosted conversations prove:

- low-risk `ORD-1001` completion without HITL;
- high-value `ORD-1009` approval/resume; and
- damaged-item `ORD-1001` approval/resume.

An app-only release must not:

- run `azd provision`;
- create or update infrastructure, role assignments, project connections,
  models, capacities, PostgreSQL schema, credentials, firewall rules, Bot
  resources, or Teams channels;
- reconcile unrelated drift;
- deploy mutable tags as runtime authority; or
- claim success from a preview, build, smoke result, or historical evidence
  alone.

## Bootstrap or infrastructure reconciliation

Use this path only for a new public lane or an explicitly reviewed
infrastructure reconciliation. It is not a fallback for a blocked app-only
release.

### 1. Select bootstrap authority and prepare inputs

Set `INFRASTRUCTURE_MODE=bootstrap` in the ignored profile, then run:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"

read -r -s -p "PostgreSQL administrator password: " secure_value
printf '\n'
azd env set POSTGRES_ADMIN_PASSWORD "$secure_value" \
  --cwd infra/foundry-hosted \
  --no-prompt
unset secure_value

read -r -s -p "Bootstrap runtime database URL: " secure_value
printf '\n'
azd env set BOOTSTRAP_RUNTIME_DATABASE_URL "$secure_value" \
  --cwd infra/foundry-hosted \
  --no-prompt
unset secure_value

make foundry-bootstrap-env
make foundry-iac-build
make foundry-capacity-preflight-full
```

`foundry-bootstrap-env` determines the operator IP when needed and validates
required inputs. The bootstrap runtime URL is an initial secure placeholder
that the credential workflow replaces before release. PostgreSQL
administrator and runtime passwords are secrets in the ignored local AZD
environment or interactive process; never add them to the profile or command
output.

### 2. Preview and review

```bash
make foundry-provision-preview \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
```

The resource group must already exist for the preview. Review every proposed
create, update, delete, replacement, role assignment, firewall rule, service
SKU, model deployment, and region. A preview is not deployment proof.

Stop if the preview proposes an unexpected deletion or replacement, changes a
retained stateful resource, broadens PostgreSQL access beyond the documented
public-lane contract, weakens evaluation-storage restrictions, or differs from
the approved profile.

### 3. Apply the reviewed public resource graph

After explicit review:

```bash
FOUNDRY_FULL_INFRA_AUTHORIZED=true \
make foundry-provision \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
```

The full-infrastructure flag authorizes only the reviewed operation. It must
not be exported permanently or combined with `make foundry-release`.

### 4. Bootstrap PostgreSQL and the runtime connection

Administrator-owned schema and credential operations are separate:

```bash
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-postgres-schema
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-postgres-credentials
make foundry-postgres-readiness
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-runtime-connection
```

`foundry-postgres-credentials` can prompt for secrets. It creates or rotates
the least-privilege runtime credential, verifies it, and stores the runtime URL
only in the ignored local AZD environment. Production runtimes use
`DB_SCHEMA_MANAGED_EXTERNALLY=true`; they receive table DML and sequence usage,
not schema ownership, broad `CREATE`, role creation, or administrator access.

### 5. Return to reuse and release the application

After successful provisioning and output hydration, set the ignored profile to:

```dotenv
INFRASTRUCTURE_MODE=reuse
```

Reapply and run the normal release:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap
make foundry-release
```

This separation ensures application deployment is still proven through the
same app-only release gates rather than being inferred from infrastructure
creation.

## Teams Shared publication

Teams enablement is a separately reviewed post-release operation. It must not
add a VNet, private endpoint, private runner, private DNS, capability host, or
browser-facing backend ingress.

### 1. Verify Responses and the publication identity

```bash
make foundry-smoke \
  SMOKE_MESSAGE="Resolve delayed order ORD-1001"

az account show --query user.type --output tsv
```

The user type must be `user` for Shared publication. Verify that
`infra/foundry-hosted/teams-publication.json` has approved organization
metadata, `publishScope` is `Shared`, and `appVersion` is greater than the last
published version.

### 2. Plan the endpoint and Bot changes

```bash
make foundry-activity-plan
make foundry-teams-plan
make foundry-teams-preview
```

The Activity plan must retain Responses, Entra authorization, unrelated
protocols, and unrelated authorization schemes. The Bot what-if must contain
only the expected single-tenant Bot Service, `MsTeamsChannel`, and diagnostics
changes.

### 3. Deploy the reviewed Bot resources

```bash
FOUNDRY_FULL_INFRA_AUTHORIZED=true \
make foundry-teams-deploy-bot
```

Do not use the full-infrastructure flag for the normal application release.

### 4. Generate, inspect, publish, and verify

```bash
make foundry-teams-package
```

Package generation performs merge-preserving Activity apply, adding Activity
and `BotServiceRbac` while retaining Responses and Entra. Inspect the ignored
package and generated state under `.artifacts/teams-publication/`; do not
commit, attach, or paste them into release evidence.

Publish and verify:

```bash
make foundry-teams-publish
make foundry-teams-verify-local-state
```

Shared acceptance must verify:

1. a low-risk request completes;
2. high-risk and damaged-item requests display an Adaptive Card;
3. Approve resumes the exact checkpoint;
4. Reject escalates the exact checkpoint;
5. typed `Approve`, `Reject`, `yes`, or `no` does not resolve a Teams
   checkpoint;
6. replay is rejected;
7. the wrong user or conversation cannot use the card;
8. concurrent Approve and Reject actions cannot both resume; and
9. Responses behavior and the public browser path remain intact.

Cards contain only proposed-action labels and opaque action tokens. Token
hashes are bound in PostgreSQL to the Teams-origin workflow, checkpoint,
decision, user, conversation, expiry, and action batch.

## CI/CD and operation ownership

### Automatic and manually dispatched CI

| Workflow | Trigger and responsibility |
| --- | --- |
| `../../../.github/workflows/order-resolution-public-ci.yml` | Pull requests, pushes to `main`, and manual `workflow_dispatch`; performs operating-model routing/enforcement, backend lint/tests/evals when full validation is selected, frontend build, Docker E2E, deterministic design review, or quick validation. |

This workflow is credential-free. It does not log in to Azure, provision,
deploy, publish Teams packages, mutate PostgreSQL, or claim live release
evidence. Manual dispatch reruns CI only.

### Protected/manual Azure ownership

There is intentionally **no public-lane Azure deployment workflow** under the
repository's `.github/workflows` directory. Protected/manual operations are
owned by the authenticated operator shell:

| Operation | Owner and command |
| --- | --- |
| Routine application release | Authenticated operator; `make foundry-release` |
| Full public infrastructure | Authenticated operator after reviewed preview; `FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-provision` |
| PostgreSQL schema/runtime credential | PostgreSQL administrator through the explicit Make targets |
| Runtime project connection | Authenticated operator with full-infrastructure authority; `make foundry-runtime-connection` |
| Teams Bot/channel apply | Authenticated operator after reviewed what-if; `make foundry-teams-deploy-bot` |
| Shared Microsoft 365 publication | Interactive Azure CLI user; `make foundry-teams-publish` |
| Evidence retry or diagnostics | Same source and release context only; individual verification targets or a fresh complete release |

Do not add Azure credentials to the CI workflow to bypass this ownership model.
If protected GitHub deployment workflows are introduced in the future, the
engineering operating model, deployment flow, profile contract, evidence
authority, and this section must change together.

## Operations

### Verify the active deployment

For the selected local AZD environment:

```bash
make foundry-verify
make foundry-smoke \
  SMOKE_MESSAGE="Resolve delayed order ORD-1001"
```

`foundry-verify` checks exact immutable images, active ACA revisions, external
frontend/internal backend ingress, same-origin frontend/backend health, hosted
version/image and literal database placeholders, hosted RBAC, Application
Insights, runtime-secret connection, backend database parity, and externally
managed schema mode.

Run browser acceptance against the public frontend, never the internal backend:

```bash
WEB_URL="$(azd env get-value WEB_URL \
  --cwd infra/foundry-hosted \
  --no-prompt)"
PLAYWRIGHT_BASE_URL="$WEB_URL" make test-e2e
unset WEB_URL
```

For a low-risk direct Responses diagnostic:

```bash
HOSTED_AGENT_NAME="$(azd env get-value HOSTED_AGENT_NAME \
  --cwd infra/foundry-hosted \
  --no-prompt)"

azd ai agent show "$HOSTED_AGENT_NAME" --output json
azd ai agent invoke "$HOSTED_AGENT_NAME" \
  "Resolve delayed order ORD-1001" \
  --protocol responses \
  --conversation-id diagnostic-c1 \
  --no-prompt
azd ai agent invoke "$HOSTED_AGENT_NAME" \
  "Why was that resolution selected?" \
  --protocol responses \
  --conversation-id diagnostic-c1 \
  --no-prompt

unset HOSTED_AGENT_NAME
```

Use `make foundry-hosted-e2e` for approval/resume. Free-form `Approve` or
`Reject` is ordinary conversation text; the supported Responses decision is a
checkpoint-keyed structured `function_call_output`.

### Verify PostgreSQL

```bash
make foundry-postgres-readiness
```

Readiness requires the canonical TLS URL, matching runtime credentials,
password and Entra authentication, the expected database, the Azure-services
and operator-IP firewall rules, required schema objects, and least-privilege
runtime access. The application credential must not be upgraded to repair an
administrator-owned schema problem.

### Re-run hosted diagnostic gates

For controlled diagnostics in the same selected environment:

```bash
make foundry-hosted-e2e
make foundry-appinsights-connection
make foundry-telemetry
make foundry-eval
```

These commands have release-context and freshness requirements. Prefer a fresh
`make foundry-release` when source or deployed artifacts changed. Do not combine
evidence from different releases, source revisions, conversations, or time
windows.

### Evidence authority

| Authority | Purpose |
| --- | --- |
| [`.azure/deployment-plan.md`](.azure/deployment-plan.md) | Current deployment contract, authority boundaries, validation recipe, and recorded progress. |
| [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md) | Canonical dated public-lane release, incident, remediation, and acceptance ledger. |
| `.artifacts/releases/<release-id>/release.json` | Generated v1 machine-readable authority record for one local release window. |
| `.artifacts/releases/<release-id>/evidence/` | Ignored detailed preview, preflight, deployment, E2E, evaluation, and telemetry evidence. |
| `.artifacts/releases/<release-id>/logs/` | Ignored local release logs. |

A release claim requires fresh, same-window, secret-free evidence for preview,
capacity, exact deployment state, smoke, three-conversation hosted E2E,
Application Insights connection, evaluation, telemetry, and finalization.
Finalization rejects missing, stale, cross-window, failed, secret-bearing, or
inconsistent artifacts and an app-only-start-to-telemetry-success interval
above 15 minutes.

Historical ledger entries remain historical. Checkboxes, source code, local
tests, Bicep compilation, package validation, a preview, or a partially
completed Azure operation do not establish that the current source is live.

### Application rollback

Application rollback requires operator review; there is no generic
one-command rollback target.

1. Preserve and finalize the failed release record when possible.
2. Identify a previously verified hosted-agent version and backend/frontend
   immutable revisions from a successful authority record.
3. Confirm the rollback changes only application versions. It must not mutate
   PostgreSQL, models, capacity, project connections, role assignments,
   monitoring, Bot resources, or other shared/stateful infrastructure.
4. Reactivate or restore only those previously verified application versions
   through the approved Azure operational procedure.
5. Re-run exact deployment verification, Responses smoke, browser acceptance,
   hosted E2E, evaluation, telemetry, and fresh aggregate evidence.
6. Record the rollback and its evidence in the canonical ledger.

Do not use a stale image tag, rebuild old source under a new tag, reset the
database, or run full provisioning as an application rollback.

### Teams rollback without harming Responses

1. Remove the Shared catalog entry through Microsoft 365 governance.
2. Review the non-destructive plan:

   ```bash
   make foundry-teams-rollback-plan
   ```

3. Remove Activity and Bot authorization while retaining Responses, Entra, and
   unrelated endpoint state:

   ```bash
   make foundry-activity-rollback
   ```

4. Re-run Responses smoke:

   ```bash
   make foundry-smoke \
     SMOKE_MESSAGE="Resolve delayed order ORD-1001"
   ```

Microsoft does not document a Foundry unpublish API. Bot Service retention or
deletion is a separate reviewed ARM/Bicep lifecycle decision. Teams rollback
must not delete the Foundry project, hosted agent, PostgreSQL data, Responses
protocol, Entra authorization, or browser topology.

## Troubleshooting

### Local workstation and stack

| Symptom | Action |
| --- | --- |
| Python virtual-environment creation fails | Install Python 3.13 with `venv`, remove only the local `backend/.venv`, and rerun `make bootstrap`. |
| Locked wheel or image dependency installation fails | Run `make foundry-python-wheelhouse`; verify the CPython 3.13 Linux AMD64 hash-locked wheelhouse completes. Do not add online package resolution to an image build. |
| Frontend install or build fails | Rerun `make bootstrap`, then `npm run build` from `frontend/`. Do not edit `package-lock.json` manually. |
| Playwright reports a missing browser | Run `cd scripts/playwright && npx playwright install --with-deps chromium`, or use `make docker-test`. |
| PostgreSQL is unavailable | Run `make up` or `make test`; confirm Docker is running and the local URL still targets localhost. |
| Ports are already in use | Stop the conflicting local process or use `make test-e2e`, which selects isolated dynamic ports. |
| Local output differs from hosted | Confirm `RUNTIME_TARGET=local_maf`, `STORE_PROVIDER=postgres`, and that no unintended Foundry wrapper settings override local mode. |

### Profile, authentication, and preview

| Symptom | Action |
| --- | --- |
| Profile validation fails | Compare the ignored file with `foundry-public.env.example`; remove unknown/duplicate keys and replace every placeholder with an approved non-secret value. |
| Azure CLI uses the wrong subscription | Stop, reload and validate the ignored profile, run `az account set`, and repeat the non-printing ID comparison. |
| `azd` uses the wrong environment | Re-run `make foundry-profile-apply` and `make foundry-bootstrap`; do not reuse an unrelated AZD environment. |
| A required binary is missing | Install the named prerequisite (`az`, `azd`, `jq`, `psql`, Python, Make, or Docker) and rerun the failed stage rather than bypassing it. |
| Reuse preview proposes any mutation | Stop the app-only release. Review drift through the explicit full-infrastructure path; never accept create/update/delete/replace in reuse mode. |
| Full preview proposes unexpected stateful or access changes | Stop and reconcile the profile/design before apply. A successful preview is not permission to normalize unrelated drift. |
| Capacity preflight fails | Resolve the exact service availability, model/version/SKU/capacity, regional quota, or retained-resource mismatch. Do not silently change the approved model set or reduce required capacity. |
| Azure AI Search is unavailable in the selected region | Select an approved Search region in the external profile and review a new preview; do not move unrelated resources without approval. |

### PostgreSQL and runtime connection

| Symptom | Action |
| --- | --- |
| Schema bootstrap fails | Verify the administrator credential, operator firewall rule, TLS/FQDN, database, and `psql`; do not grant schema ownership to the runtime role. |
| Runtime credential provisioning fails | Re-run `make foundry-postgres-credentials` with valid administrator and hosted passwords; output is intentionally withheld. |
| Readiness reports URL mismatch | Ensure `DATABASE_URL` and `RUNTIME_DATABASE_URL` are identical canonical `postgresql+psycopg` URLs for the configured server, runtime user, database, port 5432, and `sslmode=require`. |
| Readiness reports firewall drift | Restore only the documented Azure-services and operator-IP rules through the reviewed infrastructure procedure. Do not add broad ad hoc client rules. |
| Runtime startup attempts DDL | Confirm the deployed runtime uses `DB_SCHEMA_MANAGED_EXTERNALLY=true` and the administrator schema bootstrap completed. Do not grant runtime `CREATE`. |
| Runtime-secret connection check fails | Verify the deterministic project `CustomKeys` connection. Full-authority convergence uses `make foundry-runtime-connection`; app-only may only check it. |
| Hosted metadata exposes a database URL | Treat this as a release blocker. Hosted definitions and metadata must contain only `${{connections.orderresolutionruntimesecrets.credentials.database_url}}`. |

### Deployment, Responses, evaluation, and telemetry

| Symptom | Action |
| --- | --- |
| Release router rejects the change | An infrastructure change cannot flow through automatic app-only authority. Use a reviewed full preview/apply, then return to reuse. |
| Hosted version creation is unauthorized | Verify the interactive operator has the required Foundry project data-plane role. Do not broaden the hosted runtime identity beyond its documented account-scoped model-use role. |
| Evaluator RBAC preflight fails | Strict cloud evaluation requires the release identity to have account-scoped `Foundry User` and `Cognitive Services OpenAI User`; assign only those reviewed roles at the Foundry account. |
| Azure CLI asks for login | Refresh the interactive login in the approved tenant, reselect the profile subscription, and start a new release window. Do not reuse a release that failed during authentication. |
| ACR or image deployment fails | Verify ACR availability, scoped pull permissions, successful digest resolution, and the exact existing Container Apps target. |
| Hosted invocation returns transient `404`, `409`, `429`, or `5xx` | Retry through the bounded smoke/E2E tooling. For session quota `429`, reduce synthetic concurrency or resolve quota before another release. |
| Structured approval is treated as text | Use the repository E2E path and checkpoint-keyed `function_call_output`; free-form approval words are conversation text. |
| Approval affects the wrong or no workflow | Verify the checkpoint is pending, belongs to the same Responses conversation, and originated from Responses. Teams-origin checkpoints require their card action. |
| Exact deployment verification fails | Compare active revisions, immutable images, ingress, same-origin health, hosted version/placeholders, App Insights, runtime connection, and database parity. Do not continue to evidence. |
| Evaluation returns zero rows | Confirm fresh E2E evidence exists and allow only the bounded error-free ingestion retry. A real evaluator/service error is not a zero-row retry case. |
| Any evaluator fails, errors, or skips | Treat the release as failed. An aggregate score cannot override an individual failed/errored/skipped result. |
| Telemetry is delayed | Allow the bounded ingestion window and retry only within the same source/deployment/release context. Do not redeploy solely to wait for ingestion. |
| Evidence is stale, mixed, or over 15 minutes | Treat finalization as failed, preserve the record, diagnose the slow or stale stage, and run a new complete release window. |

### Teams and Adaptive Cards

| Symptom | Action |
| --- | --- |
| Shared publication rejects the identity | Confirm `az account show --query user.type --output tsv` returns `user`; service-principal, managed-identity, and OIDC contexts are unsupported for Shared publication. |
| Bot or channel what-if is unexpected | Stop before apply. Review the profile, hosted identity, endpoint, Log Analytics target, and Bicep changes. |
| Bot deployment refuses to run | Re-run the reviewed what-if, then invoke the target with `FOUNDRY_FULL_INFRA_AUTHORIZED=true` for that command only. |
| Package metadata is rejected | Replace example organization metadata and increment `appVersion`; never reuse or decrease a published version. |
| App cannot be acquired in Teams | Check custom-app and app-permission policies for the publishing user. Do not switch to Tenant publication as a workaround. |
| Adaptive Card returns `409` | The action is already used, superseded, expired, or no longer pending. Use the current pending card. |
| Adaptive Card returns `403` | The action belongs to another user or conversation. Use it only where it was issued. |
| Typed approval text does nothing | Expected. Teams approval authority is the bound Adaptive Card action, not message text. |
| Teams appears to use older behavior | Start a fresh Teams session after the approved hosted version and publication update; do not infer the active version from an old conversation. |
| Teams does not stream tokens | Expected for the current direct Activity handler. |

For prior root causes and exact remediations, consult the
[public delivery ledger](docs/design/issues-changes-fixes.md). Do not copy live
identifiers from historical evidence into new documentation.

## Project map

| Path | Responsibility |
| --- | --- |
| `backend/` | FastAPI wrapper, shared MAF workflow, hosted Responses/Activity entrypoint, persistence, tests, and evaluations |
| `backend/app/api/v1/` | Stable HTTP, workflow, HITL, native SSE, and additive projection routes/contracts |
| `backend/app/modules/order_resolution/` | Application service, domain seams, ports, and event projection |
| `backend/app/maf/` | Sequential MAF prompts, agents, tools, executors, runner, middleware, and workflow |
| `backend/app/infrastructure/` | PostgreSQL, Foundry, MCP/RAG, checkpoint, idempotency, workflow, and Teams action adapters |
| `backend/foundry/` | Responses and additive Activity hosting in one process |
| `frontend/` | React/Vite workflow UI, same-origin browser client, and optional read-only selected-thread experience |
| `infra/foundry-hosted/` | Public Foundry, Container Apps, PostgreSQL, monitoring, Search, Bot/Teams, AZD, and Bicep assets |
| `deployment/` | Portable external-profile parser, application helper, example profile, and profile tests |
| `scripts/foundry/` | Preview, capacity, PostgreSQL, packaging, deployment, Teams, verification, E2E, evaluation, telemetry, and evidence automation |
| `scripts/playwright/` | Workflow browser regression suite |
| `scripts/skills/` | Change routing, operating-model enforcement, and deterministic review gates |
| `docs/` | Product/design contracts, manual testing, deployment flow, Teams integration, and release history |
| `.azure/deployment-plan.md` | Deployment authority, validation recipe, stop conditions, and progress record |
| `agents.md` | Coding-agent boundaries, invariants, and required verification |

## Documentation map

The public lane currently retains its `docs/design/` documentation layout.
Its product requirements file is still present; the project has not moved to
the private lane's separate functional/business/technical specification
filenames.

### Product and behavior

- Product requirements and acceptance criteria:
  [docs/design/prd.md](docs/design/prd.md)
- User journey:
  [docs/design/userflow.md](docs/design/userflow.md)
- HITL and decision-authorization rules:
  [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
- Manual local and hosted test scenarios:
  [docs/manual-testing.md](docs/manual-testing.md)

### Architecture and technical contracts

- System, process, network, identity, persistence, and scenario views:
  [docs/design/architecture.md](docs/design/architecture.md)
- API, event, persistence, and telemetry schema:
  [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
- Technology and dependency baseline:
  [docs/design/techstack.md](docs/design/techstack.md)
- Repository structure:
  [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Backend runtime details:
  [backend/README.md](backend/README.md)
- Frontend runtime details:
  [frontend/README.md](frontend/README.md)

### Delivery and operations

- Canonical engineering operating model:
  [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Command-to-stage deployment flow:
  [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
- Foundry-hosted infrastructure and release guide:
  [infra/foundry-hosted/README.md](infra/foundry-hosted/README.md)
- Script ownership and release route:
  [scripts/README.md](scripts/README.md)
- Teams topology, publication, card security, and rollback:
  [docs/design/teams-foundry-integration.md](docs/design/teams-foundry-integration.md)
- Current deployment contract and progress:
  [.azure/deployment-plan.md](.azure/deployment-plan.md)
- Canonical dated release and incident evidence:
  [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
- Private/public parity contract:
  [docs/design/foundry-private-upgrade.md](docs/design/foundry-private-upgrade.md)

Read [agents.md](agents.md) and
[.github/copilot-instructions.md](.github/copilot-instructions.md) before
changing this project. They define the single-workflow boundary, stable event
contracts, PostgreSQL and HITL security rules, public deployment ownership,
documentation obligations, and required verification.
