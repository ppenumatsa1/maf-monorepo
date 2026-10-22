# Scripts

- `foundry/deploy_public_dev.sh`: authenticated local release sequence.
- `foundry/build_python_wheelhouse.sh`: builds and reuses the
  hash-verified CPython 3.13 Linux AMD64 runtime wheelhouse from
  `backend/requirements.lock`; both Python 3.13 image builds install from it
  offline.
- `foundry/preview_public_infrastructure.sh` and
  `foundry/validate_preview_output.py`: persist ignored preview output and
  reject any create/update/delete/replace operation in routine reuse mode.
- `foundry/capacity_preflight.py`: read-only exact-resource and incremental
  capacity/quota validation for app-only and reviewed full-infrastructure
  paths.
- `foundry/preflight_models.sh`: read-only validation of the exact
  Order Resolution chat, embeddings, and evaluator deployments plus regional
  quota records; it never changes model SKUs or capacity.
- `foundry/ensure_hosted_agent_rbac.sh`: idempotently converges only
  `Cognitive Services OpenAI User` for the hosted identity at the Foundry
  account scope.
- `foundry/reconcile_activity_endpoint.py`: GET-before-PATCH reconciliation
  that preserves Responses/Entra and unrelated endpoint state while adding or
  removing Activity and Bot authorization.
- `foundry/publish_teams_agent.py`: versioned Bot Bicep, Shared Microsoft 365
  package/publication, sanitized local state, and rollback-plan automation.
- `foundry/ensure_foundry_azd_defaults.sh`: initializes the selected public
  AZD environment and resets provision-time Container App images to the MCR
  bootstrap image so deleted ACR tags cannot block infrastructure creation.
- `foundry/hosted_smoke.sh`: direct Responses smoke with secret-free JSON
  evidence.
- `foundry/hosted_e2e.sh`: fresh ORD-1001 low-risk, ORD-1009 HITL
  approval/resume, and damaged-item HITL approval/resume regression. AZD 1.36
  output supplies conversation IDs and customer-facing text; workflow,
  checkpoint, approval, and event assertions come from authoritative
  PostgreSQL state rather than an embedded workflow JSON response.
- `foundry/verify_deployment.sh`: verifies exact active image digests, ACA
  topology, same-origin proxy health, hosted version/image/RBAC, App Insights,
  database URL parity, and externally managed schema mode.
- `foundry/verify_telemetry.sh`: bounded three-conversation Application
  Insights telemetry check.
- `foundry/release_evidence.py`: atomically initializes/finalizes the
  `maf-release/v1` record, records lock-safe UTC stage timings under
  `extensions.release_timing`, enforces required gates and successful timing
  completeness, verifies immutable hosted metadata and one fresh
  three-conversation evaluation window, and hashes artifacts under
  `.artifacts/releases/<release-id>/`.
- `foundry/release_migration.py`: dry-run-only inventory for legacy
  `deployment-report/` and singular `.artifacts/release/` candidates. It never
  copies or deletes sources; future deletion additionally requires live-release
  and durable-archive markers.
- `foundry/check_public_postgres_readiness.sh`: public PostgreSQL readiness.
- `playwright/`: local and hosted same-origin API/SSE browser regression suite.
- `make test-e2e-selected-thread`: focused frontend selected-thread integration
  test; `make test-e2e` runs it in addition to the workflow browser suite.
- `skills/`: operating-model enforcement and deterministic review gates.

GitHub Actions runs only credential-free CI. Use `make foundry-release` from an
authenticated local shell for Azure deployment and hosted validation.

Teams connectivity is a separate reviewed operation:

```bash
make test-foundry-activity-endpoint
make test-foundry-teams-publishing
make foundry-activity-plan
make foundry-teams-plan
```

Apply/package/publish commands require the selected public AZD environment.
Shared package and publication additionally require an interactive Azure CLI
user. These commands never add private networking or alter the browser/SSE
release path.

Each release writes fresh gitignored evidence for its own window. Legacy
evidence paths are inventory-only and are not release authority.

Source/local contract results alone are not live-release evidence. The current
parity release's reviewed Azure execution, hosted Responses/browser acceptance,
evaluation, telemetry, aggregate evidence, rollback readiness, Teams
deployment/publication, and Activity contract coverage are recorded in the
canonical ledger. Future revisions require fresh evidence.

Run the UI suite against the public frontend with
`PLAYWRIGHT_BASE_URL="<frontend-url>" make test-e2e`; the internal backend
Container App is not a browser target.

## Release route

`make foundry-release` is always `app_only`: it reuses the existing PostgreSQL
database and retained public-lane dependencies. The router selects quick or
full *local validation*, not a different deployment mode. The release runs the
selected validation and Bicep build in parallel, packages fresh hosted source,
checks exact retained resources/incremental quota and a zero-mutation preview,
checks PostgreSQL readiness, and verifies the existing project `CustomKeys`
connection and hosted RBAC. It activates the immutable hosted artifact first,
then deploys backend/frontend concurrently. Hosted deployment uses only the
literal connection placeholder. The release verifies the exact deployed
contract and gates on smoke, hosted E2E,
strict zero-failed/errored/skipped evaluation, correlated telemetry, and
aggregate secret-free evidence. Standalone `make eval-foundry` remains
report-only unless release mode or `FOUNDRY_EVAL_ENFORCE_PASS=true` is active.

`make foundry-provision` is not a routine release fallback. It is the explicit
full-infrastructure command and requires `FOUNDRY_FULL_INFRA_AUTHORIZED=true`:
bootstrap creates the complete lane, then output hydration switches the
selected local AZD environment to non-mutating reuse.
Run schema, runtime-credential, and readiness targets explicitly before the
first app release.

Rollback authority is intentionally narrower than deployment authority. The
release record permits reactivation of a previously verified hosted version
and restoration of prior backend/frontend revisions; it does not permit
shared/stateful infrastructure mutation. Teams endpoint rollback removes only
Activity and Bot authorization, while Microsoft 365 catalog removal and Bot
resource retention/deletion remain explicit governance and infrastructure
decisions.

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
