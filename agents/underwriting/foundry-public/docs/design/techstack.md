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

## Agent UI and CopilotKit Surface

- AG-UI protocol endpoint: `POST /api/v1/underwriting/ag-ui`
- Backend emits AG-UI-compatible event stream envelopes for underwriting run lifecycle updates.
- CopilotKit uses the public adapter's REST runtime discovery and assistant
  route. It receives a safe selected-run projection only.

## Testing

- Pytest (backend)
- Playwright (frontend E2E rubric)

## Local Runtime

- Docker Compose for PostgreSQL + backend + frontend containers
- Makefile as the primary developer command surface

## Public Runtime Integration

- Azure AI Foundry hosted Responses entrypoint that executes the MAF workflow
- Azure Container Apps for backend/frontend runtime hosting
- Azure Database for PostgreSQL over TLS with a dedicated least-privilege
  password credential injected only into the hosted runtime
- Application Insights telemetry via connection-string configuration
- Foundry User project-scope role for the public backend's user-assigned identity

The public backend relays hosted start/resume requests and reads durable
projections. The Foundry hosted agent is the production MAF executor.
