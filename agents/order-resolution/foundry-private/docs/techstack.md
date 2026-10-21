# Tech Stack

## Backend

- Python 3.13 backend and hosted-agent images
- FastAPI 0.156.3 + Uvicorn 0.54.0
- Pydantic 2.14.1
- Agent Framework Core 1.22.0
- Agent Framework Orchestrations 1.3.2
- Agent Framework Foundry 1.15.0
- Azure AI Projects 2.7.0, intentionally capped below 2.8 by Agent Framework
- httpx for MCP HTTP tool calls
- OpenTelemetry SDK + OTLP exporter

## Frontend

- React and React DOM 19.3.0
- Vite 8.3.4
- TypeScript 7.0.2 for `tsc`; `@typescript/typescript6` 6.0.2 supplies the
  compiler API required by `typescript-eslint` 8.71.2
- Zod 4.6.7
- `@copilotkit/react-core` 1.79.0 for the implemented optional read-only
  AG-UI/CopilotKit view; this is not the GitHub Copilot SDK.

## Data and Durability

- PostgreSQL as the durable source of truth for workflow runs, events, conversation messages, checkpoints, approvals, sessions, and eval records
- Psycopg v3 + connection pooling for backend persistence access

## Integration

- MCP via streamable HTTP endpoint (`MCP_SERVER_URL`)
- OTEL exporters configurable by environment variables
- App Insights enabled by setting OTLP endpoint to Azure Monitor/OpenTelemetry collector
- Private lane: external frontend Container App, same-origin proxy, internal
  FastAPI wrapper, managed-identity private Foundry Responses, private
  PostgreSQL, and VNet/private DNS boundaries
- Approved AG-UI/CopilotKit projections are allowlisted durable-event views.
  They must not receive order/customer or policy data, MCP/RAG content, tool
  arguments/results, prompts, raw model output, reviewer comments, checkpoint
  payloads, credentials, or secrets.

## Skills Baseline

Use only the task-specific skills below; do not load the full Microsoft skills
catalog. The curated baseline combines vendored Microsoft skills with
repository-owned workflow, privacy, and frontend-boundary skills.

| Skill | Use for | Source |
|---|---|---|
| `agent-framework-foundry-py` | This service's `FoundryChatClient`, `SequentialBuilder`, middleware, streamed telemetry, and checkpoint-backed HITL work | Repository-owned |
| `azure-ai-projects-py` | Azure AI Foundry project, deployment, and evaluation work | Microsoft `skills` |
| `azure-identity-py` | `DefaultAzureCredential`, managed identity, and Entra authentication | Microsoft `skills` |
| `azure-monitor-opentelemetry-py` | Application Insights and Azure Monitor OpenTelemetry work | Microsoft `skills` |
| `azure-monitor-query-py` | Read-only Azure Monitor Logs queries; supports `LogsQueryClient` telemetry correlation in `backend/evals/verify_telemetry.py` | Microsoft `skills` |
| `microsoft-foundry` | Hosted-agent lifecycle, evaluation, and Foundry observability guidance | Microsoft `skills` |
| `fastapi-router-py` | FastAPI HTTP route work | Microsoft `skills` |
| `pydantic-models-py` | Pydantic v2 API contract work | Microsoft `skills` |
| `postgres-psycopg-py` | PostgreSQL, Psycopg, pgvector, and Azure PostgreSQL persistence | Repository-owned |
| `ag-ui-streaming-fastapi-py` | Additive, redacted AG-UI/CopilotKit durable-event projections | Repository-owned |
| `ag-ui-react-integration-ts` | Private selected-thread React integration and safe CopilotKit context | Repository-owned |
| `typescript-setup` | Strict TypeScript setup for new frontend surfaces | Repository-owned |
| `typescript-update` | Strict React/TypeScript updates that preserve workflow contracts | Repository-owned |
| `e2e-rubric` | Native SSE, HITL, selected-thread privacy, and wrapper-boundary operator coverage | Repository-owned |

The five pre-existing Microsoft skills are vendored from
[`microsoft/skills`](https://github.com/microsoft/skills) commit
`c33193b1b2dd14d5946e3c6213fd095ffa5b31df`. Refresh them deliberately from that
source, preserving each complete skill directory and reviewing upstream changes before updating
the pinned revision. The two additions were selectively copied as complete directories
from [`microsoft/skills`](https://github.com/microsoft/skills) revision
`e58528db9a006528a5fb0a2c029790fa6a9a7c0e`:
`.github/plugins/azure-skills/skills/microsoft-foundry` and
`.github/plugins/azure-sdk-python/skills/azure-monitor-query-py`. Do not install the
full catalog when refreshing either pin.

`agent-framework-foundry-py` and `postgres-psycopg-py` are repository-owned because
they encode this application's workflow and persistence boundaries. The MAF skill is
grounded in current Microsoft Learn Agent Framework guidance and the installed
`agent-framework-foundry` package; it intentionally does not target
`agent-framework-azure-ai` or `AzureAIAgentsProvider`.

The selected-thread UI and modernized frontend graph pass clean installation,
TypeScript 7 typechecking, lint, production build, focused Playwright,
container build, HTTP smoke, Azure deployment, hosted E2E, telemetry, and
strict evaluation. Current hosted release and evaluation evidence is in the
[review remediation release](issues-changes-fixes.md#review-remediation-release-2026-10-21).
