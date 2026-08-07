---
name: azure-deployment
description: Execute already validated Azure deployments and verify live endpoints.
---

# Azure Deployment Skill

Use this skill only for deployments that already passed Azure validation. Do not use it to design, prepare, or validate an unvalidated app.

## Hard gates

- Require `.azure/deployment-plan.md` to exist with status `Validated`.
- Run pre-deploy checks before any mutation: active subscription, AZD environment, required variables, Docker availability when needed, and clean authentication to Azure.
- Do not perform destructive cleanup, resource deletion, environment reset, or database drop unless the user explicitly confirms that exact destructive action.

## Deployment sequence

Normal releases are always app-only, including application, Docker, and
frontend runtime-configuration changes. Use the checked-in release sequence;
do not substitute a bare `azd deploy`:

```bash
make release-app
```

It deploys only backend and frontend revisions, then calls
`make release-validate`. It must retain the approved CFS Python package feed
(`PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`) and the
Alpine/musl-compatible frontend build/runtime path.

Infrastructure provisioning is exceptional reconciliation, never an implied
response to changed IaC or runtime files. Require an explicit non-secret
owner change reference and an owner-reviewed Bicep preview:

```bash
INFRA_RECONCILIATION_APPROVED=true \
INFRA_RECONCILIATION_REFERENCE="<non-secret-review-reference>" \
make release-infra-preview
```

Only an explicitly owner-confirmed apply with the exact preview hashes may use
`make release-infra-reconcile`.
Reconciliation must preserve the existing PostgreSQL server and
`maf_workflow` database; it must never recreate, replace, drop, or silently
migrate that durable boundary. The deployment-mode router always emits
`app_only`; its reconciliation indicator means review is required, not that
provisioning is authorized.

## Known recovery

If Container Apps deployment fails because the app is not bound to ACR through its managed identity, recover with the explicit registry binding and rerun deploy:

```bash
az containerapp registry set \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --server <acr-login-server> \
  --identity system
azd deploy
```

Use this recovery only for the known registry binding issue; do not mask unrelated deployment failures.

## Post-deploy verification

- Run smoke tests against the live HTTPS endpoint.
- Verify health endpoint, Container Apps revision readiness, and recent logs.
- Run hosted Playwright UI parity against the live frontend:

```bash
PLAYWRIGHT_BASE_URL="<frontend-https-url>" make test-e2e
```

  Fail deployment verification if Workflow History shows `Unexpected token`, `not valid JSON`, or `<!doctype`; that means frontend routing/proxy/API base configuration is returning HTML instead of JSON.
- Validate RBAC live: ACR image pull, Key Vault secret reads, PostgreSQL connectivity, and observability ingestion where applicable.
- Validate `ORD-1001` completes without `hitl.request`.
- Validate `ORD-1009` emits `hitl.request` and completes the expected approval/resume path.
- Require fresh release correlation evidence: smoke writes the release run,
  thread, and workflow-run identifiers; hosted E2E, report-only Foundry
  evaluation, and Application Insights queries must use that same release
  window before the release is claimed validated.
- Local Docker E2E is optional where managed-device policy blocks Docker npm
  egress. Require the **Required cloud Docker E2E** GitHub Actions result for
  full changes; do not replace a missing cloud result with host npm success or
  a skipped local Docker run.
- Report fully qualified HTTPS endpoints for frontend, backend/API, health, and any documented smoke target.

## Output

Report deployed environment, resource group, Container Apps names, image tags when available, smoke results, RBAC results, and fully qualified HTTPS endpoints. If deployment fails, report the exact command, error, recovery attempted, and next safe action.
