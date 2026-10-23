# Underwriting Foundry Public Deployment Flow

## Purpose

Define the portable deployment, publication, verification, and rollback flow
for the public Underwriting lane. Concrete subscription, tenant, resource,
region, endpoint, release, version, count, and timing values belong only in the
operator environment, deployment plan, and dated delivery ledger.

## Runtime topology

- External React/Nginx Container App with public ingress.
- Internal FastAPI Container App reached through the frontend's same-origin
  proxy.
- Public Foundry hosted agent with Responses and, when Teams is enabled,
  Activity in the same process.
- PostgreSQL with the approved public TLS/firewall posture.
- Application Insights for correlated runtime and evaluation evidence.
- Azure Bot Service plus `MsTeamsChannel` for Shared Teams publication.

This lane does not create private-runner, VNet, private endpoint, private DNS,
Bastion, or NAT resources.

## Profile and authority

An operator-owned external profile selects:

- contract version;
- `foundry-public` lane;
- local AZD environment;
- subscription;
- resource group;
- region;
- portable name prefix.

The profile contains no secrets, endpoints, generated names, resource IDs,
image references, operator addresses, publication state, or evidence.

GitHub Actions owns automatic credential-free CI and protected OIDC workflows
for preview/provision, app-only deploy, package validation, observability, and
evidence retry. Microsoft 365 Shared publication remains an interactive
publisher operation.

## Deployment phases

### Phase 1: Validate and authorize

| Stage | Outcome |
| --- | --- |
| Profile selection | Applies the external non-secret profile and fails closed on missing or mismatched values. |
| Source validation | Runs applicable backend, frontend, browser, script, profile, packaging, formatting, and Bicep checks. |
| Authentication | Verifies Azure CLI and AZD context against the selected profile. |
| Preview | Reviews bootstrap/reconciliation changes before mutation. Reuse/app-only operation must not hide infrastructure drift. |

### Phase 2: Bootstrap the public platform

| Stage | Outcome |
| --- | --- |
| Base infrastructure | Creates the public Foundry, registry, monitoring, Container Apps, identities, PostgreSQL, and evaluation resources defined by Bicep. |
| Database administration | Applies the canonical schema and least-privilege runtime credential. Runtime applications receive no DDL authority. |
| Project connections | Converges monitoring, evaluation storage, and the project `CustomKeys` runtime database connection. |
| Readiness | Verifies PostgreSQL, model deployment/capacity, identities, connections, and expected public topology. |

Bootstrap is explicit. A routine application release must not run this phase.

### Phase 3: App-only release

| Stage | Outcome |
| --- | --- |
| Rollback baseline | Captures the active hosted version and current backend/frontend revisions before app-only mutation. |
| Package and immutable build | Recreates the Python 3.13 hash-verified wheelhouse from the lock and produces immutable backend, frontend, and hosted-agent artifacts independent of ignored developer state. |
| Hosted activation | Activates and persists the exact hosted digest/version through the current Azure AI Projects API before backend deployment. |
| Application deployment | Deploys the internal backend and external frontend without changing ingress topology. |
| Smoke and recovery E2E | Proves hosted invocation, four-way fan-in, retry, crash/resume, referral pause/resume, and idempotency. |
| Evaluation and telemetry | Enforces configured evaluator results and correlates safe web/Responses/Activity/workflow/review signals. |
| Verification and evidence | Verifies topology, exact images, hosted metadata, schema mode, runtime connection placeholder, preserved rollback versions/revisions, and release-local evidence integrity. |

Routine mode is always app-only. A deployment-mode override must fail rather
than silently invoking provisioning.

### Phase 4: Teams Shared publication

Teams publication is separate from routine application deployment:

| Stage | Outcome |
| --- | --- |
| Activity plan | Merge-preserving plan retains Responses and Entra and adds Activity plus `BotServiceRbac`. |
| Bot/Teams preview | Reviews Azure Bot Service and `MsTeamsChannel` changes without private-network additions. |
| Bot/Teams apply | Deploys the reviewed channel resources. |
| Package | Generates and inspects a sanitized Microsoft 365 package. |
| Shared publish | An interactive publisher publishes an explicit Shared app version. |
| Acceptance | Verifies authorized invocation, referral card, approve/decline, typed-text blocking, replay/expiry/concurrency, reviewer/conversation isolation, privacy, telemetry, and rollback. |

Tenant-wide publication is not the target.

## Command mapping

Commands currently defined by the project Makefile include:

| Command | Purpose |
| --- | --- |
| `make foundry-profile-apply FOUNDRY_DEPLOYMENT_PROFILE=<path>` | Apply the external target profile. |
| `make validate-quick` / `make validate-full` | Run local validation lanes. |
| `make foundry-bootstrap` | Hydrate an existing AZD environment from selected resources. |
| `make foundry-bootstrap-env` | Prepare derived bootstrap inputs. |
| `make foundry-iac-build` | Compile the public Bicep source. |
| `azd provision --preview --no-prompt` | Preview infrastructure changes. |
| `make foundry-provision` | Apply approved infrastructure, hydrate outputs after creation, migrate schema, converge runtime access, and verify PostgreSQL readiness. |
| `make foundry-provision-infrastructure` | Protected workflow stage that applies approved Bicep and hydrates only after resources exist. |
| `make foundry-provision-converge` | Protected workflow stage that migrates schema, converges runtime credentials/grants and the project connection, then verifies readiness. |
| `make foundry-postgres-schema` | Apply administrator-owned schema. |
| `make foundry-postgres-credentials` | Provision or rotate the runtime credential and converge its connection. |
| `make foundry-postgres-readiness` | Verify public PostgreSQL and least privilege. |
| `make foundry-model-preflight` | Verify model deployment, SKU, capacity, and regional quota without mutation. |
| `make foundry-capacity-preflight-full` | Verify incremental full-infrastructure capacity before bootstrap. |
| `make foundry-reuse-preview` | Require a zero-change reuse preview. |
| `make foundry-provision-preview` | Preview and validate full infrastructure changes. |
| `make foundry-release-readiness` | Run the shared database/model/connection readiness gate. |
| `make foundry-release` | Run the authenticated app-only release orchestration. |
| `make foundry-smoke` | Run hosted smoke. |
| `make foundry-hosted-e2e` | Run hosted API and deployed browser E2E. |
| `make foundry-eval` | Run report-only Foundry trace evaluation. |
| `make foundry-telemetry` | Verify Application Insights correlation. |
| `make foundry-verify` | Verify deployed topology and runtime contracts. |
| `make foundry-rollback-verify` | Verify the prior hosted version and Container App revisions remain available with their original images. |
| `make foundry-evidence` | Aggregate secret-free release-local evidence. |
| `make foundry-activity-plan` / `apply` / `rollback` | Manage merge-preserving Activity endpoint state. |
| `make foundry-teams-plan` / `preview` / `deploy-bot` | Validate and deploy Bot/Teams channel state. |
| `make foundry-teams-package` / `publish` / `status` | Verify already-applied Activity state without mutation, then generate, publish, and inspect the Shared Teams app. |
| `make foundry-teams-rollback-plan` / `rollback` | Review and execute Activity-only automation; Shared catalog and Bot completion remain recorded external steps. |

Protected workflow mapping:

| Workflow | Ownership |
| --- | --- |
| `underwriting-public-ci.yml` | Automatic credential-free CI |
| `underwriting-public-provision.yml` | Protected OIDC preview/provision |
| `underwriting-public-deploy.yml` | Protected OIDC app-only release |
| `underwriting-public-package-validation.yml` | Protected authenticated package validation |
| `underwriting-public-observability.yml` | Protected hosted E2E/evaluation/telemetry |
| `underwriting-public-evidence.yml` | Protected evidence retry |

All protected mutation/observability workflows serialize on the same release
concurrency group. Shared Microsoft 365 publication is deliberately excluded
because it requires delegated interactive user authentication.

## Clean bootstrap

1. Create and secure the external profile.
2. Apply the profile and verify authenticated context.
3. Run full source validation and Bicep compilation.
4. Run `make foundry-provision-preview` or dispatch the protected preview
   workflow.
5. Stop on unexpected create/delete/replace/network/RBAC/scaling/stateful
   mutation.
6. Run the protected provision workflow or explicitly authorize
   `FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-provision`; both separate
   the Bicep apply from post-resource schema, runtime credential/grant, runtime
   connection, and PostgreSQL readiness convergence.
7. Pass model readiness.
8. Run the app-only release.
9. If Teams is in scope, run the separate Shared publication phase.
10. Record fresh proof in the ledger.

## Routine app-only release

1. Apply the external reuse profile and hydrate AZD state.
2. Run the selected validation lane.
3. Run one shared readiness gate.
4. Capture the pre-release rollback baseline.
5. Rebuild the wheelhouse and immutable artifacts.
6. Activate and persist the hosted version.
7. Deploy backend and frontend without infrastructure reconciliation.
8. Run smoke, E2E, evaluation, telemetry, deployment verification, rollback
   verification, and evidence aggregation.
9. Record outcomes in the ledger.

## Rollback

### Application

- Preserve failed-release evidence.
- Restore the previous verified hosted version before restoring the backend
  that references it.
- Restore previous backend/frontend digests without changing ingress.
- Require pre-release and post-release evidence that the prior hosted version
  and exact Container App revisions still exist before declaring rollback
  ready.
- Re-run smoke, referral/HITL acceptance, telemetry, topology verification,
  and evidence.
- Do not drop review schema or data as an automatic rollback step.

### Teams

- Stop distribution/publication.
- Remove or supersede the Microsoft 365 catalog version through the supported
  publisher process.
- Remove Activity and Bot authorization with merge-preserving rollback that
  leaves Responses and Entra intact.
- Verify the web/Responses lane and replay protection.

## Stop conditions

Stop if:

- authenticated context differs from the external profile;
- preview contains unreviewed infrastructure mutation;
- reuse/app-only work proposes stateful resource creation or replacement;
- PostgreSQL schema, TLS, firewall, credential, or least-privilege checks fail;
- model/capacity preflight fails;
- hosted metadata contains a resolved database URL;
- the backend becomes publicly reachable;
- immutable image, hosted activation, smoke, E2E, evaluation, telemetry, or
  evidence integrity fails;
- only a partial set of direct checks is present at decision time;
- a non-referral recommendation pauses;
- machine recommendation is overwritten by reviewer outcome;
- Adaptive Card privacy, token binding, replay, expiry, concurrency,
  cross-channel, or reviewer/conversation isolation fails;
- Shared publication is replaced with Tenant publication; or
- evidence is stale, mixed across release windows, or contains sensitive
  values.
