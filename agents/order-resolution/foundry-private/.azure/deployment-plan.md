# Foundry Private Deployment Plan

> **Status:** Validated — routine app-only release only. Full
> bootstrap/reconciliation is blocked pending approved resolution of shared
> authoritative drift; no deployment is recorded by this plan.

## Target

| Setting | Value |
| --- | --- |
| Resource group | `rg-maf-ora-foundry-v2` |
| AZD environment | `foundry-private-env` |
| Region | `eastus2` (PostgreSQL: `centralus`) |
| Hosted agent | `order-resolution-hosted` |
| Canonical PostgreSQL FQDN | `maffndpgv20722.postgres.database.azure.com` |
| Private runner label | `foundry-private-v2` |

## Recorded full-IaC preview evidence

Preview run `31198356080` identified shared authoritative drift in:

- VNet and subnets;
- the Container Apps environment;
- Foundry account, project, and models;
- ACR;
- Cosmos;
- Application Insights; and
- Search.

The drift is authoritative/shared, not routine application-release scope.
Therefore no full Bicep application, automatic reconciliation, or deployment
success claim is authorized from this preview. An owner-approved reconciliation
plan must identify the intended state for every accepted change before a new
full-IaC preview and an approved bootstrap/reconciliation operation.

## Safe release classes

| Class | Scope | Preconditions and outcome |
| --- | --- | --- |
| Routine app-only release | Existing ACA backend/frontend revisions plus the existing hosted agent. | Validate the existing private dependencies. Do not invoke full Bicep, mutate shared infrastructure, accept preview drift, or change PostgreSQL access. |
| Bootstrap/reconciliation | Full Bicep management-plane scope. | Capture a current preview, review all shared-resource changes, and receive explicit approval of the reconciliation plan before execution. |
| PostgreSQL lockdown | Canonical PostgreSQL private-access controls. | Execute separately with explicit confirmation only after a fresh generated proof confirms ACA and hosted-agent connectivity to the canonical FQDN. |

## Private-network invariants

The frontend is the only external ingress and proxies `/api` to the internal
backend. The backend and hosted agent reach Foundry and PostgreSQL through
private networking. The Container Apps environment must use its dedicated
subnet, separate from the Foundry agent-host subnet. Keep
`POSTGRES_SERVER_NAME` and `RUNTIME_DATABASE_URL` aligned to the canonical
FQDN. Public-access removal and Azure-services firewall removal are allowed
only in the separate proof-gated PostgreSQL lockdown operation.

## Validation evidence and current gate

- Local `make validate-full` passed: 128 backend tests, 10 deterministic
  evaluations, 7 workflow E2E tests, 4 selected-thread E2E tests, and the
  design-review gate.
- Private static workflow validation passed in GitHub Actions run
  `31199738312` for commit `b7febf2`.
- The app-only preflight is ready to read existing topology, project
  connections, ACR roles, and revision images without modifying Azure.
- Azure Validate access is restored. AZD installation, schema/environment,
  Azure authentication, subscription/location, Docker build-context, build,
  and preview checks completed. The complete read-only app-only dependency
  preflight passed on the selected private environment.
- Protected package-only run `31206155614` passed on `vm-maffnd-runner`; it
  validated dependencies, generated the hosted-agent context, and built all
  release images without publishing or deploying them.
- Azure Policy baseline: `az policy state list` reports 18 pre-existing
  noncompliant states in `rg-maf-ora-foundry-v2`. They include shared runner
  VM, VNet, ACR, PostgreSQL, Search, and Foundry-project diagnostics resources.
  The user explicitly accepted this existing audit baseline for the routine
  app-only release on 2026-08-07. This release must not modify those shared
  resources or introduce a new policy finding; remediation remains separate.

## All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not applicable; this is not an Aspire project)
- [x] 7. Provision Preview (completed; full-IaC reconciliation remains blocked)
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation (18 existing shared-resource audit findings accepted as the app-only baseline on 2026-08-07; no new finding permitted)
- [x] 12. Aspire Post-Provisioning Checks (not applicable; this is not an Aspire project)

**Local packaging limitation.** Local Docker packaging cannot complete when `npm ci`
contacts `registry.npmjs.org`: the managed-device endpoint returns
`ERR_SSL_SSLV3_ALERT_HANDSHAKE_FAILURE`, after which npm incorrectly exits
successfully without installing TypeScript. A protected package-only workflow
will run the same `azd package --no-prompt` check on `vm-maffnd-runner`
without publishing images or modifying Azure resources. Its result is required
before the app-only deployment and passed in run `31206155614`; the local
limitation is not a release gate.

## Gate ownership and approval map

| Gate | Where it runs | Current state | Decision owner |
| --- | --- | --- | --- |
| Static workflow and Bicep validation | `.github/workflows/order-resolution-private-validation.yml` | Passed: `31206115459` | Repository maintainers |
| Private dependency/RBAC preflight | `scripts/foundry/validate_private_app_release.sh` via `make foundry-app-only-preflight` | Passed read-only | Private resource-group operator |
| Private package build | `.github/workflows/order-resolution-private-package-validation.yml` | Passed: `31206155614` | Private runner operator |
| Azure Policy compliance | Azure Policy states for `rg-maf-ora-foundry-v2` | 18 existing findings accepted as the app-only baseline; no new finding permitted | Subscription security/governance owners remediate separately |
| App-only artifact deployment | `.github/workflows/order-resolution-private-deploy.yml` | Eligible after Azure Validate completes | Release approver |
| Full reconciliation | `.github/workflows/order-resolution-private-provision.yml` and `make foundry-provision-preview` | Blocked by shared-resource drift | Shared-network, Foundry, data, registry, and observability owners |
| PostgreSQL lockdown | `make foundry-connectivity-proof` then `make foundry-postgres-lockdown` | Not eligible until after a separate fresh proof | Database owner with explicit confirmation |
| Hosted telemetry diagnosis | `.github/workflows/order-resolution-private-observability.yml` | Runs after deployment | Release owner |
| Hosted smoke/E2E/evaluation/telemetry evidence | `.github/workflows/order-resolution-private-evidence.yml` | Runs only after a successful deployment | Release owner |

### Required policy decision

Seventeen findings come from `SecurityCenterBuiltIn`, the subscription's
default **audit-only** Defender policy assignment. The remaining
`ProjectsAIFoundry_Diagnostics_Enable` finding is inherited through
`MCAPSGovDeployPolicies` at management-group scope. The current deployment
identity can remediate resource-group resources but cannot read or approve the
management-group assignment. The governance owner must approve one of:

1. a documented, time-bounded exception that permits this app-only release
   while the pre-existing findings remain; or
2. a remediation plan for the shared resources, including the Foundry
   diagnostics requirement, followed by a new compliance check.

The user selected option 1 for this release on 2026-08-07. The acceptance is
limited to the current 18 findings and the app-only scope; it does not approve
full-IaC reconciliation, PostgreSQL lockdown, or any new policy violation.

## Role Assignment Verification

**Status:** Verified statically on 2026-08-07.

- Foundry project identity: Azure AI Foundry User on the Foundry account,
  `AcrPull` and Container Registry Repository Reader on the private ACR, plus
  resource-scoped telemetry and Log Analytics roles.
- Backend Container App identity: Azure AI Foundry User on the Foundry account.
- Container Apps registry-pull identity: `AcrPull` on the private ACR.
- Foundry project/capability-host data paths: Storage Blob Data Contributor and
  scoped Blob Data Owner, Cosmos DB Operator and scoped SQL assignment, plus
  Search Index Data Contributor and Search Service Contributor.
- The private runner's subscription-scoped deployment permissions are confined
  to runner provisioning and are not used by the routine app-only release.

No missing data-plane role or overly broad application runtime assignment was
found in the Bicep review. Live role verification remains a post-deployment
Azure Deploy gate.

## 7. Validation Proof

Recorded 2026-08-07T14:13:52-05:00.

| Command or gate | Result |
| --- | --- |
| `make test` | Passed: 128 backend tests and Ruff checks. |
| `cd frontend && npm run build` | Passed production TypeScript and Vite build. |
| `azd version`, `azd auth login --check-status`, and retained environment checks | Passed for `foundry-private-env`, subscription `4f18d577-3506-4a11-85e5-a83b14727a84`, and `eastus2`. |
| `azd provision --preview --no-prompt` | Completed without applying changes; reconfirmed full-IaC shared-resource drift, which remains outside app-only scope. |
| `validate_private_app_release.sh` | Passed read-only topology, Foundry project/connection, model, PostgreSQL, ACR, revision, and RBAC validation. |
| Private static validation `31206115459` | Passed workflow contract, shell, parameter, and Bicep validation. |
| Protected package validation `31206155614` | Passed dependency preflight, hosted source sync, and package build without publishing or deployment. |
| Azure Policy state query | 18 existing findings accepted by the user as the bounded app-only baseline; no shared-resource modification or new finding is permitted. |
| Static Bicep RBAC review | Passed; resource-scoped roles match managed-identity data-plane operations. |

## Execution decision

Use the VNet-connected `foundry-private-v2` runner and serialized release
control plane. A routine app-only release validates existing dependencies and
releases only ACA revisions and the hosted agent. Do not use it to conceal,
repair, or reconcile the recorded full-IaC drift. Do not perform PostgreSQL
lockdown as part of it.

Before a bootstrap/reconciliation, rerun a full Bicep preview and require
explicit approval of every shared-resource change. The preview is not a
deployment or health proof. After any actual applicable release, record fresh
non-secret hosted E2E, evaluation, telemetry, and (for lockdown) connectivity
proof evidence in `docs/design/issues-changes-fixes.md`.
