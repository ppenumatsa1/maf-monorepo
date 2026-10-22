# Azure App-Hosted Package

## Purpose

This package deploys the React frontend and FastAPI/MAF backend as Azure
Container Apps with PostgreSQL, ACR, monitoring, managed identities, and
optional Foundry model/evaluation resources.

FastAPI remains the sole application host. Foundry is limited to model
inference and report-only evaluation.

## Target contract

All target values are supplied through a validated, ignored operator profile
and the selected AZD environment. Source templates do not prove a current
deployment, and tracked documentation must not contain concrete tenant,
subscription, user, resource, or endpoint values.

## Topology

```text
Browser
  -> external frontend Container App
  -> same-origin /api proxy
  -> internal FastAPI backend Container App
  -> managed-identity PostgreSQL

FastAPI -> optional Foundry model inference
Captured HTTP results -> report-only Foundry evaluation
Runtime spans -> Application Insights
```

## Layout

- `iac/main.bicep`: subscription-scope AZD entry point.
- `iac/modules/`: Azure resource modules.
- `iac/main.parameters.json`: AZD parameter binding.
- `runtime/.env.example`: application runtime settings.
- `runtime/smoke-test.sh`: frontend, proxied API, and baseline workflow checks.

## Runtime settings

The backend uses:

- `WORKFLOW_MODE=maf_sdk`
- PostgreSQL store and memory providers
- Azure PostgreSQL managed-identity variables
- optional Foundry model deployment settings
- Application Insights settings with content recording disabled by default

When model configuration is unavailable, deterministic triage remains within
the same MAF workflow.

## Deployment paths

### Fresh bootstrap

Prepare untracked operator inputs, review the subscription-scope preview,
provision only after authorization, establish managed-identity database access,
remove temporary bootstrap access, and transition to steady state.

### App-only release

`make release-app` deploys backend/frontend revisions only, preserves
PostgreSQL, verifies internal/external ingress, and runs smoke, browser/domain
E2E, telemetry, report-only evaluation, and final evidence.

### Infrastructure reconciliation

Use only the explicit preview/reconcile path. Changed application or Bicep
files do not imply infrastructure execution.

See the [deployment flow](../../docs/deployment-flow.md) and
[deployment plan](../../.azure/deployment-plan.md).
