# Underwriting Foundry Public Bootstrap Plan

> **Status:** Validated

## Objective

Use one parameterized AZD + Bicep source of truth to bootstrap or explicitly
reuse an Underwriting Foundry public environment.

## Target context

| Attribute | Value |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-maf-underwriting` |
| Location | `eastus2` |
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

- The target resource group exists in the intended subscription and region.
- Bicep compilation, deployment-profile/bootstrap-contract tests, PostgreSQL
  credential tests, package validation, shell syntax, and whitespace checks
  pass.
- Bootstrap preview proposes the Foundry/model, ACR, monitoring, Container
  Apps, PostgreSQL, identities, evaluation storage, connections, and RBAC
  resources without applying changes.
- Explicit reuse preview skips every existing resource without applying
  changes.

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

The 2026-08-15 reuse preview skipped all ten existing resources, package
validation built all three deployable services, and the resource-group policy
summary reported no non-compliant policies or resources.

## Role Assignment Verification

- **Status:** Verified.
- **Identities checked:** backend Container App, frontend Container App,
  Foundry account, and Foundry project managed identities.
- **Roles confirmed:** resource-scoped ACR pull/repository reader, Foundry user,
  Azure AI user, monitoring reader, and evaluation Storage Blob Data Owner
  assignments.
- **Issues:** None. Reuse mode creates no role assignments, and the app-only
  release does not mutate RBAC.

## Delivery flow

1. Invoke the validated bootstrap deployment workflow.
2. Provision runtime PostgreSQL credentials and schema.
3. Validate all three service contexts; build backend and hosted images
   concurrently in ACR and the frontend concurrently with local Docker.
4. Activate the hosted agent from its exact digest and persist its version,
   then deploy the digest-pinned internal backend and external frontend
   concurrently without repeating ingress mutations.
5. Run smoke, deployed same-origin E2E, Foundry evaluation, telemetry, and
   `foundry-verify`.
6. Aggregate secret-free release-window evidence with `make foundry-evidence`
   and record the release in `docs/design/issues-changes-fixes.md`.

Release `uw-public-51a8311-20260816140654` live-validated this flow and reached
telemetry in 14m 10.0s. Finalization rejects totals above 15 minutes.

No additional manual approval checkpoint is required. A deployment invocation
is the execution trigger; destructive PostgreSQL rebuild remains separately
guarded by its server-specific confirmation token.
