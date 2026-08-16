# Order Resolution Foundry Public Deployment Flow

## Current design

The lane is public from creation:

- Azure operations run from a locally authenticated operator environment.
- Bicep `bootstrap` mode creates the complete lane; `reuse` mode resolves
  existing resources and creates no resources or role assignments.
- PostgreSQL public access remains enabled with the Azure-services and
  operator-IP firewall rules required by the deployment contract.
- Database schema creation and runtime credential provisioning are explicit
  administrator operations.
- Backend and hosted-agent runtimes use the least-privilege
  `order_resolution_runtime` role with `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- The backend receives the URL through an ACA secret; the hosted agent receives
  only a Foundry project-connection placeholder backed by an Order-owned
  `CustomKeys` connection.
- Routine releases are app-only and do not invoke `azd provision`.
- There are no customer-managed networking, private-runner, or capability-host
  resources.

## Deployment stages

The flow is grouped into four phases and 14 clear stages.

### Phase 1: Validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Loads the secret-free public profile and resolves the subscription, resource group, location, AZD environment, and name prefix. Generated names, endpoints, resource IDs, image tags, and credentials remain outside the profile. |
| 2 | Source validation | Runs the change-aware quick or full validation lane, including applicable backend, frontend, evaluation, browser, script, profile, packaging, and design-review checks. |
| 3 | Local deployment authentication | Validates Azure CLI and AZD authentication, selects the intended subscription and local AZD environment, and hydrates the retained non-secret resource outputs. |
| 4 | Infrastructure preview | Reviews bootstrap creation or non-mutating reuse. Bootstrap must contain only the expected public-lane resources; reuse must skip existing resources and must not replace PostgreSQL or mutate retained state. |

### Phase 2: Provision the public platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base public infrastructure | Creates the Foundry account/project and chat, embeddings, and evaluator deployments; ACR; Log Analytics; Application Insights; Container Apps environment and placeholder apps; backend/frontend managed identities; PostgreSQL; evaluation storage; and resource-scoped RBAC. |
| 6 | Database bootstrap and readiness | The administrator creates or reconciles the canonical schema, creates `order_resolution_runtime`, and grants only required table DML and sequence usage. Readiness verifies TLS, canonical hostname, database access, dual authentication, firewall rules, required tables, and denied runtime DDL/role creation. |
| 7 | Foundry base connections | Creates the evaluation-storage and monitoring connections required by the public project. Foundry operates the agent session, file, and vector-store services; this lane does not configure a capability host. |

### Phase 3: Deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 8 | Packaging and shared release readiness | Synchronizes and packages the backend, frontend, and hosted-agent sources, performs read-only model/quota preflight, re-runs PostgreSQL readiness, and then idempotently converges `orderresolutionruntimesecrets` as a project `CustomKeys` connection by streaming secure Bicep parameters over stdin. No deployment SKU or capacity is changed, and the runtime URL is not written to disk or command arguments. |
| 9 | Concurrent runtime deployment | Fans out the backend, frontend, and hosted-agent deployment legs concurrently. The backend is internal and receives the runtime PostgreSQL URL through an ACA secret with `DB_SCHEMA_MANAGED_EXTERNALLY=true`; the frontend is external and uses a same-origin `/api` proxy; every leg resolves an immutable ACR digest. |
| 10 | Hosted-agent branch completion | Within the hosted deployment leg, creates and activates `order-resolution-hosted` using the immutable digest, Responses 2.0 protocol, telemetry configuration, and literal `${{connections.orderresolutionruntimesecrets.credentials.database_url}}` values for both database variables. The resolved URL is never placed in `HostedAgentDefinition` or agent metadata. The platform identity receives only `Cognitive Services OpenAI User` at Foundry account scope, and the deployment fan-in waits for this RBAC and metadata convergence plus both ACA legs. |
| 11 | Deployment verification and smoke | Confirms one healthy active revision per ACA on the exact immutable image, external frontend/internal backend ingress, frontend and same-origin backend health, hosted version/image/RBAC and literal database placeholders, project `CustomKeys` and Application Insights connections, backend database-secret parity, and `DB_SCHEMA_MANAGED_EXTERNALLY=true`, then obtains a Responses-protocol smoke result. Runtime connectivity remains proven by PostgreSQL readiness and smoke/E2E. |

### Phase 4: Prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 12 | HITL E2E | Runs low-risk `ORD-1001` without HITL, high-risk `ORD-1009` through checkpoint approval/resume, and damaged-item `ORD-1001` through checkpoint approval/resume in three fresh hosted Responses conversations. Deployed browser validation runs separately against `WEB_URL` when required. |
| 13 | Telemetry and evaluation | Correlates all three fresh conversations in Application Insights to eligible Foundry traces, verifies that the release produced no relevant exceptions, and runs the preserved Task Completion and Coherence evaluators against those traces. |
| 14 | Final evidence | `make foundry-evidence` rejects stale, cross-window, incomplete, or secret-bearing artifacts and aggregates the selected target, exact revisions/images, hosted version, model/quota preflight, conversation IDs, App Insights connection, telemetry, and evaluation into one gitignored machine-readable report. |

`release.json` records actual UTC start/end timestamps and millisecond
durations in `extensions.release_timing`. Parallel deployment legs and the
hosted-E2E/evaluation overlap remain separate intervals. The app-only total
starts immediately before packaging and ends at telemetry success; final
evidence is timed separately, and successful finalization rejects missing,
failed, misordered, or inconsistent timing data.

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
| `make foundry-runtime-connection` | 8 | Runs readiness and securely converges the deterministic project `CustomKeys` runtime connection through stdin. |
| `make foundry-model-preflight` | 8 | Validates the existing model set and quota without changing live deployment SKUs/capacity. |
| `make foundry-release-deploy` | 8-10 | Runs shared readiness/package gates and concurrently deploys the backend, frontend, and hosted-agent legs. |
| `make foundry-verify` | 11 | Independently verifies the live image, topology, endpoint, hosted-agent, RBAC, App Insights, and database contracts. |
| `make foundry-evidence` | 14 | Aggregates the current release window into one secret-free JSON report. |
| `make foundry-release` | 2-3, 6-13 | Runs the authenticated app-only release DAG. |
| Release evidence update | 14 | Reviews the generated report and records the completed release window in `docs/design/issues-changes-fixes.md`. |

## Release paths

### Fresh bootstrap

Run all 14 stages:

1. Apply the bootstrap profile and prepare the non-secret AZD inputs.
2. Validate the source and review the bootstrap preview.
3. Provision the public platform and hydrate the resulting outputs.
4. Apply the PostgreSQL schema, create the runtime credential, and pass
   readiness.
5. Run the app-only release for backend, frontend, and hosted-agent artifacts.
6. Run exact deployment verification, smoke, three-conversation hosted HITL
   E2E, telemetry correlation, evaluation, and final evidence.

### Routine app-only release

Do not reconcile infrastructure:

1. Apply the reuse profile and hydrate the retained AZD environment.
2. Run the selected validation lane and compile Bicep.
3. Package the three runtime sources.
4. Run model/quota preflight and re-run PostgreSQL readiness.
5. Converge the project runtime-secret connection through the secure stdin
   parameter stream.
6. Build and deploy backend, frontend, and hosted-agent artifacts concurrently.
7. Verify exact deployment state and both project connections, then
   run smoke.
8. Run three-conversation hosted HITL E2E, telemetry correlation, evaluation,
   and aggregate final evidence.

`make foundry-release` enforces the app-only route and does not invoke
`azd provision`.

## Measured app-only timing

Release `final-isolated-20260816T025501Z-667e609-public` reached telemetry in
**14m 01.1s**, within the 15-minute release budget.

| Stage | Duration |
| --- | ---: |
| Package preparation | 3.4s |
| Readiness before deployment | 3m 23.2s |
| Concurrent deployment critical leg | 5m 54.1s |
| Deployment verification | 2m 34.0s |
| Smoke | 31.1s |
| Hosted E2E | 1m 25.2s |
| Evaluation, overlapped | 3m 15.9s |
| Telemetry | 9.7s |
| **App-only to telemetry** | **14m 01.1s** |

## PostgreSQL security boundary

| Identity | Allowed | Denied |
| --- | --- | --- |
| PostgreSQL administrator | Create or reconcile schema objects and create or rotate `order_resolution_runtime` from the approved operator address. | Use as an application runtime credential. |
| `order_resolution_runtime` | Database connection, schema usage, required table DML, and required sequence usage. | DDL, role creation, schema ownership, broad `CREATE`, and administrator privileges. |
| Backend Container App | Consume the runtime URL through an ACA secret reference. | Receive the administrator URL or execute production schema creation. |
| Hosted agent | Resolve the runtime URL only through `${{connections.orderresolutionruntimesecrets.credentials.database_url}}`. | Store the resolved runtime URL in its definition, version metadata, deployment metadata, or evidence. |

## Private-only stages not used

| Private-lane stage | Public-lane treatment |
| --- | --- |
| VNet, NAT, private DNS, and private endpoints | Not created. The public lane uses controlled public service endpoints. |
| Private runner VM, NSG, and Bastion | Not created. Authenticated operations run from the operator workstation. |
| GitHub OIDC deployment identity | Not used for Azure mutation. GitHub Actions remains credential-free CI. |
| Cosmos DB, AI Search, and capability host | Not configured. The public lane uses evaluation storage, monitoring, and one project runtime-secret connection. |
| Private connectivity proof and PostgreSQL lockdown | Not applicable. Public readiness validates the intended TLS and firewall posture without a later lockdown mutation. |

## Stop conditions

Stop the release if:

- the selected subscription, resource group, location, or AZD environment does
  not match the public profile;
- bootstrap preview contains unexpected resources, deletion, replacement, or
  stateful mutation;
- reuse preview proposes resource or role-assignment creation;
- PostgreSQL TLS, hostname, firewall, schema, runtime connectivity, or
  least-privilege checks fail;
- a runtime attempts production DDL or receives administrator privileges;
- model/quota preflight, packaging, ACR build, ACA deployment, hosted-agent
  activation/RBAC, exact image verification, project Application Insights
  connection, runtime-secret connection or placeholder verification, backend
  database parity, same-origin health, or smoke fails;
- low-risk completion, high-risk HITL approval/resume, or damaged-item HITL
  approval/resume fails;
- telemetry cannot correlate all three fresh conversations to eligible traces;
- Task Completion or Coherence fails or returns an errored row; or
- evidence is stale, secret-bearing, incomplete, or spans multiple release
  windows.
