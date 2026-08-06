# Manual testing guide

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node 20+

## Setup

1. `make install`
2. `make up`
3. `make db-reset`
4. `make frontend-install`

## Backend scenarios (CLI)

1. Happy path: `make run`
2. Retry: `make run-fail-once`
3. Crash: `make run-crash`
4. Resume: `make resume RUN_ID=<run_id>`
5. Inspect:
   - `make state RUN_ID=<run_id>`
   - `make events RUN_ID=<run_id>`
   - `make checkpoints RUN_ID=<run_id>`

Confirm that retry emits bounded retry evidence, crash leaves a resumable `workflow_run_id`, and resume completes without duplicate terminal writes.

## Frontend scenario

1. Start backend/API: `make up`
2. Start UI: `make frontend-dev`
3. Open the Vite URL and execute:
   - happy path
   - retry
   - crash + resume
4. Confirm run status, state, event, and checkpoint panels update correctly.
5. Confirm the embedded CopilotKit assistant explains only allowlisted selected-run data.

`make test-e2e` sets `UNDERWRITING_EXECUTION_MODE=local` only for its isolated workflow validation; the deployed public adapter remains hosted-only.

## Automated validation

- Backend tests: `make test-backend`
- Frontend build check: `make test-frontend`
- E2E rubric: `make test-e2e`

## Public release smoke

1. Run the checked-in authenticated release sequence from the README.
2. Start a happy-path transaction from the public operations console.
3. Confirm the selected run reaches `COMPLETED`, its timeline is chronological, and history shows it newest first in browser-local time.
4. Run retry and crash/resume scenarios and confirm they correlate on one durable `workflow_run_id` each.
5. Ask the embedded assistant for the selected run's status and confirm it returns only a safe execution summary.
6. In Application Insights, start from the run ID and confirm the AG-UI request plus hosted workflow/model spans are visible.
7. In Foundry, confirm the corresponding `underwriting-hosted` workflow/model trace includes MAF parent/child execution, retry/fan-in/checkpoint spans, and the correlated `workflow_run_id`.
8. Record commands, run IDs, trace references, and any deferrals in `docs/design/issues-changes-fixes.md`.

## Clean cutover / no-shims checks

During public validation, confirm all of the following remain true:

- browser traffic goes to the public adapter only;
- the public adapter starts or resumes hosted Responses work;
- PostgreSQL remains the source of truth for checkpoints, events, and state;
- no test relies on a hidden adapter-side fallback workflow path;
- no browser-visible credential or direct Foundry endpoint is introduced.
