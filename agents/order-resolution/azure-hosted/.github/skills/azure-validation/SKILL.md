---
name: azure-validation
description: Validate a deployable or deployed Azure app-hosted workflow without deploying resources.
---

# Azure Validation Skill

Use this skill after IaC review and before deployment. Validate readiness and live behavior without running deployment commands that mutate Azure resources.

## Required inputs

- `.azure/deployment-plan.md` exists and proves the intended Azure target, resource model, and current status.
- Existing AZD/Bicep/package files are present for the app components being validated.
- If live resources already exist, the active Azure subscription and environment are known.

## Local validation

Run non-mutating checks only:

```bash
az bicep build --file infra/main.bicep
```

Then run package validation using repository commands that already exist, such as backend/frontend builds or tests. Do not add new tools solely for validation.

If infrastructure reconciliation is in scope, its preview is separately
guarded and requires explicit non-secret owner confirmation metadata:

```bash
INFRA_RECONCILIATION_APPROVED=true \
INFRA_RECONCILIATION_REFERENCE="<non-secret-review-reference>" \
make release-infra-preview
```

Do not infer permission to provision from a validation result. Normal releases
remain `make release-app`; an existing PostgreSQL server/database must be
preserved and never recreated as part of validation.

## Deployment-plan gate

- Confirm `.azure/deployment-plan.md` contains evidence that the app is prepared for Azure deployment.
- Confirm status distinguishes source intent from dated deployed evidence. Do
  not mark deployment-ready unless current commands and, where applicable,
  fresh smoke/E2E/evaluation/telemetry evidence pass.
- Record any missing resource, identity, SKU, or region assumption as a blocker.

## Smoke and behavior checks

- Run the repository smoke script when present; it must validate health and
  low/high-risk workflow behavior without changing infrastructure and record
  the release/thread correlation identifiers for later telemetry queries.
- For live Container Apps, verify app health endpoint, ingress URL, revision readiness, and recent logs.
- Validate live `/health` or equivalent endpoint over HTTPS.
- Run hosted Playwright UI parity against the frontend URL when live resources exist:

```bash
PLAYWRIGHT_BASE_URL="$WEB_URL" make test-e2e
```

  This must prove the frontend is wired to the API, including Workflow History loading JSON successfully. Any visible `Unexpected token`, `not valid JSON`, or `<!doctype` error is a blocker because it indicates an API route/proxy fallback to HTML.
- Validate `ORD-1001` completes without `hitl.request`.
- Validate `ORD-1009` emits `hitl.request` and can follow the expected HITL path.
- Confirm RBAC where resources exist: Container Apps managed identity can pull from ACR, read Key Vault secrets, and access PostgreSQL/observability dependencies as designed.
- Where local Docker npm egress is blocked by managed-device policy, retain the
  full-change **Required cloud Docker E2E** result as the authoritative Docker
  validation evidence rather than requiring a local Docker rerun.

## Pass/fail behavior

- Pass only when Bicep build, package validation, explicitly owner-approved preview
  where reconciliation is requested, smoke checks, hosted Playwright UI parity
  where live resources exist, health checks, workflow cases, and applicable
  RBAC checks succeed.
- If passing, update `.azure/deployment-plan.md` status to `Validated` only when explicitly requested by the user or task.
- If blocked, report the exact failing command, missing resource, or permission gap and do not deploy.
