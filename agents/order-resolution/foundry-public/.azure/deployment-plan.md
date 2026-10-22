# Order Resolution Foundry Public Deployment Plan

**Status:** Complete; deployed and live-validated by finalized same-window release evidence
**Scope:** `agents/order-resolution/foundry-public` only

## Target contract

Create an ignored profile from
`deployment/profiles/foundry-public.env.example`. Replace every placeholder
with the externally approved subscription, resource group, region, AZD
environment, resource names, model identities/versions/SKUs/capacities, and
public service settings. Do not commit the populated profile, tenant/user
identity, resource IDs, endpoints, credentials, connection strings, or image
references.

The profile parser treats profiles as data, rejects unknown/missing/duplicate
keys and placeholders, and requires `DEPLOYMENT_LANE=foundry-public`.

## Authority boundaries

### App-only release

`make foundry-release` is the only routine release path. It:

1. accepts only `INFRASTRUCTURE_MODE=reuse`;
2. runs the change-aware validation route and Bicep compilation;
3. requires a fresh non-mutating infrastructure preview;
4. validates exact existing Foundry/models, Search, PostgreSQL, ACA, ACR,
   Bot, and Teams resources;
5. requires zero incremental growth and therefore zero additional quota;
6. verifies PostgreSQL readiness, the existing runtime-secret connection, and
   hosted-agent RBAC without mutation;
7. packages clean synchronized sources and immutable images;
8. deploys the hosted version, backend, and frontend concurrently after
   packaging and runtime-connection verification;
9. verifies and smokes the deployed application;
10. runs three-conversation hosted E2E, correlates telemetry, performs strict
    evaluation, and finalizes fresh secret-free evidence.

App-only cannot provision or update shared/stateful infrastructure, resize
models/services, create role assignments, create project connections, or apply
Teams infrastructure.

### Full infrastructure

`make foundry-provision` is separate from release and requires
`FOUNDRY_FULL_INFRA_AUTHORIZED=true` after review of a fresh preview. It owns
the public Bicep resource graph and post-provision hydration. Database schema
and least-privilege runtime credential setup remain explicit administrator
operations.

Teams Bot Service, channel, diagnostics, and related infrastructure remain a
full-IaC operation. `make foundry-teams-preview` uses ARM what-if without
mutation; apply requires the full-infrastructure authority flag.

## Capacity policy

Capacity preflight compares the desired profile with live resources.

- A healthy exact match needs zero incremental capacity and passes app-only.
- Matching infrastructure with lower scalable capacity requests only the
  difference in full-infrastructure mode.
- A missing, unhealthy, wrong model/version/SKU, or otherwise drifted resource
  fails app-only closed.
- Full-infrastructure mode reports required incremental capacity and fails when
  corresponding regional quota is insufficient.
- Public preflight intentionally omits private runner, VNet, private endpoint,
  and private-network checks.

The preflight is read-only. It reports only incremental capacity: an exact
healthy retained resource contributes zero, a lower scalable capacity
contributes only the difference in full-infrastructure mode, and app-only
fails closed on any required growth.

## Release safety and evidence

The release evidence directory is
`.artifacts/releases/<release-id>/`. Required evidence includes preview,
capacity/model preflight, exact deployment verification, hosted smoke, hosted
E2E, App Insights connection, telemetry, and evaluation. Every artifact must
belong to the same release window and remain secret-free.

The authority record enumerates allowed app-only and rollback actions.
Rollback may activate a previously verified immutable application version; it
cannot mutate shared/stateful infrastructure. Finalization rejects missing,
failed, stale, cross-window, secret-bearing, or inconsistent evidence and any
app-only-to-telemetry duration above 15 minutes.

Teams rollback is separate: endpoint rollback removes only Activity and Bot
authorization, catalog removal is an explicit Microsoft 365 governance action,
and Bot retention or deletion requires a reviewed infrastructure decision.
Neither rollback path may delete PostgreSQL state, Responses, Entra
authorization, or shared/stateful infrastructure.

## Validation commands

- [x] All validation checks pass
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
- **Identities checked:** backend and frontend user-assigned identities,
  Foundry account system identity, and Foundry project system identity.
- **Roles confirmed:** resource-scoped ACR Pull and repository read,
  Azure AI/Foundry user, Log Analytics reader, and evaluation-storage blob
  data owner assignments.
- **Scope:** assignments are limited to the specific registry, Foundry
  account/project, monitoring resources, and evaluation storage account.
- **Issues:** none; PostgreSQL uses separately provisioned least-privilege
  database credentials rather than Azure management-plane roles.

```bash
make test-deployment-profile
bash scripts/foundry/tests/test_release_portability_contract.sh
bash scripts/foundry/tests/test_release_scripts_contract.sh
bash scripts/foundry/tests/test_bootstrap_infrastructure_contract.sh
python3 -m pytest -q \
  scripts/foundry/tests/test_capacity_preflight.py \
  scripts/foundry/tests/test_preview_safety.py \
  scripts/foundry/tests/test_release_evidence.py \
  scripts/foundry/tests/test_teams_publishing.py
make foundry-iac-build
make foundry-capacity-preflight-full
make foundry-package
```

Run `azd config validate` from `infra/foundry-hosted` when the installed AZD
version supports it. Package checks are local-only and must not push images.

## 7. Validation Proof

- AZD 1.36 authentication, the new external bootstrap profile, and the
  selected East US 2 environment passed target validation.
- The official Azure Developer CLI schema validator accepted `azure.yaml`.
- Bicep compiled for the primary graph, runtime-secret connection, and
  Teams/Bot modules.
- The full-infrastructure AZD preview completed without mutation and proposed
  only expected creates; it proposed no deletes or replacements.
- Live model validation confirmed `gpt-4.1-mini` `2025-04-14` and
  `text-embedding-3-small` `1` support `GlobalStandard` with sufficient
  incremental quota.
- PostgreSQL 17 `Standard_D2ds_v5`, Azure AI Search, Container Apps,
  compute, ACR, monitoring, storage, and Bot Service prerequisites passed.
- Subscription and inherited policy assignments were reviewed; template
  validation and the successful what-if reported no policy conflict.
- Static least-privilege RBAC review passed, including resource-scoped data
  roles and no subscription- or resource-group-wide application roles.
- Hosted, backend, and frontend packaging passed from the clean synchronized
  source using the 112-wheel CPython 3.13 Linux AMD64 wheelhouse.
- Focused capacity, preview-safety, release-script, and Teams IaC regression
  tests passed after fixing the AZD agent name, bootstrap-preview resource
  group handling, public Bot networking, script execution modes, and current
  PostgreSQL capability response parsing.

## Stop conditions

Stop if target/profile validation fails; preview proposes mutation during
app-only; a retained resource is missing, unhealthy, or drifted; incremental
quota is required during app-only; PostgreSQL/runtime connection/RBAC checks
fail; package or immutable deployment checks fail; hosted activation does not
precede ACA deployment; E2E/evaluation/telemetry fails; or evidence is stale,
secret-bearing, incomplete, or over budget.

The public resources and application are deployed. Release
`order-resolution-20261022T001617Z-1249190` finalized every same-window gate
and is the current live-validation record.

## Live deployment progress

- Shared public infrastructure converged after reviewed previews, including
  Foundry/project/models, ACR, evaluation storage, monitoring, Container Apps,
  PostgreSQL, managed identities and scoped application roles.
- Azure AI Search was added to the public Bicep contract. East US 2 lacked
  allocation capacity for a new Basic service, so only Search was placed in
  Canada Central after a second preview; the application topology remains in
  East US 2.
- PostgreSQL schema, least-privilege runtime credentials, and the Foundry
  runtime-secret connection converged without committing credentials.
- Hosted activation, Bot/Teams deployment and Shared publication,
  backend/frontend deployment, runtime-secret verification, and resource-
  scoped role verification completed.
- Release `order-resolution-20261022T001617Z-1249190` completed preview, model
  preflight, concurrent stateless deployment, verification, smoke,
  three-conversation hosted E2E, telemetry correlation, strict Foundry
  evaluation, and aggregate evidence finalization.
- The app-only-to-telemetry interval was **11m 45.254s**, below the 15-minute
  budget. Task Completion and Coherence each passed 3/3 conversations;
  telemetry correlated all three conversations with zero exceptions.
- Final evidence aggregation passed after correcting telemetry/evaluation
  timing order, allowing numeric evaluator token-usage metrics, and making a
  failed final-evidence timing attempt retryable.
