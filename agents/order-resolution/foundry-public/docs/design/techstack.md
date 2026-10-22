# Tech Stack

## Backend

- Python 3.13 for both API and hosted-agent containers
- Hash-locked runtime graph in `backend/requirements.lock`, with offline
  CPython 3.13 Linux AMD64 wheelhouse installation in both images
- FastAPI 0.156.3 + Uvicorn 0.54
- Pydantic 2.14
- Agent Framework Core 1.22, Orchestrations 1.3, and Foundry 1.15
- Azure AI AgentServer Responses 2.3 and Activity 1.0 beta adapters
- Azure AI Projects 2.7 and Azure Identity 1.26
- Psycopg 3.3 and Psycopg Pool 3.3
- Azure Monitor OpenTelemetry 1.8 and Azure Monitor Query 2.0

## Frontend

- React/React DOM 19.3
- Vite 8.3
- CopilotKit 1.79 and Zod 4.6
- Playwright 1.64 and ESLint 10.12
- TypeScript 7 executable with a TypeScript 6 compiler API alias for
  `typescript-eslint`

## Data and Durability

- PostgreSQL as the durable source of truth for workflow runs, events, conversation messages, checkpoints, approvals, sessions, and eval records
- Psycopg v3 + connection pooling for backend persistence access
- Administrator-owned schema DDL, externally managed production schema
  validation, DML/sequence-only runtime grants, and hosted pool defaults
  `0/2/30` (minimum/maximum/idle seconds)

## Integration

- MCP via streamable HTTP endpoint (`MCP_SERVER_URL`)
- OTEL exporters configurable by environment variables
- Public Azure: Foundry Responses, Container Apps, managed identity, PostgreSQL
  Flexible Server, and Application Insights
- Additive Foundry Activity hosting, Azure Bot Service, `MsTeamsChannel`,
  Adaptive Cards, and Shared Microsoft 365 publication automation
- App Insights enabled through `APPLICATIONINSIGHTS_CONNECTION_STRING`; FastAPI
  health and SSE request spans are excluded to keep workflow telemetry visible
- AG-UI-compatible selected-thread SSE and CopilotKit are redacted durable-event
  projections; they do not receive MCP/RAG content, order/policy payloads, raw
  model output, or credentials

This is the checked-in source baseline, not a live-deployment statement.

## Skills Baseline

Use only the task-specific skills below; do not load the full Microsoft skills catalog.
The curated baseline contains six vendored Microsoft skills and two local
(repository-owned) skills.

| Skill | Use for | Source |
|---|---|---|
| `agent-framework-foundry-py` | This service's `FoundryChatClient`, `SequentialBuilder`, middleware, streamed telemetry, and checkpoint-backed HITL work | Repository-owned |
| `azure-ai-projects-py` | Azure AI Foundry project, deployment, and evaluation work | Microsoft `skills` |
| `azure-identity-py` | `DefaultAzureCredential`, managed identity, and Entra authentication | Microsoft `skills` |
| `azure-monitor-opentelemetry-py` | Application Insights and Azure Monitor OpenTelemetry work | Microsoft `skills` |
| `fastapi-router-py` | FastAPI HTTP route work | Microsoft `skills` |
| `microsoft-foundry` | Foundry hosted-agent lifecycle, safe invocation, evaluation, trace analysis, and troubleshooting | Microsoft `skills` |
| `pydantic-models-py` | Pydantic v2 API contract work | Microsoft `skills` |
| `postgres-psycopg-py` | PostgreSQL, Psycopg, and Azure PostgreSQL workflow-audit persistence | Repository-owned |

The original five Microsoft skills are vendored from
[`microsoft/skills`](https://github.com/microsoft/skills) commit
`c33193b1b2dd14d5946e3c6213fd095ffa5b31df`. Refresh them deliberately from that
source, preserving each complete skill directory and reviewing upstream changes before updating
the pinned revision. `microsoft-foundry` is selectively vendored as its complete
`.github/plugins/azure-skills/skills/microsoft-foundry` directory from the same
catalog at revision `e58528db9a006528a5fb0a2c029790fa6a9a7c0e`; no other catalog
skills are installed by that addition.

`agent-framework-foundry-py` and `postgres-psycopg-py` are repository-owned because
they encode this application's workflow and persistence boundaries. The MAF skill is
grounded in current Microsoft Learn Agent Framework guidance and the installed
`agent-framework-foundry` package; it intentionally does not target
`agent-framework-azure-ai` or `AzureAIAgentsProvider`.
