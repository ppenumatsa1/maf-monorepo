# Underwriting Foundry Public Deployment Flow

## Current design

The browser lane is public from creation; the application backend is private
to the Container Apps environment:

- Azure operations run from a locally authenticated operator environment.
- The canonical target is subscription
  `7df95e88-701c-4693-af77-3159f83b558d`, resource group
  `rg-maf-underwriting`, in `eastus2`.
- Bicep `bootstrap` mode creates the complete lane; `reuse` mode resolves
  existing resources and creates no resources or role assignments.
- PostgreSQL public access remains enabled with the Azure-services and
  operator-IP firewall rules required by the deployment contract.
- Database schema creation and runtime credential provisioning are explicit
  administrator operations. Production sets
  `DB_SCHEMA_MANAGED_EXTERNALLY=true`; runtime startup validates schema parity
  but emits no table, column, or index DDL.
- The backend and hosted agent use the least-privilege
  `underwriting_runtime` PostgreSQL role over TLS.
- The hosted PostgreSQL URL is stored in the project-scoped
  `underwritingruntimesecrets` `CustomKeys` connection. Hosted agent
  `DATABASE_URL` and `RUNTIME_DATABASE_URL` metadata contain only the Foundry
  connection placeholder.
- Routine releases are hard-enforced as `app_only`, reject
  `FOUNDRY_DEPLOY_MODE`, and do not invoke `azd provision`.
- The external frontend owns an Underwriting-local Nginx `/api` proxy to the
  internal backend FQDN. Browser and hosted Playwright requests remain
  same-origin; `/backend-health` verifies the private hop.
- The internal backend adapter relays hosted start and resume operations and
  exposes durable read models.
- There are no customer-managed networking, private-runner, or capability-host
  resources.

## Deployment stages

The flow is grouped into four phases and 14 clear stages.

### Phase 1: Validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Loads the secret-free public profile and resolves the subscription, resource group, location, AZD environment, and name prefix. Generated names, endpoints, resource IDs, image tags, and credentials remain outside the profile. |
| 2 | Source validation | Runs the change-aware quick or full validation lane, including applicable backend, frontend, browser, script, profile, AZD packaging, formatting, and Bicep checks. |
| 3 | Local deployment authentication | Validates Azure CLI and AZD authentication, selects the intended subscription and local AZD environment, and hydrates the retained non-secret resource outputs. |
| 4 | Infrastructure preview | Reviews bootstrap creation or non-mutating reuse. Bootstrap must contain only the expected public-lane resources; reuse must skip existing resources and must not replace PostgreSQL or mutate retained state. |

### Phase 2: Provision the public platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base public infrastructure | Creates the Foundry account/project and parameterized `gpt-4.1-mini` deployment; ACR; Log Analytics; Application Insights; Container Apps environment and placeholder apps; backend/frontend managed identities; PostgreSQL; evaluation storage; and resource-scoped RBAC. |
| 6 | Database bootstrap and readiness | The administrator creates or reconciles the canonical schema, creates `underwriting_runtime`, and grants only required runtime access. Readiness verifies the TLS URL, canonical hostname, password credential, dual authentication, database existence, Azure-services firewall rule, complete table/column/index parity, external-schema mode, and denied runtime DDL/role creation. |
| 7 | Foundry connections | Creates the Application Insights, evaluation-artifacts storage, and runtime-storage connections required by the public project. This lane does not configure Cosmos DB, AI Search, or a capability host. |

### Phase 3: Deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 8 | Shared release readiness | Runs PostgreSQL/schema readiness once, performs a read-only model deployment/SKU/capacity/regional-quota preflight, and idempotently converges the project `CustomKeys` runtime-secret connection by streaming the secure Bicep parameters to Azure CLI over stdin. The preflight never edits a live `GlobalStandard` deployment. |
| 9 | Immutable image build | Synchronizes the canonical hosted source, validates all three Docker contexts, builds backend and hosted-agent images concurrently in ACR, builds the frontend concurrently with local Docker, resolves all three digests, and writes release-local image inputs. |
| 10 | Hosted-agent then ACA deployment | Activates the hosted agent from its prebuilt digest, converges RBAC, and persists the active agent name/version/Responses endpoint. It then deploys the digest-pinned internal backend and external frontend concurrently. Routine releases require the existing frontend-external/backend-internal topology and do not repeat ingress mutations. |

### Phase 4: Prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 11 | Hosted smoke | Invokes the active Responses endpoint after the ordered deployment and proves the runtime can resolve its project connection and complete the selected smoke scenario. |
| 12 | Recovery E2E | Uses only the frontend origin to run distinct happy, retry, and `medical_check` crash scenarios, verifies checkpoint resume, four-way fan-in, and idempotency-skip visibility, then runs deployed Playwright through the same `/api` proxy. |
| 13 | Telemetry and evaluation | Correlates all fresh `workflow_run_id` values across internal-adapter requests, hosted Foundry invocation dependencies, workflow spans, and exceptions. Conversation evaluation uses the supported Task Completion and Coherence evaluators. |
| 14 | Deployment verification and final evidence | Confirms ACA ready revisions/images, frontend-external/backend-internal ingress, same-origin frontend/backend health and API, direct-backend public denial, hosted version/image, Application Insights connection, external-schema mode, and the exact runtime connection placeholder. It then aggregates verification, smoke, E2E, telemetry, and evaluation artifacts into one machine-readable release window. |

## Command mapping

| Command or operation | Stages | Purpose |
| --- | --- | --- |
| `make foundry-profile-apply` | 1 | Applies a secret-free bootstrap or reuse target profile. |
| `make validate-quick` / `make validate-full` | 2 | Runs the validation lane selected by the deployment router. |
| `make foundry-bootstrap` | 3 | Selects and hydrates an existing reuse environment without provisioning. |
| `azd provision --preview --no-prompt` | 4 | Reviews a bootstrap or reuse plan without applying the deployment. |
| `make foundry-provision` | 3-5, 7 | Creates bootstrap infrastructure or performs template-defined non-mutating reuse, then hydrates outputs. |
| `make foundry-postgres-schema` | 6 | Applies the administrator-owned canonical schema. |
| `make foundry-postgres-credentials` | 6 | Creates or rotates the least-privilege runtime credential. |
| `make foundry-postgres-readiness` | 6 | Validates PostgreSQL and the runtime permission boundary before deployment. |
| `make foundry-package` | 9 | Runs the full standalone AZD package path when explicitly requested. |
| `make foundry-release-package` | 9 | Synchronizes and validates the three release contexts without rebuilding images. |
| `make foundry-release-build` | 9 | Builds all three immutable images concurrently and records their digests in the current release directory. |
| `make foundry-release-hosted-activate` | 10 | Activates the hosted agent from the prebuilt digest and persists its exact version. |
| `make foundry-release-app-deploy` | 10 | Deploys the prebuilt backend and frontend digests concurrently without mutating ingress topology. |
| `make foundry-model-preflight` | 8 | Verifies the existing model deployment and regional quota without changing SKU or capacity. |
| `make foundry-runtime-connection` | 8 | Converges the deterministic project `CustomKeys` connection using an in-memory stdin parameter stream; the runtime URL is not written to disk or command arguments. |
| `make foundry-release-readiness` | 6, 8 | Runs the one shared readiness gate before packaging and ordered deployment. |
| `make foundry-postgres-rebuild CONFIRM=REBUILD-<server>` | 5-6 | Explicitly rebuilds only the selected PostgreSQL server after server-specific confirmation; it is not part of a routine release. |
| `make foundry-release` | 2-3, 8-14 | Runs the authenticated app-only release DAG. |
| `make foundry-backend-internalize CONFIRM=INTERNALIZE-<backend>` | One-time migration | Validates the canonical target, deploys and verifies the proxy frontend, changes backend ingress to internal, and proves direct public denial. It has no public-ingress toggle. |
| `make foundry-verify` / `make foundry-evidence` | 14 | Verifies the deployed contract and emits/aggregates secret-free JSON evidence. |

## Release paths

### Fresh bootstrap

Run all 14 stages:

1. Apply the bootstrap profile and prepare the non-secret AZD inputs.
2. Validate the source and review the bootstrap preview.
3. Provision the public platform and hydrate the resulting outputs.
4. Apply the PostgreSQL schema, create the runtime credential, and pass
   readiness.
5. Validate all service contexts, build the three immutable images
   concurrently, and persist their digests in the release directory.
6. Activate and persist hosted-agent metadata, then deploy backend and
   frontend concurrently.
7. Run smoke, hosted recovery E2E, telemetry correlation, and evaluation.
8. Verify the exact deployment contract and aggregate final evidence.

### Routine app-only release

Do not reconcile infrastructure:

1. Apply the reuse profile and hydrate the retained AZD environment.
2. Run the selected validation lane and compile Bicep.
3. Run the single database/model/runtime-connection readiness gate.
4. Validate the service contexts and build all three immutable images
   concurrently.
5. Activate and persist the hosted-agent version from its prebuilt digest,
   then deploy the digest-pinned backend and frontend concurrently.
6. Verify the Application Insights connection and run the selected smoke mode.
7. Run hosted recovery E2E, telemetry correlation, and evaluation.
8. Verify the exact deployment contract and aggregate final evidence.

`make foundry-release` accepts only the app-only route. Full provisioning and
the guarded PostgreSQL rebuild remain explicit, separate operations.
`FOUNDRY_DEPLOY_MODE` is rejected rather than treated as an override.

## Measured app-only timing

Release `uw-public-51a8311-20260816140654` from commit `51a8311` reached
telemetry in **14m 10.0s**, 50.0 seconds inside the 15-minute budget. Compared
with the prior complete 18m 07.4s run, the two-phase build/activation flow
saved **3m 57.5s** without removing smoke, recovery E2E, evaluation, or
telemetry coverage.

| Stage | Duration |
| --- | ---: |
| Package/context validation | 0.1s |
| Concurrent immutable image build | 4m 52.5s |
| Hosted-agent activation and RBAC | 2m 08.3s |
| Concurrent backend/frontend ACA deployment | 3m 00.9s |
| Smoke | 53.4s |
| Recovery E2E | 2m 28.3s |
| Evaluation, overlapped with E2E | 1m 50.1s |
| Telemetry | 46.2s |
| **App-only to telemetry** | **14m 10.0s** |
| Post-telemetry deployment verification | 2m 32.5s |
| Final evidence aggregation | 0.3s |

The deployment sequence is intentionally two-phase: build all immutable
artifacts first, activate the exact hosted digest second, and only then deploy
the backend that references the newly persisted hosted version. Backend and
frontend deployment remain parallel. This avoids both ACR queue serialization
and a race in which the backend could retain the previous hosted-agent version.

## Four-lane app-only benchmark

These are the latest verified lane-local release records. They were measured
independently rather than as one simultaneous execution; if launched together,
the critical wall-clock bound is the slowest lane, **14m 10.0s**.

| Lane | App-only to telemetry | 15-minute result | Earlier baseline | Improvement |
| --- | ---: | --- | ---: | ---: |
| Order Resolution - Azure Hosted | 13m 24.6s | Passed | Not directly comparable | - |
| Order Resolution - Foundry Public | 14m 01.1s | Passed | 16m 22.1s | 2m 21.0s |
| Order Resolution - Foundry Private | 6m 36.8s | Passed | 8m 43.0s | 2m 06.2s |
| Underwriting - Foundry Public | 14m 10.0s | Passed | 18m 07.4s | 3m 57.5s |
| **Aggregate / average** | **48m 12.5s / 12m 03.1s** | **4/4 passed** | - | - |

### One-time migration for an existing public backend

Before the first standardized routine release against a legacy environment:

```bash
make foundry-backend-internalize \
  CONFIRM=INTERNALIZE-$(cd infra/foundry-hosted && azd env get-value BACKEND_CONTAINER_APP_NAME)
```

The command is idempotent when ingress is already internal. It refuses a
non-canonical target, verifies the proxy-capable frontend before changing
ingress, and never provides a path to make the backend public again.

## PostgreSQL security boundary

| Identity | Allowed | Denied |
| --- | --- | --- |
| PostgreSQL administrator | Create or reconcile schema objects and create or rotate `underwriting_runtime` from the approved operator address. | Use as an application runtime credential. |
| `underwriting_runtime` | Database connection, schema usage, required table DML, and required sequence usage for checkpoints, workflow projections, results, and idempotency records. | DDL, role creation, schema ownership, broad `CREATE`, and administrator privileges. |
| Backend | Consumes the TLS runtime URL through an ACA secret and validates the externally managed schema at startup. | Receive the administrator URL, acquire schema-owner privileges, or execute runtime DDL. |
| Hosted agent | Resolves the TLS runtime URL from the project `CustomKeys` connection placeholder at runtime. | Store the resolved URL in agent definition metadata or expose it through verification evidence. |

## Private-only stages not used

| Private-lane stage | Public-lane treatment |
| --- | --- |
| VNet, NAT, private DNS, and private endpoints | Not created. The public lane uses controlled public service endpoints. |
| Private runner VM, NSG, and Bastion | Not created. Authenticated operations run from the operator workstation. |
| GitHub OIDC deployment identity | Not used for Azure mutation. Deployment is an authenticated local operation. |
| Cosmos DB, AI Search, and capability host | Not configured. The public lane uses monitoring and storage connections plus the project-scoped `underwritingruntimesecrets` `CustomKeys` connection for hosted database resolution. |
| Private connectivity proof and PostgreSQL lockdown | Not applicable. Public readiness validates the intended TLS and firewall posture without a later lockdown mutation. |

## Stop conditions

Stop the release if:

- the selected subscription, resource group, location, or AZD environment does
  not match the applied public profile;
- bootstrap preview contains unexpected resources, deletion, replacement, or
  stateful mutation;
- reuse preview proposes resource or role-assignment creation;
- PostgreSQL TLS, hostname, firewall, schema, runtime connectivity, or
  least-privilege checks fail;
- the backend and hosted agent do not use the same runtime database URL or
  `DB_SCHEMA_MANAGED_EXTERNALLY=true`;
- packaging, ACR build, ACA deployment, hosted-agent activation, hosted-agent
  RBAC, project Application Insights connection, or smoke fails;
- frontend-external/backend-internal ingress, same-origin health/API, or direct
  backend public-denial verification fails;
- the happy path, injected retry, `medical_check` crash, checkpoint, resume,
  four-way fan-in, idempotency-skip, or deployed Playwright checks fail;
- telemetry cannot correlate all three fresh workflow runs across the required
  request, dependency, and workflow signals;
- Task Completion or Coherence fails the configured
  threshold or returns an errored row; or
- evidence is stale or spans multiple release windows.
