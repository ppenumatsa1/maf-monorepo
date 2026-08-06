# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the underwriting public Foundry lane.
Business intent and workflow shape come from the underwriting design docs.
Implementation changes, release validation, and readiness claims must follow this operating model.

## Runtime policy

This branch has three supported execution surfaces:

1. **Local full stack:** React, FastAPI, AG-UI, and PostgreSQL run through Docker or Make targets. This is the authoritative local validation surface.
2. **Public Foundry hosted agent:** `backend/foundry/main.py` exposes the underwriting workflow through the Responses protocol and owns production workflow execution.
3. **Public UI/API wrapper:** the browser-facing API starts or resumes hosted work, serves durable projections from PostgreSQL, exposes AG-UI, and hosts the CopilotKit bridge.

Concrete resource identifiers belong to the active operator environment and the delivery ledger, not this contract.

## Clean cutover policy

Underwriting adopts Order Resolution's release governance without changing the underwriting workflow semantics.

- Keep **one MAF underwriting workflow** with risk, credit, medical, and driving fan-out plus deterministic fan-in/final decision.
- Keep **PostgreSQL** as the durable source of truth for checkpoints, events, state, and final results.
- Keep **hosted Responses** as the production orchestration entrypoint.
- Keep **AG-UI** and **CopilotKit** as public adapter surfaces backed by durable projections.
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
- Stable browser-facing surfaces remain `POST /api/v1/underwriting/runs`, `POST /api/v1/underwriting/runs/{run_id}/resume`, the durable read-model routes, `POST /api/v1/underwriting/ag-ui`, and the CopilotKit discovery/run routes.
- Release readiness is claimed only from fresh evidence recorded in `docs/design/issues-changes-fixes.md`.

## Delivery and validation

| Change | Required local gates | Required hosted/public evidence |
| --- | --- | --- |
| Documentation only | Link and command accuracy checks | Update the delivery ledger when operator steps or release expectations change |
| Application behavior | `make test`, `make quality`, `make test-e2e` | None unless the hosted path or public adapter behavior changed |
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
2. Run the selected validation target and Bicep build concurrently; after
   shared readiness, deploy the backend, frontend, and hosted agent
   concurrently. The deployment router selects full provisioning or app-only
   deployment.
3. Run hosted smoke before the Foundry evaluation and deployed browser E2E
   gates, which run concurrently; start telemetry validation after E2E writes
   its evidence.
4. Do not claim readiness from partial command success.
5. Record the exact commands, outcomes, `workflow_run_id` values, evaluation
   IDs, and deferrals in the delivery ledger.
6. If a clean cutover problem is found, fix the hosted path or adapter boundary; do not paper over it with compatibility shims.

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
