# MAF Underwriting Agent (Foundry Public)

## Goal

Build a verifiable underwriting workflow that:

- auto-approves low-risk insurance applications,
- surfaces risky applications with transparent score rationale,
- preserves workflow checkpoints and audit history end-to-end.

Primary scenarios include happy path approvals, retryable check failures, and crash/resume recovery from persisted checkpoints.

## Start Here (Self-Serve Onboarding Path)

1. **Product + business intent**
   - PRD: [docs/design/prd.md](docs/design/prd.md)
   - User flow: [docs/design/userflow.md](docs/design/userflow.md)
2. **Architecture + contracts**
   - Architecture: [docs/design/architecture.md](docs/design/architecture.md)
   - Architecture decisions: [docs/design/architecture-decisions.md](docs/design/architecture-decisions.md)
   - API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
3. **Delivery model + release governance**
   - Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
   - Issues / changes / fixes ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
4. **Implementation + repo shape**
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
   - Delivery phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)
5. **Validation + operator guidance**
   - E2E rubric: [docs/design/e2e-rubric.md](docs/design/e2e-rubric.md)
   - Customer Q&A grounding: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)
   - Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## Journey Status

| Stage | Status | Runtime path |
| --- | --- | --- |
| Local MAF | Implemented in repo | Shared MAF workflow under `backend/app/maf/workflows` |
| Public Foundry hosted agent | Implemented in repo | Hosted Responses workflow executor under `backend/foundry/main.py`; it runs MAF and writes durable state |
| Public operations UI/API | Implemented in repo | React UI + FastAPI adapter relays hosted work, projects history/checkpoints, streams AG-UI progress, and embeds CopilotKit |
| Public release evidence | Operator-recorded | Fresh smoke/E2E/eval/telemetry evidence belongs in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md) |

This README describes the supported architecture and release workflow. It does not, by itself, claim a currently live hosted deployment.

## Underwriting Flow

1. Intake creates an underwriting context for one `workflow_run_id`.
2. Parent workflow fans out to four child checks: risk, credit, medical, and driving.
3. Fan-in aggregator merges child results into shared workflow state.
4. Final decision computes approval/review and produces deterministic score components.
5. LLM rationale generation runs only after deterministic decision computation, with fallback available.
6. Checkpoints and events are persisted to PostgreSQL throughout execution.
7. Resume uses latest checkpoint for the run and idempotency prevents duplicate side effects.

## Canonical operating model and clean cutover

Underwriting now follows the same engineering operating model and release governance shape used by Order Resolution while preserving the underwriting-specific workflow design.

- **One business workflow:** fan-out/fan-in underwriting orchestration stays in MAF.
- **Hosted public execution:** `backend/foundry/main.py` remains the public hosted Responses executor.
- **Adapter-only public API:** the FastAPI layer starts/resumes hosted work, serves durable read models, exposes AG-UI, and hosts the CopilotKit bridge.
- **No compatibility shims:** do not add a second orchestration engine, shadow checkpoint store, direct browser-to-Foundry path, or legacy public-lane fallback that bypasses the hosted workflow.
- **Clean cutover rule:** deployed public traffic uses the hosted Responses lane; local execution mode exists only for isolated local validation.
- **Evidence-driven release claims:** fresh hosted smoke, E2E, eval, and telemetry evidence must be recorded in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md) before claiming release readiness.

## Hosted deployment boundary

- **Local full stack** owns browser, FastAPI APIs, AG-UI stream, and isolated MAF validation.
- **Public Foundry hosted lane** executes the agent-specific Responses workflow and owns MAF/PostgreSQL writes.
- **Public UI/API** relays hosted start/resume, reads PostgreSQL run/state/event/checkpoint history, and exposes it to operators.
- **Public browser path** never calls Foundry directly and does not receive Foundry credentials.

The hosted runtime uses a dedicated least-privilege PostgreSQL password over TLS. The password is provisioned and rotated by the checked-in release workflow, injected only into the hosted runtime, and never stored in source, browser configuration, or telemetry.

## Quick Start (Local)

1. Bootstrap local environment and dependencies:

```bash
make install
```

2. Configure environment:

```bash
cp .env.example .env
```

3. Start local services:

```bash
make up
```

4. Open endpoints:

- Frontend: http://localhost:4173
- Backend health: http://localhost:8000/health

## Required validation gates

Run these before considering a change complete:

```bash
make test
make quality
make test-e2e
```

For hosted release validation, run the authenticated lane and then record evidence in the delivery ledger:

```bash
make foundry-smoke
make foundry-eval
```

## Canonical public release workflow

Use the current operator environment and authenticated local secrets, then run the checked-in release sequence:

```bash
make foundry-bootstrap
make foundry-iac-build
make foundry-provision
make foundry-postgres-schema
make foundry-postgres-credentials
make foundry-postgres-readiness
make foundry-deploy
make foundry-backend-deploy
make foundry-frontend-deploy
make foundry-smoke
make foundry-eval
```

Release governance expectations:

1. Run local gates first.
2. Provision and deploy the hosted lane through the checked-in sequence only.
3. Validate happy path, retry, and crash/resume behavior through hosted smoke and browser E2E.
4. Verify Foundry and Application Insights traces correlate on `workflow_run_id`.
5. Record commands, results, run IDs, and any deferrals in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md).

Treat this README as the contract for the workflow, not as a source of truth for current resource names or a declaration that a release already completed.

## Local operations commands

- `make help`: print command catalog.
- `make run`: run happy path underwriting workflow.
- `make run-fail-once`: inject one retryable failure.
- `make run-crash`: crash after `medical_check` (or `CRASH_TARGET=<executor> make run-crash`).
- `make resume RUN_ID=<workflow_run_id>`: resume from latest checkpoint.
- `make state RUN_ID=<workflow_run_id>`: show persisted business state.
- `make events RUN_ID=<workflow_run_id>`: show persisted workflow events.
- `make checkpoints RUN_ID=<workflow_run_id>`: show persisted MAF checkpoints.

## AG-UI and history surface

The backend exposes `POST /api/v1/underwriting/ag-ui` for Agent Framework AG-UI streaming. The UI still relies on persisted run/state/events/checkpoints APIs as the durable source of truth for replay and refresh scenarios.

The embedded CopilotKit assistant discovers `/api/v1/underwriting/copilotkit/info` and calls the named run-assistant route at the configured backend origin. It receives only allowlisted selected-run metadata and does not call Foundry from the browser.

## Documentation Map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- Architecture: [docs/design/architecture.md](docs/design/architecture.md)
- Architecture decisions: [docs/design/architecture-decisions.md](docs/design/architecture-decisions.md)
- API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery and implementation

- Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Issues / changes / fixes ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
- Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
- Implementation phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)

### Validation and operations

- E2E rubric: [docs/design/e2e-rubric.md](docs/design/e2e-rubric.md)
- Customer questions and evidence mapping: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)
- Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
