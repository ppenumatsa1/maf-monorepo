# Order Resolution - Azure Hosted

## Goal

Run one explainable Microsoft Agent Framework (MAF) order-resolution workflow
as a conventional Azure application:

- FastAPI is the only application host, locally and in Azure;
- a React/Nginx frontend and FastAPI backend run as separate Azure Container
  Apps;
- PostgreSQL durably stores workflow runs, events, messages, checkpoints,
  approvals, and idempotency records;
- low-risk synthetic cases complete automatically;
- high-risk and damaged-item cases pause for human-in-the-loop (HITL)
  approval;
- Foundry supplies optional model inference and report-only evaluation, never
  application hosting; and
- Application Insights correlates the exact deployed release scenarios.

This lane exists for teams that want the MAF workflow hosted entirely in their
FastAPI application while still using Foundry models and evaluators. It is
deliberately different from a Foundry-hosted-agent lane: there is no hosted
agent, Responses application host, capability host, or second orchestration
runtime.

The project uses synthetic data. Do not commit customer data, credentials,
connection strings, operator IP addresses, generated endpoints, release
artifacts, or tenant-specific secrets.

## Choose a path

| Goal | Start here |
| --- | --- |
| Install and run locally | [Local development](#local-development) |
| Verify workflow and HITL behavior | [Workflow validation](#workflow-validation) |
| Run local quality gates | [Test gates](#test-gates) |
| Configure an Azure target | [Portable target and profile configuration](#portable-target-and-profile-configuration) |
| Deploy application changes to an existing environment | [Routine app-only release](#routine-app-only-release) |
| Create a clean environment | [Clean bootstrap](#clean-bootstrap) |
| Reconcile existing infrastructure intentionally | [Infrastructure reconciliation](#infrastructure-reconciliation) |
| Understand GitHub automation | [CI/CD ownership](#cicd-ownership) |
| Operate a deployed release | [Operations](#operations) |
| Recover from a bad release | [Rollback](#rollback) |
| Diagnose a failure | [Troubleshooting](#troubleshooting) |

## Architecture at a glance

1. The browser calls the external frontend Container App.
2. Frontend Nginx proxies same-origin `/api` requests to the backend Container
   App.
3. The backend Container App hosts FastAPI and the only MAF workflow runtime.
4. The FastAPI-hosted workflow retrieves order/policy context, optionally
   calls the configured Foundry model deployment, and persists durable state
   in PostgreSQL.
5. Native SSE drives the operator timeline and durable HITL controls.
6. Optional AG-UI and CopilotKit views select an existing durable thread and
   expose only a redacted projection.
7. Foundry evaluation judges captured HTTP workflow results after execution;
   it cannot start, resume, or change a workflow.
8. Application Insights receives correlated workflow, model, HITL, and release
   telemetry.

This public Azure-hosted lane contains both frontend and backend Container
Apps. Only the frontend is public to the browser. The app-only release
converges the backend to internal ingress and configures the frontend proxy to
reach it.

```text
Operator browser
        |
        v
External React/Nginx frontend Container App
        |
        | same-origin /api proxy
        v
Internal FastAPI/MAF backend Container App
        |                       |
        |                       +--> Foundry model inference
        v
Azure Database for PostgreSQL

Captured HTTP workflow results --> Foundry report-only evaluation
Correlated runtime/HITL spans  --> Application Insights
```

See the [architecture document](docs/architecture.md) for the complete
logical, process, development, physical, and scenario views.

## Behavioral contracts

### One workflow and one application host

- FastAPI is the sole MAF application host.
- The same sequential MAF workflow runs locally and in the backend Container
  App.
- When Foundry model settings are absent, deterministic triage remains inside
  that workflow; it does not select a fallback orchestrator.
- Foundry is limited to model inference and report-only evaluation.
- This lane has no Microsoft Teams, Bot Service, Activity protocol, or Teams
  publication contract.

### Durable HITL

- `ORD-1001` is the low-risk baseline and normally completes without HITL.
- `ORD-1009` is the high-risk baseline and requires HITL.
- Damaged-item and `manual_review` policy cases require HITL.
- The workflow persists a checkpoint before emitting an approval request.
- Approve resumes the exact checkpoint and submits the protected action once.
- Reject resolves the checkpoint as an escalation without submitting the
  proposed action.
- PostgreSQL, not browser memory, is the authority for pending checkpoints and
  approval history.

The exact decision rules are in
[HITL approval conditions](docs/hitl-approval-conditions.md).

### Stable event and API boundaries

The stable native SSE event types are:

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

`GET /api/chat/stream/{thread_id}/rich` remains an additive native-rich
envelope for existing consumers. It contains native payload data and is not an
assistant contract.

`GET /api/chat/stream/{thread_id}/ag-ui` is an additive, read-only, redacted
projection of one existing durable thread.

`GET /api/copilotkit/info` and `GET /api/copilotkit` return static discovery.
`POST /api/copilotkit` uses only an existing `threadId` as a selector and
discards compatible messages, state, tools, context, and forwarded properties.
It cannot create, approve, reject, resume, or otherwise mutate a workflow.

AG-UI and CopilotKit must never expose raw native payloads, order or policy
data, MCP results, tool arguments/results, prompts, model output, checkpoint
state, credentials, or secrets. Their failure must not make native SSE,
durable history, or HITL controls unavailable. CopilotKit here means
`@copilotkit/react-core`, not the GitHub Copilot SDK.

### Release boundary

- Routine releases update only backend and frontend Container App revisions.
- PostgreSQL and its `maf_workflow` database are retained.
- Infrastructure reconciliation is never inferred from changed files.
- Release success requires fresh deployment verification, smoke, hosted
  browser E2E, three HTTP domain scenarios, report-only evaluation, exact
  Application Insights correlation, and final evidence from one release
  window.
- Finalization enforces the configured app-only-to-telemetry time budget.

## Prerequisites

### Local development

- Git
- Make
- Python 3.13
- Node.js 20 and npm
- Docker with Docker Compose
- Chromium dependencies when running Playwright outside its container

### Azure operations

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- Bicep CLI, or Azure CLI permission to install it
- Docker for release images and local Docker E2E
- Access to the selected Azure subscription and existing AZD environment
- Permission to read the selected Container Apps, ACR, PostgreSQL, Foundry,
  Log Analytics, and Application Insights resources
- Deployment permission only when performing an authorized release or
  reconciliation

GitHub CLI is optional; repository workflows can also be inspected and
dispatched from the GitHub Actions UI.

## Local development

Run commands in this project directory:

```bash
cd agents/order-resolution/azure-hosted
```

### 1. Configure the backend

Create the ignored local environment file:

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

The local application always uses the MAF workflow. PostgreSQL-backed tests and
E2E targets supply their own isolated database settings. For a manually
managed local server, review these optional settings in `backend/.env`:

```dotenv
APP_ENV=local
STORE_PROVIDER=postgres
MEMORY_PROVIDER=postgres
MCP_SERVER_URL=http://localhost:8011/mcp
```

Foundry model inference is optional locally:

```dotenv
FOUNDRY_PROJECTS_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL_DEPLOYMENT_NAME=<chat-deployment-name>
```

Do not put access tokens or production connection strings in the tracked
example file.

### 2. Install dependencies

```bash
make bootstrap
```

This creates `backend/.venv`, installs `backend/requirements-dev.txt`, installs
the frontend packages, and installs the Playwright package dependencies.

To install one side only:

```bash
make install-backend
make install-frontend
```

### 3. Start the application

The simplest path starts PostgreSQL, the mock MCP server, backend, and frontend
through Docker Compose:

```bash
make up
```

Open:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/api/health`

Inspect or stop the stack:

```bash
make ps
make logs
make down
```

To run development servers separately, first provide PostgreSQL and any desired
MCP service, then run these in separate terminals:

```bash
make run-backend
make run-frontend
```

The frontend development server defaults to the backend at
`http://localhost:8000`. See the
[frontend guide](frontend/README.md) for runtime endpoint precedence.

## Workflow validation

Use the UI or API to verify these baseline scenarios:

1. Submit an `ORD-1001` delayed-order request.
2. Confirm the ordered triage, policy retrieval, resolution, and terminal
   events appear without `hitl.request`.
3. Submit an `ORD-1009` request.
4. Confirm `checkpoint.created` and `hitl.request` appear before any protected
   resolution.
5. Approve the pending checkpoint and confirm one `hitl.response` followed by
   a completed `workflow.output`.
6. Run a damaged-item case and verify it also pauses for HITL.
7. Reopen each thread through the workflow/history views and confirm the
   transcript, events, checkpoint, and decision remain available.

For the complete operator matrix:

```bash
make manual-matrix
```

To target another authorized backend:

```bash
API_URL="https://<backend-host>" make manual-matrix
```

The [manual testing guide](docs/manual-testing.md) documents the complete
ORD-1001 through ORD-1010 matrix, durable-state checks, selected-thread safety
checks, and Azure parity procedure.

## Test gates

### Required local gates

```bash
make test
make eval-backend
make test-e2e-selected
make test-e2e
./scripts/skills/design-review-skill.sh
```

- `make test` runs Ruff and backend tests.
- `make eval-backend` runs deterministic workflow contract evaluation.
- `make test-e2e-selected` focuses on AG-UI/CopilotKit selected-thread
  boundaries.
- `make test-e2e` covers workflow and selected-thread browser behavior.
- The design-review script consolidates the deterministic architecture and
  contract checks.

The backend test, deterministic evaluation, and local browser targets use
isolated Compose projects and dynamically selected ports. They do not use a
developer's default PostgreSQL database or fixed app ports.

### Additional gates

```bash
make format-check
make eval-foundry
make docker-test
make validate-full
```

`make eval-foundry` is report-only and requires Foundry configuration.
`make docker-test` is optional on managed devices where Docker npm egress is
blocked. The GitHub Actions **Required cloud Docker E2E** job is the
authoritative exact-image Docker/browser gate for full-validation changes.

For release-contract and infrastructure-source checks:

```bash
make release-source-validation
make test-subscription-portability
make bicep-build
make release-infra-mock-test
```

These commands validate source intent. They are not Azure deployment evidence.

## Portable target and profile configuration

### Profile ownership

Azure target values belong in a validated, ignored operator profile outside
tracked documentation and examples. Profiles are secret-free data files, not
shell scripts. The default path is `.azure/azure-hosted.env`; set
`AZURE_HOSTED_PROFILE` to select another ignored regular file.

The minimum target identity is:

```dotenv
CONTRACT_VERSION=1
DEPLOYMENT_LANE=azure-hosted
AZURE_ENV_NAME=<azd-environment>
AZURE_TENANT_ID=<tenant-guid>
AZURE_SUBSCRIPTION_ID=<subscription-guid>
AZURE_RESOURCE_GROUP=<resource-group>
AZURE_LOCATION=<azure-location-name>
NAME_PREFIX=<3-to-15-character-prefix>
POSTGRES_DATABASE_NAME=maf_workflow
```

The bootstrap example documents additional approved model, PostgreSQL, and
capacity selectors. Do not add credentials, connection strings, tokens,
operator IPs, image references, generated resource IDs, or endpoints.

Validate the selected profile without sourcing it:

```bash
profile_path="${AZURE_HOSTED_PROFILE:-$PWD/.azure/azure-hosted.env}"
deployment/profile.sh validate "$profile_path"
```

### Authenticate and verify context

Authenticate without recording command output in documentation or evidence:

```bash
az login --tenant "<tenant-id>" --use-device-code \
  --only-show-errors --output none
```

Load the profile through its parser, select the subscription, and compare the
active context:

```bash
source deployment/profile.sh
profile_path="${AZURE_HOSTED_PROFILE:-$PWD/.azure/azure-hosted.env}"
deployment_profile_load "$profile_path"
deployment_profile_validate

profile_subscription="$(deployment_profile_value AZURE_SUBSCRIPTION_ID)"
az account set --subscription "$profile_subscription"
actual_subscription="$(az account show --query id --output tsv)"

if [[ "$actual_subscription" != "$profile_subscription" ]]; then
  echo "STOP: Azure CLI does not match the selected profile." >&2
  exit 1
fi

unset actual_subscription profile_path profile_subscription
```

The selected AZD environment must contain matching tenant, subscription,
resource group, location, service outputs, model/evaluation settings, and
monitoring outputs. Release scripts fail closed on a mismatch or a tracked,
symlinked, or non-ignored in-repository profile.

Prepare the release context without deploying:

```bash
make release-profile-apply
make release-app-dry-run
```

## Routine app-only release

Use this path for normal backend, frontend, dependency, runtime-configuration,
or release-automation changes against an existing Azure-hosted environment:

```bash
make release-app
```

The target:

1. runs release preflight and source-contract validation;
2. deploys backend and frontend through their existing AZD services;
3. pins deployed images to immutable ACR digests;
4. converges backend ingress to internal and frontend ingress to external;
5. points the frontend proxy at the internal backend;
6. verifies the active revisions and images;
7. runs smoke, hosted browser E2E, and three HTTP/durable domain scenarios;
8. correlates the exact domain-scenario thread/workflow pairs in Application
   Insights;
9. runs report-only Foundry evaluation against the captured HTTP results; and
10. aggregates final release evidence.

An app-only release must not:

- run `azd provision`;
- reconcile shared infrastructure;
- recreate, replace, reset, or migrate PostgreSQL implicitly;
- change PostgreSQL network access or administrator configuration;
- add a Foundry application host;
- claim success from local tests, source configuration, historical telemetry,
  or an earlier release bundle.

The validation sequence is also available for an already deployed candidate:

```bash
make release-validate
```

Use it only with the matching release context and deployed source. A new
source revision requires a new complete release window.

## Clean bootstrap

Use bootstrap only for a fresh, approved target.

### 1. Supply untracked operator inputs

```bash
export POSTGRES_BOOTSTRAP_ALLOWED_IP="<operator-public-ipv4>"
export BACKEND_IMAGE="<registry>/<repository>:<tag>"
export FRONTEND_IMAGE="<registry>/<repository>:<tag>"
export POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME="<entra-user-principal-name>"
export POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID="<entra-object-id>"
```

Optional Foundry deployment names, versions, SKUs, and capacities may also be
set as environment variables before preparation. The preparation script
validates supported values and writes them to the selected local AZD
environment without adding them to tracked profiles.

### 2. Prepare and preview

```bash
make prepare-bootstrap
azd provision --preview --environment "<azd-environment>" --no-prompt
```

Review the full subscription-scope preview. Stop on a target mismatch,
unexpected deletion/replacement, unsupported model SKU, PostgreSQL or
Container Apps capacity failure, excessive privilege, or an unplanned public
access change.

### 3. Apply only after authorization

```bash
azd provision --environment "<azd-environment>" --no-prompt
```

Bootstrap creates the initial platform and runs the PostgreSQL Entra grant
hook. It is not the routine deployment path.

### 4. Transition to steady state

```bash
make prepare-steady-state
```

The transition verifies the retained PostgreSQL server and database, deletes
and verifies removal of the exact `allow-bootstrap-runner` firewall rule, then
sets the local AZD environment to `steadyState`. It fails closed when cleanup
or identity verification is ambiguous.

In steady state, PostgreSQL and both Container App modules are excluded from
IaC reconciliation. Routine application delivery then uses:

```bash
make release-app
```

## Infrastructure reconciliation

Infrastructure reconciliation is exceptional and separate from application
delivery. A changed Bicep file does not authorize it.

Preview without mutation:

```bash
make release-infra-preview
```

Review the fresh what-if. It must exclude PostgreSQL and the application
Container Apps in steady state. Stop on any unexpected stateful mutation,
network weakening, identity/RBAC expansion, resource replacement, or target
mismatch.

When reconciliation has been explicitly authorized:

```bash
make release-infra-reconcile
```

Direct invocation is execution intent. The target obtains and validates a new
what-if in the same invocation before apply; it does not accept a historical
preview, caller-supplied digest, or separate approval reference. Afterward,
run a fresh app-only release if application revisions or release evidence also
need to change.

The complete stage model is in
[deployment flow](docs/deployment-flow.md).

## CI/CD ownership

The repository owns one path-scoped workflow:

- [Order Resolution Azure-Hosted CI](../../../.github/workflows/order-resolution-azure-hosted-ci.yml)

It runs only for this lane or changes to its own workflow definition.

### Pull requests

Pull requests are credential-free for source validation:

- operating-model routing and enforcement;
- release-asset and reconciliation contract tests;
- backend lint, tests, and deterministic evaluation when full validation is
  selected;
- frontend build;
- local workflow and selected-thread Playwright coverage;
- deterministic design review; and
- exact-image Docker E2E when full validation is selected.

Pull requests do not deploy Container Apps or mutate Azure infrastructure.

### Protected `main` release

On a qualifying `main` push, the protected **Required cloud Docker E2E** job:

1. authenticates with GitHub OIDC through the configured GitHub environment;
2. builds the backend and frontend images once;
3. runs Docker E2E against those exact images;
4. pushes and deploys their immutable ACR digests;
5. updates only the existing Container Apps;
6. runs release verification, smoke, hosted browser E2E, the three HTTP domain
   scenarios, telemetry correlation, report-only evaluation, and final
   aggregation; and
7. uploads the sanitized release bundle even when a later gate fails.

The workflow uses one serialized lane release concurrency group and does not
run infrastructure reconciliation. Automation resolves non-secret target
selection from its protected environment; local operators use the ignored
profile. Credentials and tokens must never be stored in profiles.

`workflow_dispatch` provides an explicit validation entry point, but the
workflow's Azure deployment steps remain restricted to a qualifying `main`
push.

## Operations

### Verify local health

```bash
curl --fail --silent --show-error http://localhost:8000/api/health
curl --fail --silent --show-error http://localhost:5173/health
```

### Verify an existing Azure deployment

Read endpoints from the selected AZD environment:

```bash
API_URL="$(azd env get-value API_URL --environment "<azd-environment>")"
WEB_URL="$(azd env get-value WEB_URL --environment "<azd-environment>")"

curl --fail --silent --show-error "$API_URL/api/health"
curl --fail --silent --show-error "$WEB_URL/health"
curl --fail --silent --show-error "$WEB_URL/api/health"
```

The frontend health check proves public ingress. The proxied API check proves
the frontend can reach the internal backend.

Run the package smoke contract:

```bash
infra/azure-apphosted/runtime/smoke-test.sh "$API_URL" "$WEB_URL"
```

When model inference is expected:

```bash
EXPECT_TRIAGE_MODE=foundry_models \
  infra/azure-apphosted/runtime/smoke-test.sh "$API_URL" "$WEB_URL"
```

### Run parity checks

```bash
PARITY_LOCAL_API_URL=http://localhost:8000 \
PARITY_LOCAL_WEB_URL=http://localhost:5173 \
PARITY_AZURE_API_URL="$API_URL" \
PARITY_AZURE_WEB_URL="$WEB_URL" \
make parity-all
```

Parity reports are generated under `scripts/parity/reports/`. They are useful
diagnostics, not a replacement for the canonical release bundle.

### PostgreSQL operations

PostgreSQL is the durability authority. Routine releases must leave the server,
database, schema, and data intact. If the server is stopped or unavailable,
restore the existing server through an approved Azure operation, verify its
identity and readiness, then retry the application release. Do not bootstrap a
replacement database, add a temporary public bypass, or grant schema/admin
privileges to the runtime as a recovery shortcut.

### Telemetry, evaluation, and evidence authority

Use these sources in this order:

1. [Deployment plan](.azure/deployment-plan.md) for current committed
   deployment status and acceptance.
2. [Delivery evidence ledger](docs/issues-changes-fixes.md) for dated
   releases, incidents, and remediations.
3. `.artifacts/releases/<release-id>/release.json` for generated release
   state and timing.
4. `.artifacts/releases/<release-id>/evidence/` for structured release-local
   evidence.
5. `.artifacts/releases/<release-id>/logs/` for diagnostics and browser output.

Do not copy exact release IDs, endpoints, image digests, correlation IDs,
evaluation run IDs, or telemetry counts into this README. Their authoritative
home is the deployment plan, evidence ledger, or generated release bundle.

`make eval-foundry` is report-only. In a release, evaluation is still a
blocking quality gate: it must complete with zero failed or errored rows.
Telemetry validation uses only the three exact HTTP domain-scenario
`thread_id`/`workflow_run_id` pairs from the same release window and requires
nonzero correlated telemetry with zero relevant exceptions.

## Rollback

Rollback is application-only unless a separately reviewed infrastructure
recovery is required.

1. Stop promoting the failed release and retain its failed evidence bundle.
2. Restore the last known-good backend/frontend source or image inputs.
3. Run the normal app-only path:

   ```bash
   make release-app
   ```

4. Require a new release ID and a complete fresh validation window.
5. Confirm the frontend proxy targets the restored internal backend revision.
6. Confirm PostgreSQL retained the existing workflow and HITL history.
7. Record the rollback result only in the deployment plan and evidence ledger.

Do not use `azd provision`, infrastructure reconciliation, database
recreation, schema rollback, or data deletion merely to roll back application
code. If only one Container App changed before a failure, still converge both
services through the same app-only release so the deployed pair and evidence
remain coherent.

## Troubleshooting

### Local installation and runtime

| Symptom | Action |
| --- | --- |
| `python3 -m venv` fails | Install Python 3.13 and recreate `backend/.venv`; do not reuse an incompatible environment. |
| Backend imports or `pytest` are missing | Run `make install-backend`, then `make test`. |
| Frontend packages or Vite are missing | Run `make install-frontend`, then `npm run build` from `frontend/`. |
| Playwright browser is missing | From `scripts/playwright/`, run `npx playwright install --with-deps chromium`, then rerun the E2E target. |
| PostgreSQL is unavailable | Run `make up` or use the isolated `make test`/`make test-e2e` targets. Do not point tests at an unrelated developer database. |
| Local ports are occupied | Stop the conflicting process or use the isolated test targets, which allocate dynamic ports. |
| MCP calls fail locally | Confirm `make up` started `mock-mcp`, or run `make run-mock-mcp` and check `MCP_SERVER_URL`. |
| Model inference is not used | Confirm both `FOUNDRY_PROJECTS_ENDPOINT` and `FOUNDRY_MODEL_DEPLOYMENT_NAME` are present. Without them, deterministic triage remains inside the same MAF workflow. |
| `make docker-test` cannot fetch npm packages | Treat the local Docker gate as blocked by device/network policy and rely on the required cloud Docker job; do not claim a local pass. |

### Workflow, HITL, and selected-thread views

| Symptom | Action |
| --- | --- |
| `ORD-1001` pauses for HITL | Inspect the issue classification, amount/risk, damaged-item signal, and retrieved `manual_review` policy. |
| `ORD-1009` does not pause | Verify the baseline fixture, emitted amount, and `hitl-approval-conditions.md`; run `make eval-backend`. |
| Approval does not resume | Confirm the checkpoint is still pending and the response uses the exact checkpoint ID. Replayed decisions must not create a second terminal action. |
| Workflow disappears after restart | Check PostgreSQL connectivity and the durable workflow/message/event tables. Native SSE is live delivery; durable APIs are the recovery read model. |
| `/rich` shows broader data than AG-UI | Expected. `/rich` is the native-rich contract and must never be passed to the assistant UI. |
| AG-UI or CopilotKit exposes business payloads | Stop the release. Run `make test-e2e-selected` and review the projection allowlist before retrying. |
| CopilotKit cannot start or approve a workflow | Expected. It is a read-only existing-thread selector; use the native workflow and HITL APIs. |

### Target, authentication, and profiles

| Symptom | Action |
| --- | --- |
| Profile validation fails | Check the approved keys, GUID shape, lowercase location, name-prefix length, and absence of shell syntax or secrets. |
| Azure CLI uses the wrong subscription | Stop, reload the ignored operator profile through `deployment/profile.sh`, select the profile subscription, and repeat the comparison. |
| AZD target values do not match | Select or reconstruct the intended AZD environment. Do not override release guards to force a different target. |
| Bootstrap profile is rejected | Validate the ignored operator profile, then align any still-required compatibility input and rerun `make test-subscription-portability`. |
| Bicep build fails | Run `make bicep-build` and fix the reported template or parameter binding before any preview. |
| Preview reports quota or SKU failure | Resolve capacity in the approved target or choose an explicitly reviewed supported SKU. Do not silently switch subscription, region, or model family. |

### App-only deployment

| Symptom | Action |
| --- | --- |
| Preflight fails | Inspect the current release logs and run `make release-source-validation`; do not skip the failing contract. |
| Backend or frontend deployment fails | Inspect `.artifacts/releases/<release-id>/logs/`; verify AZD authentication, service outputs, ACR access, and the selected Container Apps. |
| Image cannot be pinned by digest | Verify the deployed image exists in the selected ACR and the release identity can read manifest metadata. |
| Backend is publicly reachable | Stop the release. The app-only path must converge backend ingress to internal before validation succeeds. |
| Frontend proxy health fails | Verify the internal backend FQDN and the frontend `NGINX_API_UPSTREAM` setting, then redeploy through `make release-app`. |
| PostgreSQL startup times out | Check the retained server state and runtime identity connectivity. Start the existing server if authorized; do not replace it. |
| Revision update is rejected | Check Container Apps revision-suffix and image rules in the deployment log. Use the repository release scripts rather than hand-constructed suffixes. |

### Evaluation, telemetry, and evidence

| Symptom | Action |
| --- | --- |
| `make eval-foundry` lacks configuration | Set the Foundry project endpoint, chat deployment, and evaluator settings, or run only the deterministic local evaluation. |
| Deployed evaluation has zero rows | Verify the deployed HTTP capture set and allow bounded ingestion time. Do not substitute a historical evaluation. |
| An evaluator fails or errors | Treat the release as failed even if a run-level summary appears successful. |
| Telemetry is not visible immediately | Allow the bounded retry in `make release-telemetry` to complete. Confirm the Log Analytics output belongs to the selected target. |
| Telemetry has no exact pair match | Rerun the domain scenarios in a new release window; do not broaden the query or use unrelated threads. |
| Relevant exceptions are present | Treat telemetry validation as failed and diagnose the correlated workflow before another release. |
| Final evidence is missing after a gate failure | Inspect the current release directory. The validation trap attempts failed aggregation; preserve its logs and repair the aggregation error before claiming a result. |
| Release timing exceeds the budget | Treat finalization as failed and investigate packaging, deployment, ingestion, or evaluation latency. |
| Evidence contains secrets or customer data | Stop distribution, remove the generated artifact from the release handoff, rotate exposed credentials if necessary, and fix the producer before rerunning. |

### Infrastructure lifecycle

| Symptom | Action |
| --- | --- |
| Bootstrap preview shows unexpected replacement/deletion | Stop. Correct the target or IaC before applying. |
| Bootstrap preparation rejects the operator IP | Supply one explicit public IPv4 address; never track it in a profile. |
| PostgreSQL Entra administrator setup fails | Verify the principal belongs to the selected tenant and retry the supported bootstrap path. |
| `prepare-steady-state` cannot delete or verify the firewall rule | Leave the environment in bootstrap mode, resolve the exact rule lookup/deletion failure, and retry. Do not clear the IP or switch modes manually. |
| Steady-state preview contains PostgreSQL or Container Apps | Stop reconciliation. Those resources must be excluded from steady-state IaC. |
| Reconciliation reports unrelated drift | Review it separately. Do not normalize drift as part of an app-only release. |

For earlier root causes and exact remediations, use the
[delivery evidence ledger](docs/issues-changes-fixes.md).

## Project map

| Path | Responsibility |
| --- | --- |
| `backend/` | FastAPI host, shared MAF workflow, APIs, PostgreSQL adapters, tests, and evaluations |
| `frontend/` | React/Vite operator UI, native timeline, HITL controls, and optional selected-thread views |
| `infra/azure-apphosted/` | Bicep/AZD package for Container Apps, PostgreSQL, ACR, monitoring, identities, and Foundry model/evaluation resources |
| `deployment/` | Lane-local compatibility profiles and release artifact contracts |
| `scripts/local/` | Isolated local PostgreSQL and test helpers |
| `scripts/playwright/` | Workflow and selected-thread browser coverage |
| `scripts/release/` | Target checks, app-only deployment, reconciliation guards, telemetry, and evidence aggregation |
| `scripts/parity/` | Local/Azure parity runner and generated reports |
| `docs/` | Product, architecture, behavior, operating model, deployment flow, runbook, and evidence history |
| `.azure/deployment-plan.md` | Current deployment status and release acceptance authority |
| `agents.md` | Coding-agent boundaries and required verification |

## Documentation map

| Need | Read |
| --- | --- |
| Documentation index | [Documentation README](docs/README.md) |
| Product behavior | [Functional specification](docs/functional-spec.md) |
| Business decisions | [Business rules](docs/business-rules.md) |
| Runtime and deployment contract | [Technical specification](docs/technical-spec.md) |
| Application and trust boundaries | [Architecture](docs/architecture.md) |
| User journey and API behavior | [User flow](docs/userflow.md) |
| HITL decision rules | [HITL approval conditions](docs/hitl-approval-conditions.md) |
| Schema, API, event, and telemetry contracts | [Schema, I/O, and telemetry](docs/schema-io-telemetry.md) |
| Delivery responsibilities and gates | [Engineering operating model](docs/engineering-operating-model.md) |
| Bootstrap, steady state, app release, and evidence stages | [Deployment flow](docs/deployment-flow.md) |
| Operator and customer demo procedure | [Customer demo runbook](docs/customer-demo-runbook.md) |
| Current deployment status | [Deployment plan](.azure/deployment-plan.md) |
| Dated release and remediation history | [Delivery evidence ledger](docs/issues-changes-fixes.md) |
| Complete manual workflow matrix | [Manual testing guide](docs/manual-testing.md) |
| Backend runtime and API map | [Backend guide](backend/README.md) |
| Frontend proxy and runtime configuration | [Frontend guide](frontend/README.md) |
| Azure package details | [Azure app-hosted package](infra/azure-apphosted/README.md) |
| Deployment artifacts and profile ownership | [Deployment contract](deployment/README.md) |
| Validation and release scripts | [Scripts guide](scripts/README.md) |
| Coding-agent constraints | [Agents guide](agents.md) |

Read [agents.md](agents.md) before changing the project. It defines the
single-host MAF boundary, stable event contracts, HITL and persistence
invariants, app-only release governance, documentation updates, and required
verification.
