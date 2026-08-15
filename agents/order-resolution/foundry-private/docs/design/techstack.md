# Tech Stack

## Backend

- Python 3.10+
- FastAPI + Uvicorn
- Pydantic v2
- httpx for MCP HTTP tool calls
- OpenTelemetry SDK + OTLP exporter

## Frontend

- React 18
- Vite 5
- TypeScript
- `@copilotkit/react-core` for the implemented optional read-only
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

The selected-thread UI's strict typecheck, lint, build, and focused Playwright
gates are implemented and locally validated: 133 tests passed, the
deterministic evaluation completed 10/10, seven workflow and four
selected-thread E2E cases passed, and design review passed. The protected
run `31911162673` app-only deployment, hosted E2E, Foundry evaluation, and
telemetry evidence are recorded in
[issues-changes-fixes.md](issues-changes-fixes.md#app-only-release-feedback-optimization-2026-08-15).
Those results are distinct from the local frontend gates.
