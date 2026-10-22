# Infrastructure

The only Azure deployment path defined by the current source is
[Foundry hosted](foundry-hosted/README.md). It provisions the public Foundry
account, project, model deployments, ACR, and shared observability/data
dependencies from an empty resource group, deploys an external frontend
Container App and an internal FastAPI wrapper Container App, and hosts the
Responses-native MAF agent.

The same hosted process also composes the additive Activity protocol for
Microsoft Teams. The separate Teams Bicep module defines Azure Bot Service,
`MsTeamsChannel`, and diagnostics without adding private networking.

Browser traffic is same-origin through the frontend's `/api` proxy. The internal
backend uses managed identity to call Foundry and shares PostgreSQL durable
workflow state with the hosted agent. Local Docker remains the API/SSE/UI
development environment.

These templates and scripts describe source intent. A reviewed preview, apply,
deployment verification, live acceptance, evaluation, telemetry, and evidence
ledger entry are still required before claiming the current source is live.
