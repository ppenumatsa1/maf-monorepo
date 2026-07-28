# Public Foundry Delivery Ledger

## Current architecture

The supported hosted path is:

```text
Browser
  -> external React/Nginx frontend Container App
  -> same-origin /api and SSE proxy
  -> internal FastAPI responses-wrapper Container App
  -> managed-identity Foundry Responses agent
  -> shared PostgreSQL workflow/checkpoint/approval/event state
```

The browser never receives a Foundry endpoint credential. The wrapper creates a
Foundry `conv_...` conversation before the first request, persists that thread
identifier, dispatches the initial Responses request without remote streaming,
and resumes HITL using checkpoint-keyed `function_call_output`. Browser live
updates come from persisted PostgreSQL projections through polling and stable
native SSE; the rich stream is additive.

## Redeployment baseline

The public Foundry resources were intentionally deleted on 2026-07-28. The
target details and release evidence below are historical only and must not be
used to claim a current deployment. A clean `make foundry-release` run must
recreate infrastructure, deploy the agent and Container Apps, then produce new
smoke, E2E, evaluation, and telemetry evidence.

The delivery ledger was stale because the successful 2026-07-27 release
evidence was retained without a teardown status transition. The README and this
ledger now identify deleted resources and require fresh evidence before a live
deployment is claimed.

## Clean-provision repair (2026-07-28)

**RCA.** `infra/foundry-hosted/iac/main.bicep` declared the parent Foundry
account, ACR, Log Analytics workspace, and Application Insights component as
`existing`. After the intentional lane teardown, the deployment therefore
failed before it could create the project, role assignments, connections,
Container Apps, storage, PostgreSQL, or agent prerequisites. The evaluator also
pinned `gpt-4o-mini` / `GlobalStandard` / `2024-07-18`; the provision warning
showed that this pinned offering could not be resolved in the target region.

**Fix.** The template now manages those four named resources, creates the chat
and embeddings deployments that the hosted configuration names, and orders
their consumers through resource references: Foundry account -> deployments and
project -> roles/connections; Log Analytics -> Application Insights -> Container
Apps environment/apps; ACR -> pull identities/roles/apps; and PostgreSQL ->
database/firewall -> generated backend connection string. Existing names and
parameter overrides are preserved. Evaluator/chat/embeddings model-version
parameters now default to empty so Azure selects its current regional default;
the model name, deployment name, and capacity remain configurable. On
2026-07-28, `az cognitiveservices model list --location eastus2` reported the
current catalog's `gpt-4o-mini` `GlobalStandard` offering and
`text-embedding-3-small` version `1`; the version is deliberately not
hard-coded because the earlier pin was the failure mode.

The first non-mutating preview found the deleted Foundry account retained as an
Azure soft-deleted account, which requires the write-only `restore: true` flag.
The managed account now sets that flag through the
`restoreFoundryAccount` parameter (default `true`); this preserves the
established account name without requiring an out-of-band purge. Set
`RESTORE_FOUNDRY_ACCOUNT=false` after the account becomes active because Azure
rejects restore on an active account.

**Validation.** Bicep compilation and a non-mutating
`AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --preview --no-prompt`
must complete before any actual provision. No live provision or deployment is
performed as part of this repair.

## Provision retry corrections (2026-07-28)

The clean-provision attempt created the Foundry account/project, monitoring,
and PostgreSQL resources but exposed two template defects before the remaining
resources could finish. A Standard SKU ACR rejected the configured network
rule/bypass settings with `NetworkRuleNotSupported`; the public lane needs only
public network access, so those unsupported settings were removed while
retaining `publicNetworkAccess: 'Enabled'` and disabling the admin user.

The evaluator deployment completed, but the chat and embeddings deployment
requests overlapped on the same Foundry account and failed with
`RequestConflict: Another operation is being performed on the parent Foundry
account`. The template now serializes account mutations explicitly:
evaluator -> chat -> embeddings -> project. This is an ordering correction,
not a model substitution: all model-version parameters remain empty by default
so Azure resolves the current regional default, including when the earlier
`gpt-4o-mini` GlobalStandard availability warning is present.

Validation for this correction is Bicep compilation and the same non-mutating
AZD provision preview only; no retrying actual provision occurs in this change.

## Foundry public-network ACL correction (2026-07-28)

The next actual retry failed while updating the Foundry account with
`BadRequest: NetworkAcls is required for this resource.` The account now
declares the validated public-lane ACL shape on
`Microsoft.CognitiveServices/accounts`: `defaultAction: 'Allow'` and
`bypass: 'AzureServices'`, alongside `publicNetworkAccess: 'Enabled'`. These
are Foundry account settings only; the unsupported ACR network-rule settings
remain removed.

The restore flag is now omitted from account properties unless
`RESTORE_FOUNDRY_ACCOUNT=true`. Its source default is `false`, so normal
creation and active-account re-provisions cannot request a restore. A
soft-deleted account is restored by setting the flag to `true` for that single
provision and resetting it to `false` once the account is active.

## Container App bootstrap-image correction (2026-07-28)

The next provision completed Foundry, models, project, monitoring, and
PostgreSQL but failed creating Container Apps because the retained AZD
environment supplied `SERVICE_BACKEND_IMAGE_NAME` with a deleted ACR image tag.
Although Bicep defaults to the public MCR quickstart image, AZD environment
values override that default.

`ensure_foundry_azd_defaults.sh`, which is called by the public provision, up,
and release paths, now resets both service image variables to
`mcr.microsoft.com/k8se/quickstart:latest` before provisioning. This is the
source-of-truth clean bootstrap and does not preserve or hard-code a stale ACR
tag. The normal subsequent `azd deploy` replaces the bootstrap image with the
freshly built backend and frontend images. Validation remains Bicep/static
checks and a non-mutating provision preview only.

## Local E2E bootstrap correction

The local Foundry-public E2E target referenced the ignored `backend/.env`
directly, so a clean checkout failed before it could start its isolated Compose
stack. The target now uses `backend/.env` when a developer created one and
otherwise falls back to the checked-in non-secret `backend/.env.example`.
This keeps local E2E reproducible without reading deployment credentials.

## Previous public target (deleted)

- Resource group: `rg-maf-ora-foundry-public-dev2`
- Foundry project: `order-resolution-public-managed-dev2`
- Hosted agent: `order-resolution-hosted`
- Public frontend:
  `https://ora-public-dev2-frontend.greentree-dc9ce897.eastus2.azurecontainerapps.io/`
- Backend: internal-only Container App; it is not a browser endpoint.

## Superseded release evidence (2026-07-27)

- Local backend tests, deterministic evaluation, local Playwright, Docker
  Playwright, and the deterministic review gate passed.
- Hosted browser Playwright passed all seven workflow scenarios, including
  low-risk completion, approval/resume, damaged-item rejection, workflow
  history, and native/rich event presentation.
- Direct Foundry Responses E2E passed for low-risk and HITL approval/resume.
- Enforced Foundry trace evaluation
  `eval_e41c203d70bd4a0782778954f7d73db4` /
  `evalrun_958cceeac33848b693928863e957e41b` completed with two passed, zero
  failed, and zero errored conversations.
- Application Insights correlation verified workflow and HITL spans for the
  hosted E2E conversations.

## Monorepo redeployment blocker and fix

On 2026-07-27, the monorepo Foundry Public `azd provision --preview` showed
that `maffndevaljaq57wl77uqws` would change from
`publicNetworkAccess: Disabled` to `Enabled`. The live account was already
working with public access disabled, `allowBlobPublicAccess: false`, and
`allowSharedKeyAccess: false`; enabling its public endpoint would weaken the
proven security posture without being required for deployment.

The cause was the evaluation artifact Storage account declaration in
`infra/foundry-hosted/iac/main.bicep`, which set
`publicNetworkAccess: 'Enabled'`. It now declares `Disabled`, matching the
live account. Its existing Azure Services bypass and `defaultAction: Allow`
settings are unchanged because public network access is disabled. Provisioning
and application deployment remain blocked until a fresh preview confirms that
this public-access drift is gone.

The first monorepo `azd deploy` then failed because the clean repository does
not track the generated `infra/foundry-hosted/agent/` deployment source. This
is expected generated input, not missing application code. Running the existing
`scripts/foundry/sync_hosted_source.sh` helper recreated it from `backend/`;
the retry deployed the backend, frontend, and hosted agent successfully.

## PostgreSQL startup incident and recovery

After the monorepo deployment, backend revision
`ora-public-dev2-backend--azd-1785186052` failed activation and the frontend
`/api/health` proxy timed out. Container Apps console logs identified
`psycopg_pool.PoolTimeout` during `postgres_db.ensure_schema()`. The root cause
was the public Flexible Server `maffndpgbfscpfhjr7sp4cu` being in the `Stopped`
state; its FQDN, public-access setting, and Azure-services firewall rule were
otherwise correct.

Starting the existing server restored backend health. Hosted workflow UI checks
then passed, including the HITL approval/resume path. One manual-test case
timed out while the database recovered, but its immediate isolated retry passed
without code changes, confirming recovery latency rather than a UI or workflow
regression.

## Telemetry signal policy

The public project and both Container Apps export to the configured Application
Insights resource. FastAPI `/health`, `/api/health`, and chat SSE request spans
are intentionally excluded from request telemetry so Container Apps probes and
long-lived streams do not obscure workflow signal. Foundry `/readiness`,
invocation, model, workflow, checkpoint, and HITL spans remain observable.

Use a workflow dependency query rather than the portal's newest-first Search
list when investigating a conversation:

```kusto
AppDependencies
| where TimeGenerated > ago(6h)
| where Name startswith "workflow."
| extend thread_id = tostring(Properties["workflow.thread_id"])
| project TimeGenerated, Name, thread_id, OperationId
| order by TimeGenerated desc
```

Open an end-to-end transaction for a returned `OperationId` to inspect the
correlated Foundry, model, workflow, and HITL hierarchy.

## Clean-runner E2E dependency correction (2026-07-28)

GitHub Actions run `30370781990` failed the design-review browser gate because
the job installed Playwright but not the frontend Vite dependencies. The
isolated backend was ready, but Vite never opened its dynamic local port, so
all browser scenarios received `ERR_CONNECTION_REFUSED`.

The public design-review and quick-validation CI jobs now run `npm ci` for the
frontend. Quick validation also installs the Playwright package and Chromium
before it calls `make validate-quick`. Clean runner validation no longer
depends on ignored local `node_modules` directories.

## Provision image preservation correction (2026-07-28)

The clean-provision helper initially reset every Container App image to the MCR
bootstrap image. That is correct when apps are absent after teardown, but an
infrastructure-only provision of an active environment would replace healthy
application revisions before `azd deploy` republished them.

The helper now reads each existing Container App's active image and preserves
it in the selected AZD environment. It uses a bootstrap image only when that
app is absent, retaining both safe active-environment reconciliation and clean
teardown recovery.

## Hosted-agent clean-rebuild investigation (2026-07-28)

After clean provisioning, `azd deploy order-resolution-hosted` failed with
Foundry `ImageError: Container image not found`. The recreated ACR contained
the backend and frontend artifacts but no hosted-agent image.

Comparison with the known-good
`ppenumatsa1/maf-order-resolution-agent` branch
`feature/foundry-public` shows the same hosted-agent manifest and deployment
script, with the Foundry project scoped to `AcrPull` only. The monorepo
therefore retains that least-privilege, proven role shape; `AcrPush` is not a
known requirement for this deployment path.

**Current validation boundary.** On 2026-07-28, both the project identity and
the restored hosted agent's blueprint and instance identities were granted the
required pull roles. Backend and frontend remote builds published successfully,
but the Foundry remote code deployment still returned `ImageError` and created
no hosted-agent repository or manifest in ACR. This is a Foundry code-build
platform failure before image publication, not a missing image tag, role, or
network-policy workaround. Keep the public hosted deployment, hosted E2E,
Foundry evaluation, and telemetry gates pending until the Foundry request IDs
can be resolved by the service.

An isolated POC using the official Python hosted-agent quickstart was also
uploaded directly through `AIProjectClient.create_version_from_code` to the
same public project. The unmodified basic sample failed immediately on version
1 with the identical `ImageError`; its failed version was deleted. This
eliminates the Order Resolution source tree, its azd manifest, and its release
scripts as causes. The failure is scoped to the recreated public Foundry
project/account code-build path and requires Foundry service investigation.
