# Public Foundry Delivery Ledger

## Purpose

This document is the canonical ledger for underwriting public-lane issues, changes, fixes, and release evidence.
Use it to separate **architecture intent** from **verified execution evidence**.

## Release-governance rule

- README and design docs describe the supported architecture and release workflow.
- Only a fresh, dated ledger entry in this file should be used to claim hosted readiness, smoke completion, evaluation success, or telemetry verification.
- If a change affects runtime behavior, release steps, telemetry, or public-lane topology, update this ledger in the same change set.
- `deployment-report/` is ignored local timing evidence only; it is not a
  substitute for this canonical release-evidence ledger.

## Clean cutover acceptance checks

Every hosted release entry should confirm the following:

1. Browser traffic stays same-origin through the public UI/API boundary.
2. The internal backend adapter starts or resumes the hosted Responses workflow
   behind the external frontend proxy; it does not run a second production
   orchestration path.
3. PostgreSQL remains the durable store for `maf_checkpoints`, run history, state, events, and results.
4. AG-UI and CopilotKit surfaces read or explain allowlisted durable projections only.
5. Retry/idempotency and crash/resume behavior still correlate on one `workflow_run_id`.
6. No compatibility shims were added to hide a hosted-lane defect.
7. The master workflow's direct risk, credit, medical, and driving executors fan out/fan in in one superstep.
8. Resume accepts only checkpoints written by the deployed direct-executor graph; version-40 nested-graph checkpoints are rejected without a compatibility workflow or fallback.

## Entry template

Use one section per meaningful operational change.

```md
## YYYY-MM-DD - short title

**Change**
- What changed.

**Why**
- Why the change was required.

**Files / surfaces**
- README.md
- docs/design/...
- backend / infra / scripts / hosted runtime surfaces as applicable

**Local validation**
- Commands run
- Pass/fail notes

**Hosted validation**
- Smoke / E2E commands run
- Scenario names
- `workflow_run_id` values or conversation identifiers

**Telemetry / evaluation evidence**
- Foundry evaluation ID(s)
- Application Insights query or trace identifiers
- Any material delays before traces/evals became visible

**Issues found**
- Problem summary
- User-visible effect
- Root cause

**Fix / decision**
- Applied fix or explicit decision taken
- Why no shim/fallback was introduced

**Deferrals**
- Anything intentionally left for later
```

## Documentation-only alignment note

This file may also capture documentation-only operating-model updates. Those entries should explicitly say that no hosted release completion is being claimed.

## 2026-10-22 - Teams published; hosted resilience and evaluation pass; native acceptance pending

**Change**

- Deployed Azure Bot Service, `MsTeamsChannel`, Bot diagnostics, and the
  merge-preserving public Activity endpoint while retaining Responses, Entra,
  and `BotServiceRbac`.
- Added the required Activity Protocol query version
  `2025-05-15-preview`, generated package version `1.0.0`, and completed Shared
  Microsoft 365 publication.
- Activated hosted version 7 with the natural command
  `start sample underwriting review`.
- Replaced direct local Activity POSTs with an observer that accepts only real
  Teams-origin PostgreSQL outcomes: one human approval and one human decline.
  The observer stores only workflow IDs and hashed conversation bindings.
- Hardened trace evaluation so nested evaluator errors fail the release even
  when the service's top-level result count reports the conversation as passed.

**Issues found**

- The public Activity endpoint initially inherited a private-network-only flag
  and omitted the mandatory API version.
- A normal Azure CLI user token could reach the Activity boundary but could not
  represent signed Bot/Teams channel traffic; direct POSTs were therefore not
  valid native Teams evidence.
- Checkpoint recovery marked the workflow `COMPLETED` but omitted the terminal
  `workflow_completed` audit event.
- Foundry evaluation authorization initially failed until the least-privilege
  model data-plane role propagated. A later intermittent criterion error also
  exposed that top-level evaluation counts alone were insufficient.

**Fix / decision**

- Removed the private-network Activity exception from the public topology and
  pinned the Bot endpoint to the required API version.
- Added `workflow_completed` after successful checkpoint recovery and retained
  the distinct `resume_completed` event.
- Kept wrong-user, wrong-conversation, typed-text, replay, expiry, concurrency,
  cross-channel, and privacy behavior in automated contract/integration tests.
  Native delivery claims now require actual Teams card actions observed from
  durable state and later correlated in Application Insights.
- Did not weaken Bot authentication, enable local-key authentication, grant a
  broad role, or convert a direct Entra request into success-shaped evidence.

**Validation**

- Hosted version 7 passed happy, retry, and crash/resume smoke.
- The latest strict trace evaluation passed task completion and coherence; the
  evidence records two passed criterion results and zero failed, errored, or
  skipped criteria.
- Azure Resource Health reported the Foundry account, PostgreSQL, evaluation
  storage, and Log Analytics workspace available.
- Focused resume, Responses, evidence aggregation, observer, and evaluation
  tests passed. Ruff and shell syntax checks passed for the changed surfaces.
- The native observer connected to live PostgreSQL and timed out cleanly when
  no new Teams reviews existed, proving that it does not synthesize traffic.

**Deferrals**

- Final readiness is not claimed. Start a fresh canonical release, complete one
  approval and one decline in the published Teams agent, verify exact
  Application Insights correlation and rollback, aggregate release evidence,
  then commit and push the final delivery state.

## 2026-10-21 - Clean East US 2 infrastructure provisioned; release acceptance pending

**Change**

- Selected East US 2 after verifying the exact `gpt-4.1-mini`
  `2025-04-14` `GlobalStandard` catalog record and subscription quota.
- Reduced the bootstrap model allocation from 2,500K TPM to 100K TPM after the
  safety preview proved that only 2,220K TPM was currently unallocated.
- Provisioned the public Foundry account/project/model, ACR, monitoring,
  Container Apps environment and placeholder apps, PostgreSQL, evaluation
  storage, identities, connections, and resource-scoped RBAC.

**Issues found**

- The first provision exposed concurrent child-resource writes under one
  Cognitive Services account: the model deployment and Foundry project raced,
  causing `RequestConflict`.
- The next convergence exposed a project-scoped role assignment that referenced
  an `existing` project alias without an explicit dependency, causing a
  transient `ResourceNotFound`.
- Azure CLI authentication expired after infrastructure provisioning and before
  PostgreSQL schema/runtime credential convergence.

**Fix / decision**

- Serialized Foundry project creation after the model deployment and added a
  regression contract.
- Added an explicit Foundry-project dependency to the backend's project-scoped
  Foundry User role assignment and added a regression contract.
- Kept Cognitive Services local-key authentication disabled to align with the
  effective tenant security policy.
- Did not weaken the preview safety validator or bypass PostgreSQL readiness.
  The remaining convergence and application release will resume only after
  tenant-scoped Azure CLI authentication is restored.

**Validation**

- Official `azure.yaml` stable-schema validation passed.
- Bicep compilation, deployment-profile tests, capacity-preflight tests,
  preview-safety tests, clean three-service packaging, and the initial
  non-mutating full-infrastructure preview passed.
- The converged ARM deployment completed successfully in approximately
  two and a half minutes.
- Hosted application deployment, Teams publication, live workflow acceptance,
  evaluation, Application Insights correlation/privacy checks, and rollback
  proof remain pending and are not claimed by this entry.

## 2026-10-21 - Rubber Duck and code-review remediations locally accepted

**Findings and verified fixes**

- Hosted web and Responses review mutation no longer derives reviewer authority
  from request headers. Hosted review is Teams-only; missing and spoofed
  `X-MS-CLIENT-PRINCIPAL-ID` requests fail with HTTP 403, structured Responses
  review output is rejected, and the referral remains pending.
- The optional administrative review path is explicitly limited to non-hosted
  local execution with `ENABLE_LOCAL_REVIEW_MUTATION=true` and a
  server-configured `LOCAL_REVIEW_ACTOR_ID`. It records reviewer type
  `administrative`; externally managed/hosted schema mode cannot enable it.
- Every check, final-decision, failure-injection, and review idempotency key is
  scoped by `workflow_run_id`. Two runs using the same application ID retain
  disjoint results, inputs, origins, and recommendations.
- Existing PostgreSQL upgrades now create missing tables, add nullable
  columns, backfill legacy values, apply defaults and `NOT NULL`, then add
  checks, unique constraints, and indexes. The DDL is idempotent on a real
  legacy PostgreSQL schema.
- Runtime grants include `underwriting_approvals` and `teams_card_actions`;
  table and sequence allowlists are asserted exactly against SQLAlchemy
  metadata. The runtime role retains only required DML and sequence `USAGE`.
- Hosted deployment and verification require one immutable digest while
  preserving both Responses 2.0.0 and Activity 2.0.0. The hosted image
  repository comes from the deployment profile rather than a hardcoded name.
- Bootstrap initialization performs no Azure resource lookup before resources
  exist. Protected provision separates reviewed infrastructure apply from
  schema migration, runtime credential/connection convergence, and readiness.
- Release authority now requires fresh referral-pending, hosted web-mutation
  rejection, Teams card delivery, typed-text blocking, reviewer/conversation
  isolation, replay, expiry, concurrent single-winner, cross-channel,
  evaluation, and exact telemetry-run evidence. During this final review, the
  live E2E harness was found still claiming header-authorized web approvals;
  it and the evidence aggregator were corrected to enforce Teams-only
  production decisions.
- Bot IaC uses the exact Foundry Activity Protocol endpoint, a single-tenant
  `azurebot`, disabled Bot public network access, declarative
  `MsTeamsChannel`, and Log Analytics diagnostics.
- Teams package and publish commands verify but never patch Activity state;
  Bot preview uses ARM what-if. Rollback reports
  `fullRollbackComplete=false` after Activity-only automation and names the
  remaining Shared catalog and Bot lifecycle steps.

**Exact local validation**

- `make quality` passed Ruff lint/format, frontend lint/build,
  `make test`, and `make test-scripts`: 91 backend tests passed with 2
  environment-gated tests skipped; 4 PostgreSQL credential tests passed with
  1 environment-gated test skipped; 36 hosted/release/evidence tests and 15
  subtests passed; capacity 9, preview safety 8, Activity reconciliation 11,
  Teams publication 24, and Teams IaC 7 tests passed. Five runtime/bootstrap/
  release/portability shell contracts passed.
- The three environment-gated cases were then run against PostgreSQL 16:
  legacy-schema migration, exact least-privilege grants, and concurrent
  approve/decline single-winner all passed (3/3).
- A clean frontend install added 1,101 locked packages. ESLint, TypeScript,
  production build, and the full Playwright suite passed (2/2).
- The validated wheelhouse contained 120 CPython 3.13 Linux AMD64 wheels.
  Direct backend, hosted backend, and frontend images built (3/3). Composed
  backend health and proxied backend health returned `{"status":"ok"}` and
  the frontend returned HTTP 200.
- Main and Teams Bicep compiled (2/2). Release packaging passed. AZD packaged
  backend, frontend, and hosted services (3/3) in 13 seconds using a temporary
  local package environment; no provision or deployment command ran.
- Deployment-profile checks passed. Documentation validation covered 26
  documents, 88 relative links, 89 operational Make references, and 17
  workflow references. All 6 Underwriting workflow YAML files had non-empty
  jobs, and 28 current guidance/profile files passed the identifier/privacy
  scan.
- Git whitespace checks and shell syntax checks passed. No Azure resource,
  Activity endpoint, Bot, Microsoft 365 catalog, Teams publication, database,
  role assignment, or hosted-agent mutation was performed.

**Live-only acceptance still pending**

- Live Azure/Teams/Foundry evaluation/Application Insights acceptance remains
  pending. A readiness claim still requires a fresh reviewed target preview,
  protected provision or app-only deployment as applicable, Responses and
  Activity acceptance, interactive Shared Teams publication, strict live
  evaluation, exact Application Insights correlation, deployment and rollback
  verification, and sanitized release evidence from one release window.

## 2026-10-21 - Integrated local acceptance passed; live evidence pending

**Scope**

- Completed the integrated local acceptance pass for dependency locks,
  PostgreSQL concurrency, HITL/Teams contracts, frontend E2E, offline image
  builds, Bicep, AZD packaging, release/rollback contracts, documentation, and
  identifier hygiene.
- This entry records source and local-contract evidence only. It does **not**
  claim Azure deployment, Azure preview acceptance, live capacity, Activity
  endpoint reconciliation, Teams publication, live Foundry evaluation, or
  Application Insights evidence.

**Fixes found during integration**

- Applied Ruff formatting to three Underwriting files that failed the format
  gate.
- Replaced the Docker Compose backend health check's unavailable `curl`
  dependency with Python `urllib`, matching the Python 3.13 backend image.
- Removed retained target subscription, resource, managed-identity, and
  Container Apps endpoint values from tracked Underwriting plans, ledgers, and
  example evidence. External target values remain owned by ignored deployment
  profiles.

**Local validation**

- `make install`, `.venv/bin/pip check`, and
  `make foundry-python-wheelhouse` passed. The runtime wheelhouse contains
  exactly 120 hash-verified CPython 3.13 Linux AMD64-compatible wheels, and
  pip reported no broken requirements.
- `make validate-full` passed after the formatting fix.
- The real PostgreSQL backend suite passed 88 tests with 1 optional
  environment-gated test skipped and 762 warnings. The skipped real
  PostgreSQL action race was then run explicitly against PostgreSQL 16 and
  passed 1 test with 4 deprecation warnings.
- `make test-scripts test-deployment-profile` passed: 3 PostgreSQL credential
  tests; 25 hosted/release/evidence tests plus 13 subtests; capacity 9;
  preview safety 8; Activity reconciliation 11; Teams publication 22; Teams
  IaC 7; runtime/bootstrap/release shell contracts; public portability; and
  deployment-profile contracts.
- A clean `npm ci` installed 1,101 packages. Frontend lint, TypeScript,
  production build, one focused review Playwright test, and the full two-test
  Playwright suite passed. npm reported 7 low-severity audit notices.
- Direct backend, hosted backend, and frontend Docker images built from the
  validated wheelhouse/lockfiles. The composed frontend returned HTTP 200 and
  `/backend-health` returned `{"status":"ok"}`.
- `make foundry-iac-build` compiled both main and Teams Bicep.
- `make foundry-release-package` passed, and `azd package --no-prompt`
  packaged backend, frontend, and hosted services in 7 seconds without
  provisioning.
- Current operator/design documentation validation covered 23 files, 92
  relative links, 86 Make command references, and 16 workflow references with
  no missing targets. All 6 Underwriting GitHub Actions workflow YAML files
  parsed with non-empty job definitions.
- Identifier/privacy scans found no retained real Underwriting target
  subscription, tenant/user, customer/applicant, credential, managed-identity,
  or deployment-endpoint values in the tracked application/evidence set.
- No separate deterministic local evaluation command is configured. The
  deterministic workflow, review, privacy, retry, recovery, and concurrency
  behavior is covered by the backend and Playwright gates above; the configured
  Foundry trace evaluation is live-only.

**Remaining live-only requirements**

- Run and review the authenticated target capacity check and infrastructure
  preview before any approved deployment.
- Perform app-only deployment, Responses and Teams Activity acceptance,
  interactive Shared Teams publication, rollback verification, live Foundry
  evaluation, Application Insights correlation, and sanitized release
  evidence aggregation in one fresh release window.

## 2026-10-21 - Release hardening implemented; live release evidence pending

**Change**

- Hardened the app-only release DAG around clean wheelhouse preparation,
  hosted-first exact-digest activation, active hosted metadata persistence,
  release-window evidence, and read-only rollback verification.
- Changed direct hosted smoke assertions so AZD output is treated as
  customer-facing text while PostgreSQL run, result, event, and checkpoint
  projections remain the business authority.
- Added direct Responses JSON transport for the structured resume request used
  by crash/recovery smoke instead of treating a JSON file as ordinary client
  text.
- Replaced the fixed trace-age evaluation delay with bounded readiness retry.
  Only empty result sets without a service error and malformed JSON polling
  are retryable; authorization, configuration, and service errors fail
  immediately. The successful status remains `completed`, with zero failed,
  errored, or skipped rows required.
- Added pre-release capture and post-release verification that the prior
  hosted version and exact backend/frontend Container App revisions remain
  available with their original immutable images.

**Files / surfaces**

- `Makefile`
- `.dockerignore`
- `backend/evals/foundry_trace_eval.py`
- `backend/eval.yaml`
- `infra/foundry-hosted/runtime/smoke-test.sh`
- `scripts/foundry/*release*`, deployment, telemetry, evaluation, evidence,
  and hosted-agent inspection scripts
- focused backend/script contract tests
- `underwriting-public-ci.yml`
- README and deployment-flow documentation

**Local validation**

- Focused Ruff checks and 27 hosted-deployment, evaluator,
  release-authority, and evidence tests passed.
- `make test-scripts test-deployment-profile` passed: 28 pytest cases with
  13 subtests, runtime/bootstrap/release shell contracts, capacity (9),
  preview safety (8), activity reconciliation (11), Teams publishing (22),
  Teams IaC (7), public portability, and deployment-profile checks.
- Shell syntax, release-order contracts, and `git diff --check` passed.
- A clean `make foundry-release-package` regenerated and validated 120
  CPython 3.13 Linux AMD64 wheels and a 204-file hosted build context without
  relying on pre-existing ignored artifacts.

**Hosted validation**

- Not run in this todo. No Azure mutation was authorized.

**Release status**

- Source and local-contract implementation only.
- A fresh authenticated app-only release must still produce hosted smoke/E2E,
  strict evaluation, telemetry, exact deployment verification, rollback
  verification, and sanitized aggregate evidence within the 15-minute
  app-only-to-telemetry budget.

## 2026-10-21 - Hardened Foundry parity audit (implementation and deployment evidence pending)

**Change**

- Audited the current Underwriting public source against the hardened Order
  Resolution private release completed in commits `10003c4`, `e3dcfac`, and
  `919d327`.
- Used the newest private release records and the detailed public-lane upgrade
  inventory as the comparison baseline, while inspecting the current
  Underwriting code, package manifests, persistence schema, deployment
  scripts, infrastructure, tests, README, and release-evidence contracts.
- Recorded the initial Underwriting-specific parity matrix below. No runtime,
  infrastructure, dependency, schema, workflow, Teams, or release-script
  change is made by this entry.

**Classification key**

- **Shared behavior to port:** topology-neutral runtime, security, dependency,
  test, or release behavior that should match the hardened baseline.
- **Public-topology adaptation:** the baseline behavior is required, but its
  implementation must retain the external frontend, internal FastAPI adapter,
  public Foundry lane, and locally authenticated public release path.
- **Underwriting-domain adaptation:** the control is required, but its
  workflow, persistence, card, or acceptance semantics must reflect
  Underwriting rather than Order Resolution.
- **Not applicable:** private-network or Order Resolution-specific mechanics
  that must not be copied into this public Underwriting lane.

### Initial parity matrix

| Area | Classification | Current Underwriting inventory | Initial parity disposition |
| --- | --- | --- | --- |
| Backend dependency graph | Shared behavior to port | Direct dependencies remain on the earlier Agent Framework and Agent Server generations; several Azure and web packages use ranges rather than the resolver-safe hardened pins. | Resolve the Underwriting graph independently, align compatible direct versions, preserve `agent-framework-azure-ai` where the Underwriting implementation requires it, and document any unavoidable domain-specific divergence. |
| Python images, locks, and wheelhouse | Shared behavior to port | The backend image uses Python 3.11, the hosted image uses Python 3.12, both install online, and there are no runtime/development hash locks or validated wheelhouse scripts. | Move both images to Python 3.13; generate Underwriting-owned runtime and development locks; install offline with hashes from a CPython 3.13 Linux AMD64 wheelhouse; make every image-building target create and validate that wheelhouse first; prove a clean-worktree build. |
| Release-host Python | Public-topology adaptation | `make install` and release/evaluation scripts rely on the workstation's `python3` and the existing project virtual environment without a supported-version selection contract. | Add a fail-closed Python 3.11+ guard and prefer an isolated Python 3.13 toolchain for package, deployment, evaluation, and evidence operations. Do not copy private-runner bootstrap mechanics. |
| FastAPI lifecycle | Shared behavior to port | `app.server` constructs settings and the database-backed service at import time; no FastAPI lifespan owns startup validation or engine disposal. | Move service initialization and external-schema readiness into lifespan, retain production no-DDL behavior, and close/dispose runtime resources deterministically. |
| PostgreSQL pool and hosted connection retirement | Shared behavior to port | SQLAlchemy uses its default pool with only `pool_pre_ping`; the hosted handler constructs a new `LocalUnderwritingService` and engine for a request, with no explicit hosted pool or retirement settings. | Establish a singleton/reused runtime database boundary and an Underwriting-equivalent hosted pool contract matching the hardened `min=0`, `max=2`, `max_idle=30s` intent, with focused lifecycle and connection-pressure tests. |
| External schema and least-privilege grants | Shared behavior to port | `DB_SCHEMA_MANAGED_EXTERNALLY=true`, startup schema validation, administrator-owned schema generation, and explicit runtime table/sequence grants already exist. The grant allowlist is manually maintained and has no exact schema-parity test. | Preserve the current production no-DDL and `CustomKeys` placeholder contracts; add a canonical schema-to-grant parity test and extend the administrator migration plus grants atomically for every future review/card table. |
| Azure AI Projects hosted-version API | Shared behavior to port | Deployment already uses `AIProjectClient`, `agents.create_version`, `HostedAgentDefinition`, `ContainerConfiguration`, protocol records, immutable image digests, and activation before backend deployment. | Retain this foundation, pin it through the resolved dependency graph, verify exact active-version metadata, and continue preserving prior hosted versions for rollback. |
| AZD hosted invocation compatibility | Shared behavior to port | Hosted smoke sends positional AZD input, but still expects the older embedded JSON workflow result from `azd ai agent invoke`. The deployed browser E2E uses durable API projections instead. | Parse the assigned conversation from current AZD output and assert workflow status, checkpoints, results, and events from PostgreSQL. Send any future structured decision as a real Responses body rather than JSON wrapped as ordinary text. |
| Foundry evaluation compatibility | Shared behavior to port | Evaluation already treats `completed` as success and enforces zero failed, errored, or skipped results, but uses a fixed minimum trace-age delay and has no narrowly classified retry for an empty/malformed in-progress poll. | Retain strict result counting, replace fixed readiness assumptions with bounded adaptive polling, and retry only the known transient malformed/empty poll condition; authorization, configuration, and service errors must fail immediately. |
| Frontend modernization | Shared behavior to port | The lockfile exists, but CopilotKit, React, Zod, Vite, Playwright, ESLint, and TypeScript remain below the hardened baseline. No direct Zod API use was found in `frontend/src`. | Regenerate the lock through the approved Microsoft npm feed; align the modern package baseline; adopt TypeScript 7 for `tsc` plus the TypeScript 6 compiler-API alias while required by `typescript-eslint`; rerun lint, build, focused AG-UI/CopilotKit coverage, full Playwright, Docker build, and HTTP smoke. |
| Dual Responses/Activity host | Public-topology adaptation | The hosted process and `azure.yaml` declare Responses only. There is no Activity host, Activity endpoint reconciliation, Bot Service module, or `MsTeamsChannel` IaC. | Compose Responses and Activity in the same hosted process and keep one Underwriting MAF workflow. Add merge-preserving Activity reconciliation, Bot Service, Teams channel, and rollback that removes Activity/Bot authorization without damaging Responses or Entra. Do not add VNet, private endpoint, Bastion, or private-runner resources. |
| Shared Teams publication | Public-topology adaptation | No publication manifest, package automation, publisher prerequisite check, Shared publication state, publication tests, or Teams acceptance harness exists in the implemented lane. The current Teams design document is planning material, not executable proof. | Add sanitized package generation and inspection, interactive-publisher prerequisite validation, Shared publication, title/catalog state only in ignored sensitive storage, and contract tests. Tenant-wide publication is not the target. |
| Underwriting review trigger and immutable machine recommendation | Underwriting-domain adaptation | The current workflow computes a categorical final decision but has no secure human-review pause or separately persisted reviewer outcome. | Only `REFER_TO_HUMAN_UNDERWRITER` may create the secure Teams review checkpoint. `APPROVED`, `APPROVED_WITH_CONDITIONS`, and `DECLINED` remain terminal machine recommendations. The machine recommendation must remain immutable; the reviewer's `APPROVED` or `DECLINED` decision and its audit metadata must be stored separately rather than overwriting it. |
| Privacy-safe Adaptive Card | Underwriting-domain adaptation | No Underwriting Adaptive Card renderer or action repository exists. Current application and result models contain applicant and underwriting details that must not be copied into Teams. | Cards must contain only a privacy-safe categorical summary, generic review context, checkpoint/run reference suitable for the reviewer, and opaque actions. Do not include applicant identity, health disclosures, income, credit score, raw check results, prompts, rationale, model output, database values, endpoints, or credentials. |
| Trusted origin and structured decisions | Shared behavior to port | Workflow runs do not persist a trusted server-selected origin; resume is a generic start/resume action and there is no cross-channel authorization boundary or structured review-decision parser. | Persist server-selected `api`, `responses`, or `teams_activity` origin. Responses may resolve only Responses-originated review checkpoints through structured input; Teams review requires the bound card action. Free-form words such as approve, decline, yes, or no must remain ordinary text. |
| Atomic action claims and replay protection | Shared behavior to port | There is no card-action table, action batch, claim/complete/release lifecycle, user/conversation binding, expiry, sibling supersession, or concurrent-decision test. Existing workflow start/resume idempotency does not provide this Teams security contract. | Add opaque hashed tokens bound to workflow, checkpoint, decision, reviewer, conversation, expiry, and batch. Atomically claim one action in PostgreSQL before resume, supersede its sibling, complete after success, and release only while review is still pending after a failed resume. Cover wrong user, wrong conversation, expiry, replay, and concurrent clicks. |
| Review schema migration | Underwriting-domain adaptation | The canonical schema contains runs, state, results, events, idempotency, and MAF checkpoints only. | Add trusted origin, immutable machine recommendation as needed, separate reviewer-decision/audit persistence, and card-action state through an idempotent administrator-owned migration before activating a Teams-capable hosted version; update least-privilege grants in the same release. |
| Capacity preflight | Public-topology adaptation | A read-only model deployment/quota check exists, but there is no consolidated resource-aware capacity preflight for the public lane and no focused incremental-capacity test suite. | Preserve exact Underwriting model/version/SKU checks, then calculate quota only for absent or expanding public-lane resources. Healthy matching Foundry model, ACA environment/apps, registry, and PostgreSQL capacity must not be treated as new demand. Search and private-runner checks apply only if Underwriting later introduces those resources. |
| Deployment profiles and confidentiality | Shared behavior to port | Profile loading exists, but target profiles are tracked and generic README, verification, migration, and aggregate-evidence paths still contain target-specific fallback or equality values. | Move target values to validated ignored external profiles, fail closed when required values are absent, and keep tracked source, logs, packages, and evidence free of tenant, subscription, user, resource, endpoint, credential, applicant, and customer identifiers. |
| Preview safety and app-only boundary | Public-topology adaptation | Routine release correctly rejects a deployment-mode override and uses the existing hosted-first two-phase app-only sequence. The release orchestrator compiles Bicep but does not produce and validate a fresh non-mutating preview before app activation. | Add a reviewed preview gate that rejects unexpected create, delete, replace, network, RBAC, scaling, or stateful-resource changes. Preserve public frontend/internal backend topology, separate explicit bootstrap, immutable digest activation, and the 15-minute app-only-to-telemetry budget. |
| Release and evidence gates | Shared behavior to port | Release-local records, artifact hashes, stale/cross-release rejection, exact-digest builds, hosted-first activation, browser E2E, strict evaluation, telemetry, topology verification, and aggregate evidence are already substantial. | Keep those gates; add wheelhouse portability, preview safety, current-AZD smoke, schema/grant parity, review/Teams acceptance, rollback verification, and privacy assertions. Remove target-specific values from generic evidence generation. |
| CI/CD | Public-topology adaptation | There is no Underwriting project workflow under the repository GitHub Actions directory; validation and authenticated release are currently local only. | Add credential-free CI for dependency locks, backend/frontend tests, script contracts, clean wheelhouse/image prerequisites, Bicep, AZD packaging, and documentation checks. Keep authenticated Azure preview, deployment, publication, and evidence execution on the approved local public-lane operator path unless the operating model is explicitly changed. |
| README and documentation split | Underwriting-domain adaptation | The repository catalog already links directly to the Underwriting project, and the project README provides onboarding and release flow. It lacks the hardened operator depth for dependency installation, Teams publication, rollback, troubleshooting, CI/CD, and fresh-evidence interpretation, and it currently exposes concrete target configuration. | Keep `docs/design/` as the canonical Underwriting design location; make the README a self-contained, environment-neutral operator entry point; keep exact run IDs, counts, timings, and telemetry only in dated ledger entries; reconcile or retire duplicate historical issues/fixes material rather than presenting it as current release proof. |
| Private-only topology mechanics | Not applicable | The hardened source release includes private runner, VNet, private endpoint, private DNS, Bastion/tunnel, and private-only PostgreSQL/Foundry reconciliation mechanics. | Do not port them. The target remains public networking with an external frontend, internal backend, public Foundry service boundary, and the narrowly controlled public Activity route required by Teams. |
| Order Resolution scenarios and data | Not applicable | Order IDs, damaged-item rules, sequential order stages, order/customer card content, and Order Resolution retrieval dependencies do not exist in the Underwriting domain. | Replace acceptance scenarios with Underwriting happy, retry, crash/resume, direct-executor fan-in, `REFER_TO_HUMAN_UNDERWRITER`, reviewer approve/decline, replay/isolation, and privacy cases. Do not copy Order Resolution data or prompts. |

### Initial sequencing and evidence gaps

1. **Dependency and build foundation:** resolve backend/frontend graphs, add
   Python 3.13 locks and wheelhouse delivery, and prove clean builds.
2. **Runtime foundation:** introduce FastAPI lifespan ownership, bounded
   PostgreSQL pooling, schema/grant parity, and current AZD/evaluation
   compatibility.
3. **Release safety:** remove target-specific tracked values, add
   resource-aware capacity and preview gates, then extend credential-free CI.
4. **Underwriting review model:** implement the `REFER_TO_HUMAN_UNDERWRITER`
   pause, immutable machine recommendation, separate reviewer outcome, trusted
   origin, and administrator-owned additive schema.
5. **Teams delivery:** add dual protocol, Bot/Teams IaC, Shared publication,
   privacy-safe Adaptive Cards, and atomic action claims without changing the
   public browser/Responses path.
6. **Fresh acceptance:** run full local gates; reviewed public preview; package
   and image builds; app-only deployment; Responses and browser happy,
   retry, crash/resume, and referred-review scenarios; Teams authentication,
   card render, reviewer approve/decline, wrong-user/conversation, typed-text
   blocking, replay, concurrent-action, and privacy checks; strict evaluation;
   correlated Application Insights evidence; aggregate evidence; and rollback
   verification.

**Local validation**

- Documentation inspection and source inventory only.
- No backend, frontend, Bicep, package, Docker, browser, or Azure validation
  gate was run because this todo edits only the parity ledger.

**Hosted validation**

- Not run.
- Historical Underwriting release entries remain historical evidence for the
  source deployed at that time. They do not prove that any item in this
  parity matrix is implemented or deployed.

**Release status**

- This audit is not deployment evidence.
- It does not claim current source parity, a successful preview, publication,
  deployment, smoke test, Teams conversation, Adaptive Card action, Foundry
  evaluation, Application Insights correlation, rollback, or release
  completion.
- The public-networking target and existing browser/Responses architecture
  remain unchanged by this documentation-only entry.

## 2026-08-15 - Deployment documentation synchronized

**Change**

- Aligned the deployment flow, README, agent instructions, Copilot
  instructions, deployment profile guide, Azure plan, architecture contracts,
  and deployment skill with the implemented external-frontend/internal-backend
  topology.
- Documented the actual release order: shared readiness and project
  `CustomKeys` connection convergence, packaging, hosted-agent deployment and
  metadata/RBAC persistence, parallel internal-backend/external-frontend
  deployment, smoke, recovery E2E, telemetry/evaluation, then exact deployment
  verification and aggregate evidence.
- Replaced outdated "public adapter" and hosted-only database-secret wording
  with the current internal backend adapter plus separate ACA-secret and
  Foundry-connection delivery mechanisms.

**Local validation**

- Deployment-profile and script contracts passed.
- Full backend/frontend/E2E validation passed.
- Bicep builds, three-service AZD packaging, shell syntax for 24 scripts, and
  scoped diff checks passed.

**Hosted validation**

- Not run for this documentation-only alignment.

No hosted release completion, evaluation run, telemetry window, or ingress
migration is claimed by this entry.

## 2026-08-14 - Environment-independent bootstrap IaC validation

**Change**

- Validated explicit `bootstrap` and non-mutating `reuse` modes for the public
  lane against isolated and existing Azure environments.
- Corrected bootstrap naming to reserve capacity for the strictest resource
  limits after the preview rejected an overlength Container App and Storage
  account name.
- Corrected AZD missing-value handling and reuse-mode `NAME_PREFIX`
  compatibility before Azure preview.

**Azure validation**

- Created an empty target resource group from the ignored external deployment
  profile.
- Bootstrap preview passed and proposes 12 resources: Foundry account/project
  and model, ACR, PostgreSQL, monitoring, Container Apps environment/apps,
  identities, and evaluation storage. It applied no changes.
- Reuse preview passed for the existing environment and skipped all resources.
- Tenant-authenticated `azd package --no-prompt` passed. It created only a
  local image tag; no image or Azure resource was pushed or deployed.

**Release status**

- Validation evidence only. No Azure infrastructure deployment, app
  deployment, smoke test, E2E, evaluation, or telemetry result is claimed.
- Validated bootstrap or release workflow invocation is the execution trigger;
  no additional manual approval checkpoint is required.

## Environment-independent bootstrap IaC (no Azure deployment evidence)

**Change**

- Added explicit `bootstrap` and non-mutating `reuse` IaC modes for the public
  lane, including parameterized Foundry/model, ACR, monitoring, Container
  Apps, identities, PostgreSQL, and evaluation storage.
- Added a non-secret bootstrap profile and deterministic,
  subscription/resource-group-qualified resource naming.
- Replaced the fixed-subscription PostgreSQL rebuild helper with selected-AZD
  environment inputs and a server-specific confirmation token.

**Local validation**

- Deployment-profile contract, PostgreSQL credential tests, bootstrap-contract
  test, Bicep compilation, shell syntax checks, and `git diff --check` pass.

**Deferrals**

- Superseded by the 2026-08-14 validation entry. No Azure preview, resource
  creation, deployment, smoke test, E2E, evaluation, or telemetry result was
  claimed by this earlier static-only record.

## 2026-08-06 - Direct-executor master-workflow cutover (release evidence pending)

**Change**

- Documented the replacement of the nested parent/child workflow with one
  master underwriting workflow whose direct risk, credit, medical, and driving
  executors fan out and fan in in one superstep.
- Marked version-40 nested-graph checkpoints unsupported for resume after
  deployment. No compatibility workflow or fallback is available.

**Root cause / learning**

- Nested graph checkpoints encode the former parent/child graph shape. The
  master direct-executor graph has a different checkpoint topology, so treating
  a version-40 checkpoint as resumable would create ambiguous recovery
  behavior.
- A clean cutover must reject that ambiguity rather than retain a second graph
  only to resume historical checkpoints.

**Expected verification (not yet performed)**

- Deploy the master direct-executor graph.
- Confirm a fresh crash/resume run resumes from a checkpoint written by that
  graph and retains retry, idempotency, fan-in, and telemetry correlation.
- Confirm a version-40 nested-graph checkpoint is not resumed and that no
  compatibility workflow or fallback path is invoked.
- Record hosted smoke, deployed E2E, Foundry evaluation, Application Insights
  evidence, and run identifiers in a subsequent dated entry.

**Release status**

- Documentation-only record. It does not claim deployment, smoke, E2E,
  evaluation, telemetry, or release success.

## 2026-08-06 - Release validation blocked by container package TLS

**Change**

- Created the required `.azure/deployment-plan.md` and ran the selected
  non-destructive Azure validation flow for `underwriting-foundry-public`.
- Removed the mutable `pip`/`setuptools`/`wheel` upgrade from
  `backend/Dockerfile.hosted`; the image now installs the application directly.

**Local validation**

- AZD schema validation, authentication, environment selection, Bicep preview,
  and policy inspection completed.
- `azd provision --preview --no-prompt` completed without applying changes.
  It previewed updates to the Foundry Application Insights connection and
  PostgreSQL server settings; no resources were changed.
- `azd package --no-prompt` failed before any Azure deployment.

**Issues found**

- Microsoft-managed-device Central Feed Services policy intentionally blocks
  direct access to `pypi.org/simple` and `files.pythonhosted.org`.
- Docker build containers receive `SSLV3_ALERT_HANDSHAKE_FAILURE`; the failure
  persists with Docker host networking, the Windows Docker CLI, and native
  Windows Schannel. It is policy enforcement, not an Underwriting, Azure,
  Docker Desktop, or WSL defect.
- The approved CFS PyPI endpoint
  `https://packagefeedproxy.microsoft.io/pypi/simple` resolves and downloads
  packages through pip from both the host and a clean Python container.

**Fix / decision**

- Do not bypass CFS, downgrade transport security, or deploy an unvalidated
  image.
- Configure the hosted-image pip client with the approved CFS PyPI index:
  `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`.
- `azd package --no-prompt` passed after the configuration change. The release
  can proceed through its remaining validation and deployment gates.

**Deferrals**

- No provision, deployment, hosted smoke, deployed browser E2E, Foundry
  evaluation, or Application Insights telemetry validation was run.
- After package validation passes, resume at provision and record fresh hosted
  evidence in this ledger.

## 2026-08-06 - Clean architecture and delivery-model alignment

**Change**

- Replaced the legacy Underwriting backend layout with explicit API routers and
  schemas, module ports and projections, core composition, persistence
  adapters, and modular MAF factory/workflow boundaries.
- Removed the former route, repository, checkpointing, and parent-workflow
  paths rather than retaining compatibility imports or endpoint fallbacks.
- Preserved the four-check fan-out/fan-in workflow, deterministic decision and
  rationale, retry/idempotency, PostgreSQL checkpoints, crash/resume, Foundry
  Responses, AG-UI, CopilotKit, and operator run-history capabilities.
- Added canonical frontend API configuration and rebuilt the operator UI
  clients, panels, and E2E contract around the new supported API surface.
- Adopted Order Resolution-style repository instructions, architecture/release
  skills, validation routing, Foundry release orchestration, trace evaluation,
  and App Insights verification scripts.
- Added the engineering operating model and refreshed all design, manual-test,
  project-structure, technology, customer-Q&A, and E2E-rubric documentation.

**Files / surfaces**

- Governance: `.github/copilot-instructions.md`, `agents.md`, and the
  repository skill catalog.
- Backend: `backend/app/api/v1/routers`, `backend/app/core`,
  `backend/app/infrastructure/persistence`, `backend/app/modules/underwriting`,
  and `backend/app/maf`.
- Frontend: API configuration, operator components, CopilotKit setup, and
  Playwright coverage.
- Delivery: `Makefile`, Foundry scripts, runtime assets, smoke datasets, trace
  evaluation evidence, and validation/deployment skills.
- Documentation: `README.md` and `docs/design/*`.

**Local validation**

- `make validate-full` passed: backend and frontend linting, 42 backend tests,
  frontend build, script tests, and Playwright E2E.
- `python3 -m compileall backend scripts` passed.
- Shell syntax validation and non-mutating Make target dry runs passed.
- `make foundry-iac-build` passed. The existing Bicep
  `no-deployments-resources` warning remains non-blocking.

**Hosted validation**

- Not executed. This change does not claim a hosted deployment, smoke result,
  Foundry evaluation, or Application Insights result.

**Fix / decision**

- Underwriting now follows the Order Resolution architecture and delivery
  model while remaining the source of truth for its domain workflow and
  operator capabilities.
- No backward-compatibility routes, aliases, shims, or frontend fallbacks were
  introduced. Consumers must use the new supported contracts as one cutover.

**Deferrals**

- Run the authenticated `make foundry-release` sequence only when a deployment
  is explicitly authorized, then add dated hosted smoke, browser E2E, Foundry
  evaluation, and Application Insights evidence to this ledger.

## 2026-08-06 - Optimized gated release baseline 1

**Change**

- Deployed the concurrent release graph without removing a release gate:
  local validation and Bicep preparation overlap, the three independently
  deployable runtime components fan out after shared readiness, and Foundry
  evaluation overlaps deployed browser E2E.
- Released hosted agent version `40`, including redacted
  `gen_ai.input.messages` and `gen_ai.output.messages` attributes on the
  `foundry.responses.invoke` span.
- Corrected the telemetry gate to correlate hosted OpenTelemetry dependency
  spans rather than treating the Application Insights `traces` table as a
  required signal.

**Why**

- The original serial gate order made a release wait for independent work and
  caused a false telemetry timeout because hosted spans export as
  Application Insights dependencies.
- Foundry trace evaluation requires GenAI input and output message attributes;
  applicant inputs and underwriting rationale must not be copied into
  telemetry to satisfy that requirement.

**Files / surfaces**

- Release orchestration: `Makefile` and `scripts/foundry/deploy_public_dev.sh`.
- Trace privacy: `backend/foundry/main.py` and hosted telemetry regression
  tests.
- Validation: `scripts/foundry/verify_telemetry.sh`.
- Reusable guidance: Azure deployment, Foundry evaluation, telemetry, and
  release-readiness skills.

**Local validation**

- The full validation route passed before deployment, including local backend,
  frontend, script, and Playwright checks.
- The three concurrent ACR builds completed successfully; their image-build
  durations were approximately 52 seconds, 62 seconds, and 154 seconds.

**Hosted validation**

- Resource-reuse provisioning completed as a no-op; it made no Azure changes.
- The recorded public backend and frontend revisions are running.
- Hosted smoke approved
  `run-smoke-20260806204039-292096` for conversation
  `conv_3821b67230037df300mkcGnjf0Oa6xl8shkyJ0PhCZFcdOyr6c`.
- Deployed browser E2E passed in 36.8 seconds. The happy and recovered runs
  were `run-hosted-happy-20260806204240-294236` and
  `run-hosted-recover-20260806204240-294236`; both were approved.

**Telemetry / evaluation evidence**

- Foundry evaluation `eval_ddc6cba8d07f455fba4ee2f352296780` / run
  `evalrun_28cdcbbb44034166ab66cf246d3ba0e7` passed 1 of 1 with no failed or
  errored results.
- Application Insights recorded 64 correlated rows for both deployed E2E
  runs: 3 request rows and 61 dependency rows, including an invocation and
  workflow span for each run. There were zero correlated exceptions.
- The evaluation trace attributes contain only action, terminal status, and
  decision summaries; no applicant name, income, credit score, health
  disclosure, or workflow payload is exported.

**Issues found**

- No deployment-blocking issue occurred in this baseline. The initial
  `deploy_mode=full` diagnostic line is emitted before change routing; the
  router correctly selected the requested `app_only` deployment mode.

**Fix / decision**

- Preserve every IaC, deployment, smoke, E2E, evaluation, and telemetry gate.
  Reduce wall-clock time only by parallelizing dependency-independent work and
  skipping provisioning when its preview is genuinely a no-op.
- Do not enable broad message-content capture and do not add a telemetry
  fallback. The structured, redacted GenAI attributes are the sole supported
  evaluation contract.

**Deferrals**

- This is baseline 1 of 3 for the optimized release timing sample. Future
  application-only releases should append comparable timing evidence before
  setting a steady-state target.

## 2026-08-06 - Direct-executor master-workflow cutover

**Change**

- Flattened the underwriting MAF graph so one master workflow fans out directly
  to risk, credit, medical, and driving executors, then incrementally fans in
  their `CheckResult` messages before final decisioning.
- Removed four one-step nested workflow wrappers and changed direct checks from
  terminal `yield_output` calls to typed `send_message` routing.
- Excluded nested `__pycache__` directories from generated hosted-agent source
  packaging after review found stale bytecode in the ignored build context.

**Why**

- One-step child workflows added indirection without a reusable or multi-step
  boundary. Direct executors retain the same Agent Framework superstep
  concurrency while making the topology simpler and type-validated.
- Old nested-topology checkpoints have a different graph signature. The clean
  cutover deliberately rejects them rather than maintaining a second workflow
  or recovery fallback.

**Validation and release evidence**

- The full local validation route passed, including 43 backend tests, frontend
  checks, scripts, and local Playwright E2E. The topology test proves direct
  graph nodes and no `WorkflowExecutor` wrappers.
- A Rubber Duck review confirmed the routing change is required: nested
  wrappers formerly forwarded child `yield_output` values, while direct nodes
  must send `CheckResult` messages to the fan-in edge.
- Hosted agent v41 and the recorded backend/frontend revisions deployed
  successfully.
- Smoke run `run-smoke-20260806214717-357052`, both deployed E2E runs
  `run-hosted-happy-20260806214836-359053` and
  `run-hosted-recover-20260806214836-359053`, Foundry evaluation
  `eval_286f9bdf2cab4166accb2422a9292e55` (1 of 1), and telemetry correlation
  (64 rows, zero exceptions) all passed.

**Issue and fix**

- The initial concurrent hosted-agent ACR build hit a transient CFS pip
  `BrokenPipeError`. Backend and frontend deployment succeeded; retrying only
  the failed hosted-agent leg succeeded. This is a package-feed recovery
  sample, not a topology defect or steady-state timing baseline.

**Decision**

- Keep a direct executor in the master workflow while its check is one step.
  Introduce a sub-workflow only for a reusable or multi-step pipeline with
  meaningful internal branching, tools, or lifecycle.

## 2026-08-10 - Existing-target deployment profile standardization

**Change**

- Added a versioned non-secret profile wrapper for selecting an existing
  Underwriting Foundry-public AZD target and generalized the shared profile
  applicator to accept the caller's AZD project directory.
- Removed hardcoded target defaults from bootstrap, required selected AZD
  target values, and kept PostgreSQL location discovery dependent on the
  selected PostgreSQL server.
- Changed routine release routing to app-only; provisioning remains explicit
  and separately approved.

**Validation**

- Profile application, secret-exclusion, missing-target rejection, app-only
  release routing, shell syntax, and Makefile dry-run checks passed locally.

**Release status**

- Implementation-only record. No Azure deployment, smoke, E2E, evaluation, or
  telemetry result is claimed.

## 2026-08-10 - Existing-target public release evidence

**Change**

- Released the app-only Foundry-public lane after a resource-reuse
  `azd provision` reported no changes.
- Updated the PostgreSQL readiness script to use the current Azure CLI
  flexible-server show arguments: `--server-name` and `--name`.

**Validation and release evidence**

- Full local validation passed: lint, 43 backend tests, scripts, frontend
  checks, and local Playwright E2E. Bicep compiled with only its existing
  non-blocking linter warning.
- PostgreSQL readiness, ACR availability, Container App readiness, and
  backend managed-identity `AcrPull` all passed before deployment.
- Hosted agent version `42` and the recorded backend/frontend revisions are
  active and Running.
- Smoke passed for `run-smoke-20260810195340-158524`; deployed E2E passed for
  `run-hosted-happy-20260810195505-160963` and
  `run-hosted-recover-20260810195505-160963`.
- Foundry evaluation `eval_d0e6c3dfb31d44f0bb6b1e3d44cb194f` passed 1 of 1.
  Application Insights returned 64 correlated rows for the two E2E runs and
  zero exceptions.

**Issue and resolution**

- The initial release stopped before app deployment because the readiness
  gate passed obsolete firewall-rule and database argument names to Azure CLI.
  The corrected gate passed against the existing target, and the retry
  completed every release gate without provisioning a new resource or adding
  a fallback.

## 2026-08-10 - Final existing-target app-only release evidence

**Validation and release evidence**

- Bicep compiled and the existing PostgreSQL readiness gate passed; no
  provisioning or retained-infrastructure mutation occurred.
- Hosted agent version `43` and the recorded backend/frontend revisions are
  active and Running.
- Smoke passed for `run-smoke-20260810203807-206537`; deployed E2E passed for
  `run-hosted-happy-20260810203934-208937` and
  `run-hosted-recover-20260810203934-208937`.
- Foundry evaluation `eval_4082061319e44f38b7e1520ae9122c7f` completed 1/1
  with zero failures/errors. Application Insights returned 64 correlated rows
  and zero exceptions for the two E2E runs.

## 2026-08-12 - Validation-only catalog skill refresh and sanity run

**Change**

- Selectively vendored the complete `microsoft-foundry` (185 files) and
  `agent-framework-azure-ai-py` (5 files) directories under `.github/skills/`.
- Recorded the `microsoft/skills` source pin
  `e58528db9a006528a5fb0a2c029790fa6a9a7c0e` in
  `.github/skills/README.md`, and added both skills to the instruction,
  agent-guide, and technology-stack inventories.

**Candidate review**

- Reviewed the recipes and called scripts for `foundry-iac-build`,
  `foundry-postgres-readiness`, `foundry-smoke`, `foundry-hosted-e2e`,
  `foundry-eval`, and `foundry-telemetry` before execution.
- The selected validation routes compile or read/query existing resources;
  smoke and E2E submit disposable validation workflows and write local
  evidence. Their existing evidence files were restored after each attempt so
  pre-existing worktree changes remain intact.

**Commands and outcomes**

- `make foundry-iac-build` passed. The existing Bicep
  `no-deployments-resources` warning remains.
- `make foundry-postgres-readiness` failed: `PostgreSQL server is not Ready.`
  This was a read-only preflight; no PostgreSQL change was attempted.
- `make foundry-smoke` reached the existing endpoint but failed its completed
  response assertion (`.status == "COMPLETED"`; no result payload was
  extracted). No fresh workflow or conversation identifier was produced.
- `make foundry-hosted-e2e` failed with HTTP 504. It produced no fresh
  workflow-run identifiers or E2E evidence.
- `./scripts/foundry/run_foundry_trace_eval.sh --check` passed, confirming
  selected-AZD evaluation configuration. `make foundry-eval` was not run
  because it would consume the pre-existing smoke evidence; no historical
  conversation was treated as fresh evidence.
- `make foundry-telemetry` was not run because it requires fresh hosted-E2E
  evidence, which the failed E2E gate did not create. Pre-existing telemetry
  evidence was not reused.

**Release status and blockers**

- No deployment, release, provisioning, `foundry-up`, infrastructure
  reconciliation, PostgreSQL change, or app-only deployment was performed.
- The safe source identifier for this change is the catalog revision above;
  no credentials, connection strings, or other secrets are recorded here.
- Re-run `make foundry-postgres-readiness`, then `make foundry-smoke`,
  `make foundry-hosted-e2e`, `make foundry-eval`, and
  `make foundry-telemetry` only after the existing PostgreSQL service and
  hosted endpoint are healthy. This entry does not claim historical evidence
  as current.

## 2026-08-13 Release Gate Blocked: Frozen Manifest Unavailable

- The requested existing-environment release was stopped before Bicep
  compilation, Azure preview, provisioning, or application deployment.
- The exact release-input freeze at the supplied session-state path could not
  be read by this execution environment (`Permission denied`). Consequently,
  the current dirty worktree manifest cannot be verified against the required
  frozen manifest, and no deployment-safe approval can be established.
- Current safe manifest digests were recorded locally for `Makefile`,
  `pyproject.toml`, `requirements.txt`, `infra/foundry-hosted/azure.yaml`, and
  `frontend/package.json`; `Makefile` is modified in the dirty worktree. No
  secret, resource, deployment, database, network, or RBAC identifier was
  produced or changed.
- Remediation: restore read access to the exact freeze file, compare the
  frozen and current manifests, then restart the Azure Validate workflow and
  run fresh validation evidence. Do not reuse prior smoke, E2E, evaluation,
  or telemetry artifacts.

## 2026-08-13 Existing-Environment Release Gate Blocked: PostgreSQL Stopped

- A fresh lane-local non-secret manifest was created from
  `git status --short -uall` and SHA-256 file digests before validation. The
  release remained an existing-environment operation selected through the
  ignored external profile; no bootstrap was attempted.
- Azure YAML schema validation passed and `make foundry-iac-build` passed.
  Bicep emitted only the existing `no-deployments-resources` warning for
  `resourceReuseValidation`.
- `make foundry-postgres-readiness` failed with `PostgreSQL server is not
  Ready.` The independent non-mutating
  `azd provision --preview --no-prompt` also failed with
  `ServerStoppedError` for the externally selected existing PostgreSQL server;
  it applied no changes.
- No guarded release, provisioning, deployment, PostgreSQL rebuild/reset,
  database/network/RBAC mutation, smoke, hosted E2E, Foundry evaluation, or
  telemetry gate ran after this failed prerequisite. No fresh run,
  conversation, revision, or evaluation identifier was produced.
- Root cause: the existing PostgreSQL server was stopped. Remediation is to
  have the environment owner restore its Ready state, then repeat the full
  fresh validation, preview review, guarded release, and evidence gates
  without reusing prior artifacts.

## 2026-08-13 Existing-Environment Release Completion Evidence

- With explicit approval, only the lifecycle state of existing PostgreSQL
  externally selected PostgreSQL server was changed from `Stopped` to `Ready`. No
  database data/configuration, public access, firewall, RBAC, network, reset,
  or rebuild operation was performed.
- A refreshed lane-local non-secret manifest was created before validation and
  remained byte-identical through the guarded pipeline. Fresh Bicep
  compilation and PostgreSQL readiness passed; Bicep retained only the known
  `no-deployments-resources` warning.
- `azd provision --preview --no-prompt` completed without applying changes.
  Its only retained-resource differences were the declared Foundry
  Application Insights connection and PostgreSQL resource-reuse properties;
  no unexpected database, network, firewall, or RBAC mutation was shown.
- The existing guarded `make foundry-release` path completed successfully.
  The active backend and frontend revisions reported `Running` and
  `Healthy`.
- Fresh hosted smoke passed with
  `run-smoke-20260813154647-80855`. Hosted E2E passed with
  `run-hosted-happy-20260813154812-83546` and
  `run-hosted-recover-20260813154812-83546`.
- Report-only Foundry evaluation
  `eval_99ff1f7625084ef7a9f9c5015bc04708` completed with 1 passed of 1 and
  zero errors or failures. Application Insights verification correlated both
  E2E runs with two request, hosted-invocation, and workflow-span records,
  with zero correlated exceptions.

## 2026-08-13 — Approved npm feed policy

The frontend uses the approved Microsoft npm feed
`https://packagefeedproxy.microsoft.io/npm/` for all locked installs. Its
checked-in `.npmrc` requires TLS validation and sets
`replace-registry-host=npmjs` so registry.npmjs.org lockfile tarballs cannot
bypass the approved feed. The Docker build copies this policy before
`npm ci`. This is a package-acquisition policy change only; no deployment or
release evidence was rerun.

## 2026-08-14 - Deployment guidance reference access denied

**Issue**

- The deployment preflight could not read two installed Azure Deploy skill
  reference files: the pre-deploy checklist and the AZD recipe guide. The
  tooling returned `Permission denied and could not request permission from
  user`.

**Impact**

- This is a local content-access restriction on installed skill documentation,
  not an Azure authorization or resource failure.
- No Azure CLI, AZD provisioning, deployment, database, network, RBAC, smoke,
  E2E, evaluation, or telemetry command ran as a result. No target resource
  changed.

**Decision**

- Continue only with the validated lane-local deployment plan, checked-in
  release scripts, and explicit deployment authorization.
- Reconcile the restricted skill-reference access separately; do not bypass
  it by reading the denied files through another tool or by treating the
  restriction as a successful pre-deployment check.

## 2026-08-14 - New-subscription bootstrap retry after Foundry project location failure

**Issue**

- The first authorized bootstrap attempt created the Foundry account/model,
  ACR, evaluation storage, monitoring, Container Apps environment/apps, and
  PostgreSQL, but ARM rejected the child Foundry project with
  `LocationRequired`.

**Root cause and fix**

- The `Microsoft.CognitiveServices/accounts/projects@2025-06-01` resource did
  not explicitly set `location`, although its parent account did.
- The child project now receives the same parameterized location as the parent,
  and the bootstrap contract test asserts that property.
- The next retry reached the project API but exposed a second missing parent
  contract: project creation requires the `AIServices` account to set
  `allowProjectManagement: true`. The account now declares that property, and
  the same bootstrap contract test covers it.
- The following reconciliation exposed that role assignments scoped directly
  to conditional resource symbols compiled at resource-group scope. This
  created duplicate `Log Analytics Reader` assignments and failed with
  `RoleAssignmentExists`.
- Role assignments now use unconditional existing-resource aliases for their
  extension scopes. The contract test parses the generated ARM template and
  requires all ten assignments to contain explicit resource scopes.
- Because Azure role-assignment GUIDs cannot move between scopes, the corrected
  resource-scoped assignments use a versioned deterministic GUID seed. The
  superseded resource-group assignments are removed only after all replacement
  assignments are live and verified.
- Nine replacement assignments were created successfully. The Application
  Insights reader had never been created at the incorrect scope and already
  existed correctly under its original deterministic ID, so that one ID is
  retained instead of creating a duplicate.
- After resources, scoped RBAC, and the project connection reconciled, ARM
  failed output evaluation because the 2025-06-01 account API exposes
  `endpoint` at the response root rather than under `properties`. The
  `AZURE_OPENAI_ENDPOINT` output now reads the actual API shape, with a
  regression assertion in the bootstrap contract test.
- The first runtime-credential attempt stopped before changing PostgreSQL
  because its firewall lookup used unsupported Azure CLI `--rule-name`
  syntax. It now uses the current `--server-name <server> --name <rule>`
  contract, matching the readiness validator.
- The next attempt incorrectly reported that the declaratively created
  database was absent because `db show` used unsupported `--database-name`
  syntax and suppressed the CLI diagnostic. Live enumeration confirmed the
  `underwriting` database exists; the check now uses `--name`.
- The first app release built and pushed all three images and activated hosted
  agent version 1, but backend rollout stopped because the current Container
  Apps CLI rejects `--target-port` on `az containerapp update`. Backend image
  and environment updates now use `containerapp update`, followed by the
  supported `containerapp ingress update --target-port 8000`.
- Direct hosted smoke then passed, but deployed public E2E failed at the
  adapter relay. The backend revision had no Foundry project endpoint, pinned
  hosted-agent endpoint/version, or `AZURE_CLIENT_ID` for its user-assigned
  identity. Backend deployment now injects those values from AZD outputs and
  the live managed identity, while keeping credentials out of source.

## 2026-08-14 - New-subscription E2E deployment completed

**Target**

- Subscription, resource group, region, and Foundry account/project were
  supplied through the ignored external deployment profile.
- Model deployment: `underwriting-gpt-4-1-mini`, `gpt-4.1-mini`
  `2025-04-14`, Global Standard capacity 2500

**Infrastructure and database**

- Bootstrap provisioning completed for Foundry/model, ACR, evaluation storage,
  Log Analytics, Application Insights, Container Apps environment/apps,
  PostgreSQL, managed identities, the Foundry Application Insights connection,
  and scoped role assignments.
- Live RBAC verification found all ten IaC-required resource-scoped
  assignments, one additional platform-managed OpenAI User assignment for the
  hosted agent identity, and no residual assignment at resource-group scope.
- PostgreSQL schema bootstrap and least-privilege runtime credential
  provisioning passed. Readiness verified TLS, matching runtime URLs, Ready
  server state, database existence, dual password/Entra authentication, the
  Azure-services firewall rule, and the release-operator rule.

**Deployment**

- The recorded backend revision is active, provisioned, and healthy.
- The recorded frontend revision is active, provisioned, and healthy.
- Hosted agent `underwriting-hosted` version 1 is active with the Responses
  protocol.
- Backend health and frontend availability passed at the externally selected
  deployment endpoints; endpoint values are intentionally not retained.

**Validation evidence**

- The release validation lane passed 43 backend tests, three PostgreSQL/script
  tests, and local Playwright.
- Hosted happy smoke passed for
  `run-smoke-20260814203420-205557`, decision `APPROVED`.
- Deployed E2E passed for
  `run-hosted-happy-20260814204326-212165` and
  `run-hosted-recover-20260814204326-212165`. Both completed with
  `APPROVED`; deployed Playwright passed.
- Report-only Foundry trace evaluation
  `eval_92d28e20777343c3be0ed8e688e4d02b` /
  `evalrun_2e89f0eb60164f6c997856eacdb92e24` completed with one passed,
  zero failed, and zero errors.
- Application Insights correlated 64 rows across both E2E workflow runs:
  three requests, 61 dependencies, both hosted-invocation/workflow-span run
  pairs, and zero exceptions.

**Operational learnings**

- A first evaluation submitted immediately after smoke found zero trace rows
  and failed. Retrying after trace ingestion completed passed; no evaluator or
  runtime fallback was introduced.
- One backend redeploy attempt stopped before mutation because local DNS could
  not resolve `management.azure.com`. The identical idempotent retry succeeded.
- Native evaluation-suite generation remains deferred under the selected
  acceptance policy because the organization blocks its public
  evaluation-storage route. Report-only trace evaluation is the completed
  release gate.
- The first post-release preview showed that the selected environment still
  declared `bootstrap`, which would reconcile released Container Apps back to
  placeholder images and port 80. Successful bootstrap hydration now
  transitions the AZD environment to explicit `reuse`, so future provision
  previews create or modify no resources.
- Built-in role definitions are now explicitly resolved at subscription scope
  in Bicep, and the generated-template contract verifies every assignment uses
  a subscription-scoped role definition.
- The destructive PostgreSQL rebuild command now refuses to delete from a
  `reuse` environment because that mode cannot guarantee declarative server
  recreation. Its server token, live-location check, and other destructive
  safeguards remain in force for bootstrap-mode recovery.

**Safety**

- The retry uses the same selected AZD environment and deterministic names, so
  already-created resources are reconciled rather than duplicated.
- No PostgreSQL rebuild, data deletion, credential provisioning, app release,
  smoke, E2E, evaluation, or telemetry operation occurred before this fix.

## 2026-08-16 - Two-phase release optimization and final evidence

**Issue.** The prior complete app-only release required **18m 07.4s** to reach
telemetry. Limited ACR task concurrency serialized one remote build, while
deploying all three runtime legs together could let the backend read the
previous hosted-agent version.

**Fix.** Release `uw-public-51a8311-20260816140654` builds backend and hosted
images concurrently in ACR and the frontend concurrently with local Docker.
It resolves immutable digests, activates the hosted agent from its exact
prebuilt digest, persists version 7, and only then deploys the backend and
frontend concurrently. Routine app deployment now validates the existing
frontend-external/backend-internal topology instead of repeating ingress
updates. Verification accepts both tag- and digest-pinned repository
references.

**Evidence.** The release passed smoke, happy/retry/crash-and-resume E2E,
deployed Playwright, Task Completion and Coherence evaluation, 89 correlated
Application Insights rows across all three fresh workflow runs with zero
exceptions, deployment verification, and strict final evidence. App-only to
telemetry was **14m 10.0s**, 50.0 seconds inside the hard 15-minute budget and
**3m 57.5s faster** than the prior complete run.
