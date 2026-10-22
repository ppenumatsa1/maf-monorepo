# Scripts

Scripts support local validation, target preparation, app-only release,
explicit infrastructure reconciliation, telemetry, evaluation, and evidence.

## Key paths

- `local/`: isolated local PostgreSQL and test helpers.
- `playwright/`: workflow and selected-thread browser scenarios.
- `parity/`: local and Azure endpoint comparison.
- `manual/`: repeatable workflow scenario matrix.
- `rubric/`: end-to-end quality rubric.
- `skills/`: deterministic design and release routing checks.
- `azure/`: managed-identity PostgreSQL bootstrap helpers.
- `release/`: target checks, bootstrap transition, app release, telemetry,
  report-only evaluation, and evidence aggregation.

## Local browser validation

From the package root:

```bash
make test-e2e-selected
make test-e2e
make docker-test
```

Use the frontend's same-origin URL for deployed browser validation. The
internal backend is not a browser-facing endpoint.

## Endpoint parity

```bash
PARITY_LOCAL_API_URL=http://localhost:8000
PARITY_LOCAL_WEB_URL=http://localhost:5173
PARITY_AZURE_API_URL=https://<frontend-host>/api
PARITY_AZURE_WEB_URL=https://<frontend-host>
make parity-all
```

Resolve `<frontend-host>` from the selected AZD environment; do not store it in
tracked files.

## Release evidence

`make release-app` performs the routine app-only path. It must not provision
infrastructure or recreate PostgreSQL.

The proof order is:

1. deployment verification;
2. smoke;
3. browser E2E;
4. three HTTP/durable domain scenarios;
5. exact Application Insights correlation;
6. report-only Foundry evaluation; and
7. final evidence.

Foundry evaluation judges captured HTTP results only and cannot invoke or
mutate workflows. The validation wrapper must preserve failed final evidence
when an intermediate gate stops the release.

Use `make release-infra-preview` for a non-mutating preview and
`make release-infra-reconcile` only for an explicit steady-state infrastructure
operation.
