# Project Structure

```text
foundry-public/
  README.md
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
  docs/
    manual-testing.md
    design/
      architecture.md
      customer-questions-answers.md
      e2e-rubric.md
      engineering-operating-model.md
      implementation-phases.md
      issues-changes-fixes.md
      prd.md
      projectstructure.md
      schema-io-telemetry.md
      techstack.md
      userflow.md
```

## Boundary ownership

- `backend/app/api/v1/*`: HTTP contracts and DTOs for run/resume/history/state/events/checkpoints plus AG-UI and CopilotKit browser-facing routes.
- `backend/app/modules/underwriting/*`: domain and application service boundary.
- `backend/app/maf/*`: workflow runtime internals (executors, tools, prompts, middleware, AG-UI adapters).
- `backend/app/infrastructure/*`: persistence adapters and LLM/checkpoint integrations.
- `backend/foundry/main.py`: hosted Responses workflow executor; owns the production MAF runner and PostgreSQL persistence connection.
- `frontend/src/*`: operator console orchestration, API/AG-UI client integration, and the CopilotKit selected-run assistant.
- `docs/design/engineering-operating-model.md`: canonical release-governance contract.
- `docs/design/issues-changes-fixes.md`: evidence ledger for hosted issues, changes, fixes, and readiness claims.

## Design rule

Route -> adapter -> hosted workflow/infrastructure flow only. The public service owns browser-facing contracts and durable read projections; the hosted agent owns production orchestration and writes.

## No-shims guidance

- Do not reintroduce a second public-lane workflow engine in the adapter.
- Do not add a shadow checkpoint or history store outside PostgreSQL.
- Do not add direct browser-to-Foundry surfaces.
- Fix hosted/runtime issues at the boundary that owns them rather than masking them with compatibility layers.
