# Delivery Evidence

## Current status

**Source implementation synchronized; no current deployment validation
claimed.** Historical entries below explain prior work but do not prove a
currently live endpoint or revision. Current deployed evidence belongs in the
dated ledger in `.azure/deployment-plan.md` only after its commands complete.

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
