# Order Resolution Foundry Private Deployment Plan

> **Status:** Deployed and verified — private-only PostgreSQL release evidence passed

## Objective

Prepare a portable, fresh-bootstrap and steady-state deployment contract for
`agents/order-resolution/foundry-private`.

The currently selected target is supplied only through the target profile:

| Setting | Selected input |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Tenant | `a679d99f-b8f5-4d50-843e-5b73405ce0fc` |
| Resource group | `rg-maf-ora-foundry-private` |
| Foundry, Container Apps, and PostgreSQL region | `eastus2` |
| AI Search region | `eastus` (East US 2 capacity fallback) |
| AZD environment | `ora-foundry-private` |
| Access path | New private VM runner and Bastion in the target VNet |

These values are deployment inputs, not defaults that may be embedded in
generic Bicep, scripts, Make targets, `azure.yaml`, or workflow YAML. The
legacy `rg-maf-ora-foundry-v2`, `foundry-private-env`, `maffndpgv20722`, and
`foundry-private-v2` environment is historical evidence only and must not be
mutated.

## Portability contract

- `agents/order-resolution/deployment/profiles/foundry-private.env` is the
  canonical non-secret target profile shared through the Order Resolution
  profile framework.
- One shared loader validates and exports profile inputs.
- Secrets remain in AZD/GitHub secure stores or the process environment.
- Required target inputs have no target-specific fallback and fail closed.
- GitHub variables needed before checkout or for `runs-on` mirror the profile;
  a gate requires exact equality before mutation.
- A static contract rejects selected target literals in generic code outside
  the profile, this plan, and evidence documentation.
- Foundry account/project identifiers and endpoints are hydrated from actual
  provision outputs; they are never pre-constructed from an assumed name.
- Bootstrap creates resources and then transitions to reuse. Reuse must not
  reset images, secrets, network injection, capability hosts, PostgreSQL, or
  other stateful resources.

## Architecture

- External frontend Container App.
- Internal backend Container App.
- Private Foundry Responses agent.
- Private PostgreSQL Flexible Server.
- BYO VNet with separate `/24` Foundry agent-host subnet, private-endpoint
  subnet, Container Apps infrastructure subnet, runner subnet, and Bastion
  subnet.
- Private endpoints and DNS for Foundry, ACR, Storage, Cosmos DB, AI Search,
  and PostgreSQL.
- New VNet-connected self-hosted runner for private data-plane operations.
- Staged Foundry project connections and capability hosts after project
  identity and scoped RBAC propagation.

## PostgreSQL contract

- Bootstrap creates the server/database with public network access disabled.
- No Azure-services firewall rule or public-access compatibility path exists.
- An administrator-owned private-runner step applies the schema over the
  private FQDN.
- A separate runtime credential receives only database `CONNECT`, schema
  `USAGE`, table DML, and sequence `USAGE`.
- Runtime Container Apps and hosted agents set
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` and do not execute production DDL.
- The runtime URL, never the administrator URL, is stored in application
  secrets and Foundry runtime connections.
- `make foundry-postgres-readiness` must validate the disabled public-access
  state, approved private endpoint, private DNS mapping/VNet link, runner
  resolution, schema, and exact runtime privileges before app deployment.
- The readiness check is non-persistent and creates no proof artifact.

## Execution DAG

1. Implement the profile, loader, fail-closed portability contracts, and
   generic bootstrap/reuse IaC.
2. Implement least-privilege PostgreSQL schema/runtime separation.
3. Migrate runner workflows to profile-backed GitHub variables and a new
   target runner.
4. Run local tests, package checks, Bicep build, workflow contracts, profile
   tests, and target-literal scans.
5. Mark this plan `Ready for Validation` and invoke Azure Validate.
6. After validation, use Azure Deploy for provider/quota/policy checks, fresh
   preview, control-plane provisioning, runner bootstrap, output hydration, and
   reuse preview.
7. From the VNet runner, initialize the private PostgreSQL schema/runtime role
   and pass the private readiness gate.
8. Converge Foundry connections/RBAC and deploy immutable
   backend/frontend/hosted-agent artifacts.
9. Run fresh smoke, low-risk and HITL E2E, telemetry correlation, and strict
   exact-trace evaluation.

## Validation requirements

- Missing profile values fail before preview.
- No target-specific values appear as generic defaults.
- Fresh preview contains expected creates only and does not reference legacy
  resources.
- Reuse preview allows only reviewed benign metadata noise and contains no
  delete, replace, secret reset, network mutation, or stateful-resource drift.
- Model/SKU, PostgreSQL SKU, Search, Container Apps quota, providers, policy,
  and scoped RBAC are validated for the selected target.
- Runtime database startup succeeds without schema ownership or `CREATE`.
- Fresh provisioning never enables PostgreSQL public network access or creates
  a firewall rule.
- Private PostgreSQL readiness passes before application deployment.
- Only fresh release evidence is accepted.

## All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not applicable)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not applicable)

### Validation proof

- AZD 1.31.1 authentication resolves the selected tenant/subscription,
  `ora-foundry-private` environment, and East US 2 target.
- The Azure YAML schema is accepted by AZD packaging; the Bicep template
  compiles against PostgreSQL API `2024-08-01`.
- Full backend lint/test validation passed with 132 tests.
- Backend, frontend, and hosted-agent AZD packages all completed successfully.
- The PostgreSQL cutover preview completed without any delete or replacement.
  PostgreSQL, its private endpoint, and all private endpoints were `Skip`;
  no firewall resource or public-access enablement was proposed.
- Azure Policy evaluation found the existing management-group audit for
  PostgreSQL Entra-only authentication. This cutover intentionally retains
  password authentication; passwordless authentication remains a separately
  approved follow-up and did not block preview.
- Static RBAC verification remains valid because the cutover changes no
  principals, roles, or scopes.

| Command or gate | Result |
| --- | --- |
| `make test-foundry-portability` | Passed profile/release portability contracts. |
| `make foundry-iac-validate` | Bicep compiled with PostgreSQL API `2024-08-01`; no PostgreSQL network-property warning remains. |
| Focused database/IaC pytest selection | 7 passed. |
| `validate_private_runner_workflows.py` | Passed private workflow static contracts. |
| `make test` | Ruff passed and 132 backend tests passed. |
| `make foundry-package` | Backend, frontend, and hosted-agent packages passed. |
| Azure profile/authentication checks | Passed for the selected subscription, resource group, environment, and East US 2 location. |
| Azure Policy validation | Existing Entra-only PostgreSQL audit recorded as a separate passwordless-authentication follow-up. |
| `azd provision --preview --no-prompt` | Passed; PostgreSQL and private endpoints were unchanged, with no delete/replace/public-access/firewall action. |
| Static role verification | Passed; the cutover changes no RBAC assignments. |

## Live deployment and release evidence

| Stage | Workflow | Result |
| --- | --- | --- |
| Private infrastructure, preview, and PostgreSQL readiness | [`31906517820`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31906517820) | Passed |
| Final app-only deployment, commit `6e83a97` | [`31908682961`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31908682961) | Passed; hosted agent version 4 active |
| Final HITL, telemetry, and strict evaluation | [`31908858225`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31908858225) | Passed; 3/3 traces passed |

The final telemetry gate correlated 122 Application Insights rows and four
eligible Foundry evaluation spans across all three fresh hosted E2E
conversations. The strict Foundry result was `passed=3`, `failed=0`,
`errored=0`, `skipped=0`.

## Measured delivery timing

| Flow | Start | Telemetry ready | Elapsed |
| --- | --- | --- | ---: |
| Infrastructure/IaC to telemetry | Provision run `31906517820` at `20:22:38Z` | Evidence run `31906891692` at `20:36:15Z` | **13m 37s** |
| App-only to telemetry | Deployment run `31908682961` at `21:10:09Z` | Evidence run `31908858225` at `21:18:52Z` | **8m 43s** |

The infrastructure measurement includes the workflow handoffs: 3m36s for
preview/provision/readiness, 3m37s for app deployment, 5m18s from evidence
start to telemetry readiness, and 1m06s of dispatch gaps. The final app-only
measurement includes a 3m33s deployment, a 10s handoff, and 5m00s from
evidence start to telemetry readiness.

Telemetry readiness intentionally excludes Foundry evaluator completion. In
the final strict run, exact-trace evaluation finished at `21:22:03Z`, making
app-only deployment to complete release evidence **11m 54s**.

## Role Assignment Verification

- **Status:** Verified.
- Foundry project identity: Foundry User on the Foundry account; `AcrPull` and
  Container Registry Repository Reader on the target ACR; resource-scoped
  telemetry and Log Analytics roles.
- Capability-host data paths: Storage Blob data roles, Cosmos account/container
  roles, and Search index/service roles scoped to their target resources.
- Container Apps pull identity: `AcrPull` scoped to the target ACR.
- Backend identity: Foundry User scoped to the target Foundry account.
- Private runner identity: Contributor scoped to the selected resource group.
  Optional resource-group User Access Administrator remains disabled.
- Deployment identity bootstrap templates use resource-group Contributor/User
  Access Administrator and project/ACR-scoped release roles; no application
  runtime receives generic Contributor/Owner.

## Live issues and fixes

Every implementation, validation, preview, provisioning, database, runner,
release, or evidence issue must be appended immediately to
`docs/design/issues-changes-fixes.md` with the profile identifier, diagnosis,
fix, verification, and remaining impact.

## Stop conditions

- Azure/AZD resolves a different target from the profile.
- A selected target literal is embedded in generic code.
- A required input silently falls back.
- A preview references the legacy environment or proposes unexpected
  deletion/replacement, subnet pruning, network-injection changes, broad RBAC,
  public-access weakening, cross-region drift, or stateful mutation.
- A runtime receives administrator/schema-owner credentials or attempts DDL.
- The private runner, endpoints, DNS, project connections, capability hosts,
  RBAC, private PostgreSQL readiness, package build, deployed revisions, smoke,
  E2E, evaluation, or telemetry validation fails.
- A preview proposes enabling PostgreSQL public access, creating a firewall
  rule, replacing the server, or weakening its private endpoint/DNS contract.

## Planned repository surfaces

- `deployment/profiles/**`
- `infra/foundry-hosted/azure.yaml`
- `infra/foundry-hosted/iac/**`
- `Makefile`
- `.github/workflows/order-resolution-private-*.yml`
- `backend/app/core/database.py` and related tests
- `scripts/foundry/**`
- `scripts/github/**`
- `docs/design/issues-changes-fixes.md`
- directly affected README and operating-model documentation
