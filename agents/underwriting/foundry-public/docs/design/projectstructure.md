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
    README.md
    manual-testing.md
    design/
      functional-spec.md
      business-rules.md
      technical-spec.md
      hitl-review.md
      architecture.md
      architecture-decisions.md
      customer-questions-answers.md
      e2e-rubric.md
      engineering-operating-model.md
      implementation-phases.md
      issues-changes-fixes.md
      projectstructure.md
      schema-io-telemetry.md
      secure-foundry-agent-to-teams.md
      techstack.md
      userflow.md
```

## Boundary ownership

- `backend/app/api/v1/*`: HTTP contracts and DTOs for run/resume/history/state/events/checkpoints plus AG-UI and CopilotKit browser-facing routes.
- `backend/app/modules/underwriting/*`: domain and application service boundary.
- `backend/app/maf/*`: workflow runtime internals (executors, tools, prompts, middleware, AG-UI adapters).
- `backend/app/infrastructure/*`: persistence adapters and LLM/checkpoint integrations.
- `backend/foundry/main.py`: hosted Responses and additive Activity workflow
  executor; owns the production MAF runner and PostgreSQL persistence
  connection.
- `frontend/src/*`: operator console orchestration, API/AG-UI client integration, and the CopilotKit selected-run assistant.
- `docs/design/functional-spec.md`: product behavior and acceptance scope.
- `docs/design/business-rules.md`: authoritative decision, review, privacy,
  isolation, and evidence rules.
- `docs/design/technical-spec.md`: runtime and implementation contract.
- `docs/design/hitl-review.md`: referral-only pause and secure reviewer action
  contract.
- `docs/design/engineering-operating-model.md`: canonical release-governance contract.
- `docs/design/issues-changes-fixes.md`: evidence ledger for hosted issues, changes, fixes, and readiness claims.

## Design rule

Route -> adapter -> hosted workflow/infrastructure flow only. The public service owns browser-facing contracts and durable read projections; the hosted agent owns production orchestration and writes.

## No-shims guidance

- Do not reintroduce a second public-lane workflow engine in the adapter.
- Do not add a shadow checkpoint or history store outside PostgreSQL.
- Do not add direct browser-to-Foundry surfaces.
- Do not merge machine recommendation and reviewer outcome.
- Do not allow free-form or cross-channel approval decisions.
- Do not expose underwriting data in Adaptive Cards or assistant projections.
- Fix hosted/runtime issues at the boundary that owns them rather than masking them with compatibility layers.
