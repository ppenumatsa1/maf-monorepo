# Project Structure

```text
maf-order-resolution-agent/
  backend/
    app/
      api/v1/
        routers/
        schemas/
      core/
      infrastructure/
        events/
        mcp/
        persistence/
        rag/
      maf/
        agents/
        executors/
        prompts/
        tools/
        workflows/
        clients.py
        factory.py
        middleware.py
        runner.py
      modules/order_resolution/
      main.py
    foundry/main.py
    tests/
    .foundry/
      datasets/
      evaluators/
      suites/
    Dockerfile.hosted
    eval.yaml
  frontend/
    src/
    package.json
  infra/
    foundry-hosted/
  scripts/
    github/
    parity/
    playwright/
    skills/
  docs/design/
```

## Boundary ownership

- `backend/app/api/v1/*`: HTTP and SSE contracts.
- `backend/app/api/v1/routers/*` and `schemas/*`: own the approved
  selected-thread AG-UI/CopilotKit HTTP contracts; the bridge remains a
  read-only selector and is not a workflow command path.
- `backend/app/modules/order_resolution/*`: application service, domain models, ports, projections.
- `backend/app/modules/order_resolution/*`: owns the allowlisted,
  privacy-safe durable-event projection rules. It must not use `/rich` or raw
  native-event payloads as assistant context.
- `backend/app/maf/*`: MAF runtime internals (prompts, agents, executors, workflow, runner).
- `backend/app/infrastructure/*`: persistence and external adapters.
- `backend/foundry/main.py`: Foundry-hosted Responses adapter that invokes the shared service/workflow path; `backend/Dockerfile.hosted` packages it for ACR image deployment.
- `frontend/src/*`: retains the native timeline and HITL controls. Approved
  follow-on work may add optional selected-thread AG-UI/CopilotKit presentation
  through the same-origin proxy only; no direct private Foundry, PostgreSQL, or
  MCP/RAG client belongs here.
