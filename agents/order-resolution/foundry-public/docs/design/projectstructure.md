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
        foundry/
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
        agui.py
        durable_events.py
        rich_events.py
      main.py
    foundry/main.py
    foundry/teams_cards.py
    tests/
    .foundry/
      datasets/
      evaluators/
      suites/
    Dockerfile.hosted
    eval.yaml
    requirements.lock
    requirements-dev.lock
  frontend/
    src/
      lib/
    package.json
  infra/
    foundry-hosted/
      iac/teams/
      teams-publication.json
  scripts/
    foundry/
    playwright/
    skills/
  docs/design/
```

## Boundary ownership

- `backend/app/api/v1/*`: HTTP and SSE contracts.
- `backend/app/api/v1/routers/copilotkit.py`: read-only CopilotKit
  selected-thread endpoint; it is not a workflow command path.
- `backend/app/modules/order_resolution/*`: application service, domain models, ports, projections.
- `backend/app/modules/order_resolution/agui.py`: allowlisted, redacted
  AG-UI/CopilotKit projection of durable workflow events.
- `backend/app/modules/order_resolution/durable_events.py`: persisted-event
  polling used by the separate hosted agent and API-wrapper processes.
- `backend/app/maf/*`: MAF runtime internals (prompts, agents, executors, workflow, runner).
- `backend/app/infrastructure/*`: persistence and external adapters.
- `backend/app/infrastructure/foundry/*`: managed-identity Foundry Responses
  client used by the internal API wrapper.
- `backend/app/infrastructure/persistence/teams_card_action_repository.py`:
  opaque, hashed, batched Teams approval actions with atomic claim/replay
  protection.
- `backend/foundry/main.py`: one Foundry-hosted process composing Responses and
  Activity adapters around the shared service/workflow path.
- `backend/foundry/teams_cards.py`: privacy-minimized pending/resolved Adaptive
  Card construction and action parsing.
- `infra/foundry-hosted/iac/teams/`: Azure Bot Service, `MsTeamsChannel`, and
  diagnostics module plus credential-free contract tests.
- `scripts/foundry/*`: hash-locked wheelhouse, incremental capacity, preview
  safety, app-only/full-infrastructure routing, evaluation/evidence, Teams
  publication, and rollback automation.
