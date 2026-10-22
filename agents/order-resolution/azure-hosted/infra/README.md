# Infrastructure

`azure-apphosted/` is the Azure package for:

- an external React/Nginx frontend Container App;
- an internal FastAPI/MAF backend Container App;
- retained Azure Database for PostgreSQL;
- Azure Container Registry, Log Analytics, and Application Insights;
- managed identities and scoped RBAC; and
- optional Foundry model inference and report-only evaluation resources.

FastAPI is the only MAF application host. This lane excludes private
networking, Foundry hosted-agent/Responses, Bot, Activity, Teams, and Adaptive
Cards.

## Target selection

Tenant, subscription, resource group, region, names, and endpoints come from a
validated, ignored operator profile and the selected AZD environment. Tracked
infrastructure docs contain no concrete environment values.

## Lifecycle

- Fresh bootstrap creates the initial profile-selected platform.
- Transition to steady state removes temporary bootstrap access and retains
  PostgreSQL.
- `make release-app` updates application revisions only.
- `make release-infra-preview` is non-mutating.
- `make release-infra-reconcile` is an explicit exceptional action.

Generated release proof belongs under
`.artifacts/releases/<release-id>/evidence/`, with logs in the sibling
`logs/` directory.
