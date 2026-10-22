# Public Foundry Hosted Agent

`infra/foundry-hosted` is the only Azure deployment path defined in this
branch. It
deploys the shared MAF workflow as a public Foundry Responses+Activity agent,
an external React frontend Container App, and an internal FastAPI
Responses-wrapper Container App.

## IaC ownership boundary

The Bicep template has two explicit modes. `bootstrap` creates the complete
lane: Foundry account/project/models, ACR, monitoring, Container Apps
environment/apps, separate app identities, PostgreSQL, evaluation storage,
connections, and resource-scoped RBAC. `reuse` resolves deterministic existing
names and creates no resources, connections, or role assignments.

Evaluation storage is reachable by Foundry through the validated
selected-network/trusted-service posture: public network access is enabled,
the default network action is deny, and only the `AzureServices` bypass is
configured. Blob public access and shared-key authorization remain disabled.
Do not change storage to fully public access or disable networking without a
private endpoint.

Reuse hydration writes every required Bicep output into the selected local AZD
environment, including project/model values, monitoring and Container Apps
resource IDs, PostgreSQL FQDN, and `API_BASE_URL`/`WEB_URL`.

PostgreSQL administration is an explicit post-provision sequence. The canonical
schema is applied with the local administrator credential, a dedicated runtime
login receives DML-only grants, the runtime URL is stored only in the local AZD
environment, and readiness verifies TLS, dual authentication, database and
firewall state before an app release.

Foundry supplies and operates the agent session, file, and vector-store services.
This deployment configures none of the shared resources for those capabilities.

There are no customer-managed networking or runner resources.

The current source and local contracts do not prove that this resource graph
or the Teams extension is deployed. Live status requires a reviewed preview
and apply, exact deployment verification, channel acceptance, evaluation,
telemetry, rollback review, and a dated canonical-ledger entry.

## Public target

The target is supplied through an ignored external profile created from
`deployment/profiles/foundry-public.env.example`. The profile contains only
non-secret desired values and is validated fail-closed; no subscription,
tenant, user, resource identifier, endpoint, or live profile is tracked.
Routine app-only releases require `reuse`. Full infrastructure creation requires
an explicit reviewed preview plus `FOUNDRY_FULL_INFRA_AUTHORIZED=true`.
`make foundry-model-preflight` checks exact existing resources and computes
quota only for incremental growth.

## Authenticated local release

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE=deployment/profiles/foundry-public.env
make foundry-bootstrap
make foundry-release
```

The release script uses the change-aware deployment router, runs its selected
local validation concurrently with Bicep compilation, and accepts only
app-only authority. It verifies a zero-mutation reuse preview, exact retained
resources, PostgreSQL readiness, the runtime-secret connection, and hosted RBAC.
It then activates the hosted agent by immutable ACR digest before deploying the
backend and frontend concurrently by immutable digest. App-only never creates a
role assignment, project connection, or shared/stateful infrastructure.
The hosted definition contains only the literal project-connection placeholder,
never the resolved URL. `make foundry-verify` then checks active revisions/images, external
frontend/internal backend ingress, frontend and same-origin backend health,
hosted version/image and placeholders, App Insights, backend database-secret
parity, and externally managed schema mode. After smoke, the evaluator waits
for fresh three-conversation hosted-E2E evidence and its configured HITL trace
age; telemetry begins only after that evidence exists. `make foundry-evidence`
closes the release with one secret-free JSON report.

The router distinguishes validation depth from deployment authority. Runtime,
package, release-script, or application changes select full local validation
but still route to `app_only`. Any `infra/` change makes automatic release
ineligible and requires the explicit full-infrastructure preview and authority
path.

Infrastructure creation is a separate authorized `make foundry-provision`
operation. Apply an external bootstrap profile, review preview output, set
`FOUNDRY_FULL_INFRA_AUTHORIZED=true`, and run `make foundry-bootstrap-env`
before first creation. After successful provisioning, output hydration switches
the local environment to reuse mode.

Before an authenticated release, follow the non-mutating validation recipe and
proof template in [the deployment plan](../../.azure/deployment-plan.md). After deployment, run hosted
browser validation:

```bash
PLAYWRIGHT_BASE_URL="$(azd env get-value WEB_URL --cwd infra/foundry-hosted)" \
make test-e2e
```

## Foundry evaluation configuration

From the repository root, `make eval-foundry` resolves its evaluator endpoint
and deployment names through this nested AZD project's selected environment.
It uses an allow-list of non-secret values and does not source or display the
environment `.env` file. Check resolution without contacting Foundry:

```bash
make eval-foundry-config
```

To evaluate against another existing local environment without running
`azd env select`, use:

```bash
FOUNDRY_AZD_ENV_NAME=<environment> make eval-foundry
```

`make foundry-up` verifies the deployed project still has an
`ApplicationInsights` connection targeting the configured component. The same
check is part of `make foundry-verify`, which fails before hosted
E2E/evaluation if that prerequisite is absent or drifted.

Telemetry-reader access remains an operational prerequisite. The release path
verifies the Order-owned runtime-secret project connection and hosted
identity's required account-scoped role; it does not mutate either or add
shared monitoring roles.

For the explicit PostgreSQL sequence:

```bash
make foundry-postgres-schema
make foundry-postgres-credentials
make foundry-postgres-readiness
make foundry-runtime-connection
```

Compile before a deployment:

```bash
az bicep build --file infra/foundry-hosted/iac/main.bicep
az bicep build --file infra/foundry-hosted/iac/teams/main.bicep
```

Bootstrap uses public placeholder images only for initial Container App
creation. The app-only release scripts build uniquely tagged images, resolve
their ACR digests, deploy those immutable digest references, persist safe
gitignored component metadata, rotate the backend database secret, preserve the
internal backend/external frontend ingress boundary, and replace the
placeholders.

## Container dependency feed

The backend and hosted-agent Dockerfiles use Python 3.13 and install
`backend/requirements.lock` exclusively from a prepared wheelhouse with
`--no-index --require-hashes`. `make foundry-python-wheelhouse` downloads and
validates CPython 3.13 Linux AMD64 wheels before any package or image build.
The images retain the approved CFS `PIP_INDEX_URL`; adding online dependency
resolution to the image build is not permitted.

## Teams Activity and Shared publication

The hosted version declares both Responses 2.0 and Activity 2.0. The runtime
composes both hosts in one process, but the normal public browser topology
continues to use Responses through the internal FastAPI wrapper.

After a Teams-capable hosted version is active:

```bash
make foundry-activity-plan
make foundry-activity-apply
make foundry-teams-plan
make foundry-teams-deploy-bot
make foundry-teams-package
make foundry-teams-publish
make foundry-teams-verify-local-state
```

The Activity reconciler retains Responses, Entra, unrelated protocols, and
non-Bot authorization schemes. Shared apply adds Activity and
`BotServiceRbac`; rollback removes only Activity and Bot authorization.

`iac/teams/main.bicep` deploys a single-tenant Azure Bot Service,
`MsTeamsChannel`, and Bot diagnostics against the existing Log Analytics
workspace. It adds no VNet, private endpoint, private runner, or private DNS.
Publication metadata is reviewed in
[`teams-publication.json`](teams-publication.json). Generated packages and
sanitized local state remain under ignored `.artifacts/teams-publication/`.
Shared package/publish operations require an interactive Azure CLI user.

Microsoft does not document a Foundry unpublish API. Use
`make foundry-teams-rollback-plan` and `make foundry-activity-rollback`, remove
the catalog entry through Microsoft 365 governance, and handle Bot retention or
deletion only through a reviewed ARM/Bicep lifecycle action.
