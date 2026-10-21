# Order Resolution Foundry Private Deployment Plan

> **Status:** Validated and deployed for the 2026-10-21 review-remediation
> release; hosted version 17 is active

## Review remediation release (2026-10-21)

Release `20261021T180156Z-4e57d58ce4df` completed through the app-only path.
No infrastructure reconciliation, network, SKU, scaling, RBAC, deletion, or
replacement operation was performed.

| Gate | Result |
| --- | --- |
| Application deployment | New backend and frontend Container App revisions succeeded. |
| Hosted deployment | `order-resolution-hosted` version 17 is active. |
| Local verification | Ruff and 170 backend tests passed, including concurrent PostgreSQL action-claim coverage. |
| Responses E2E | Three fresh conversations passed low-risk, follow-up, high-risk approval, damaged-item approval, exact checkpoint resume, and persistence assertions. |
| Observability | Application Insights correlated 279 rows across all three conversations with zero exceptions. |
| Foundry evaluation | `task_completion` and `coherence` each passed 3/3 with zero failed, errored, or skipped results. |
| Release budget | Telemetry was ready in about 6m 06s and final evidence completed in about 6m 30s, within the 15-minute gate. |

Current detail:
[review remediation release](../docs/issues-changes-fixes.md#review-remediation-release-2026-10-21).

## Historical dependency modernization release (2026-10-20)

Release `20261020T231549Z-4e57d58ce4df` completed the app-only modernization
without provisioning or reconciling infrastructure.

| Gate | Result |
| --- | --- |
| Application deployment | Backend and frontend Container App revisions succeeded and use the existing private ACR. |
| Hosted deployment | `order-resolution-hosted` version 11 is active with Responses and Activity `2.0.0`. |
| Dependency contract | Python 3.13 application images install the 112-package hash-locked runtime graph offline; `azure-ai-projects` remains intentionally capped at `2.7.0` for Agent Framework compatibility. |
| Responses E2E | Low-risk completion, same-conversation follow-up, high-risk approval, damaged-item approval, workflow state, checkpoints, and required events passed. |
| Teams Activity E2E | Typed decisions remained blocked; Approve and Reject, wrong-conversation isolation, replay rejection, and pending-card creation passed. Synthetic outbound Bot callbacks returned the expected non-success status because no real SMBA conversation existed. |
| Observability | Application Insights returned 190 correlated rows and four evaluation-eligible spans for the three release conversations. |
| Foundry evaluation | `task_completion` passed 3/3 and `coherence` passed 3/3; zero failed, errored, or skipped results. |
| Release budget | App-only start through telemetry completed in 252,830 ms, within the 15-minute gate. |
| Endpoint state | Activity reconciliation is no-change with `activity,responses` and `BotServiceRbac,Entra`; Azure Bot and `MsTeamsChannel` both report `Succeeded`. |
| Database pool | Hosted version 11 uses `min=0`, `max=2`, and `max_idle=30s`; after acceptance traffic the runtime role had two idle connections and no connection-pressure error. |
| Rollback | No prior version was deleted. Version 9 remains the accepted pre-modernization rollback point; version 10 is retained as the diagnostic modernization deployment. |

The subsequent React 19.3, CopilotKit 1.79, Zod 4, Vite 8.3, and TypeScript 7
frontend dependency update is locally validated only. It is not part of the
deployed release above.

## Current deployment increment: Teams Adaptive Card approvals

This increment updates the existing hosted-agent image and PostgreSQL schema in
the active Shared Teams demo environment. It does not provision, replace,
resize, or delete Azure infrastructure.

| Attribute | Decision |
| --- | --- |
| Recipe | Existing PostgreSQL bootstrap plus the controlled hosted-agent deployment script |
| Target selection | Existing ignored external deployment profile; no target identifiers are committed |
| Location | Reuse the existing deployed resource locations |
| Resources added | One PostgreSQL action-token table and one immutable hosted-agent version |
| Infrastructure changes | No Azure resource changes; the hosted container now declares Responses and Activity protocol version `2.0.0` |
| Quota impact | None; the version uses the existing Foundry hosted-agent, ACR, model, monitoring, and PostgreSQL resources |
| Verification | Private Responses invocation plus live Activity approve/reject, card creation, wrong-conversation, replay, and conversation-isolation validation |

The code change composes `ResponsesAgentServerHost` and
`ActivityAgentServerHost` in one process. Private Responses clients keep their
existing path. Teams messages use the native Activity handler, which emits an
Adaptive Card when the workflow pauses for approval. Each button carries only
an opaque random token; PostgreSQL stores only token, user, and conversation
hashes and validates the token against the exact pending checkpoint.

### Validation steps for this increment

- [x] Confirm the Responses server output is text-only and select the supported
  native Activity host for Adaptive Card attachments and invoke handling.
- [x] Preserve private Responses by using cooperative dual-protocol host
  composition.
- [x] Add hashed, expiring, one-time card-action persistence.
- [x] Add focused approve, reject, wrong-user/conversation, replay, and no-typed
  Teams fallback tests.
- [x] Run focused Ruff and tests.
- [x] Apply the PostgreSQL schema from the private runner before activating the
  new image.
- [x] Build and activate one immutable hosted-agent version.
- [x] Reconcile the endpoint and verify both Responses and Activity remain
  enabled.
- [x] Verify the new action-token table and exact runtime DML privileges.
- [x] Run a private Responses smoke invocation and correlate the successful
  hosted workflow, model, and PostgreSQL spans in Application Insights.
- [x] Validate version 9 Activity handling from the private runner with genuine
  pending workflows and production action-token persistence.
- [x] Verify typed Teams decisions do not resolve checkpoints, wrong-conversation
  actions return `403`, replay returns `409`, Approve completes the workflow,
  Reject escalates it, and both resolved cards replace the pending card.
- [x] Verify live message handling creates one pending approval and two actions
  without the prior Attachment validation error.
- [x] Reconfirm endpoint convergence: `activity,responses`,
  `BotServiceRbac,Entra`, and the Microsoft 365 public Activity route enabled.
- [x] Correlate version 9 Activity spans in Application Insights and confirm no
  recent `ClaimsIdentity`, Attachment alias, or PostgreSQL connection-limit
  exceptions.
- [ ] Open a fresh signed-in Teams conversation and visually confirm the card
  render and button click. Existing conversations can remain pinned to their
  creation-time hosted version.

The private-runner rollout progressed through three immutable versions:

- Version 7 introduced the native Activity runtime and secure Adaptive Card
  actions. Its first privilege check found that `teams_card_actions` was absent
  from the explicit runtime table allowlist. The allowlist and regression test
  were corrected, grants were reapplied, and the runtime role now has exact DML
  privileges without schema ownership or DDL rights.
- Version 8 upgraded `azure-ai-agentserver-activity` to `1.0.0b4`, which fixes
  the Microsoft Agents SDK 1.9 `ClaimsIdentity.is_authenticated` incompatibility.
- Version 9 corrected the real Microsoft `Attachment` model construction to use
  the serialized `contentType` alias and added regression coverage against the
  actual SDK type.

Final version 9 acceptance initially encountered the runtime role's
20-connection cap because 15 disposable synthetic hosted sessions retained
idle PostgreSQL pools. Azure Resource Health remained healthy. The sessions
owned by the acceptance identity were deleted through the hosted-session data
plane; no PostgreSQL limit, infrastructure, or unrelated connection was
changed. Reject and card-creation acceptance then passed. The service marked
all 15 synthetic sessions stopped, but 13 idle runtime-role connections were
still visible at the final observation. This no longer blocks the demo, but
hosted-session pool sizing and connection retirement remain production
hardening before broader concurrent use.

## Objective

Prepare a portable, fresh-bootstrap and steady-state deployment contract for
`agents/order-resolution/foundry-private`.

The selected target is supplied only through an ignored external profile:

| Setting | Source |
| --- | --- |
| Subscription and tenant | External deployment profile |
| Resource group and resource names | External deployment profile |
| Foundry, Container Apps, PostgreSQL, and Search regions | External deployment profile after capacity validation |
| AZD environment | External deployment profile |
| Access path | Private VM runner and Bastion in the target VNet |

These values are deployment inputs, not defaults that may be embedded in
generic Bicep, scripts, Make targets, `azure.yaml`, or workflow YAML. The
legacy target is historical evidence only and must not be mutated. Environment-
specific identifiers remain outside tracked documentation.

## Portability contract

- `agents/order-resolution/deployment/profiles/foundry-private.env` is the
  canonical non-secret target profile shared through the Order Resolution
  profile framework.
- One shared loader validates and exports profile inputs.
- Secrets remain in AZD/GitHub secure stores or the process environment.
- Required target inputs have no target-specific fallback and fail closed.
- GitHub variables needed before checkout or for `runs-on` mirror the profile;
  a gate requires exact equality before mutation.
- A static contract rejects selected target literals in generic code outside
  the profile, this plan, and evidence documentation.
- Foundry account/project identifiers and endpoints are hydrated from actual
  provision outputs; they are never pre-constructed from an assumed name.
- Bootstrap creates resources and then transitions to reuse. Reuse must not
  reset images, secrets, network injection, capability hosts, PostgreSQL, or
  other stateful resources.

## Architecture

- External frontend Container App.
- Internal backend Container App.
- Private Foundry Responses agent.
- Private PostgreSQL Flexible Server.
- BYO VNet with separate `/24` Foundry agent-host subnet, private-endpoint
  subnet, Container Apps infrastructure subnet, runner subnet, and Bastion
  subnet.
- Private endpoints and DNS for Foundry, ACR, Storage, Cosmos DB, AI Search,
  and PostgreSQL.
- New VNet-connected self-hosted runner for private data-plane operations.
- Staged Foundry project connections and capability hosts after project
  identity and scoped RBAC propagation.

## PostgreSQL contract

- Bootstrap creates the server/database with public network access disabled.
- No Azure-services firewall rule or public-access compatibility path exists.
- An administrator-owned private-runner step applies the schema over the
  private FQDN.
- A separate runtime credential receives only database `CONNECT`, schema
  `USAGE`, table DML, and sequence `USAGE`.
- Runtime Container Apps and hosted agents set
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` and do not execute production DDL.
- The runtime URL, never the administrator URL, is stored in application
  secrets and Foundry runtime connections.
- `make foundry-postgres-readiness` must validate the disabled public-access
  state, approved private endpoint, private DNS mapping/VNet link, runner
  resolution, schema, and exact runtime privileges before app deployment.
- The readiness check is non-persistent and creates no proof artifact.

## Execution DAG

1. Implement the profile, loader, fail-closed portability contracts, and
   generic bootstrap/reuse IaC.
2. Implement least-privilege PostgreSQL schema/runtime separation.
3. Migrate runner workflows to profile-backed GitHub variables and a new
   target runner.
4. Run local tests, package checks, Bicep build, workflow contracts, profile
   tests, and target-literal scans.
5. Mark this plan `Ready for Validation` and invoke Azure Validate.
6. After validation, use Azure Deploy for provider/quota/policy checks, fresh
   preview, control-plane provisioning, runner bootstrap, output hydration, and
   reuse preview.
7. From the VNet runner, initialize the private PostgreSQL schema/runtime role
   and pass the private readiness gate.
8. Converge Foundry connections/RBAC and deploy immutable
   backend/frontend/hosted-agent artifacts.
9. Run fresh smoke, low-risk and HITL E2E, telemetry correlation, and strict
   exact-trace evaluation.

## Validation requirements

- Missing profile values fail before preview.
- No target-specific values appear as generic defaults.
- Fresh preview contains expected creates only and does not reference legacy
  resources.
- Reuse preview allows only reviewed benign metadata noise and contains no
  delete, replace, secret reset, network mutation, or stateful-resource drift.
- Model/SKU, PostgreSQL SKU, Search, Container Apps quota, providers, policy,
  and scoped RBAC are validated for the selected target.
- Runtime database startup succeeds without schema ownership or `CREATE`.
- Fresh provisioning never enables PostgreSQL public network access or creates
  a firewall rule.
- Private PostgreSQL readiness passes before application deployment.
- Only fresh release evidence is accepted.

## All validation checks pass

### 2026-10-21 review-remediation release

- [x] 1. AZD installation and schema validation
- [x] 2. Environment, authentication, subscription, and location checks
- [x] 3. Private provider, capacity, model, policy, and runner preflight
- [x] 4. Non-mutating provision preview with no delete or replacement
- [x] 5. Backend lint, full tests, deterministic evaluation, and release contracts
- [x] 6. Frontend clean install, lint, TypeScript build, and focused Playwright
- [x] 7. Backend and hosted-agent Docker build-context validation
- [x] 8. Foundry package validation
- [x] 9. Static least-privilege RBAC verification
- [x] 10. App-only deployment, private smoke, hosted Responses/Activity E2E,
  Foundry evaluation, and Application Insights correlation

### Current Teams observability increment

- [x] 1. Azure CLI installation and authenticated subscription context
- [x] 2. Repository source, lint, test, documentation, and Mermaid validation
- [x] 3. Hosted-agent Docker build on the private runner
- [x] 4. Azure Policy review: no infrastructure or policy-governed resource
  mutation is proposed
- [x] 5. Private invocation and Application Insights dependency verification

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

### Validation proof

#### 2026-10-21 review-remediation release

This release is app-only: it may create new
Container App revisions and one immutable hosted-agent version, and it may
apply the additive PostgreSQL schema migration. It does not authorize resource
deletion, replacement, network mutation, scaling, or RBAC changes.

| Check | Result |
| --- | --- |
| AZD/schema/auth/profile | AZD authentication and official `azure.yaml` schema validation passed for the selected ignored external profile. |
| Subscription policy | Subscription and inherited management-group assignments were reviewed. The app-only release proposes no infrastructure or RBAC mutation. |
| Capacity and dependencies | Live private preflight passed. Existing matching Search, runner VM, Container Apps environment, AI Services account, and exact model deployments require no incremental quota. |
| Backend | Ruff passed; 170 tests passed, including concurrent PostgreSQL card-action claims, Agent Server structured-input parsing, and persisted trusted-origin lookup. |
| Deterministic evaluation | Passed 10/10. |
| Frontend | Clean Microsoft-feed install, ESLint, TypeScript 7 build, and focused Playwright passed 4/4. |
| Browser E2E | Local workflow and selected-thread suites passed 11/11. |
| Release contracts | Portability, upstream baseline, Activity reconciliation, Teams publication, and Bot/Teams IaC contracts passed. |
| Build/package | Backend and hosted images built from 112 Linux AMD64 wheels; all three AZD services packaged successfully. |
| Bicep | Main template compiled with the existing non-blocking linter warnings. |
| Static RBAC | No role-assignment change is in this release. Existing principals retain resource-scoped Foundry, ACR, telemetry, Storage, Cosmos, and Search data-plane roles; runner Contributor remains resource-group scoped and optional User Access Administrator remains disabled. |
| Provision preview | Passed after starting the existing PostgreSQL server and private runner. The preview contained zero Create, Delete, or Replace operations; reported Modify entries were existing Azure API/default-property readback differences. No infrastructure apply is authorized. |

#### 2026-10-20 dependency modernization

| Check | Result |
| --- | --- |
| Dependency resolution | Passed: 21 runtime direct pins and five development pins resolved into hash-locked Python 3.13 runtime and Python 3.12 development graphs. `azure-ai-projects==2.7.0` is the newest Agent Framework-compatible release. |
| Python validation | Ruff passed; 164 backend tests passed; `pip check` reported no broken requirements. |
| Frontend validation | TypeScript build and ESLint passed. |
| Container validation | Backend and hosted Python 3.13 images built from 112 offline, hash-verified wheels and passed import smoke checks. |
| Foundry packaging | Backend, frontend, and hosted-agent services packaged successfully with AZD. |
| Teams/IaC contracts | Activity endpoint reconciliation, Teams publication, Bot/Teams Bicep, portability, and upstream baseline tests passed. |
| Bicep validation | Main infrastructure template compiled; existing linter warnings remain unchanged. |
| Azure schema/auth/profile | `azure.yaml`, AZD authentication, selected local deployment profile, providers, capacity, model, quota, and runner SKU checks passed. |
| Provision preview | Non-mutating preview completed with no delete or replacement operation; reported differences were existing API/default-property readback. |
| Policy review | Assigned subscription and management-group policies were reviewed; the app-only release creates no infrastructure resource and requires no policy exception. |
| Static RBAC review | Existing resource-scoped data-plane roles, runner Foundry access, Container Apps ACR pull, project telemetry access, and Teams/Bot IaC contracts remain intact. |

#### Teams observability increment

| Check | Command or gate | Result | Timestamp |
| --- | --- | --- | --- |
| Azure target context | Compared the authenticated CLI subscription and tenant with the ignored external demo profile | Passed | 2026-10-20 |
| Local source validation | Ruff plus focused database, telemetry, and hosted-agent tests | Passed: 59 tests | 2026-10-20 |
| Private-runner source validation | Ruff plus focused hosted runtime tests | Passed: 57 tests | 2026-10-20 |
| Hosted-agent package build | Repository source sync followed by the hosted-agent Docker build on the private runner | Passed | 2026-10-20 |
| Documentation | Mermaid render, relative-link validation, and whitespace validation | Passed | 2026-10-20 |
| Static RBAC review | No Bicep, role assignment, identity, scope, or authorization change in this increment | Passed | 2026-10-20 |

The deployment increment is limited to one immutable hosted-agent version.
No infrastructure apply, resource replacement, scaling, deletion, network
change, or RBAC mutation is authorized.

#### Deployment proof

| Check | Result | Timestamp |
| --- | --- | --- |
| Hosted-agent activation | Version 6 active from the private runner | 2026-10-20 |
| Private Responses invocation | Completed with the concise order-resolution response | 2026-10-20 |
| Trace correlation | Verified the exact invocation trace in Application Insights | 2026-10-20 |
| PostgreSQL visibility | Two successful `postgresql.connection` dependencies with `DependencyType=postgresql` | 2026-10-20 |
| Telemetry content safety | Dependency `Data` is empty and properties contain no SQL, parameters, hostnames, prompts, or payloads | 2026-10-20 |
| Trace health | AI, HTTP, in-process, queue, and PostgreSQL dependencies reported zero failures; zero exceptions | 2026-10-20 |
| Live RBAC | Existing runner Contributor and ACR pull/read assignments remain present | 2026-10-20 |

- AZD 1.31.1 authentication resolves the selected tenant/subscription,
  `ora-foundry-private` environment, and East US 2 target.
- The Azure YAML schema is accepted by AZD packaging; the Bicep template
  compiles against PostgreSQL API `2024-08-01`.
- Full backend lint/test validation passed with 133 tests.
- Backend, frontend, and hosted-agent AZD packages all completed successfully.
- The PostgreSQL cutover preview completed without any delete or replacement.
  PostgreSQL, its private endpoint, and all private endpoints were `Skip`;
  no firewall resource or public-access enablement was proposed.
- Azure Policy evaluation found the existing management-group audit for
  PostgreSQL Entra-only authentication. This cutover intentionally retains
  password authentication; passwordless authentication remains a separately
  approved follow-up and did not block preview.
- Static RBAC verification remains valid because the cutover changes no
  principals, roles, or scopes.

| Command or gate | Result |
| --- | --- |
| `make test-foundry-portability` | Passed profile/release portability contracts. |
| `make foundry-iac-validate` | Bicep compiled with PostgreSQL API `2024-08-01`; no PostgreSQL network-property warning remains. |
| Focused database/IaC pytest selection | 7 passed. |
| `validate_private_runner_workflows.py` | Passed private workflow static contracts. |
| `make test` | Ruff passed and 133 backend tests passed. |
| `make foundry-package` | Backend, frontend, and hosted-agent packages passed. |
| Azure profile/authentication checks | Passed for the selected subscription, resource group, environment, and East US 2 location. |
| Azure Policy validation | Existing Entra-only PostgreSQL audit recorded as a separate passwordless-authentication follow-up. |
| `azd provision --preview --no-prompt` | Passed; PostgreSQL and private endpoints were unchanged, with no delete/replace/public-access/firewall action. |
| Static role verification | Passed; the cutover changes no RBAC assignments. |
| Current pre-release revalidation | Passed on 2026-08-15: all three packages built, policy summary reported no non-compliance, and the non-mutating preview contained no create/delete/replace operations. PostgreSQL and all private endpoints were skipped; reported modifications were Azure API/default-property readback drift, so no infrastructure apply is authorized. |

## Live deployment and release evidence

| Stage | Workflow | Result |
| --- | --- | --- |
| Private infrastructure, preview, and PostgreSQL readiness | [`31906517820`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31906517820) | Passed |
| Optimized app-only deployment and chained evidence, commit `a39ad24` | [`31911162673`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31911162673) | Passed; hosted agent version 6 active and 3/3 traces passed |
| Prior GitHub 15-minute-budget authority | [`31922650130`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31922650130) | Passed; 6m 36.8s to telemetry and 6m 57.8s through strict evaluation |
| Current private-runner review-remediation authority | Release `20261021T180156Z-4e57d58ce4df` | Passed; hosted agent version 17 active, about 6m 06s to telemetry, and about 6m 30s through final evidence |

The current telemetry gate correlated 279 Application Insights rows and four
eligible Foundry evaluation spans across all three fresh hosted E2E
conversations. The strict Foundry result was `passed=3`, `failed=0`,
`errored=0`, `skipped=0`; both `task_completion` and `coherence` passed 3/3.

## Measured delivery timing

| Flow | Start | Telemetry ready | Elapsed |
| --- | --- | --- | ---: |
| Infrastructure/IaC to telemetry | Provision run `31906517820` at `20:22:38Z` | Evidence run `31906891692` at `20:36:15Z` | **13m 37s** |
| App-only to telemetry, before optimization | Deployment run `31908682961` at `21:10:09Z` | Evidence run `31908858225` at `21:18:52Z` | **8m 43s** |
| App-only to telemetry, optimized steady state | Workflow `31922650130` | Same workflow | **6m 36.8s** |
| Review-remediation app-only to telemetry | Release `20261021T180156Z-4e57d58ce4df` at `18:01:56Z` | Telemetry accepted at `18:08:01Z` | **~6m 06s** |

The infrastructure measurement includes the workflow handoffs: 3m36s for
preview/provision/readiness, 3m37s for app deployment, 5m18s from evidence
start to telemetry readiness, and 1m06s of dispatch gaps.

The optimized app-only workflow preserves a requirements-hash-validated Python
environment, overlaps the hosted-agent image build with ACA deployment,
continues directly into evidence, and submits evaluation as soon as Foundry
can read the exact traces. The latest authority improves app-only telemetry by **2m 06.2s** from the
8m43s baseline. Complete strict evaluation finished in **6m 57.8s**, a
**4m 56.2s** improvement from 11m54s. The 15-minute budget remains enforced.
The current review-remediation release completed its final evidence bundle at
`18:08:26Z`, about **6m 30s** after release start.

## Role Assignment Verification

- **Status:** Verified.
- Foundry project identity: Foundry User on the Foundry account; `AcrPull` and
  Container Registry Repository Reader on the target ACR; resource-scoped
  telemetry and Log Analytics roles.
- Capability-host data paths: Storage Blob data roles, Cosmos account/container
  roles, and Search index/service roles scoped to their target resources.
- Container Apps pull identity: `AcrPull` scoped to the target ACR.
- Backend identity: Foundry User scoped to the target Foundry account.
- Private runner identity: Contributor scoped to the selected resource group.
  Optional resource-group User Access Administrator remains disabled.
- Deployment identity bootstrap templates use resource-group Contributor/User
  Access Administrator and project/ACR-scoped release roles; no application
  runtime receives generic Contributor/Owner.

## Live issues and fixes

Every implementation, validation, preview, provisioning, database, runner,
release, or evidence issue must be appended immediately to
`docs/issues-changes-fixes.md` with the profile identifier, diagnosis,
fix, verification, and remaining impact.

## Stop conditions

- Azure/AZD resolves a different target from the profile.
- A selected target literal is embedded in generic code.
- A required input silently falls back.
- A preview references the legacy environment or proposes unexpected
  deletion/replacement, subnet pruning, network-injection changes, broad RBAC,
  public-access weakening, cross-region drift, or stateful mutation.
- A runtime receives administrator/schema-owner credentials or attempts DDL.
- The private runner, endpoints, DNS, project connections, capability hosts,
  RBAC, private PostgreSQL readiness, package build, deployed revisions, smoke,
  E2E, evaluation, or telemetry validation fails.
- A preview proposes enabling PostgreSQL public access, creating a firewall
  rule, replacing the server, or weakening its private endpoint/DNS contract.

## Planned repository surfaces

- `deployment/profiles/**`
- `infra/foundry-hosted/azure.yaml`
- `infra/foundry-hosted/iac/**`
- `Makefile`
- `.github/workflows/order-resolution-private-*.yml`
- `backend/app/core/database.py` and related tests
- `scripts/foundry/**`
- `scripts/github/**`
- `docs/issues-changes-fixes.md`
- directly affected README and operating-model documentation
