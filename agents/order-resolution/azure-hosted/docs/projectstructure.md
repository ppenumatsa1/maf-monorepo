# Project Structure

```text
README.md                         operator entry point
backend/                          FastAPI host, MAF workflow, persistence, tests
frontend/                         React/Nginx UI and same-origin proxy
infra/azure-apphosted/            Bicep/AZD Azure application package
deployment/                       profile schema/compatibility and evidence contracts
scripts/local/                    isolated local validation helpers
scripts/playwright/               browser workflow and selected-thread tests
scripts/parity/                   local/Azure comparison tooling
scripts/release/                  bootstrap, app release, telemetry, evidence
docs/                             product, engineering, operations, evidence
.azure/deployment-plan.md         current deployment policy and acceptance
.github/copilot-instructions.md   coding-agent repository instructions
agents.md                         contributor and agent guardrails
```

## Backend boundaries

```text
backend/app/
  api/v1/                         HTTP and SSE routes/contracts
  core/                           configuration, database, telemetry, composition
  infrastructure/                 persistence and external adapters
  maf/                            prompts, agents, tools, executors, runner, workflow
  modules/order_resolution/       application service, ports, models, projections
```

FastAPI owns the only MAF runtime. The Azure package adds deployment,
PostgreSQL, monitoring, and optional Foundry model/evaluation resources; it
does not add another workflow host.

`backend/app/modules/order_resolution/agui.py` is an allowlist projection of
durable events. The existing rich-event module retains the native `/rich`
contract and must not be used as assistant input.

## Documentation ownership

The canonical documentation inventory is [docs/README.md](README.md). Product
behavior, technical contracts, operating guidance, and dated evidence each
have one authoritative home.
