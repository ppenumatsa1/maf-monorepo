# Public Foundry Hosted Agent

`infra/foundry-hosted` is the only Azure deployment path in this branch. It
deploys the shared MAF workflow as a public Foundry Responses agent, an external
React frontend Container App, and an internal FastAPI Responses-wrapper
Container App.

## IaC ownership boundary

This deployment requires existing, retained public-lane dependencies. Bicep
references—but does not configure or recreate—the Container Apps environment,
ACR, Foundry account/project/model deployments, and Application Insights
component. Existing Foundry connections, evaluation storage, monitoring
configuration, and their RBAC remain outside this template.

The only deployable resources retained in Bicep are this lane's external
frontend and internal backend Container Apps, their lane-specific registry-pull
identity, and the two resource-scoped assignments required by those apps:
`AcrPull` for the pull identity and Azure AI User for the backend identity at
the existing project scope. The existing PostgreSQL server and `maf_workflow`
database are never represented as Bicep resources; the backend receives the
operator-supplied TLS connection string as a Container Apps secret.

Foundry supplies and operates the agent session, file, and vector-store services.
This deployment configures none of the shared resources for those capabilities.

There are no customer-managed networking or runner resources.

The configured public frontend FQDN is
`https://ora-public-dev2-frontend.greentree-dc9ce897.eastus2.azurecontainerapps.io/`.
It is an existing-resource target, not evidence of a currently live revision.
The backend FQDN is internal by design and must not be used as a browser API
base URL.

## Public target

- Resource group: `rg-maf-ora-foundry-public-dev2`
- azd environment: `foundry-public-dev2`
- Project: `order-resolution-public-managed-dev2`
- Agent: `order-resolution-hosted`

## Authenticated local release

```bash
AZURE_SUBSCRIPTION_ID="<subscription-id>" \
RUNTIME_DATABASE_URL="postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/maf_workflow?sslmode=require" \
make foundry-release
```

The release script uses the change-aware deployment router, runs its selected
local validation concurrently with Bicep compilation, and always takes the
app-only route by default. It fresh-syncs and packages the hosted
context, checks the existing PostgreSQL target once, and deploys the backend,
frontend, and hosted agent independently. After smoke, the evaluator waits for
fresh hosted-E2E evidence and its configured HITL trace age; telemetry begins
only after that E2E evidence exists. It reports completion only after both
evaluation and telemetry gates succeed. The workflow reuses the existing
database and never authorizes a destructive PostgreSQL action.

An actual infrastructure reconciliation is exceptional. It requires both
`FOUNDRY_INFRA_RECONCILIATION_APPROVED=true` and a non-secret
`FOUNDRY_INFRA_RECONCILIATION_REFERENCE`; without both, `make
foundry-provision` refuses before invoking Azure. The approval must cover a
reviewed non-mutating preview of the fixed target.

Before an authenticated release, follow the non-mutating validation recipe and
proof template in `.azure/deployment-plan.md`. After deployment, run hosted
browser validation:

```bash
PLAYWRIGHT_BASE_URL="https://ora-public-dev2-frontend.greentree-dc9ce897.eastus2.azurecontainerapps.io" \
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
`ApplicationInsights` connection targeting the configured component. It fails
before hosted E2E/evaluation if that prerequisite is absent or drifted.

Telemetry-reader and Foundry-connection access are existing operational
prerequisites. The release path does not add RBAC assignments to shared
monitoring or Foundry resources.

For an infrastructure-only PostgreSQL check:

```bash
AZURE_SUBSCRIPTION_ID="<subscription-id>" make foundry-postgres-readiness
```

Compile before a deployment:

```bash
az bicep build --file infra/foundry-hosted/iac/main.bicep
```

Before an approved `make foundry-provision`,
the shared AZD environment bootstrap resets both `SERVICE_*_IMAGE_NAME` values
to `mcr.microsoft.com/k8se/quickstart:latest`. This prevents a retained
environment from referring to a deleted ACR/tag during Container App creation.
The following `azd deploy` builds and replaces both bootstrap images with the
published application images.

## Container dependency feed

The backend and hosted-agent Dockerfiles set
`PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`, the approved
CFS package feed. Keep that feed unchanged for release-image dependency
installation; a package-feed change is a full-validation surface, not a
routine app-only edit.
