# Scripts

Scripts support local validation and the planned Azure app-hosted package.

## Key paths

- `playwright/`: browser workflow and selected-thread scenarios.
- `parity/`: local and Azure endpoint parity runner.
- `rubric/`: end-to-end quality rubric.
- `skills/design-review-skill.sh`: deterministic review gate.
- `skills/deployment-mode-router.sh`: validation/deployment routing.
- `azure/grant-postgres-identity.sh`: AZD post-provision PostgreSQL Entra grant.
- `release/`: app-only deployment, guarded infrastructure reconciliation, and
  release evidence collection.

## Local browser test

```bash
cd scripts/playwright
npm install
npx playwright install
PLAYWRIGHT_BASE_URL=http://localhost:5173 npm run test:e2e
```

From the package root, prefer the isolated targets:

```bash
make test-e2e-selected  # selected-thread AG-UI and CopilotKit contract
make test-e2e           # complete workflow plus selected-thread suite
make docker-test        # separate Docker Compose suite on dynamic ports
```

## Endpoint parity

```bash
PARITY_LOCAL_API_URL=http://localhost:8000
PARITY_LOCAL_WEB_URL=http://localhost:5173
PARITY_AZURE_API_URL=https://<backend-host>
PARITY_AZURE_WEB_URL=https://<frontend-host>
make parity-all
```

The Azure variables are for authorized post-deployment validation only; this
branch currently makes no deployment claim.

## Release evidence

Use `make release-app` for normal backend/frontend releases. It does not
provision infrastructure or recreate PostgreSQL. `make release-validate`
collects low/high-risk smoke evidence, hosted Playwright, report-only Foundry
evaluation, and Application Insights correlation in one fresh release window.

Use `make release-infra-preview` only after setting an explicit non-secret
approval/reference; it performs a Bicep/AZD preview. Reconciliation apply is a
separate guarded action. Do not use a historical successful query or previous
thread as evidence for a new release.
