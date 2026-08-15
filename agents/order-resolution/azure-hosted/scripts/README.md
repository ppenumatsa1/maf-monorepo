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
- `release/prepare-bootstrap-environment.sh`: validates the approved
  target-only profile and prepares local AZD bootstrap values.
- `release/transition-bootstrap-to-steady-state.sh`: verifies retained
  PostgreSQL identities, deletes and verifies removal of the exact bootstrap
  operator firewall rule, then excludes PostgreSQL from future IaC. A retry
  accepts confirmed rule absence after a partial AZD update, but lookup/auth
  failures remain blocking.

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
collects deployment verification, low/high-risk smoke evidence, hosted
Playwright, the three HTTP domain scenarios, report-only Foundry evaluation,
exact Application Insights correlation, and final evidence in one fresh release
window.
Tracked release inputs remain in `deployment/profiles/` and the checked-in
design/deployment contract docs; the generated release bundle is written to
`.artifacts/releases/<release-id>/`.

The generated bundle is the release-local evidence handoff and includes:

- `release.json`
- `evidence/release-context.json`
- `evidence/source-validation.json`
- `evidence/images.json`
- `evidence/deployment.json`
- `evidence/smoke.json`
- `evidence/domain-e2e.json`
- `evidence/evaluation.json`
- `evidence/telemetry.json`
- `evidence/release-evidence.json`
- `logs/` (including `browser-e2e.log`)

`release-eval` passes the canonical evaluation output path to the evaluator and
enforces a completed run with zero failed or errored rows. `release-validate`
uses `validate-hosted-release.sh`, whose exit trap writes a failed final
evidence record even when an intermediate gate stops the release.

Use `make release-infra-preview` for a non-mutating Bicep/AZD preview.
`make release-infra-reconcile` is a separate direct guarded action: it obtains
and validates a fresh steady-state what-if before apply and rejects any
PostgreSQL entry. Do not use a historical successful query or previous thread as
evidence for a new release.
