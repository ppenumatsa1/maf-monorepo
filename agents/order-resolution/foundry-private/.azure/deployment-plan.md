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
- The mandatory Azure Validate skill workflow could not be executed because
  its workflow resources were denied by the content-exclusion policy. This
  plan is therefore **not Validated**, and the protected app-only deployment
  must not start until that gate can run successfully.

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
