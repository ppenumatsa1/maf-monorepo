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

## Validation evidence

- The target resource group exists in the intended subscription and region.
- Bicep compilation, deployment-profile/bootstrap-contract tests, PostgreSQL
  credential tests, package validation, shell syntax, and whitespace checks
  pass.
- Bootstrap preview proposes the Foundry/model, ACR, monitoring, Container
  Apps, PostgreSQL, identities, evaluation storage, connections, and RBAC
  resources without applying changes.
- Explicit reuse preview skips every existing resource without applying
  changes.

## Delivery flow

1. Invoke the validated bootstrap deployment workflow.
2. Provision runtime PostgreSQL credentials and schema.
3. Package all declared services and run the app-only release workflow: deploy
   and persist the hosted agent first, then deploy the internal backend and
   external frontend concurrently.
4. Run smoke, deployed same-origin E2E, Foundry evaluation, telemetry, and
   `foundry-verify`.
5. Aggregate secret-free release-window evidence with `make foundry-evidence`
   and record the release in `docs/design/issues-changes-fixes.md`.

No additional manual approval checkpoint is required. A deployment invocation
is the execution trigger; destructive PostgreSQL rebuild remains separately
guarded by its server-specific confirmation token.
