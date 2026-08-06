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
2. The public adapter starts or resumes the hosted Responses workflow; it does not run a second production orchestration path.
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
- Public backend revision
  `azcawhcedyxchnbtmpubbe--0000019` and frontend revision
  `azcawhcedyxchnbtmpubfe--0000010` are running.
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
- Hosted agent v41, backend revision
  `azcawhcedyxchnbtmpubbe--0000020`, and frontend revision
  `azcawhcedyxchnbtmpubfe--0000011` deployed successfully.
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
