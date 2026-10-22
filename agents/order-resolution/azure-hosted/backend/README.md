# Backend - Azure-Hosted MAF Order Resolution

## Runtime status

FastAPI is the only application host for the MAF workflow. The same sequential
workflow runs locally and in the internal backend Container App. Foundry is
limited to optional model inference and report-only evaluation of captured HTTP
results.

There is no hosted-agent, Responses, Activity, Bot, Teams, or Adaptive Card
runtime in this lane.

## Run locally

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set `FOUNDRY_PROJECTS_ENDPOINT` and `FOUNDRY_MODEL_DEPLOYMENT_NAME` to enable
model inference. If they are absent, only triage summary generation falls back
deterministically; MAF orchestration remains the same.

## Internal boundaries

- `app/api/v1/routers/*` owns HTTP and SSE routes.
- `app/api/v1/schemas/*` owns API contracts.
- `app/modules/order_resolution/*` owns application services, ports, models,
  and event projections.
- `app/core/*` owns configuration, database, telemetry, and composition.
- `app/infrastructure/*` owns persistence and external adapters.
- `app/maf/*` owns prompts, agents, tools, executors, runner, and workflow.

## APIs

- `POST /api/chat/run`
- `GET /api/chat/stream/{thread_id}`
- `GET /api/chat/stream/{thread_id}/rich`
- `GET /api/chat/stream/{thread_id}/ag-ui`
- `GET /api/copilotkit/info` and `GET /api/copilotkit`
- `POST /api/copilotkit`
- `POST /api/hitl/respond`
- `GET /api/workflows`
- `GET /api/workflows/{thread_id}`
- `GET /api/workflows/{thread_id}/events`
- `GET /api/sessions/{session_id}/messages`
- `GET /health` and `GET /api/health`

## Event and selected-thread contracts

Stable native events:

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

`/rich` preserves native payloads and is not assistant input. AG-UI and
CopilotKit select only an existing durable thread and expose an allowlisted
redacted projection. They cannot start, approve, reject, resume, or otherwise
mutate a workflow.

## PostgreSQL

PostgreSQL stores workflow runs, events, messages, checkpoints, approvals, and
idempotency state. Azure runtime access uses managed identity. Do not add a
stored-password fallback or recreate the retained database during an app-only
release.

## Evaluation

- `make eval-backend` runs deterministic workflow contract evaluation.
- `make eval-foundry` captures FastAPI workflow results and submits them for
  report-only evaluation.
- Foundry evaluation never invokes or mutates application workflows.

See the [technical specification](../docs/technical-spec.md) and
[business rules](../docs/business-rules.md).
