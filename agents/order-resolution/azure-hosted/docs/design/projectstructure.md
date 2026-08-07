# Project Structure

```text
backend/
  app/
    api/v1/          HTTP and SSE contracts
    core/            configuration, database, telemetry, composition
    infrastructure/  persistence and external adapters
    maf/             prompts, agents, tools, executors, runner, workflows
    modules/order_resolution/
frontend/            React UI
  src/config.ts      Runtime endpoint configuration
  src/copilot.ts     Redacted selected-thread context allowlist
infra/azure-apphosted/
                    Container Apps deployment package
scripts/             validation, parity, and Azure helper scripts
docs/design/         architecture and contract documentation
```

The backend FastAPI application owns the only MAF runtime. The Azure package
adds infrastructure and model/evaluation resources; it does not add another
workflow host. `backend/app/modules/order_resolution/agui.py` projects durable
events for the additive selected-thread route; the existing rich-event module
retains the native `/rich` contract and must not be used as assistant input.
