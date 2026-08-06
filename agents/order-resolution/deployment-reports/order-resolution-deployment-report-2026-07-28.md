# Order Resolution Deployment Report

**Report date:** 2026-07-28  
**Repository:** `ppenumatsa1/maf-monorepo`  
**Scope:** `agents/order-resolution` local, Azure-hosted, Foundry-public, and
Foundry-private release recovery after intentional lane teardown.

## Executive status

| Lane | Current state | Deployment evidence | Outstanding release gates |
| --- | --- | --- | --- |
| Local | Complete | Parallel local validation passed: Azure-hosted tests/evals/E2E, Foundry-public tests/evals/E2E, and Foundry-private tests (`112 passed`). | None for the agreed local scope; private local E2E/evals are intentionally deferred. |
| Azure-hosted | Complete | Fresh reprovision, backend/frontend deployment, smoke, hosted E2E, Foundry evaluation, and telemetry all passed. | None. |
| Foundry-public | Complete | Fresh infrastructure and app deployment, hosted agent version 14, browser E2E, hosted Responses E2E, Foundry evaluation, and telemetry validation all passed. | None. |
| Foundry-private | Prepared / pending private runner | Source, staged provisioning, and release workflow are repaired and statically validated. | Private runner recovery/registration, staged provision, hosted deployment, connectivity proof, PostgreSQL lockdown, hosted E2E, evaluation, and telemetry remain pending. |

## Completed work

### Shared local validation

- Added `make -C agents/order-resolution validate-parallel`.
- Added `scripts/local/validate_parallel.sh`, which isolates each lane using a
  unique Compose project and dynamic PostgreSQL host ports.
- Preserved existing single-lane commands.
- Deliberately limits Foundry-private local validation to `make test`; private
  local hosted E2E and Foundry evaluation remain out of scope until the
  private deployment exists.
- Repaired Foundry-public local E2E to fall back from ignored `backend/.env` to
  `backend/.env.example`.
- Added clean GitHub-runner dependency setup:
  - frontend `npm ci` for design-review and quick validation;
  - Playwright `npm ci` plus Chromium install for quick validation.

### Azure-hosted lane

**Status: complete and deployed.**

| Item | Result |
| --- | --- |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Frontend | `https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io` |
| Backend | `https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io` |
| Smoke | Passed |
| Hosted Playwright | 7/7 scenarios passed |
| Foundry evaluation | 2 passed, 0 failed, 0 errored |
| Telemetry | 32 workflow/HITL dependency spans observed |

Completed fixes:

1. Purged the intentionally soft-deleted deterministic Foundry account name so
   clean Bicep creation could proceed.
2. Added bounded retry logic for PostgreSQL Microsoft Entra administrator
   propagation before granting the backend managed identity.
3. Added `make eval-foundry-deployed`, which obtains non-secret deployment
   context from the selected AZD environment and sets
   `FOUNDRY_EVAL_API_URL` correctly.
4. Replaced historical/deleted deployment claims with fresh current evidence in
   `.azure/deployment-plan.md` and the lane RCA ledger.

### Foundry-public lane

**Status: complete and deployed.**

Successfully provisioned:

- Foundry account and project;
- model deployments for chat, embeddings, and evaluation;
- ACR, Log Analytics, Application Insights, and evaluation Storage;
- PostgreSQL;
- Container Apps environment;
- backend and frontend Container Apps.

Successfully deployed after provisioning:

- backend Container App;
- frontend Container App.

Clean-provision fixes implemented:

1. Changed previously assumed `existing` Foundry, ACR, monitoring resources
   into managed resources.
2. Added Foundry model deployments and serialized account mutations:
   evaluator -> chat -> embeddings -> project.
3. Removed unsupported Standard ACR network-rule settings.
4. Added required public Foundry network ACLs:
   `defaultAction: Allow`, `bypass: AzureServices`.
5. Implemented one-time Foundry soft-delete restore behavior.
6. Added bootstrap-image handling for absent Container Apps while preserving
   active app images during later infrastructure-only provisions.
7. Replaced the failing remote source-build path with a reproducible ACR image
   build plus SDK registration path. The public project identity uses
   `Container Registry Repository Reader` and `AcrPull`, and ACR enables Azure
   AD authentication as ARM for image pulls. `AcrPull` remains required by the
   current Agent Service despite newer Repository Reader guidance.

Resolved remote-build boundary:

```text
Foundry source-code deployment fails with:
[ImageError] Container image not found
```

The same failure reproduced with the unmodified official Python hosted-agent
quickstart. A known-present image from that sample activated immediately, which
isolated the issue to Foundry's remote source-build path. The repository now
builds the generated hosted Docker context in ACR and registers the image
through `AIProjectClient.create_version`.

Fresh hosted-agent evidence:

- ACR image:
  `maffndacrpubdev2eus2.azurecr.io/order-resolution-hosted:8807bbd45a5a-20260728182002`
- Foundry agent: `order-resolution-hosted`, version `14`, active.
- Responses smoke: `ORD-1001` completed through Foundry Models and PostgreSQL,
  conversation `conv_ad0825e2b0ac6dc400W59cDlBuRk8Km64lb5pFzMYMaYWzoppD`,
  trace `3ae160e935d56a643fd1d2204c2dcacf`.

Completed post-smoke gates:

1. Deployed browser E2E passed all 7 workflow scenarios.
2. Hosted Responses E2E completed low-risk, conversation-continuity, and
   high-risk approval/resume flows using conversations
   `conv_533cb6371aeafb4300trdXELCjbKQzOJvW1bL6WTMKPoSOhm1V` and
   `conv_a77ea962fae1664c00s4H2GgqB00zhP8tKJAGOqM14PJJ1QB1C`.
3. Enforced Foundry trace evaluation
   `eval_ba88f785636644758e0027e8be963ed2` /
   `evalrun_9f4964e7e8f14ebdbbec85eb549c4112` passed 2 conversations with
   0 failed and 0 errored.
4. Application Insights telemetry validation found 51 correlated rows and no
   exception rows for those hosted E2E conversations.

### Foundry-private lane

**Source and workflow readiness: complete; release execution pending.**

Completed fixes:

1. Rebuilt `foundry-access-path` around the retained
   `foundry-private-env` and `main.bicep`; removed references to the deleted
   `access-path.bicep` and nonexistent resource group.
2. Required an explicit SSH public-key path for runner recovery.
3. Standardized runner registration on `foundry-private-v2`.
4. Added private Foundry soft-delete restore support and safe automatic
   clearing of the restore flag after the account becomes active.
5. Split private infrastructure into:
   - core provisioning with `MANAGE_PROJECT_CONNECTIONS=false`;
   - a later `foundry-project-connections` stage after identity/RBAC
     propagation.
6. Ordered runtime secret connections and project capability host creation
   behind project connection/RBAC completion.
7. Enforced one private release mutex:
   `order-resolution-private-release`.
8. Enforced release order:
   provision -> app deployment -> hosted-agent deployment -> connectivity proof
   -> explicit PostgreSQL-lockdown confirmation -> hosted E2E -> enforced
   evaluation -> telemetry evidence.
9. Removed optional password-repair, optional hosted-agent refresh, and
   optional evidence branches.
10. Added static workflow validation for the runner/release contract.

Known private platform conditions and prescribed handling:

| Condition | Cause | Correct response |
| --- | --- | --- |
| `FlagMustBeSetForRestore` | Azure retains the deleted Foundry account name. | Use the parameterized one-time restore; do not purge or recreate names outside source control. |
| Key Vault MSI token failure while creating Foundry connections | Restored project identity/RBAC propagation has not completed. | Wait and retry the staged `foundry-project-connections` step. |
| `OperationNotAllowedWhenLastOperationTypeIsDelete` on PostgreSQL private endpoint | Azure has not finished deleting the previous endpoint. | Wait for deletion completion and retry; do not enable public access. |
| Private ACR 403 from workstation | Expected private networking enforcement. | Deploy only from the VNet-connected `foundry-private-v2` runner. |

Current execution findings on 2026-07-28:

- `vm-maffnd-runner` is running but its offline runner registration belongs to
  the retired `ppenumatsa1/maf-order-resolution-agent` repository. It must be
  re-registered through Bastion in `ppenumatsa1/maf-monorepo` with the
  `foundry-private-v2` label. The repository registration helper now has an
  explicit reconfiguration mode for that recovery.
- The existing Bastion host was Basic SKU, which cannot support the native SSH
  recovery path. The private-runner IaC now declares Standard SKU with native
  client tunneling, and the existing host is upgraded in place before runner
  registration. This does not expose a private workload endpoint.
- The rebuilt runner VM lacked `jq`, revealing that the registration helper
  checked a bootstrap-installed dependency before invoking bootstrap. The
  tracked script now performs that check after host bootstrap.
- Core provision authenticated, recreated its AZD environment, and passed
  preflight before Azure rejected the failed PostgreSQL private endpoint left
  by the previous delete operation. Diagnostics confirmed the server remained
  healthy and the endpoint had no DNS record; the exact failed endpoint was
  deleted so Bicep can recreate it on the next staged provision. Public
  database access remains disabled.
- Protected private core provision `30397620770` then completed successfully.
  Bicep recreated the PostgreSQL endpoint and its private DNS record
  (`10.90.2.13`) while PostgreSQL public access remained disabled. The
  project-connections and deployment stages are next.
- Private GitHub OIDC and RBAC are now being migrated from the historical
  ad-hoc application to a dedicated source-controlled Bicep identity stack.
  Its first deployment exposed Entra service-principal replication timing;
  the declared role assignments now specify `principalType:
  ServicePrincipal` before the retry. Verification also corrected an initial
  role-ID typo that would have assigned Managed Identity Operator rather than
  User Access Administrator; the scoped bootstrap removes only that
  superseded assignment.
- Recovery is now complete for the private control path: the source-managed
  identity has one active monorepo environment federation and exactly
  Contributor plus User Access Administrator at the target resource group;
  Bastion is Standard with native tunneling; and
  `vm-vm-maffnd-runner-foundry-private-v2` is online in the monorepo.
- The first protected provision reached OIDC login but GitHub emitted an
  ID-qualified subject claim. The identity IaC now records that exact
  environment subject instead of widening the trust relationship.
- PostgreSQL private endpoint `mafprv0722v3-postgres-pe-4aiw7fw5gjdo4` is
  failed after the previous delete operation, with no private DNS A record.
  Azure must accept endpoint reconciliation before staged core provision can
  resume.
- Foundry's runtime-secret connection remains blocked on project
  managed-identity/Key Vault token propagation. The staged connection target
  is retained for retry only after that identity path becomes available.
- The private source gate is current: Ruff passed and `make test` passed
  112 tests.

Pending private release steps:

1. Confirm the private endpoint delete operation is complete.
2. Run runner recovery through Bastion and register an online
   `foundry-private-v2` GitHub runner.
3. Run private core provisioning.
4. After identity propagation, run staged project connections.
5. Dispatch protected private deployment with required deployment and lockdown
   confirmations.
6. Collect fresh connectivity proof before PostgreSQL lockdown.
7. Run hosted smoke, browser E2E, enforced evaluation, and telemetry checks.

## Commits containing recovery work

| Commit | Purpose |
| --- | --- |
| `ba8affe` | Made multi-lane local validation reproducible. |
| `571e37d` | Added clean provisioning and private recovery foundations. |
| `544fc2d` | Added CI clean-runner dependencies, public bootstrap handling, private staged connections, private restore safety, and release enforcement. |
| `544ae02` | Historical attempted project ACR publish-permission change; later reverted to the known-good `AcrPull` model. |
| `c6aa67b` | Documented the verified public Foundry hosted code-build blocker. |

## Validation completed

- `make -C agents/order-resolution validate-parallel`
- `make -C agents/order-resolution/foundry-private test` (`112 passed`)
- Private workflow static contract validator
- Bicep compilation for all lane entry points
- Public Bicep preview and actual provision
- Azure-hosted end-to-end release gates listed above
- Public backend and frontend `azd deploy`
- Public deployed browser E2E (7/7), hosted Responses E2E, Foundry evaluation
  (2/2 passed), and telemetry correlation (51 rows, no exception rows)
- Targeted source review of the aggregate recovery diff

## Work still pending

The private release remains incomplete until:

1. Foundry-private release completes from the approved private runner with
   fresh proof/evidence.
2. The current CI workflows for commits `544fc2d`, `544ae02`, and `c6aa67b`
   are reviewed and any remaining failures corrected.
3. Final aggregate release review is rerun after the private lane has fresh
   evidence.

## Operating rules retained

- Azure-hosted and Foundry-public may run independently once validation is
  green.
- Foundry-private is serialized and must run from `foundry-private-v2`.
- Never use public ACR, public Foundry, database password repair, or firewall
  bypasses to resolve private-lane failures.
- Historical evidence from 2026-07-27 is not current deployment proof after
  the 2026-07-28 teardown.

## Official hosted-agent POC result

An isolated copy of the official Microsoft Python hosted-agent quickstart was
uploaded directly through `AIProjectClient.create_version_from_code` to the
recreated public project. The unmodified basic sample failed on version 1 with
the same `ImageError: Container image not found` observed for Order Resolution.
The same sample built in ACR and registered as a Foundry image agent successfully.
All POC agents, images, and temporary role assignments were deleted. This
confines the unresolved platform issue to remote source builds; the repository
uses the verified image path.
