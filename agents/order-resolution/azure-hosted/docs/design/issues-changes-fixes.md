# Delivery Evidence

## Current status

**Source implementation synchronized; no current deployment validation
claimed.** Historical entries below explain prior work but do not prove a
currently live endpoint or revision. Current deployed evidence belongs in the
dated ledger in `.azure/deployment-plan.md` only after its commands complete.

## 2026-08-10 — PostgreSQL recovery and release-readiness hardening

**Observed issue.** Backend revision
`maf-backend-puzsry--ci-ci-31328131254-1` could not start because the existing
Flexible Server `maf-ora-azure-pg-puzsry` was stopped. Application startup
waited for the managed-identity PostgreSQL pool and then failed with
`psycopg_pool.PoolTimeout`. The server was started by the operator and later
reported `Ready`; the active backend revision became healthy and the frontend
same-origin `/api/health` proxy returned HTTP 200.

**Guardrail.** The app-only release path remains unchanged: it does not
reconcile infrastructure, alter PostgreSQL configuration, network access, or
RBAC. Runtime smoke now retries a bounded number of non-empty `/api/chat/run`
responses, and the hosted validation reader retries transient transport or
JSON-decode failures while awaiting workflow events. Both paths still fail
explicitly when their retry limit is exhausted. The release asset validation
now runs a contract test that proves recovery after empty or failed chat
responses and explicit failure after the retry limit.

**Pre-release evidence.** Azure Validate completed for the selected target;
the app-only release preflight, Bicep compilation, and credential-free
reconciliation guard passed. GitHub Actions run
[`31399361069`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31399361069)
stopped at operating-model enforcement because this ledger had not yet been
included in the pushed change. It did not build, deploy, smoke-test, run E2E,
evaluate, or query telemetry. A subsequent run is required before any new
release evidence is claimed.

**Fresh release evidence.** Full app-only release run
[`31400240425`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31400240425)
completed after the retry-contract test changed the runtime release surface.
It passed backend lint/tests/deterministic evaluation, browser E2E, Docker E2E,
immutable backend/frontend image deployment, fresh smoke, hosted E2E,
report-only Foundry evaluation, and exact-pair Application Insights telemetry.
No infrastructure reconciliation occurred.

## 2026-08-07 — Azure-hosted parity: selected-thread safety and release evidence

### Learning issues

1. The existing native `/rich` contract retains native event payloads. Passing
   it through an assistant UI would expose a broader event shape than a
   selected-thread assistant needs.
2. A generic CopilotKit request can contain messages, state, tools, context,
   and run identifiers. Treating those fields as workflow input would create a
   second execution/mutation channel.
3. A frontend image needs deployed endpoint configuration at runtime; relying
   only on build-time values risks proxy/API mismatch. A developer inspector
   also expands the visible data surface.
4. Release packaging must keep the approved CFS Python feed and account for
   the frontend Alpine/musl runtime.
5. Provisioning as a default response to changed files risks replacing durable
   PostgreSQL state. A successful old preview or telemetry result is not
   evidence for a new application revision.
6. Release validation needs one fresh chain from hosted E2E stimulus to
   Application Insights correlation, rather than an unrelated broad lookback.

### Fixes and guardrails

- `/api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` now document
  the intended read-only selected-existing-thread boundary. The projection
  allows only safe lifecycle/tool labels, validated checkpoint/decision
  summaries, and generic terminal/error text. It never exposes raw native rich
  payloads, orders, policy/MCP data, tool data, prompts, model output,
  checkpoint payloads, credentials, or secrets.
- `GET /api/copilotkit/info` and its root alias are static discovery.
  Compatibility fields in the POST bridge are discarded; the bridge cannot
  start, approve, reject, resume, or otherwise alter a workflow. The
  CopilotKit inspector remains disabled.
- The frontend documents runtime `window.__APP_CONFIG__` precedence for
  `API_BASE`, `AG_UI_URL`, and `COPILOTKIT_URL`, ahead of Vite fallbacks.
- Normal releases are `make release-app` application-only releases. They retain
  the CFS feed, musl-compatible frontend build, existing PostgreSQL server, and
  `maf_workflow` database. Infrastructure reconciliation requires explicit
  non-secret approval/reference and Bicep preview; it is never implicit.
- Smoke captures a release/time/thread/workflow-run evidence set. Hosted E2E,
  report-only evaluation, and telemetry validation must correlate to that
  fresh set before a deployment is recorded as validated.

### Evidence and blocker status

This documentation-only synchronization did **not** run Azure deployment,
hosted smoke, hosted Playwright, report-only Foundry evaluation, or Application
Insights queries, so none is claimed here. Docker E2E has no pass claim in this
entry; if its TLS trust/handshake setup blocks the test, record the exact
failure as a Docker E2E blocker rather than substituting local or historical
results.

### Single-maintainer reconciliation follow-up (2026-08-07)

This project currently uses an explicit owner-confirmed reconciliation gate
rather than a team-review workflow. An apply requires
`INFRA_RECONCILIATION_APPROVED=true`, a non-secret owner change reference, and
the exact preview and template/parameter SHA-256 values emitted by the
owner-reviewed `make release-infra-preview`.

The simplified gate still uses a subscription-scoped Azure what-if and rejects
every PostgreSQL mutation before apply. It verifies the existing server and
database are `NoChange`, preserves their post-apply identity, and requires
fresh per-thread/per-workflow-run telemetry correlation. Reintroduce external
reviewer attestation and protected-environment enforcement when the project has
multiple maintainers.

### Managed-device Docker npm egress follow-up (2026-08-07)

Host npm installs and direct npm registry downloads succeeded, while Docker
builds on this managed device were blocked by the endpoint policy (`[TE] NPM
URL Block`). The Microsoft npm proxy was reachable but did not contain the
locked Vite and Linux-musl binding versions, so changing registries or
downgrading dependencies would be an unvalidated compatibility change.

The local `docker-test` target is therefore optional. The existing GitHub
Actions **Required cloud Docker E2E** job is the authoritative full-change
Docker image/browser gate. This preserves Docker coverage without treating a
managed-device egress restriction as an application failure.

## 2026-08-10 — Final app-only rerun blocked by managed-device npm egress

**Preflight.** Release safeguards, the credential-free reconciliation guard,
smoke retry contract, and Bicep compilation passed. Infrastructure
reconciliation was not invoked.

**Observed issue.** The local app-only release deployed backend revision
`maf-backend-puzsry--azd-1786393782`, then stopped while building the frontend.
`npm ci --include=dev --no-audit` emitted npm's internal `Exit handler never
called` error and returned without installing `tsc`; three verified retries
reproduced the failure. The frontend remains on the prior running revision
`maf-frontend-puzsry--ci-ci-31400240425-1`.

**Decision.** The Dockerfile now verifies `node_modules/.bin/tsc` and retries
the install before allowing a build, so an incomplete install cannot proceed
to a misleading later failure. This did not overcome the managed-device Docker
npm egress policy. The approved Microsoft npm proxy remains incomplete for the
locked Vite/musl dependencies, and the Azure-hosted CI only authorizes Azure
deployment on a `main` push. No registry, firewall, dependency, or CI
authorization workaround was applied.

**Release status.** This is not a completed release: smoke, deployed E2E,
Foundry evaluation, and telemetry were not run after the frontend build
failure. Use the required cloud Docker-E2E app-only release on a `main` push
for the next complete Azure-hosted evidence chain.

### Cloud app-only release lane (2026-08-07)

The Azure-hosted CI workflow now triggers only for
`agents/order-resolution/azure-hosted/**` and its own workflow file. Its
full-validation release job builds backend/frontend images once, runs Docker
E2E against those exact local images, pushes them to ACR only after the test
passes, and deploys immutable image digests to the existing Container Apps.
The same job then captures fresh smoke, hosted browser E2E, report-only
Foundry evaluation, and App Insights correlation evidence.

The release identity uses GitHub OIDC and a dedicated scoped app identity; no
deployment password or Azure client secret is stored in GitHub. Infrastructure
reconciliation remains outside this lane because the Azure preview reported a
PostgreSQL modification, which the owner-confirmed guard blocks.

The first cloud run correctly stopped before image push or Container Apps
mutation when the Docker browser test exposed an insecure-origin compatibility
gap. Chromium does not expose `crypto.randomUUID()` to the Compose hostname, so
AG-UI silently discarded frames and CopilotKit failed before sending its
read-only request. Client-only frame/run identifiers now use
`crypto.randomUUID()` when available with a monotonic fallback otherwise.
Focused browser, lint, typecheck, build, and release-guard checks passed before
the retry.

The subsequent CI attempt deployed the tested image digests and passed smoke
plus hosted workflow E2E, then stopped before final evidence because the Docker
Playwright container left root-owned result files in the mounted workspace.
The Compose test service now runs as the invoking host/runner UID and GID so
the following hosted selected-thread E2E can clean and write its own artifacts.

That retry passed Docker E2E, app deployment, smoke, both hosted browser suites,
and the report-only Foundry evaluation. The final telemetry gate found the
expected App Insights data but rejected it because Azure CLI emits KQL results
as a list of dictionaries rather than the Log Analytics REST table-and-row
shape. The verifier now accepts both documented shapes while preserving exact
thread/workflow-run pairing, the fresh-release timestamp, and the zero-exception
requirement.

The final path-scoped run
[`31204487857`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31204487857)
passed every release gate: Docker E2E, immutable app-only deployment, smoke,
workflow and selected-thread hosted E2E, Foundry evaluation, and fresh exact-pair
App Insights correlation with zero exceptions. The deployment plan records the
non-secret endpoints, digests, evaluation IDs, and telemetry evidence. No
infrastructure reconciliation occurred.

### Release critical-path optimization (2026-08-07)

The cloud release job initially took 8m 37s. The final optimization keeps the
same gates and exact-image invariant while prebuilding unpushed Docker layers
through the GitHub Actions cache, caching Playwright browsers, and running
hosted browser E2E with the independent Foundry evaluation after smoke.
Telemetry remains after those two gates to avoid concurrent Azure CLI token
cache access; backend/frontend Container App updates also remain sequential to
avoid a mixed-version partial deployment.

The first raw Buildx cache attempt did not expose GitHub runtime credentials,
so it rebuilt every layer. It was replaced with `docker/build-push-action`,
which supplies those credentials. Verified run
[`31214807222`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31214807222)
reported cached backend/frontend layers and passed every gate in 5m 54s for
the cloud job and 9m 24s end-to-end, versus 8m 37s and 11m 26s respectively.

## Historical source-of-truth correction (2026-07-28)

The delivery record continued to describe the deleted resources as active.
The root cause was preserving successful 2026-07-27 release evidence without a
teardown status transition. The affected deployment plan and README now label
that evidence historical; a new release must replace it with fresh endpoint
and validation evidence.

## Historical clean-provision recovery (2026-07-28)

The clean Azure preview initially failed with `FlagMustBeSetForRestore` because
the deterministic Foundry account name remained soft-deleted after the
intentional teardown. The deleted account was purged so the clean Bicep plan
could create it again. The subsequent provision created all resources but the
post-provision PostgreSQL grant attempted token authentication before the newly
created Microsoft Entra administrator had propagated. The same grant succeeded
after propagation, confirming a timing issue rather than an identity mismatch.

The post-provision hook now retries the first Entra-authenticated PostgreSQL
connection for a bounded interval before granting the backend managed identity.
Clean release validation must run preview, provision, backend/frontend deploy,
smoke, hosted Playwright, evaluations, and telemetry against the newly assigned
endpoints.

The local `make eval-foundry` target correctly defaults to localhost for
developer use. `make eval-foundry-deployed` now reads only the selected AZD
environment's non-secret `API_URL` and passes it as `FOUNDRY_EVAL_API_URL`,
making the deployed Foundry report a reproducible release gate.

## Historical validation record

Keep the following evidence current for the deployed environment:

- `make test`
- `make eval-backend`
- `make eval-foundry-deployed`
- `make test-e2e`
- `make docker-test`
- `./scripts/skills/design-review-skill.sh`
- Bicep/AZD, IaC, and Azure readiness validation

Do not retain historical deployment ledgers or references to retired hosting
paths in this document.

## Clean-runner E2E dependency correction (2026-07-28)

GitHub Actions run `30370787270` failed the quick-validation E2E gate even
though the same target passed on a prepared workstation. The job installed
Node.js but did not install either the frontend Vite dependencies or the
Playwright package/browser. Consequently, the local Vite process never opened
its dynamically assigned port and the proxy readiness check failed.

The design-review and quick-validation CI jobs now install the frontend with
`npm ci`; quick validation also installs the Playwright package and Chromium
before running `make validate-quick`. This makes the clean GitHub runner
contract match the documented local E2E target without relying on ignored
`node_modules` directories.

## 2026-08-12 — Validation-only hosted sanity run

**Skills decision.** No skill was added or changed. The existing curated
skills match this Container Apps-hosted MAF application: MAF/Foundry client,
Azure identity, Azure Monitor telemetry, Azure deployment-validation, IaC,
local-validation, and E2E skills cover the service boundaries already in use.
`agent-framework-foundry-py` and `azure-ai-projects-py` support the existing
MAF model-inference and report-only evaluation integrations; they do not make
Foundry an application host. In particular, `microsoft-foundry` and every
other additional Microsoft skill remain deliberately unadded.

**Candidate target safety review.** `bicep-build` compiles Bicep to stdout;
`release-preflight` runs source assertions, the credential-free local
reconciliation mock, smoke-retry contract tests, and Bicep compilation; and
`release-validate` reads the selected AZD non-secret outputs, drives the
existing endpoints with the required validation workflows, creates validation
artifacts, runs the report-only evaluation, and queries telemetry. None calls
`release-app`, image deployment, `azd provision`, infrastructure
reconciliation, or PostgreSQL administration. The endpoint workflows create
their normal durable validation records; the mock preflight's fake apply is
local-only and cleaned up.

**Commands and fresh outcomes.** The first root-level `make bicep-build`
invocation correctly failed because that target belongs to this lane; the
corrected lane commands below passed:

- `make -C agents/order-resolution/azure-hosted bicep-build`
- `make -C agents/order-resolution/azure-hosted release-preflight`
- `make -C agents/order-resolution/azure-hosted release-validate`

IaC compilation and the deploy-not-run preflight passed. The latter also
passed release asset checks, the local credential-free reconciliation guard,
and the smoke retry contract. Fresh validation began at
`2026-08-12T14:46:36.747596Z` with release-run identifier
`20260812T144636Z-25678`: existing-endpoint smoke passed; hosted Playwright
passed all 7 workflow and 3 selected-thread tests; the report-only Foundry
evaluation `eval_5fa101257e5445b284d9a3a5eb5cf243` /
`evalrun_8597954a4b2149d39c01f4de9682ca74` completed with 2/2 cases passed;
and exact-pair Application Insights correlation passed with zero exceptions
for the two fresh smoke thread/workflow-run pairs (39 and 5 telemetry items).

**Boundary and blockers.** No deployment, `release-app`, app-only deployment,
image push, provision, infrastructure reconciliation, or PostgreSQL
administration/schema change was performed. Required endpoint workflows created
only their normal durable validation records. There were no gate blockers.
Azure CLI emitted its non-fatal `--subscription`/`--ids` warning during the
read-only telemetry query; the telemetry gate still passed. This entry records
fresh validation-only evidence, not a release or deployment claim, and
contains no secrets.

## 2026-08-13 — Release gate blocked before IaC execution

**Pre-deployment checks.** The selected Azure account resolved to subscription
`4f18d577-3506-4a11-85e5-a83b14727a84`, and AZD resolved the existing
`maf-ora-azure` environment. The frozen-release manifest SHA-256 was
`04e56fc79a11e09d60865dde0f190cf9aa7755318decb8ed942e212d856b1c98`
both before release work and at stop time.

**Blocker.** The required Azure Validate workflow command was denied before it
could report or perform a validation step. Per the release stop-on-failure
rule, Bicep compilation, the non-mutating subscription provision preview,
proposed-change review, `make release-app`, smoke, hosted Playwright E2E,
report-only Foundry evaluation, and exact-pair Application Insights telemetry
were not run. No PostgreSQL mutation, reconciliation, reset, or other
deployment action was attempted. This is a blocked release, not deployment
evidence.

## 2026-08-13 — Azure Validate access diagnosis and lane-local gate

**Central workflow diagnosis.** The command
`bash /home/praveen/.agents/skills/azure-validate/references/scripts/workflow.sh --workspace-path /home/praveen/projects/poc/maf/maf-monorepo/agents/order-resolution/azure-hosted`
was retried once. The task execution layer denied it before a shell could
start, reporting exactly: `Permission denied and could not request permission
from user`. This is an execution-context restriction on the centrally
installed skill script, not an Azure command or project-script failure.

**Equivalent lane checks.** Azure authentication resolved subscription
`4f18d577-3506-4a11-85e5-a83b14727a84`; the selected existing AZD environment
was `maf-ora-azure` with resource group `rg-maf-ora-azure`. Bicep compilation
and `make release-preflight` passed, including release asset/policy checks,
the credential-free reconciliation guard, and the smoke-retry contract. The
resource-group role review returned `Contributor`.

**Preview blocker.** The guarded non-mutating preview command
`RELEASE_RUN_ID=validation-20260813T152900Z INFRA_RECONCILIATION_PARAMETERS_FILE=infra/azure-apphosted/iac/main.parameters.json make release-infra-preview`
stopped before contacting Azure because its security guard rejected the local
AZD executable: `Infrastructure reconciliation refuses azd: it must be
root-owned and not group/world writable.` No Azure what-if was produced, so
there were no proposed changes to inspect and no PostgreSQL mutation result.
Per stop-on-failure, `make release-app`, smoke, hosted E2E, Foundry evaluation,
and telemetry were not run. No infrastructure or PostgreSQL mutation was
attempted.

**Frozen-input check.** The final required manifest recheck detected a change:
the initial SHA-256 was
`04e56fc79a11e09d60865dde0f190cf9aa7755318decb8ed942e212d856b1c98`,
while the final SHA-256 was
`1a55d84a892275eb8857777d7a2594053c1e7b6aae053ed7eaeefbafdc016e82`.
The manifest was not modified by this release task. This independently blocks
any later deployment from this run.

## 2026-08-13 — Retry blocked by task-context access controls

The requested retry of the central Azure Validate command was again denied
before shell execution with `Permission denied and could not request permission
from user`. The required diagnostic for an alternate trusted AZD binary/path
was also denied by the task execution layer before it could inspect candidates.
Consequently, no system-owned executable was changed, no alternate trusted
environment was identified, and the guarded preview could not be retried.
There was no new Azure validation, preview, deployment, smoke, hosted E2E,
evaluation, or telemetry result.

## 2026-08-13 — IaC preview exposed retained-resource drift

**Local guard adjustment.** With explicit owner authorization for this
single-user workstation, the reconciliation command check now accepts an
executable that is not group- or world-writable without requiring that it be
root-owned. The credential-free mock guards, release-asset checks, smoke-retry
contract, and Bicep compilation passed after this narrow local-tooling change.
The guard still rejects group- or world-writable command targets.

**Preview result.** `azd provision --preview --environment maf-ora-azure
--no-prompt` completed without applying changes. It proposed `Modify` actions
for the two Container Apps, their Container Apps environment, Azure AI
Services and model deployments, Foundry project, ACR, Application Insights,
and the existing PostgreSQL Flexible Server
`maf-ora-azure-pg-puzsry`.

**Issue and disposition.** The project’s app-only release boundary retains the
existing PostgreSQL server/database and does not reconcile shared Foundry,
ACR, monitoring, or Container Apps environment resources. The proposed
PostgreSQL and shared-resource changes are therefore unsafe for this run.
`make release-app`, smoke, hosted E2E, Foundry evaluation, and telemetry were
not run. This is no deployment evidence. Reconciliation remains a separate
owner-reviewed operation with a reviewed what-if and explicit approval.

## 2026-08-13 — App-only release stopped at frontend packaging

**Preflight and release boundary.** Release asset validation, Bicep
compilation, the credential-free reconciliation mock guards, and the
smoke-retry contract passed. The subscription preview was read-only. Its
retained-resource drift remains a reconciliation concern and did not invoke a
provision or apply operation for this app-only release.

**Observed issue.** `make release-app` deployed the backend successfully, but
the frontend Docker build failed before image publication. In the
`node:20.19.0-alpine3.20` build stage, each of the three bounded
`npm ci --include=dev --no-audit` attempts ended with npm's internal `Exit
handler never called` failure. The Dockerfile verified that `tsc` was not
installed and failed explicitly rather than producing an invalid frontend
image.

**Disposition.** The managed-device Docker/npm egress issue remains external
to the application source. The approved Microsoft npm proxy does not contain
the locked Vite/Linux-musl dependencies, so no registry swap, dependency
downgrade, firewall change, or CI authorization workaround was applied. The
frontend was not deployed, and fresh smoke, hosted E2E, Foundry evaluation,
and telemetry were not run. Use the required cloud Docker-E2E app-only
release from a `main` push to build/test/publish the exact frontend image
before attempting another complete hosted-evidence chain.

## 2026-08-13 — Approved npm feed configured for local and Docker installs

**Issue correction.** Direct npm downloads are not permitted on this managed
workstation. The approved Microsoft npm feed
`https://packagefeedproxy.microsoft.io/npm/` is reachable and serves Vite.
The prior assertion that the approved feed could not supply the relevant
frontend dependencies is superseded pending a clean locked-install test.

**Fix.** The frontend now carries a checked-in `.npmrc` that uses only the
approved feed, requires TLS validation, and sets
`replace-registry-host=npmjs` so npm rewrites registry.npmjs.org lockfile
tarball URLs rather than bypassing the feed. Its Dockerfile copies that file
before `npm ci`, making local and container installs follow the same policy.
The Playwright package uses the same policy for local E2E dependencies.

**Release status.** No deployment was started by this configuration change.
The previously deployed backend-only revision remains incomplete release
evidence until the frontend can build and the full smoke, hosted E2E,
evaluation, and telemetry gates are rerun.

## 2026-08-13 — Approved-feed lockfile validation

**Root cause and fix.** The original lockfile pinned artifacts newer than the
approved feed snapshot, including `update-browserslist-db@1.3.0` and
`caniuse-lite@1.0.30001809`. A clean lockfile was regenerated from the
approved feed with no public npm download. It changes nine transitive packages
within their declared ranges: the CopilotKit packages resolve from `1.66.4`
to `1.66.2`, `caniuse-lite` from `1.0.30001809` to `1.0.30001807`, and
`update-browserslist-db` from `1.3.0` to `1.2.3`.

**Feed behavior.** The frontend `.npmrc` uses
`replace-registry-host=npmjs`, not `always`: registry.npmjs.org lockfile URLs
are rewritten to the approved proxy, while the proxy's returned Microsoft
Artifact URLs are preserved rather than incorrectly rewritten a second time.
TLS validation remains required.

**Validation.** A clean `npm ci` and `npm run build` completed in the
`node:20.19.0-alpine3.20` Docker build using only the approved feed. The
validated local image is
`sha256:fb094faf1c6030959c52de6544fc2f4f08eda40ff39874b7ac81715df9afc88d`.
This validation did not deploy resources; fresh release evidence remains
required.

## 2026-08-13 — App-only release completed through approved npm feeds

**Deployment.** The validated app-only release deployed backend revision
`maf-backend-puzsry--azd-1786652208` and frontend revision
`maf-frontend-puzsry--azd-1786652208` to the existing Container Apps. No
infrastructure reconciliation or PostgreSQL operation was performed.

**Fresh gates.** Release `20260813T201627Z-196242` passed smoke, all 7 hosted
workflow Playwright tests, and all 3 frontend integration tests. Report-only
Foundry evaluation `eval_0f534cf971bf4e82b1b16e25ba8f1e6e` /
`evalrun_a7551dccd66e433d934299d84c6029bc` passed 2 of 2 cases with zero
errors or failures.

**Telemetry.** Exact-pair Application Insights validation found 43 telemetry
items for `ORD-1001` workflow `fc24d69b-702a-4919-8d2b-4bb305e5ec98` and 44
for `ORD-1009` workflow `7c428464-d784-45ff-8aa9-4997a48469a2`, with zero
exceptions in each pair. Both frontend and backend endpoints were returned by
AZD as deployed and healthy.
