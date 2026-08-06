# Project Structure

```text
foundry-public/
  backend/
    app/
      api/v1/
        routes/
        schemas/
      core/
      infrastructure/
        checkpointing/
        db/
        llm/
        repositories/
      maf/
        clients/
        executors/
        middleware/
        prompts/
        tools/
        workflows/
        agui.py
        runner.py
      modules/underwriting/
      main.py
      server.py
    foundry/main.py
    tests/
  frontend/
    src/
    tests/e2e/
  infra/
    foundry-hosted/
  scripts/
    foundry/
  docs/design/
```

## Boundary Ownership

- `backend/app/api/v1/*`: HTTP contracts and DTOs for run/resume/history/state/events/checkpoints.
- `backend/app/modules/underwriting/*`: domain and application service boundary.
- `backend/app/maf/*`: workflow runtime internals (executors, tools, prompts, middleware, AG-UI adapters).
- `backend/app/infrastructure/*`: persistence adapters and LLM/checkpoint integrations.
- `backend/foundry/main.py`: hosted Responses workflow executor; owns the MAF
  runner and PostgreSQL persistence connection.
- `frontend/src/*`: operator console orchestration, API/AG-UI client
  integration, and the CopilotKit selected-run assistant.

## Design Rule

Route -> adapter -> hosted workflow/infrastructure flow only. The public
service owns browser-facing contracts and durable read projections; the hosted
agent owns production orchestration and writes.
