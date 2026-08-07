# Foundry Private Deployment Plan

> **Status:** Ready for Validation — routine app-only release only. Full
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
- Azure Policy validation is **not passing**: `az policy state list` reports
  18 noncompliant states in `rg-maf-ora-foundry-v2`. They include shared runner
  VM, VNet, ACR, PostgreSQL, Search, and Foundry-project diagnostics resources.
  The app-only lane must not modify those shared resources, so this plan is
  **not Validated** and the protected app-only deployment must not start until
  the policy owners provide an approved remediation or exception decision.

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
- [ ] 11. Azure Policy Validation (18 existing noncompliant shared-resource states)
- [x] 12. Aspire Post-Provisioning Checks (not applicable; this is not an Aspire project)

**Packaging execution note.** Local Docker packaging is blocked when `npm ci`
contacts `registry.npmjs.org`: the managed-device endpoint returns
`ERR_SSL_SSLV3_ALERT_HANDSHAKE_FAILURE`, after which npm incorrectly exits
successfully without installing TypeScript. A protected package-only workflow
will run the same `azd package --no-prompt` check on `vm-maffnd-runner`
without publishing images or modifying Azure resources. Its result is required
before the app-only deployment.

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
