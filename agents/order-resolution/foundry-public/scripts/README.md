# Scripts

- `foundry/deploy_public_dev.sh`: authenticated local release sequence.
- `foundry/ensure_foundry_azd_defaults.sh`: initializes the selected public
  AZD environment and resets provision-time Container App images to the MCR
  bootstrap image so deleted ACR tags cannot block infrastructure creation.
- `foundry/hosted_e2e.sh`: Responses low-risk, approval, rejection, and
  duplicate-response regression.
- `foundry/verify_telemetry.sh`: bounded Application Insights telemetry check.
- `foundry/check_public_postgres_readiness.sh`: public PostgreSQL readiness.
- `playwright/`: local and hosted same-origin API/SSE browser regression suite.
- `make test-e2e-selected-thread`: focused frontend selected-thread integration
  test; `make test-e2e` runs it in addition to the workflow browser suite.
- `skills/`: operating-model enforcement and deterministic review gates.

GitHub Actions runs only credential-free CI. Use `make foundry-release` from an
authenticated local shell for Azure deployment and hosted validation.

Run the UI suite against the public frontend with
`PLAYWRIGHT_BASE_URL="<frontend-url>" make test-e2e`; the internal backend
Container App is not a browser target.

## Guarded release route

`make foundry-release` is always `app_only`: it reuses the existing PostgreSQL
database and retained public-lane dependencies. The router selects quick or
full *local validation*, not a different deployment mode. The release runs the
selected validation and Bicep build in parallel, packages fresh hosted source,
checks PostgreSQL readiness once, fans out backend/frontend/hosted-agent
deployment, verifies the Foundry-to-App-Insights connection, then gates on
smoke, hosted E2E, report-only evaluation, and correlated telemetry.

`make foundry-provision` is not a routine release fallback. It requires both
`FOUNDRY_INFRA_RECONCILIATION_APPROVED=true` and a non-secret
`FOUNDRY_INFRA_RECONCILIATION_REFERENCE` after preview review.

## Known non-blocking diagnostics

- `make up` may warn that it could not acquire an Azure CLI token (or that the
  CLI is absent) for a locally configured hosted mode; Compose still starts and
  an operator must provide `FOUNDRY_HOSTED_API_KEY` if that mode needs it.
- `foundry-postgres-readiness` may warn that database names could not be listed.
  The gate still requires the server Ready state, Azure-services firewall rule,
  and any supplied URL's TLS/FQDN validation.
- Hosted E2E may continue after an `azd ai agent invoke` nonzero exit only when
  the command produced parseable JSON; all subsequent response assertions still
  gate the run.
- The design-review skill warns when more than 20 files changed. It is a scope
  warning, not a release-gate pass or failure.
