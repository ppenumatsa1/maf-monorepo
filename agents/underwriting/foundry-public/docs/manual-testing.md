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

## Frontend scenario

1. Start backend/API: `make up`
2. Start UI: `make frontend-dev`
3. Open Vite URL and execute:
   - happy path
   - retry
   - crash + resume
4. Confirm run status, state, event, and checkpoint panels update correctly.
   `make test-e2e` sets `UNDERWRITING_EXECUTION_MODE=local` only for its
   isolated workflow validation; deployed adapters remain hosted-only.

## Automated validation

- Backend tests: `make test-backend`
- Frontend build check: `make test-frontend`
- E2E rubric: `make test-e2e`

## Public release smoke

1. Run resource-reuse IaC and deploy the hosted agent, public backend, and
   frontend through the `make foundry-*` release sequence in the README.
2. Start a happy-path transaction from the public operations console.
3. Confirm the selected run reaches `COMPLETED`, its timeline is chronological,
   and history shows it newest first in browser-local time. Ask the embedded
   assistant for the selected run's status and confirm it returns only a safe
   execution summary.
4. In Application Insights, find the successful
   `HTTP POST /api/v1/underwriting/ag-ui` **Request** and then query all
   telemetry by its `workflow.run_id`. Health, CORS preflight, and polling
   GETs must not appear as application-created Request telemetry.
5. In Foundry, confirm the corresponding `underwriting-hosted` workflow/model
   trace includes MAF parent/child execution, retry/fan-in/checkpoint spans,
   and the correlated `workflow_run_id`. It must not capture message content,
   credentials, or raw checkpoint data.

The hosted agent is the production durable executor. The public backend is a
browser-facing adapter and durable-read projection boundary.
