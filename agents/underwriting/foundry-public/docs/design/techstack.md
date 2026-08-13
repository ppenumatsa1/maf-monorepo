# Tech Stack

## Backend

- Python 3.11+
- FastAPI + Uvicorn
- Microsoft Agent Framework Python SDK
- Agent Framework AG-UI integration (`agent-framework-ag-ui`)
- SQLAlchemy + psycopg (PostgreSQL)
- OpenTelemetry SDK (console exporter in local mode)
- Azure Monitor OpenTelemetry exporter for Application Insights
- OpenTelemetry OpenAI v2 instrumentation for safe model metadata

## Frontend

- React 19
- Vite
- TypeScript
- Fetch-based API client for run/history/read-model routes
- SSE consumption for AG-UI stream events
- `@copilotkit/react-core` for the embedded selected-run assistant

## Agent UI and CopilotKit surface

- AG-UI protocol endpoint: `POST /api/v1/underwriting/ag-ui`
- Backend emits AG-UI-compatible event stream envelopes for underwriting run lifecycle updates.
- CopilotKit uses the public adapter's REST runtime discovery and assistant route. It receives a safe selected-run projection only.

## Testing and validation

- Pytest (backend)
- Playwright (frontend E2E rubric)
- Makefile as the primary developer and release command surface
- Hosted validation targets such as `make foundry-smoke` and `make foundry-eval`
- Selectively vendored Microsoft catalog skills: `microsoft-foundry` and
  `agent-framework-azure-ai-py`; the exact source revision and refresh policy
  are recorded in [`.github/skills/README.md`](../../.github/skills/README.md).

## Local runtime

- Docker Compose for PostgreSQL + backend + frontend containers
- Local CLI commands for happy path, retry, crash, resume, and durable-state inspection

## Public runtime integration

- Azure AI Foundry hosted Responses entrypoint that executes the MAF workflow
- Azure Container Apps for backend/frontend runtime hosting
- Azure Database for PostgreSQL over TLS with a dedicated least-privilege password credential injected only into the hosted runtime
- Application Insights telemetry via connection-string configuration

The public backend relays hosted start/resume requests and reads durable projections. The Foundry hosted agent is the production MAF executor.

## Release governance surfaces

- `docs/design/engineering-operating-model.md` defines the canonical release workflow.
- `docs/design/issues-changes-fixes.md` is the evidence ledger for hosted readiness claims.
- Local validation and authenticated hosted release remain separate concerns: local gates prove code behavior, while hosted smoke/eval/telemetry prove the clean public cutover.
