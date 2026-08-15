# Order Resolution Foundry Private Deployment Plan

> **Status:** Validated

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

- Bootstrap creates the server/database in the profile-selected region.
- An administrator-owned step applies the schema over the private FQDN.
- A separate runtime credential receives only database `CONNECT`, schema
  `USAGE`, table DML, and sequence `USAGE`.
- Runtime Container Apps and hosted agents set
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` and do not execute production DDL.
- The runtime URL, never the administrator URL, is stored in application
  secrets and Foundry runtime connections.
- Public access is disabled only after fresh ACA and hosted-agent connectivity
  proof validates the canonical private endpoint and DNS.

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
   preview, runner bootstrap, full provisioning, connection/RBAC convergence,
   database bootstrap, output hydration, and reuse preview.
7. Deploy immutable backend/frontend/hosted-agent artifacts.
8. Run fresh smoke, low-risk and HITL E2E, evaluation, telemetry, connectivity
   proof, PostgreSQL lockdown, and post-lockdown verification.

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

- AZD authentication resolves the selected tenant/subscription and
  `ora-foundry-private` environment.
- The target resource group does not exist, as expected for clean bootstrap.
- Required providers are registered and the deployment identity has Owner.
- East US 2 has PostgreSQL `Standard_B1ms`/version 18 support, 48 available
  Container Apps environments, 100 available Dsv7-family vCPUs, and sufficient
  network quota.
- Foundry capacity discovery selected `gpt-4o` 2024-11-20 Global Standard,
  capacity 1, with 450K TPM available; the deprecated `gpt-4o-mini` version was
  rejected and removed from the profile.
- Full local validation passed: 130 backend tests, 10/10 deterministic
  evaluations, seven workflow and four selected-thread Playwright tests,
  design review, Bicep/profile/workflow/database contracts, and all three AZD
  packages.
- Fresh `azd provision --preview --no-prompt` passed with expected creates only
  in `rg-maf-ora-foundry-private`; no legacy resource or delete/replace action
  was proposed.

| Command or gate | Result |
| --- | --- |
| `make test-foundry-portability` | Passed profile/release portability contracts. |
| `make foundry-iac-validate` | Bicep compiled; lint warnings are non-blocking and recorded. |
| Focused database/IaC pytest selection | 11 passed. |
| `validate_private_runner_workflows.py` | Passed private workflow static contracts. |
| `make validate-full` | 130 tests, 10/10 eval cases, 7 workflow E2E, 4 selected-thread E2E, and design review passed. |
| `make foundry-package` | Backend, frontend, and hosted-agent packages passed. |
| Azure provider/RBAC/profile checks | Passed for the selected subscription, target, and Owner identity. |
| Azure quota/capability checks | PostgreSQL, Foundry model, Container Apps, VM, and network capacity passed. |
| `azd provision --preview --no-prompt` | Passed with expected fresh creates only. |
| Static role verification | Passed after narrowing runner Contributor to resource-group scope. |

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
  RBAC, package build, deployed revisions, smoke, E2E, evaluation, telemetry,
  connectivity proof, or lockdown validation fails.

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
