# Order Resolution Foundry Private Deployment Flow

## Current design

The lane is private-only from creation:

- PostgreSQL public access is disabled in IaC.
- No `allow-azure-services` firewall rule exists.
- Database bootstrap and readiness run from the VNet-connected runner.
- Backend and hosted agent use the least-privilege `maf_runtime` role.
- Connectivity-proof, lockdown, and post-lockdown stages are retired.

## Deployment stages

The flow is grouped into four phases and 16 clear stages.

### Phase 1: Validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Loads the canonical private profile and resolves the subscription, resource group, regions, AZD environment, resource names, and runner label. |
| 2 | Source validation | Runs profile, portability, workflow, syntax, JSON, Bicep, database-permission, backend, and packaging checks. |
| 3 | Deployment authentication | Validates GitHub variables, authenticates to Azure through OIDC, and reconstructs the retained private AZD environment. |
| 4 | Infrastructure preview | Runs a non-mutating preview and rejects PostgreSQL replacement, public access, firewall creation, private-endpoint deletion, DNS weakening, or unexpected stateful changes. |

### Phase 2: Provision the private platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base infrastructure | Creates VNet/subnets, NAT, private DNS, private endpoints, private-only PostgreSQL, ACR, Storage, Cosmos DB, Search, Foundry, monitoring, and the ACA environment. |
| 6 | Private runner | Creates the runner VM, NSG, managed identity, and Bastion path; installs the GitHub runner, Docker, Azure CLI, AZD, Python, and PostgreSQL tooling. |
| 7 | Deployment identity | Configures GitHub OIDC trust and scoped Azure RBAC for the runner, Foundry project, Container Apps, ACR, data services, and telemetry. |
| 8 | Database bootstrap and readiness | The administrator creates/reconciles tables and sequences, creates `maf_runtime`, and grants only required DML/sequence access. The readiness gate verifies disabled public access, private endpoint/DNS resolution, connectivity, and denied runtime DDL/role creation. |
| 9 | Foundry connections and capability host | Creates Storage, Cosmos, Search, Application Insights, and runtime-secret project connections, then configures the capability host and required pre/post capability-host RBAC. |

### Phase 3: Deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 10 | Application packaging | Builds backend and frontend artifacts while the hosted-agent image builds concurrently, then pushes all images to private ACR. |
| 11 | ACA deployment | Deploys backend and frontend Container Apps. The backend receives the runtime PostgreSQL URL through an ACA secret and runs with `DB_SCHEMA_MANAGED_EXTERNALLY=true`. |
| 12 | Hosted-agent deployment | Creates and activates the Foundry hosted-agent version using the private ACR image and runtime-secret connection. |
| 13 | Health, image, and smoke verification | Confirms ready ACA revisions, HTTP 200 health, intended ACR images, active hosted-agent version, and a valid Responses-protocol smoke response. |

### Phase 4: Prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 14 | HITL E2E | Runs low-risk `ORD-1001`, high-risk `ORD-1009`, and damaged-item scenarios, including checkpoint pause/resume and approval. |
| 15 | Telemetry and evaluation | Correlates all three conversations in Application Insights to exact eligible Foundry traces, then immediately probes Foundry evaluator readiness. Only empty, error-free ingestion misses are retried; real evaluator failures stop the release. |
| 16 | Final evidence | Records target, hosted-agent version, E2E timestamps, telemetry, evaluation, and final private PostgreSQL state in one release-window report. |

## Workflow mapping

| Workflow | Stages | Primary command |
| --- | --- | --- |
| `order-resolution-private-validation.yml` | 1-2 | Static validation commands |
| `order-resolution-private-provision.yml` | 3-9 | `make foundry-provision`, `make foundry-postgres-bootstrap`, `make foundry-postgres-readiness` |
| `order-resolution-private-deploy.yml` | 8, 10-16 | `make foundry-app-only-release`, then `make foundry-evidence` by default |
| `order-resolution-private-evidence.yml` | 14-16 | Standalone evidence retry through `make foundry-evidence` |

Authenticated workflows share the `order-resolution-private-release`
concurrency group so provisioning, deployment, and evidence execution do not
overlap.

## Release record cutover status

| Path | Status | Policy |
| --- | --- | --- |
| `.artifacts/release/` and relevant tracked `.foundry/results/` history | Historical inventory | Inventory only; no copy or deletion is authorized. |
| `.artifacts/releases/<release-id>/` | Live validated | App release and same-context evidence retry write sanitized records, detailed `evidence/`, and `logs/`; workflow `31922650130` is the latest timing authority. |

`make release-history-migration-plan` is dry-run only. A later deletion design
must require both live-release and durable-archive markers; this tooling never
creates those markers or deletes source history.

## Release paths

### Fresh bootstrap or intentional reconciliation

Run all 16 stages:

1. Validate and preview.
2. Provision the private platform and runner.
3. Bootstrap and verify PostgreSQL.
4. Create Foundry connections and capability host.
5. Deploy all application artifacts.
6. Run HITL E2E, telemetry, evaluation, and final evidence.

### Routine app-only release

Do not reconcile infrastructure:

1. Validate the existing target.
2. Re-run PostgreSQL readiness.
3. Build the hosted image concurrently with backend/frontend deployment.
4. Verify health, images, and smoke.
5. Continue in the same workflow to HITL E2E, telemetry, adaptive evaluation,
   and final evidence.

## PostgreSQL security boundary

| Identity | Allowed | Denied |
| --- | --- | --- |
| PostgreSQL administrator | Create/reconcile schema, tables, sequences, and `maf_runtime` from the private runner. | Use as an application runtime credential. |
| `maf_runtime` | Database `CONNECT`, schema `USAGE`, required table DML, and required sequence `USAGE`. | DDL, role creation, table ownership, `TRUNCATE`, and broad database/sequence privileges. |
| Backend and hosted agent | Consume the runtime URL through ACA/Foundry secret references. | Receive the administrator URL or execute production schema creation. |

## Retired stages

| Former stage | Replacement |
| --- | --- |
| Private connectivity proof | Step 8 performs direct, non-persistent readiness before deployment. |
| PostgreSQL lockdown | PostgreSQL is private-only at creation; no lockdown mutation is needed. |
| Post-lockdown evidence | One evidence pass runs after private readiness. |

No workflow may recreate the retired proof file, firewall rule, lockdown
script/workflow, public-access fallback, or post-lockdown rerun.

## Measured timings

Measurements use GitHub workflow timestamps and the log timestamp at which the
Application Insights correlation gate passed.

| Flow | Runs | Time to telemetry |
| --- | --- | ---: |
| Infrastructure/IaC to telemetry | Provision `31906517820`, deploy `31906717310`, evidence `31906891692` | **13m 37s** |
| App-only to telemetry, before | Deploy `31908682961`, evidence `31908858225` | **8m 43s** |
| App-only to telemetry, optimized | Workflow `31922650130` | **6m 36.8s** |
| App-only to complete strict evaluation, before | Deploy `31908682961`, evidence `31908858225` | **11m 54s** |
| App-only to complete strict evaluation, optimized | Workflow `31922650130` | **6m 57.8s** |

The optimized steady-state run reused the requirements-hash-validated backend
environment, reused the concurrently built hosted image, and reached strict
3/3 evaluation on the first evaluator-readiness attempt. Telemetry remains the
largest variable wait; no security, HITL, trace-correlation, or evaluator gate
was removed.

| Stage | Duration |
| --- | ---: |
| Hosted package and ACA deployment, overlapped | 1m 24s |
| Verification and smoke | 6s |
| Hosted-agent activation | 53s |
| HITL E2E | 2m 07s |
| Telemetry | 2m 03s |
| Evaluation after telemetry | 21s |
| **App-only to telemetry** | **6m 36.8s** |

## Stop conditions

Stop the release if:

- target variables do not match the canonical profile;
- the private runner is offline or PostgreSQL does not resolve privately;
- preview weakens PostgreSQL, private endpoints, DNS, or stateful resources;
- runtime database permissions exceed the least-privilege contract;
- ACA revisions, images, health, hosted-agent activation, or smoke fail;
- any canonical HITL scenario fails;
- telemetry cannot correlate all fresh conversations to eligible traces;
- Task Completion or Coherence fails or returns an errored row; or
- evidence is stale or spans multiple release windows.
