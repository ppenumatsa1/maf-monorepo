# Azure App-Hosted Package

This is the only Azure deployment package. It deploys the React frontend and
FastAPI/MAF backend as Container Apps, with PostgreSQL, ACR, Log Analytics,
Application Insights, and Foundry model/evaluation resources.

FastAPI remains the sole application host. Foundry is limited to model
inference and report-only evaluation; do not add agent, Responses, manifest,
runner, or other application-hosting surfaces.

## Status and target

**Source configuration only.** The resource names, outputs, and Bicep files
describe intended deployment; they do not prove that a current revision or
endpoint is live. A release record must contain fresh, non-secret smoke,
hosted E2E, report-only evaluation, and telemetry-correlation evidence.

| Setting | Value |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Region | North Central US (`northcentralus`) |

North Central US is required because Azure PostgreSQL is offer-restricted in
East US for this target.

Foundry chat, embeddings, and evaluator deployment SKUs are parameterized.
Chat/evaluator bootstrap defaults use `Standard`; `text-embedding-3-small`
uses `DataZoneStandard` because North Central US does not support its
`Standard` SKU. Do not default any deployment to `GlobalStandard` while the
checked `gpt-4.1-mini` quota is fully consumed.
Container Apps quota-helper access is not assumed. Treat the subscription
preview as the capacity gate and stop on any quota error.

## Layout

- `iac/main.bicep`: subscription-scope AZD entry point.
- `iac/modules/`: Azure resource modules.
- `iac/main.parameters.json`: AZD parameter binding.
- `runtime/.env.example`: app-hosted runtime settings.
- `runtime/smoke-test.sh`: backend/frontend and ORD-1001/ORD-1009 checks.

This package participates in a hybrid layout: tracked profiles and deployment
contracts stay in `deployment/profiles/`, `.azure/deployment-plan.md`, and
`docs/design/`; each authorized release writes its generated evidence bundle to
`.artifacts/releases/<release-id>/`.

## Runtime settings

The backend uses:

- `WORKFLOW_MODE=maf_sdk`
- `STORE_PROVIDER=postgres`
- `MEMORY_PROVIDER=postgres`
- Azure PostgreSQL managed-identity variables
- `FOUNDRY_PROJECTS_ENDPOINT`, `FOUNDRY_MODEL_DEPLOYMENT_NAME`, and
  `FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME`
- Application Insights settings with `OTEL_RECORD_CONTENT=false`

When model configuration is unavailable, deterministic triage remains within
the same MAF workflow. HITL rules remain deterministic.

## Validate before any deployment

Follow `.azure/deployment-plan.md`. At minimum, run the local test, evaluation,
E2E, Docker, design-review, Bicep/AZD, IaC, and Azure readiness gates before
deployment. Do not change the deployment-plan status until current code and IaC
evidence exists.

Normal deployment is app-only (`make release-app`) and preserves PostgreSQL.
For a fresh subscription, `make prepare-bootstrap` validates the tracked
target-only profile and writes required untracked inputs to the selected local
AZD environment. The template requires explicit images and has no tracked
deployable placeholder parameter file. After bootstrap, `make
prepare-steady-state` verifies the PostgreSQL identities and switches the AZD
environment to `steadyState` only after deleting and verifying removal of the
exact `allow-bootstrap-runner` firewall rule.
Use `make release-infra-preview` to inspect an infrastructure reconciliation
without changing resources. `make release-infra-reconcile` is explicit
execution intent and independently runs the same guarded what-if immediately
before apply; it refuses any PostgreSQL entry because steady-state IaC excludes
the server and database. Container App modules are also bootstrap-only, so
reconciliation cannot overwrite MCP secrets, URLs, app configuration, or
revisions. Do not call reconciliation because an
app, Dockerfile, frontend runtime setting, or Bicep file changed. The backend
release image must retain the approved CFS `PIP_INDEX_URL`, and the frontend
build must remain compatible with its Alpine/musl runtime.
There is no hosted-agent deployment stage in this package; Foundry remains
limited to model inference inputs and report-only evaluation outputs.

After an authorized deployment, run:

```bash
infra/azure-apphosted/runtime/smoke-test.sh "$API_URL" "$WEB_URL"
```

Set `EXPECT_TRIAGE_MODE=foundry_models` only when verifying model inference.
The complete app-only release uses `make release-app`; its validation wrapper
always attempts final aggregation, so failed gates leave a failed
`evidence/release-evidence.json` in the current release directory.
