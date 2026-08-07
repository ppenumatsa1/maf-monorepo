# Backend - MAF Order Resolution

## Runtime

FastAPI is the sole application host for the MAF workflow. The same workflow
runs locally and in the planned Azure Container Apps deployment. Foundry is
used only for triage model inference and report-only evaluation.

There is one business workflow rooted at
`app/maf/workflows/order_resolution.py`, with prompts, agents, tools,
executors, runner, and workflow kept as separate concerns.

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
model inference. Without them, only deterministic triage falls back; MAF
orchestration does not change.

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

## Stable SSE event types

`workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
`hitl.response`, and `workflow.output`.

## Additive selected-thread projections

The native stream and `/rich` envelope retain their existing contracts. In
particular, `/rich` retains native event data and is not safe assistant input.

`/ag-ui` is a separate durable-event projection: it accepts only a valid,
already persisted thread ID and sends allowlisted lifecycle/tool labels,
validated checkpoint IDs and approval decisions, plus generic terminal/error
text. It does not stream raw native payloads.

CopilotKit is an optional selected-thread UI integration, not the GitHub
Copilot SDK. Its GET endpoints are static discovery. Its POST bridge selects
one existing `threadId`; `runId`, messages, state, tools, context, and
`forwardedProps` are accepted solely for protocol compatibility and discarded.
The bridge never starts, resumes, or mutates a workflow.

## HITL conditions

HITL is required when the amount/risk is at least 100, the issue is
`damaged_item`, or policy requires `manual_review`. `ORD-1009` requires HITL;
`ORD-1001` normally does not.

## Evaluation

`make eval-backend` is the deterministic contract gate. `make eval-foundry`
captures canonical FastAPI workflow results for a non-blocking, report-only
Foundry evaluation.
