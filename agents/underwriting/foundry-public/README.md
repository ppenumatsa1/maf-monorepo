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
   - Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
   - Deployment profiles and migration entry points: [deployment/README.md](deployment/README.md)
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
2. One master underwriting workflow fans out directly to risk, credit, medical, and driving executors in one superstep.
3. Fan-in aggregator merges the direct-executor results into shared workflow state.
4. Final decision computes approval/review and produces deterministic score components.
5. LLM rationale generation runs only after deterministic decision computation, with fallback available.
6. Checkpoints and events are persisted to PostgreSQL throughout execution.
7. Resume uses a checkpoint created by the deployed master direct-executor graph; idempotency prevents duplicate side effects.

## Canonical operating model and clean cutover

Underwriting owns an independent engineering and release contract while preserving the underwriting-specific workflow design.

- **One business workflow:** fan-out/fan-in underwriting orchestration stays in MAF.
- **Hosted public execution:** `backend/foundry/main.py` remains the public hosted Responses executor.
- **Same-origin public edge:** the external frontend Nginx container proxies
  `/api` and `/backend-health` to the internal FastAPI Container App.
- **Adapter-only internal API:** FastAPI starts/resumes hosted work, serves durable read models, exposes AG-UI, and hosts the CopilotKit bridge.
- **No compatibility shims:** do not add a second orchestration engine, shadow checkpoint store, direct browser-to-Foundry path, or legacy public-lane fallback that bypasses the hosted workflow.
- **Clean cutover rule:** deployed public traffic uses the hosted Responses lane; local execution mode exists only for isolated local validation.
- **Checkpoint migration rule:** version-40 nested-graph checkpoints are unsupported for resume after this deployment. There is no compatibility workflow or fallback; start a new run if a pre-cutover checkpoint must be retried.
- **Evidence-driven release claims:** fresh hosted smoke, E2E, eval, and telemetry evidence must be recorded in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md) before claiming release readiness.

## Hosted deployment boundary

- **Local full stack** owns browser, FastAPI APIs, AG-UI stream, and isolated MAF validation.
- **Public Foundry hosted lane** executes the agent-specific Responses workflow and owns MAF/PostgreSQL writes.
- **Public UI/internal API** uses an Underwriting-owned same-origin Nginx proxy;
  the backend has internal ACA ingress and is not directly internet reachable.
- **Public browser path** never calls Foundry directly and does not receive Foundry credentials.

The hosted runtime uses a dedicated least-privilege PostgreSQL password over
TLS. After credential provisioning, the release workflow converges the
Underwriting-owned `underwritingruntimesecrets` Foundry project `CustomKeys`
connection. Hosted agent metadata stores only
`${{connections.underwritingruntimesecrets.credentials.database_url}}`; the
resolved URL is never stored in `HostedAgentDefinition`, source, browser
configuration, or telemetry.
Production runtime sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`: startup validates
the required tables, columns, and indexes but performs no DDL.

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
make foundry-package
make foundry-smoke
make foundry-eval
make foundry-verify
make foundry-evidence
```

## Canonical public release workflow

The checked-in target contract is subscription
`7df95e88-701c-4693-af77-3159f83b558d`, resource group
`rg-maf-underwriting`, location `eastus2`.

Use the current operator environment and authenticated local secrets, then run
the checked-in release orchestrator:

```bash
make foundry-release
```

Release governance expectations:

1. Run local gates first.
2. The release orchestrator runs validation and the Bicep build concurrently,
   then runs one shared database/model readiness gate, converges the runtime
   connection, and packages all services. It deploys the hosted agent first and
   persists its active metadata before deploying backend and frontend
   concurrently. Bootstrap provisioning is separate; routine releases are
   always `app_only`, and `FOUNDRY_DEPLOY_MODE` is rejected.
3. It runs hosted smoke, then Foundry evaluation and deployed browser E2E in
   parallel, then validates Application Insights telemetry after E2E writes
   its evidence.
4. It verifies ACA revisions/images, external-frontend/internal-backend
   topology, same-origin health/API, hosted version/image, Application Insights,
   and external-schema mode, then aggregates secret-free JSON evidence.
5. Record commands, results, run IDs, and any deferrals in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md).

Invoking a validated bootstrap or release workflow is the execution trigger;
there is no additional manual approval checkpoint.

`deployment-report/` is ignored local timing evidence only. It does not prove
release readiness; the delivery ledger is the canonical release-evidence record.

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

The embedded CopilotKit assistant discovers `/api/v1/underwriting/copilotkit/info` and calls the named run-assistant route on the frontend origin. Nginx proxies it to the internal backend. It receives only allowlisted selected-run metadata and does not call Foundry from the browser.

## Documentation Map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- Architecture: [docs/design/architecture.md](docs/design/architecture.md)
- Architecture decisions: [docs/design/architecture-decisions.md](docs/design/architecture-decisions.md)
- API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery and implementation

- Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
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
