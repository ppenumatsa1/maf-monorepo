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
- `skills/`: operating-model enforcement and deterministic review gates.

GitHub Actions runs only credential-free CI. Use `make foundry-release` from an
authenticated local shell for Azure deployment and hosted validation.

Run the UI suite against the public frontend with
`PLAYWRIGHT_BASE_URL="<frontend-url>" make test-e2e`; the internal backend
Container App is not a browser target.
