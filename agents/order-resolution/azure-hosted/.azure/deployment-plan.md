# Azure App-Hosted Deployment Plan

> **Status: Validated; infrastructure and app release complete.** The approved
> target was bootstrapped and transitioned to steady state on 2026-08-14.
> PostgreSQL and Container Apps are excluded from steady-state reconciliation.
> Fresh app-only release `cli-20260815T031509Z` passed every release gate on
> 2026-08-15 without infrastructure, database, or RBAC mutation.

## Intended target

| Setting | Source intent |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Region | North Central US (`northcentralus`) |
| Package | `infra/azure-apphosted/` |
| Application topology | React/Nginx frontend Container App -> same-origin `/api` -> FastAPI/MAF backend Container App |
| Model/evaluation boundary | Foundry model inference and report-only evaluation only |

East US is excluded for this target because of the Azure PostgreSQL offer
restriction. FastAPI is the sole sequential MAF host. Do not add or document an
alternative Foundry application-hosting surface in this Azure-hosted lane.

## Target readiness findings

- Authentication resolves the approved subscription and tenant.
- `rg-maf-ora-azure` does not yet exist, so this target requires the one-time
  bootstrap path; it is not a retained-resource migration.
- Required resource providers are registered.
- `gpt-4.1-mini` `GlobalStandard` quota is fully consumed (`5000/5000`) in the
  checked target regions. Bootstrap defaults use the parameterized `Standard`
  SKU, which has 5000 available; `DataZoneStandard` remains an explicit
  operator override with 2000 available. The `text-embedding-3-small`
  deployment uses the model-specific `DataZoneStandard` default because
  North Central US does not support `Standard` for that model. No deployment
  defaults to `GlobalStandard`.
- PostgreSQL capability data includes `Standard_D2ds_v5` in the checked
  regions. The existing low-cost topology is unchanged; the bootstrap preview
  must confirm the selected PostgreSQL SKU is accepted before deployment.
- The Container Apps quota helper could not run because extension access was
  permission-denied. Do not bypass that control or infer quota. The
  subscription-scope bootstrap preview is the required capacity/readiness
  check, and any Container Apps quota failure remains a bootstrap blocker.

## One-time bootstrap

The project-local tracked profile
`deployment/profiles/azure-hosted.env` contains only the approved target and
naming contract. `deployment/profiles/azure-hosted-bootstrap.env` is retained
for bootstrap compatibility. Profiles intentionally exclude operator IPs,
images, credentials, tokens, and connection strings. Supply the required
untracked inputs and prepare the local AZD environment:

```bash
export POSTGRES_BOOTSTRAP_ALLOWED_IP="<operator-public-ipv4>"
export BACKEND_IMAGE="<explicit-bootstrap-backend-image>"
export FRONTEND_IMAGE="<explicit-bootstrap-frontend-image>"
export POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME="<entra-upn>"
export POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID="<entra-object-id>"
make prepare-bootstrap
azd provision --preview --environment maf-ora-azure --no-prompt
```

Only a separately authorized bootstrap may run `azd provision`. After it
completes, run `make prepare-steady-state`. That command verifies the selected
PostgreSQL server/database identity, verifies and deletes exactly the
`allow-bootstrap-runner` firewall rule for the recorded operator IP, then
changes local AZD configuration to `INFRASTRUCTURE_MODE=steadyState`. It fails
before transition if deletion cannot be verified. If the exact rule is already
confirmed absent after a prior partial attempt, retry completes both AZD
updates; lookup/auth errors still fail closed. In steady state the
PostgreSQL module, post-provision grant hook, and Container App modules are
excluded, so future IaC cannot alter PostgreSQL or application secrets/config.

## Normal release: app-only

Use the existing release path after applicable local gates:

```bash
make release-app
```

It deploys backend/frontend revisions only and then runs
`make release-validate`. It must not call `azd provision`, implicitly
reconcile infrastructure, recreate PostgreSQL, or reset the `maf_workflow`
database. Preserve the approved CFS Python package feed and the frontend
Alpine/musl-compatible image build.

The release target is read from the project-local
`deployment/profiles/azure-hosted.env`. One release ID owns `release.json`,
JSON evidence under `.artifacts/releases/<release-id>/evidence/`, and logs under
the sibling `logs/` directory. Evaluation is report-only but release-blocking:
it must complete with zero failed or errored rows. The validation wrapper writes
failed final evidence when an intermediate gate fails.

The release validation must capture a fresh `release_run_id`,
`release_started_at`, low/high-risk thread IDs, and workflow run IDs. In the
same evidence window it must pass:

1. HTTPS/frontend/proxied-API health and smoke;
2. `ORD-1001` completion without HITL and `ORD-1009` HITL behavior;
3. hosted Playwright E2E through the frontend proxy;
4. report-only Foundry evaluation; and
5. Application Insights telemetry/HITL correlation for those identifiers.

Record non-secret results and endpoint identities here only after they run.
Local test results, source inspection, historical records, or broad telemetry
lookbacks do not satisfy this evidence requirement.

## Azure validation checklist

All validation checks pass only when the following evidence exists:

### AZD recipe validation steps

- [x] Confirm Azure CLI and AZD authentication, selected subscription, AZD
  environment, resource group, and location.
- [x] Run the repository's release-source and subscription-portability
  validation commands.
- [x] Compile the subscription-scope Bicep template.
- [x] Run the required local build and test gates.
- [x] Review static RBAC assignments for least privilege and correct scope.
- [x] Run and review a non-mutating subscription-scope bootstrap preview.
- [x] Confirm the preview uses chat/evaluator `Standard`, embeddings
  `DataZoneStandard`, creates PostgreSQL only during bootstrap, and contains no
  unexpected deletions.
- [x] Confirm steady-state IaC excludes PostgreSQL and application Container
  Apps so retained data, secrets, and application revisions cannot be
  reconciled accidentally.

1. Azure Developer CLI and Azure authentication resolve `maf-ora-azure` to
   subscription `7df95e88-701c-4693-af77-3159f83b558d`,
   `rg-maf-ora-azure`, and `northcentralus`.
2. Release source guards, mocked reconciliation guards, Bicep compilation, and
   static least-privilege role review pass.
3. The bootstrap preview confirms Container Apps capacity and the selected
   PostgreSQL/model SKUs without relying on the inaccessible quota helper.
4. A steady-state subscription-scope IaC preview is reviewed. PostgreSQL must
   be absent from the what-if because that lifecycle is excluded after
   bootstrap; any PostgreSQL entry blocks reconciliation.
5. The **Required cloud Docker E2E** job builds the exact backend/frontend
   release images, tests them, pushes their immutable ACR digests, and only
   then updates the Container Apps.
6. The same CI job runs fresh smoke, hosted Playwright, report-only Foundry
   evaluation, and exact-pair Application Insights correlation validation.

## Validation proof

| Check | Result |
| --- | --- |
| Azure CLI/AZD authentication and selected environment | Passed on 2026-08-14: subscription `7df95e88-701c-4693-af77-3159f83b558d`, environment `maf-ora-azure`, resource group `rg-maf-ora-azure`, location `northcentralus` |
| Release source guards and mocked reconciliation boundary | `make release-source-validation` passed, including subscription portability, fail-closed PostgreSQL transition, fresh-what-if, and no-implicit-reconciliation guards |
| Bicep compilation | `make bicep-build` passed for the subscription-scope template |
| Required local build/test gates | `make test` passed (66 tests), `make eval-backend` passed (10/10), `make test-e2e` passed (7 workflow and 3 selected-thread tests), and `./scripts/skills/design-review-skill.sh` passed |
| Bootstrap subscription-scope preview | Passed: 13 creates and no modify/delete operations. Expected resources were the resource group, two Container Apps, Container Apps environment, Foundry account/project and three model deployments, ACR, PostgreSQL flexible server, Application Insights, and Log Analytics |
| Steady-state subscription-scope preview | Passed: 10 creates and no modify/delete operations on the empty target. PostgreSQL and both application Container Apps were absent, proving steady-state exclusion |
| Foundry deployment SKUs | Passed: chat `Standard`, evaluator `Standard`, embeddings `DataZoneStandard`; no `GlobalStandard` default |
| PostgreSQL lifecycle safety | Passed: bootstrap alone includes PostgreSQL and its exact operator-IP firewall rule; transition verifies server/database identity, deletes and verifies only `allow-bootstrap-runner`, then clears the IP and selects `steadyState`; grant hook exits without mutation in steady state |
| Static role review | Passed: backend/frontend `AcrPull` is scoped to ACR, backend Cognitive Services OpenAI User is scoped to the Foundry account, backend Foundry User is scoped to the project, and the project identity Foundry User role is scoped to the account. No resource-group or subscription-scope application data roles |
| Immutable image and fresh release evidence | Passed on 2026-08-15: exact backend/frontend images passed Docker E2E, were pushed by digest and deployed app-only; fresh smoke, hosted browser E2E, report-only Foundry evaluation, and exact-pair Application Insights validation all passed |

The target resource group did not exist before either preview. Both
`azd provision --preview --environment maf-ora-azure --no-prompt` runs stated
that no changes would be applied. The bootstrap preview validated the selected
PostgreSQL and model resource shapes without provisioning them. The
steady-state preview was run by changing only local AZD environment values and
then restoring `INFRASTRUCTURE_MODE=bootstrap`; it proposed neither PostgreSQL
nor application Container Apps and reported no deletion.

## Role assignment verification

**Status:** Verified statically.

- Backend managed identity: `AcrPull` at its ACR, Cognitive Services OpenAI
  User at the Foundry account, and Foundry User at the Foundry project.
- Frontend managed identity: `AcrPull` at its ACR.
- Foundry project system identity: Foundry User at its parent Foundry account.
- No role assignment in this template is scoped to the resource group or
  subscription.

## Exceptional infrastructure reconciliation

An infrastructure change is not an automatic full release. Invoking the
validated reconciliation workflow is execution intent; no separate owner
approval, reference, or caller-supplied preview/template digest is required.
Preview without changing resources:

```bash
make release-infra-preview
```

Apply directly after applicable validation:

```bash
make release-infra-reconcile
```

Apply independently resolves the approved target, requires all stateful
Foundry model/deployment parameters from the selected AZD environment, obtains
a fresh steady-state subscription-scope what-if, rejects any PostgreSQL entry,
and verifies the server identity after the operation. Container App resources
are bootstrap-only in IaC, so reconciliation cannot replace MCP secrets,
endpoint configuration, or app revisions.

## Evidence ledger

Add a dated entry only after an authorized deployment or release has completed.
Include:

- AZD environment/resource group and non-secret frontend/backend endpoints;
- revision/image identifiers when available;
- release/thread/workflow-run correlation IDs;
- smoke, hosted E2E, report-only evaluation, and telemetry results;
- exceptions or blockers, including an unresolved Docker E2E TLS
  trust/handshake failure if one actually occurred.

### 2026-08-15 fresh app-only release

- **Release:** `cli-20260815T031509Z`; evidence window
  `2026-08-15T03:19:50.037142Z`. No `azd provision`, infrastructure
  reconciliation, PostgreSQL/schema/data operation, or RBAC mutation ran.
- **Endpoints:** backend
  [https://maf-backend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io](https://maf-backend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io)
  and frontend
  [https://maf-frontend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io](https://maf-frontend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io).
- **Images/revisions:** backend
  `sha256:6dde47133ffff78105a14cd4e7c168666373f0980c4ba7fa81a9806557b988a3`
  on `maf-backend-abnhku--ci-cli-20260815t031509z`; frontend
  `sha256:2ca6d41b1d9f8598bae749b19be6eac47a5689149271c69fd557e551eb6ef0ce`
  on `maf-frontend-abnhku--ci-cli-20260815t031509z`. Both are active,
  `Running`, and ready.
- **Build/test:** backend lint and 66 tests, deterministic evaluation 10/10,
  frontend build, local Playwright 7 + 3, design review, and exact-image
  Docker E2E 7 + 3 passed before deployment.
- **Smoke/correlation:** low-risk thread
  `smoke-apphosted-cli-20260815T031509Z-ord1001`, workflow
  `11c1f439-50bb-4631-9fce-77bf347f540d`, completed without HITL and produced
  6 correlated telemetry items with zero exceptions. High-risk thread
  `smoke-apphosted-cli-20260815T031509Z-ord1009`, workflow
  `136b3ecd-f28f-4d87-9578-afd595473e74`, exercised HITL and produced 4
  correlated telemetry items with zero exceptions.
- **Hosted/Evaluation:** hosted workflow and selected-thread Playwright passed
  7 + 3. Foundry evaluation `eval_abe05815b0fc4d3fb1fc1df0598adafb`,
  run `evalrun_52f4bc6dffe445cf85438389d7eabb75`, passed 2/2 with zero
  failures, errors, or skips.
- **Resolved issue:** Azure rejected the first revision suffix because the
  timestamp contained uppercase characters. The release script now lowercases
  generated revision suffixes and release-asset validation enforces the fix.
  The failed attempt changed no Container App revision; the retry passed.

### 2026-08-14 fresh infrastructure bootstrap

- **Deployment:** subscription
  `7df95e88-701c-4693-af77-3159f83b558d`, resource group
  `rg-maf-ora-azure`, region `northcentralus`, deployment
  `maf-ora-azure-1786761892`, state `Succeeded`, correlation
  `d7c34b26-08ba-812d-7af9-4f6b0b37bded`.
- **Endpoints:** backend
  [https://maf-backend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io](https://maf-backend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io)
  and frontend
  [https://maf-frontend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io](https://maf-frontend-abnhku.politesmoke-b76fed34.northcentralus.azurecontainerapps.io).
  Backend `/health`, frontend `/`, and frontend `/api/health` returned HTTP
  200. These are provisioning checks, not app release-gate evidence.
- **Models:** `gpt-4.1-mini` and
  `gpt-4.1-mini-evaluator` are `Standard`; `text-embedding-3-small` is
  `DataZoneStandard`; all three report `Succeeded`.
- **RBAC:** backend and frontend identities have `AcrPull` only at
  `maforaazureacrpuzsryv2`; backend has Cognitive Services OpenAI User at the
  Foundry account and Foundry User at the project; the project identity has
  Foundry User at the account. Both private-image Container App revisions are
  healthy.
- **PostgreSQL:** server
  `maf-ora-azure-pg-abnhku.postgres.database.azure.com`, database
  `maf_workflow`, backend principal
  `maf-ora-azure-backend-id-abnhku`. Entra admin creation, backend role
  creation, grants, idempotent schema application, and readiness passed.
  Ten public tables exist and the backend role has database connect, schema
  usage/create, and table DML privileges.
- **Steady state:** the exact `allow-bootstrap-runner` rule was deleted and
  verified absent, the bootstrap IP was cleared, and the mode is
  `steadyState`. The final preview skipped PostgreSQL and both Container Apps,
  proposed zero creates/deletes, and showed only non-destructive Azure
  provider/default normalization on other retained infrastructure.
- **Recovery fixes:** resolved a globally unavailable ACR name, replaced an
  Entra administrator object ID from the wrong tenant, changed the async raw
  admin REST PUT to the polling Azure CLI command, and corrected current
  PostgreSQL database/firewall CLI option names.
- **Release boundary:** no app release, hosted E2E, Foundry evaluation, or
  telemetry release gate ran. Continue with `ora-azure-release`.

### 2026-08-07 app-only cloud release

- **GitHub Actions:** [run `31204487857`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31204487857), release ID `ci-31204487857-1`.
- **Endpoints:** backend [https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io) and frontend [https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io).
- **Immutable images:** backend `sha256:91c6879de9f8f50431f33669605a5476ff3997174a942b309845c6701c56abcf`; frontend `sha256:a61ff2249f01d2f49d0c9e0fea42e275e4ad7238722a9cc549ff639e3657e081`.
- **Gates:** Docker E2E, smoke, hosted workflow and selected-thread browser E2E, and report-only Foundry evaluation all passed. Foundry evaluation `eval_565e438b61934c209250de2516a2acdf` / `evalrun_4497efc4ce6f4ba6aba8c74ce2d66d6b` passed both cases.
- **Telemetry:** exact fresh pairs for low- and high-risk smoke threads recorded 6 and 5 telemetry items respectively, with zero exceptions; their App Insights correlation evidence is validated.
- **Infrastructure:** no reconciliation ran; PostgreSQL and the `maf_workflow` database were not changed.
