# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the underwriting public Foundry lane.
Business intent and workflow shape come from the underwriting design docs.
Implementation changes, release validation, and readiness claims must follow this operating model.

## Runtime policy

This branch has three supported execution surfaces:

1. **Local full stack:** React, FastAPI, AG-UI, and PostgreSQL run through Docker or Make targets. This is the authoritative local validation surface.
2. **Public Foundry hosted agent:** `backend/foundry/main.py` exposes the underwriting workflow through the Responses protocol and owns production workflow execution.
3. **Public UI/internal API wrapper:** external Nginx serves React and proxies
   same-origin `/api` traffic to the internal FastAPI Container App, which
   starts or resumes hosted work, serves durable projections, exposes AG-UI,
   and hosts the CopilotKit bridge.

Concrete resource identifiers belong to the active operator environment and the delivery ledger, not this contract.

## Clean cutover policy

Underwriting owns its release governance without changing the underwriting workflow semantics or depending on another agent's assets.

- Keep **one MAF underwriting workflow** with risk, credit, medical, and driving fan-out plus deterministic fan-in/final decision.
- Keep **PostgreSQL** as the durable source of truth for checkpoints, events, state, and final results.
- Keep **hosted Responses** as the production orchestration entrypoint.
- Keep **AG-UI** and **CopilotKit** as internal backend adapter surfaces exposed
  only through the external frontend's same-origin proxy and backed by durable
  projections.
- Use **local execution mode only for isolated local validation**.
- Do **not** add shims such as a second public-lane orchestration engine, a shadow checkpoint mechanism, or direct browser-to-Foundry calls.

## Non-negotiable contracts

- One underwriting business workflow. The hosted lane may not bypass MAF orchestration.
- Deterministic scoring remains authoritative; model rationale can explain the result but not change the policy outcome.
- Master-workflow direct-executor fan-out/fan-in behavior remains explicit and resumable only from checkpoints written by the deployed graph. Version-40 nested-graph checkpoints are unsupported after deployment; no compatibility workflow or fallback exists.
- `maf_checkpoints` remains the authoritative checkpoint backend for resume.
- Retry/backoff applies to transient read/model operations; side-effecting writes must remain idempotent.
- Resume is keyed by `workflow_run_id` and must not duplicate business writes.
- Hosted execution remains Responses-native through `backend/foundry/main.py`.
- The browser never receives a Foundry or PostgreSQL credential and never calls Foundry directly.
- The browser never calls a public backend FQDN; production API and backend
  health requests remain on the frontend origin.
- Production runtime schema is administrator-owned.
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` permits startup validation only, never
  runtime DDL.
- The hosted database URL is owned by the Underwriting project
  `CustomKeys` connection. Agent versions contain only a
  `connections.<name>.credentials.database_url` placeholder; verification must
  not retrieve the resolved secret from hosted-agent metadata.
- Stable browser-facing surfaces remain `POST /api/v1/underwriting/runs`, `POST /api/v1/underwriting/runs/{run_id}/resume`, the durable read-model routes, `POST /api/v1/underwriting/ag-ui`, and the CopilotKit discovery/run routes.
- Release readiness is claimed only from fresh evidence recorded in `docs/design/issues-changes-fixes.md`.

## Delivery and validation

| Change | Required local gates | Required hosted/public evidence |
| --- | --- | --- |
| Documentation only | Link and command accuracy checks | Update the delivery ledger when operator steps or release expectations change |
| Application behavior | `make test`, `make quality`, `make test-e2e` | None unless the hosted path or internal backend adapter behavior changed |
| Workflow, retry, persistence, crash/resume | Local gates plus targeted `make run`, `make run-fail-once`, `make run-crash`, `make resume` verification as needed | Hosted smoke covering the same scenario class when release behavior changed |
| Foundry/runtime/release workflow | Local gates plus checked-in script review | `make foundry-smoke`, `make foundry-eval`, and telemetry correlation evidence |

## Canonical release workflow

Run local gates first, then use the checked-in authenticated release
orchestrator:

```bash
make foundry-release
```

Release workflow rules:

1. Use current operator environment values and local authenticated secrets.
2. Run the selected validation target and Bicep build concurrently; after one
   database/model readiness gate, runtime-secret connection convergence, and
   package step, deploy the hosted agent and persist its active name, version,
   and Responses endpoint. Only then deploy the internal backend and external
   frontend concurrently. Routine release is app-only; bootstrap provisioning
   is a distinct prior operation.
3. Run hosted smoke before the Foundry evaluation and deployed browser E2E
   gates, which run concurrently; start telemetry validation after E2E writes
   its evidence.
4. Run `foundry-verify` and aggregate the release-window evidence; do not claim
   readiness from partial command success.
5. Record the exact commands, outcomes, `workflow_run_id` values, evaluation
   IDs, and deferrals in the delivery ledger.
6. If a clean cutover problem is found, fix the hosted path or adapter boundary; do not paper over it with compatibility shims.

## Environment bootstrap and reuse

Infrastructure is one parameterized source of truth, not a per-subscription
fork. `infra/foundry-hosted/iac/main.bicep` supports two explicit modes:

- **bootstrap** creates this lane's Foundry account/project and managed
  `gpt-4.1-mini` deployment, ACR, monitoring, Container Apps, managed
  identities, PostgreSQL, evaluation storage, connections, and role
  assignments;
- **reuse** references an existing environment and creates no resources or
  role assignments.

Bootstrap starts from a non-secret target profile followed by
`make foundry-bootstrap-env`, followed by the validated provisioning workflow.
No separate manual approval gate exists: invoking that workflow is the
execution trigger. Provisioning only establishes infrastructure; the runtime
database credential and schema are explicit subsequent steps. Routine `make
foundry-release` remains app-only in both modes and rejects deploy-mode
overrides.

## Evidence handoff

For every deployment-impacting or operating-model change, record in `docs/design/issues-changes-fixes.md`:

- change date and summary;
- files or surfaces changed;
- local gate results;
- hosted smoke/E2E scenario coverage and run identifiers;
- Foundry evaluation IDs and outcome counts;
- Application Insights / Foundry trace evidence;
- open issues, fixes, and explicit deferrals.

The ignored `deployment-report/` directory may retain local timing observations,
but it is not release evidence.

## Baseline scenarios

- **Happy path:** low-risk application completes with a deterministic result and rationale.
- **Retry path:** one injected retryable check failure records retry evidence and completes once.
- **Crash/resume path:** a controlled crash resumes from the latest PostgreSQL-backed MAF checkpoint and completes without duplicate writes.
