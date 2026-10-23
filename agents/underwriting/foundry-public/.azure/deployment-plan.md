# Underwriting Foundry Public Bootstrap Plan

> **Status:** Validated

## Objective

Use one parameterized AZD + Bicep source of truth to bootstrap or explicitly
reuse an Underwriting Foundry public environment.

## Target context

| Attribute | Value |
| --- | --- |
| Subscription | supplied by the ignored external deployment profile |
| Resource group | supplied by the ignored external deployment profile |
| Location | supplied by the ignored external deployment profile |
| New-environment mode | `bootstrap` |
| Existing-environment mode | `reuse` |

## Intended resources

Bootstrap creates Foundry account/project and parameterized `gpt-4.1-mini`
Global Standard deployment, ACR, Log Analytics, Application Insights, Container
Apps environment/apps, identities, PostgreSQL, evaluation storage, connections,
and role assignments. Reuse references existing resources and creates neither
resources nor role assignments.

Routine application release remains app-only. PostgreSQL runtime credentials
and schema are explicit post-provision actions. Fresh bootstrap creates an
external frontend and internal backend; the frontend proxies `/api` and
`/backend-health` to the backend's internal ACA FQDN.
The hosted runtime URL is converged into the Underwriting project
`underwritingruntimesecrets` `CustomKeys` connection after credential
provisioning; agent metadata contains only its connection placeholder.

## 7. Validation Proof

- **Validated at:** `2026-10-23T13:14:00Z`.
- `make quality` passed lint, formatting, backend/frontend tests, release
  script contracts, Activity reconciliation tests, Teams publication tests,
  portability checks, and strict evidence tests.
- `make test-deployment-profile foundry-iac-build foundry-package` passed.
  Both application and Teams Bicep templates compiled, all three Docker
  services packaged successfully, and the external deployment profile
  remained portable.
- `azure.yaml` passed the official stable-schema validator.
- Azure CLI and Azure Developer CLI authentication resolve to the selected
  enabled subscription and the `uw-foundry-public-eus2` AZD environment.
- The target resource group is empty, healthy, and located in East US 2.
- The selected `gpt-4.1-mini` version `2025-04-14` supports
  `GlobalStandard`; the subscription has 2,220K TPM available and this
  deployment requests 100K TPM.
- Both Bicep templates compile. Deployment-profile, capacity-preflight, and
  preview-safety tests pass.
- All three services package successfully from clean Docker build contexts;
  the Python package step reuses 120 hash-verified Python 3.13 wheels.
- The full-infrastructure `azd provision --preview --no-prompt` completed and
  passed the repository safety validator without applying resources.
- Subscription policy inventory and compliance summary were reviewed; the
  target preview reported no blocking policy failure.

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

## Role Assignment Verification

- **Status:** Verified.
- **Identities checked:** backend Container App, frontend Container App,
  Foundry account, and Foundry project managed identities.
- **Roles confirmed:** resource-scoped ACR pull/repository reader, Foundry user,
  Azure AI user, monitoring reader, and evaluation Storage Blob Data Owner
  assignments.
- **Issues:** None. Bootstrap assignments are deterministic and scoped to the
  ACR, Foundry account/project, monitoring resources, and evaluation storage.
  Live role propagation will be verified after provisioning.

## Delivery flow

1. Invoke the validated bootstrap deployment workflow.
2. Provision runtime PostgreSQL credentials and schema.
3. Validate all three service contexts; build backend and hosted images
   concurrently in ACR and the frontend concurrently with local Docker.
4. Activate the hosted agent from its exact digest and persist its version,
   then deploy the digest-pinned internal backend and external frontend
   concurrently without repeating ingress mutations.
5. Run smoke and deployed same-origin web E2E, then wait for one approved and
   one declined real Teams card action observed from PostgreSQL.
6. Run strict Foundry evaluation, correlate the exact web and Teams workflow
   runs in Application Insights, and run `foundry-verify`.
7. Aggregate secret-free release-window evidence with `make foundry-evidence`
   and record the release in `docs/design/issues-changes-fixes.md`.

Infrastructure, Teams publication, and hosted version 7 are deployed. Hosted
happy, retry, and crash/resume smoke pass, and a strict live trace evaluation
has passed both configured criteria. Final canonical release evidence still
requires real Teams approval/decline, exact telemetry correlation, deployment
verification, and rollback proof. Finalization rejects totals above 15 minutes
for app-only deployment through telemetry, excluding the documented operator
wait for native Teams actions.

The native Teams gate is an explicit operator checkpoint: send
`start sample underwriting review` twice in the published agent, approve one
card, and decline the other. Destructive PostgreSQL rebuild remains separately
guarded by its server-specific confirmation token.
