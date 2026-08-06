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
   - API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
3. **Implementation + repo shape**
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
   - Delivery phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)
4. **Validation and operation**
   - E2E rubric: [docs/design/e2e-rubric.md](docs/design/e2e-rubric.md)
   - Customer Q&A grounding: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)
   - Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## Journey Status

| Stage | Status | Runtime path |
| --- | --- | --- |
| Local MAF | Implemented | Shared MAF workflow under `backend/app/maf/workflows` |
| Public Foundry hosted agent | Implemented | Hosted Responses workflow executor under `backend/foundry/main.py`; it runs MAF and writes durable state |
| Public operations UI/API | Implemented | React UI + FastAPI adapter relays hosted work, projects history/checkpoints, streams AG-UI progress, and embeds CopilotKit |

## Underwriting Flow

1. Intake creates an underwriting context for one `workflow_run_id`.
2. Parent workflow fans out to four child checks: risk, credit, medical, and driving.
3. Fan-in aggregator merges child results into shared workflow state.
4. Final decision computes approval/review and produces deterministic score components.
5. LLM rationale generation runs only after deterministic decision computation, with fallback available.
6. Checkpoints and events are persisted to PostgreSQL throughout execution.
7. Resume uses latest checkpoint for the run and idempotency prevents duplicate side effects.

## Hosted Deployment Boundary

- **Local full stack** owns browser, FastAPI APIs, AG-UI stream, and isolated MAF validation.
- **Public Foundry hosted lane** executes the agent-specific Responses workflow and owns MAF/PostgreSQL writes.
- **Public UI/API** relays hosted start/resume, reads PostgreSQL run/state/event/checkpoint history, and exposes it to operators.
- **Public browser path** never calls Foundry directly and does not receive Foundry credentials.

The hosted runtime uses a dedicated least-privilege PostgreSQL password over
TLS. The password is provisioned and rotated by the checked-in release script,
injected only into the hosted runtime, and never stored in Bicep, source,
browser configuration, or telemetry. Bicep keeps password authentication
enabled and limits the public firewall rule to the Azure-services exception.

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

## Required Validation Gates

Run these before considering a change complete:

```bash
make test
make quality
make test-e2e
```

For hosted release validation:

```bash
make foundry-smoke
make foundry-eval
```

## Foundry Public Deployment (Resource Reuse Lane)

This lane reuses the existing underwriting Azure environment and deploys updated workloads into that boundary.

| Resource | Name |
| --- | --- |
| Resource group | `rg-underwriting-readiness-0731` |
| Foundry account/project | `azfdwhcedyxchnbtm` / `azprwhcedyxchnbtm` |
| ACR | `azcrwhcedyxchnbtm` |
| PostgreSQL | `azpgwhcedyxchnbtmpub` |
| Application Insights | `azaiwhcedyxchnbtm` |

Authenticated release sequence:

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

`make foundry-eval` follows the same report-only Foundry trace-evaluation
pattern used by Order Resolution: it evaluates the safe hosted conversations
recorded by smoke/E2E after trace materialization. `make foundry-trace-eval`
remains an alias. `make foundry-native-eval` is retained only to diagnose the
separate native `azd` suite-generation path, which requires evaluation storage
network access not permitted by the current organization policy.

The provisioning step is resource-reuse Bicep for the surrounding Foundry
resources and a normal declarative PostgreSQL server resource. It continuously
enforces the approved PostgreSQL creation, authentication, and firewall
posture rather than creating a parallel stack. Provide the runtime password
only through the local authenticated release environment when running
`make foundry-postgres-credentials`. Before `make foundry-provision`, set the
administrator password as the local azd secret `POSTGRES_ADMIN_PASSWORD`; it
is an ARM secure parameter and is never written to source or deployment
output.

### Deliberate PostgreSQL rebuild

`azpgwhcedyxchnbtmpub` and its `underwriting` database can be rebuilt only
when a full server reset is intended. Bicep declares the discovered creation
settings (North Central US, PostgreSQL 17, `Standard_D2ds_v5` General Purpose,
128 GiB storage, seven-day retention, and geo-redundant backup disabled), so
the original server name and configuration are restored declaratively.

This is destructive: it permanently deletes the server and all databases.
After `make foundry-bootstrap` has selected the local azd environment,
explicitly opt in with the exact token:

```bash
make foundry-postgres-rebuild CONFIRM=REBUILD-azpgwhcedyxchnbtmpub
```

The versioned script accepts no alternative subscription, resource group, or
server name. It verifies the fixed subscription, deletes only that server,
writes a newly generated administrator password only to the selected local
azd environment when one is not already present, waits for deletion, and then
invokes `make foundry-provision`. It intentionally does not create the
least-privilege runtime credential; run
`make foundry-postgres-schema`, `make foundry-postgres-credentials`, and
`make foundry-postgres-readiness` after the rebuild. The credential step
reruns the idempotent schema bootstrap to protect direct use of that command.
The provisioning bootstrap discovers the release machine's public IPv4 address
and Bicep maintains it as the single-address `allow-release-operator` rule.
That narrow rule permits only release-time TLS `psql` schema and credential
operations; it does not expose the server to a public IP range.
The public backend receives the same runtime URL through its Container Apps
secret `runtime-db-url`; deployment explicitly overrides the former
managed-identity database settings with password authentication.

### Release evidence

Hosted agent version `38` executes the real MAF workflow using the
credential-backed PostgreSQL runtime. Version-pinned smoke, deployed UI E2E,
trace evaluation, and Application Insights workflow-span evidence are recorded
in [`../issues-fixes.md`](../issues-fixes.md). The native generated-suite path
remains a non-release diagnostic because the evaluation-storage network policy
blocks it; it does not affect the supported trace-evaluation release gate.

## Local Operations Commands

- `make help`: print command catalog.
- `make run`: run happy path underwriting workflow.
- `make run-fail-once`: inject one retryable failure.
- `make run-crash`: crash after `medical_check` (or `CRASH_TARGET=<executor> make run-crash`).
- `make resume RUN_ID=<workflow_run_id>`: resume from latest checkpoint.
- `make state RUN_ID=<workflow_run_id>`: show persisted business state.
- `make events RUN_ID=<workflow_run_id>`: show persisted workflow events.
- `make checkpoints RUN_ID=<workflow_run_id>`: show persisted MAF checkpoints.

## AG-UI and History Surface

The backend exposes `POST /api/v1/underwriting/ag-ui` for Agent Framework AG-UI streaming. The UI still relies on persisted run/state/events/checkpoints APIs as the durable source of truth for replay and refresh scenarios.

The embedded CopilotKit assistant discovers
`/api/v1/underwriting/copilotkit/info` and calls the named run-assistant route
at the configured backend origin. It receives only allowlisted selected-run
metadata and does not call Foundry from the browser.

## Documentation Map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- Architecture: [docs/design/architecture.md](docs/design/architecture.md)
- API/event/telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery and implementation

- Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
- Implementation phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)

### Validation and operations

- E2E rubric: [docs/design/e2e-rubric.md](docs/design/e2e-rubric.md)
- Customer questions and evidence mapping: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)
- Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
