# Technology Stack

Exact dependency versions are authoritative in `pyproject.toml`,
`backend/requirements*.txt`, `backend/requirements*.lock`,
`frontend/package.json`, and the frontend lockfile. This document describes
roles and compatibility boundaries rather than duplicating a version ledger.

## Backend and hosted runtime

- Python 3.13 for local tools, FastAPI, and the hosted agent.
- FastAPI and Uvicorn for the internal API adapter.
- Pydantic for HTTP and hosted input validation.
- Microsoft Agent Framework for the master direct-executor workflow,
  checkpointing, middleware, and AG-UI projection.
- Foundry agent server Responses support; Activity support is additive in the
  same hosted process for Teams.
- Azure AI Projects and Azure Identity for project/agent lifecycle and managed
  identity.
- SQLAlchemy and Psycopg for PostgreSQL persistence.
- Azure Monitor OpenTelemetry and Application Insights for correlation.

Release images use the checked-in locked dependency and wheelhouse contract.
Local editable installation remains defined by `pyproject.toml`.

## Frontend

- React and React DOM.
- TypeScript.
- Vite.
- Nginx for the production static site and same-origin backend proxy.
- Fetch/SSE clients for run and progress surfaces.
- `@copilotkit/react-core` for the selected-run assistant.
- Zod where runtime frontend validation is required.

The frontend does not receive Foundry, PostgreSQL, Bot, or publication
credentials.

## Data and state

- PostgreSQL for application projections, MAF checkpoints, approvals,
  card-action bindings, and idempotency.
- Administrator-owned production schema.
- A least-privilege runtime database credential shared by backend and hosted
  workflow through separate secret-delivery mechanisms.
- A Foundry project `CustomKeys` connection whose placeholder, not resolved
  URL, appears in hosted-agent metadata.

## Azure runtime

- Microsoft Foundry hosted agent.
- Azure Container Apps for external frontend and internal backend.
- Azure Container Registry for immutable application images.
- Azure Database for PostgreSQL Flexible Server using the public-lane
  TLS/firewall contract.
- Log Analytics and Application Insights.
- Azure Bot Service and `MsTeamsChannel` when Shared Teams publication is
  enabled.
- Bicep and Azure Developer CLI for infrastructure and packaging.

This is a public-network lane. Private-runner, VNet, private endpoint, private
DNS, Bastion, and NAT components are not part of the topology.

## Quality and delivery

- pytest for backend and script tests.
- Ruff for backend lint/format checks.
- frontend lint and build scripts.
- Playwright for browser E2E.
- deterministic and hosted trace evaluation.
- Make as the primary command surface.
- automatic credential-free GitHub CI.
- protected GitHub OIDC workflows for preview/provision, app-only deploy,
  package validation, observability, and evidence retry.
- local authenticated equivalents for diagnosis/operator execution.
- interactive Microsoft 365 Shared publication.

## Vendored guidance

Repository skills under `.github/skills/` provide focused Microsoft platform,
SDK, validation, and documentation guidance. See
[`.github/skills/README.md`](../../.github/skills/README.md) for source and
refresh policy.

Skills guide implementation; source tests and live evidence remain the proof.
