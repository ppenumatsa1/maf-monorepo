# Azure App-Hosted Deployment Plan

> **Status:** Validated
>
> The user approved the prepared Azure-hosted parity, bootstrap, database
> transition, and deployment plan. A claim that the current source revision is
> deployed still requires a fresh generated release bundle. Historical results
> are retained in [the evidence ledger](../docs/issues-changes-fixes.md).

## Intended target

| Setting | Source intent |
| --- | --- |
| Target selection | Validated, ignored operator profile |
| Package | `infra/azure-apphosted/` |
| Browser topology | External React/Nginx frontend -> same-origin `/api` -> internal FastAPI/MAF backend |
| Database | Retained Azure PostgreSQL with backend managed identity |
| Model/evaluation boundary | Optional Foundry model inference and report-only evaluation |
| Excluded surfaces | Private networking, hosted-agent/Responses, Bot, Activity, Teams, Adaptive Cards |

Tracked documentation contains no concrete tenant, subscription, user,
resource, region, or endpoint values.

## Deployment recipe

- **Type:** Azure Developer CLI (`azd`) with subscription-scope Bicep.
- **Workspace:** this Azure-hosted lane.
- **Bootstrap:** validated ignored profile -> read-only capacity/policy checks
  -> `azd provision --preview` -> reviewed bootstrap provisioning.
- **Application deployment:** immutable backend/frontend Container App images
  through the lane's app-only release workflow.
- **Database transition:** administrator-owned PostgreSQL schema/grant
  migration after bootstrap and before application activation.

## Lifecycle model

### Fresh bootstrap

Use only for a new profile-selected environment.

1. Validate the ignored profile and active Azure/AZD context.
2. Supply untracked bootstrap inputs through the operator environment.
3. Run and review a fresh subscription-scope preview.
4. Stop on target mismatch, unexpected replacement/deletion, unsupported
   capacity, public exposure, or excessive privilege.
5. Provision only through the authorized bootstrap path.
6. Establish schema and least-privilege PostgreSQL access for the backend
   managed identity.
7. Verify identities, health, and monitoring.
8. Remove temporary bootstrap access and transition to steady state.
9. Run an app-only release to deploy and validate the application.

### Steady-state infrastructure

PostgreSQL and application data are retained. Infrastructure reconciliation is
never inferred from changed files.

```bash
make release-infra-preview
make release-infra-reconcile
```

The apply command obtains its own fresh preview and must fail on unexpected
stateful mutation, identity expansion, replacement, or public exposure.

### Routine app-only release

```bash
make release-app
```

The release:

1. validates source and target context;
2. builds and validates immutable backend/frontend images;
3. deploys only the application revisions;
4. converges the backend to internal ingress and frontend to external ingress;
5. verifies image digests, active revisions, health, and proxy behavior;
6. runs smoke, hosted browser E2E, and three HTTP/durable domain scenarios;
7. verifies exact Application Insights correlation and zero relevant
   exceptions;
8. runs report-only Foundry evaluation over the captured HTTP results; and
9. aggregates final secret-free evidence.

PostgreSQL, schema, data, and RBAC must not be recreated or broadened by this
path. Failed validation must still write failed final evidence.

## Profile contract

The operator profile is data, not shell code. It may contain only the approved
target selectors:

```dotenv
CONTRACT_VERSION=1
DEPLOYMENT_LANE=azure-hosted
AZURE_ENV_NAME=<azd-environment>
AZURE_TENANT_ID=<tenant-guid>
AZURE_SUBSCRIPTION_ID=<subscription-guid>
AZURE_RESOURCE_GROUP=<resource-group>
AZURE_LOCATION=<azure-region>
NAME_PREFIX=<name-prefix>
POSTGRES_DATABASE_NAME=<database-name>
```

The tracked bootstrap example documents additional approved model, PostgreSQL,
and capacity selectors. The selected profile must not contain user IDs,
credentials, connection strings, tokens, operator IPs, image references,
generated resource IDs, or endpoints.

## All validation checks pass

### Source and local gates

- [x] `make test`
- [x] `make eval-backend`
- [x] `make test-e2e`
- [x] `./scripts/skills/design-review-skill.sh`
- [x] release-contract/profile tests
- [x] Bicep build and local package checks

### Azure Developer CLI validation steps

- [x] 1. AZD installation.
- [x] 2. Official `azure.yaml` schema validation.
- [x] 3. Ignored AZD environment and operator-profile setup.
- [x] 4. AZD authentication check.
- [x] 5. Active tenant/subscription/location verification, including read-only
  regional capacity and quota checks.
- [x] 6. Aspire pre-provisioning checks (not applicable; this is not an Aspire
  project).
- [x] 7. Fresh non-mutating bootstrap provision preview.
- [x] 8. Backend/frontend build verification.
- [x] 9. Docker build-context and lock validation.
- [x] 10. AZD package validation for all services.
- [x] 11. Azure Policy review and static least-privilege RBAC verification.
- [x] 12. Aspire post-provisioning checks (not applicable; this is not an
  Aspire project).

Documentation-only changes may use the focused documentation validation
described in the final section instead of application test suites.

### Azure release gates

- [x] Selected profile, Azure CLI, and AZD environment match.
- [x] Exact immutable backend/frontend images are deployed.
- [x] Backend ingress is internal.
- [x] Frontend ingress is external and proxied `/api` health passes.
- [x] Low-risk scenario completes without HITL.
- [x] High-risk scenario pauses and resumes.
- [x] Damaged-item scenario pauses and resumes.
- [x] Hosted browser E2E passes.
- [x] Exact telemetry correlation passes with zero relevant exceptions.
- [x] Report-only evaluation completes with zero failed or errored rows.
- [x] Final evidence passes the app-only-to-telemetry budget.

## Validation Proof

- **AZD and authentication:** `azd version` and
  `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd auth login --check-status`
  passed.
- **Schema:** the Azure MCP `validate_azure_yaml` command validated
  `azure.yaml` against the official stable schema.
- **Environment:** `make prepare-bootstrap` created the ignored local AZD
  environment from the validated external operator profile. Bootstrap-only
  PostgreSQL selectors, administrator identity, operator IP, and image
  references remained untracked.
- **Regional preflight:** the preferred Canada Central preview was rejected by
  Azure because the required `gpt-4.1-mini` model version supports neither
  requested deployment SKU there. The previously approved East US 2 fallback
  passed model, service, quota, and resource-name checks.
- **Infrastructure preview:**
  `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --preview --no-prompt --environment <approved-environment>`
  completed successfully and proposed only the expected resource group, ACR,
  monitoring, Foundry account/project/models, PostgreSQL server, Container Apps
  environment, identities, role assignments, and two Container Apps.
- **PostgreSQL capacity recovery:** an initial live provision exposed that the
  profile's PostgreSQL SKU/tier/version selectors were validated but not passed
  into Bicep. Those selectors are now wired through the AZD environment,
  parameters, root template, and PostgreSQL module. Burstable capacity remained
  unavailable at provision time, so the profile selected the supported
  General Purpose fallback and a fresh preview accepted it.
- **Foundry concurrency recovery:** project creation is serialized after the
  account's three model deployments to prevent concurrent child-resource
  updates from returning `RequestConflict`. Bicep compilation and the fresh
  Azure preview passed with that dependency.
- **Evaluation operator scope recovery:** a live strict evaluation proved that
  project-scoped `Foundry User` does not authorize
  `Microsoft.CognitiveServices/accounts/AIServices/assets/write`. The operator
  assignment is now account-scoped, matching the validated sibling release.
  The subscription portability contract, Bicep build, official `azure.yaml`
  schema validation, policy review, AZD authentication, fresh steady-state
  provision preview, and AZD package validation all passed after the change.
- **Build and Docker contexts:** `make bicep-build` and
  `BACKEND_IMAGE=<explicit-image> FRONTEND_IMAGE=<explicit-image> make build-release-images`
  passed. The backend used the hash-verified offline Python wheelhouse; the
  frontend Docker build used its committed npm lockfile.
- **Packaging:**
  `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd package --no-prompt --environment <approved-environment>`
  packaged both services successfully.
- **Policy:** subscription and inherited management-group assignments were
  reviewed. The successful ARM preview confirmed no evaluated deny policy
  blocks the proposed East US 2 topology. Write operations still require the
  operator's current MFA authorization.
- **Result:** all recipe-specific validation, build, package, policy, and
  static role checks passed. The validated steady-state RBAC correction then
  provisioned successfully.

## Role Assignment Verification

- **Status:** Verified.
- **Identities:** backend managed identity, frontend managed identity, and
  Foundry project identity.
- **Backend:** `AcrPull` is scoped to the deployment ACR; `Cognitive Services
  OpenAI User` is scoped to the Foundry account; `Foundry User` is scoped to
  the Foundry project. PostgreSQL access is created as an Entra database
  principal and constrained with SQL grants rather than an ARM role.
- **Frontend:** `AcrPull` is scoped only to the deployment ACR.
- **Foundry project identity:** `Foundry User` is scoped only to the Foundry
  account required by the project.
- **Evaluation operator:** the explicitly supplied interactive operator
  principal has `Foundry User` only on the Foundry account because cloud judge
  evaluation asset creation is authorized at the parent account scope.
- **Monitoring:** the backend exports OpenTelemetry through the generated
  Application Insights connection string and does not require a broad Azure
  management role.
- **Forbidden scopes:** no subscription-wide or resource-group-wide application
  data roles.
- **Issues:** none. The obsolete project-scoped evaluation-operator assignment
  was removed after the account-scoped role and successful evaluation were
  verified.

### Live Role Verification

- Azure MCP and Azure CLI role queries confirmed both application identities
  have `AcrPull` only on the deployment ACR.
- The backend additionally has `Cognitive Services OpenAI User` on the Foundry
  account and `Foundry User` on the Foundry project.
- The Foundry project identity has `Foundry User` only on its parent account.
- The interactive evaluation operator has the required `Foundry User` on the
  Foundry account. The prior project-scoped assignment was removed.
- No application identity has a subscription-wide or resource-group-wide role.
- **Status:** Passed.

## Final Deployment Proof

- The selected steady-state environment provisioned the account-scoped
  evaluation-operator RBAC correction successfully.
- Both Container Apps report `Succeeded` and `Running`; backend ingress is
  internal and frontend ingress is external.
- The public frontend health endpoint returned `ok` after infrastructure
  reconciliation.
- The canonical release completed with status `succeeded`; every declared gate
  and artifact passed.
- Hosted browser E2E and the low-risk, high-risk approval/resume, and
  damaged-item approval/resume scenarios passed.
- Three telemetry correlation pairs passed with zero relevant exceptions.
- App-only start through telemetry completed in `397635` ms, below the
  15-minute budget.
- Foundry report-only evaluation completed all three conversations. Task
  Completion and Coherence each passed `3/3`, with zero failed or errored
  result rows.

## Evidence authority

Each release owns:

```text
.artifacts/releases/<release-id>/
  release.json
  evidence/
    release-context.json
    source-validation.json
    infrastructure.json        # explicit infrastructure actions only
    images.json
    deployment.json
    smoke.json
    domain-e2e.json
    telemetry.json
    evaluation.json
    release-evidence.json
  logs/
```

Exact release, target, endpoint, image, thread, workflow, evaluation, and
correlation identifiers stay in the ignored generated bundle. Tracked docs
record only profile-independent outcomes.

## Historical acceptance summary

Historical evidence records show that the then-current source completed:

- fresh bootstrap and transition to steady state;
- app-only deployment without PostgreSQL or RBAC mutation;
- browser and domain HITL validation;
- exact telemetry correlation with zero relevant exceptions;
- report-only evaluation with zero failed/errored rows; and
- the app-only-to-telemetry interval within the configured budget.

These records are operational history, not proof for the current revision.

## Documentation validation

For documentation-only changes:

1. verify every relative Markdown link resolves;
2. verify no tracked documentation references the removed nested design path;
3. verify the required documentation inventory exists;
4. verify no concrete tenant, subscription, user, Azure resource, or deployed
   endpoint values remain; and
5. report any required integration outside documentation-owned scope.
