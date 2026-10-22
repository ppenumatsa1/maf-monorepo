# Tech Stack

## Application

- Python, FastAPI, Uvicorn, and Pydantic v2
- Microsoft Agent Framework (MAF) workflow runtime
- React, Vite, and TypeScript
- CopilotKit React core for the optional redacted selected-thread UI (not the
  GitHub Copilot SDK); its inspector is disabled
- PostgreSQL with Psycopg for durable workflow state
- MCP over streamable HTTP for optional integration
- OpenTelemetry and Application Insights

## Azure target

- Azure Container Apps for the frontend and FastAPI application
- Azure Container Registry, Log Analytics, and Application Insights
- Azure Database for PostgreSQL Flexible Server with managed-identity Entra
  authentication
- Foundry model deployments for inference and report-only evaluation only
- Runtime frontend configuration injected by Nginx (`API_BASE`, `AG_UI_URL`,
  `COPILOTKIT_URL`)

## Skills

Use task-specific repository skills. `agent-framework-foundry-py` covers the
model client and MAF workflow integration; `azure-ai-projects-py` covers model
deployments and evaluations. Neither authorizes a Foundry application host.

Release images retain the approved CFS Python package feed. The frontend
Docker build/runtime is Alpine-based, so native dependencies must remain
musl-compatible.
