# Public Foundry Delivery Ledger

## Evidence rule

This is the canonical, reviewable source for Order Resolution public-lane
release evidence. Configuration, ignored local timing artifacts, and design
documents explain the intended route but never prove a deployment. A release
claim requires a dated entry with the relevant smoke, hosted E2E, evaluation,
and telemetry facts. Keep MCP/RAG execution behind the backend; record only
safe identifiers and aggregate outcomes here.

## 2026-08-10 - Public v18 rationale-evidence correction

**Observed release state.** The app-only release deployed the public backend
and hosted agent `order-resolution-hosted` version 18. Hosted smoke passed,
including the low-risk scenario, and the explanation response returned the
concrete order, issue, status, policy, action, amount, and approval factors
introduced for the v17 evaluation remediation.

**Evidence blocker.** The hosted E2E assertion still expected the retired
generic rationale wording. It therefore stopped the release before the fresh
trace evaluation and telemetry gates, despite the response satisfying the new
rationale contract. The assertion now requires the concrete factors instead
of accepting a generic completed response. Its shell contract checks,
deterministic evaluation, and focused evaluator tests passed. A new evidence
run is required; version 18 does not have a completed fresh E2E/evaluation/
telemetry record.

## 2026-08-10 - Public app-only quick-validation path correction

**Observed issue.** The app-only release stopped before deployment because
`validate-quick` invoked the selected-thread E2E target from
`scripts/playwright`, while that target is owned by the public project
Makefile. No application, Foundry agent, or infrastructure resource changed.

**Fix and validation.** The E2E recursion now re-enters the project Makefile
before it changes to the Playwright directory. The focused `validate-quick`
contract passed with a stubbed npm runner, confirming the workflow and
selected-thread targets execute from their owning directories. A fresh
app-only release is still required; do not infer smoke, hosted E2E,
evaluation, or telemetry evidence from this local correction.

## 2026-08-09 - Public lane v17 app-only release

**Released lane**

- Hosted agent `order-resolution-hosted` version 17 was deployed together with
  the existing public frontend and internal backend Container Apps. The route
  remained app-only and did not reconcile retained Foundry, PostgreSQL, ACR,
  monitoring, or shared network resources.
- PostgreSQL readiness now uses the current Azure CLI `--server-name` argument.
  The release script keeps the runtime database URL out of isolated local
  validation, while retaining it for the later runtime deployment steps.
- Browser E2E assertions now verify the structured `completed` status rather
  than obsolete response wording.

**Release evidence**

- Hosted smoke passed for the delayed-order scenario.
- Fresh hosted Responses E2E passed for two conversations.
- Application Insights correlated 30 rows across those E2E conversations.
- Trace evaluation
  `eval_a1a3de3296b84b69ae80ada8a9d0c993` /
  `evalrun_a8cc9b11ed064c198edb592cbaebbf96` completed with one passed and
  one failed result. The release command completed because the evaluator
  returned a completed run, but the failed quality result requires follow-up
  before treating the evaluation as a passing quality gate.

## 2026-08-07 - Public lane v15 response-quality remediation and release

**Released lane**

- Hosted agent `order-resolution-hosted` version 15 (v15) is the released
  public lane.
- The release retained the same-origin browser -> internal API wrapper ->
  managed-identity Foundry Responses topology, PostgreSQL durable state, stable
  native SSE, and checkpoint-keyed HITL semantics. AG-UI and CopilotKit remain
  optional redacted, read-only selected-thread views; they are not another
  workflow path.
- The release route was app-only. It reused existing retained resources and did
  not treat a deployment as approval to recreate PostgreSQL, Foundry, ACR,
  monitoring, evaluation storage, or shared connections.

**Initial evaluation finding**

- Trace evaluation `eval_0f6f06094155491aaa3ceb5d76d0ca44` /
  `evalrun_3f441ccace3e4791ae6cfc8cb1f2c4dd` completed with one passed and one
  failed conversation. The failed `task_completion` result scored `0` against
  threshold `1`: it recognized that the delayed order received a partial refund
  but found no actionable refund-process follow-up or confirmation. Coherence
  passed for both conversations.

**Remediation and replacement evidence**

- The canonical response was corrected to include the missing refund follow-up
  and redeployed; the replacement hosted smoke passed.
- Fresh hosted Responses E2E started at `2026-08-07T00:22:55Z` and generated
  its evidence at `2026-08-07T00:23:59Z`. It passed for
  `conv_18b80d5aa4a1216d00EJjgEpx0KoXLXNnHkVNsI8KlXzcl9bNV` and
  `conv_51f7aa79133a4d2d00j1sCmrukUzTd22H6JgOODo7mEhtn50xx`.
- Replacement trace evaluation
  `eval_b839dfa1132c49c0a1112ceee5dc5a09` /
  `evalrun_dc5a2cb72bca4128bbe4a8758377bc43` completed with 2 passed, 0
  failed, and 0 errored conversations. It evaluated those same two
  conversations after an `86.750592` second trace-materialization wait and
  reported explicit `completed` status.
- Application Insights verification correlated 97 rows across the two
  replacement E2E conversations with zero exception rows.

**Learning**

- The evaluation remediation is response-quality work: preserve the configured
  task-completion threshold and provide the required actionable follow-up
  rather than lowering the threshold to mask a response gap.
- Fresh E2E evidence is a dependency, not a fixed delay. The evaluator must
  retain the HITL trace-age wait and explicit completion check; telemetry must
  correlate only the current release's E2E conversations.

**Scope note**

- This entry proves the hosted smoke/Responses E2E/evaluation/telemetry gates
  listed above. It does not invent a browser Playwright identifier that is not
  recorded here. Browser regression remains a required release gate and is
  documented in `docs/manual-testing.md`.

## 2026-08-06 - Existing-environment IaC drift remediation (local validation complete)

**Finding**

Prior preview analysis identified that the Bicep template unconditionally owned
shared retained resources in `rg-maf-ora-foundry-public-dev2`: the Container
Apps environment, ACR and its policy, Foundry account/project/model
deployments, monitoring, Foundry connections, evaluation storage, and
PostgreSQL. Reapplying those declarations could change shared security,
connection-sharing, model, monitoring, or database state even when the release
only needed to publish this public lane's applications.

**Fix**

- Replaced the required ACR, Container Apps environment, Foundry account,
  Foundry project/model deployments, and Application Insights declarations with
  existing dependencies. Removed management of PostgreSQL, evaluation storage,
  monitoring configuration, Foundry connections, shared ACR policy, and their
  shared-resource RBAC.
- Retained only this lane's frontend/backend Container Apps, registry-pull
  identity, and their required resource-scoped `AcrPull` and Azure AI User
  assignments. The existing database is now represented only by the secure
  runtime connection-string input; no database administrator credential is
  accepted by Bicep.
- Changed the release router so all automatic routes are `app_only` while
  validation remains quick or full as appropriate. Infrastructure provision
  requires both `FOUNDRY_INFRA_RECONCILIATION_APPROVED=true` and a non-secret
  `FOUNDRY_INFRA_RECONCILIATION_REFERENCE`.

**Validation and status**

- Local Bicep compilation, parameter JSON parsing, shell syntax checks, router
  execution, and Make dry-runs completed. No Azure provision, deployment,
  package, or preview was run, and no secret values were displayed.
- This entry reflects the local remediation checkpoint. The later 2026-08-06
  authorized non-mutating preview and package validation are recorded in
  `.azure/deployment-plan.md`; the subsequent v15 hosted evidence is recorded
  above. Neither result authorizes an unreviewed infrastructure reconciliation.

## 2026-08-06 - Release DAG and package-governance implementation (evidence pending)

**Change**

- Defined the public release DAG as concurrent selected validation plus Bicep
  build, a change-aware `app_only` router with independent validation, one shared PostgreSQL
  readiness gate, independent backend/frontend/hosted parallel deployment,
  smoke followed by evaluation/E2E overlap, and telemetry only after fresh E2E
  evidence.
- Added a fresh `azd package --no-prompt` gate after hosted-source sync and
  excluded nested `__pycache__` directories from the generated hosted context.
- Standardized ignored local `deployment-report/` timing evidence and added the
  Azure-validation proof template in `.azure/deployment-plan.md`.

**Learning expectations**

- A completed release entry must record the router decision, package freshness,
  each parallel deployment leg's duration/result, and whether an explicit infrastructure
  reconciliation approval was genuinely needed.
- Record the E2E evidence timestamp, evaluator minimum trace-age delay, and
  explicit evaluation completion status. This makes HITL resume trace
  materialization observable rather than relying on a fixed release delay.
- Record telemetry only after its E2E evidence exists, including correlated
  workflow identifiers and exception count. Local ignored reports are timing
  aids only; the ledger is the reviewable source of truth.
- Any unexpected database, RBAC, public-access, or secret-handling change is a
  stop condition, not a reason to bypass a gate.

**Release status**

- Documentation and release-governance implementation only. No local
  validation, package validation, Azure preview, provision, deployment, smoke,
  hosted E2E, evaluation, or telemetry verification is claimed by this entry.

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

## Historical teardown and clean-provision baseline

The public Foundry resources were intentionally deleted on 2026-07-28. The
target details and release evidence below describe that historical recovery
only. They must not be used to claim a current deployment or to select the
current deployment route. The v15 public lane uses the retained-resource,
app-only route defined in `.azure/deployment-plan.md` and has the fresh evidence
recorded above.

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

## Hosted-agent remote-build failure and container release fix (2026-07-28)

**RCA.** After clean provisioning, Foundry source-code deployment
(`dependency_resolution: remote_build`) consistently failed with
`ImageError: Container image not found`, before creating a hosted-agent
repository or manifest in ACR. The same failure reproduced with the unmodified
official Python hosted-agent quickstart uploaded through
`AIProjectClient.create_version_from_code`, so it was not caused by Order
Resolution source, the legacy agent manifest, or its release script.

The current hosted-agent troubleshooting guidance requires the Foundry project
identity to have `Container Registry Repository Reader` and ACR to enable
`azureADAuthenticationAsArmPolicy`. The public template declares both, plus
`AcrPull`: removing `AcrPull` caused a fresh image version to fail with the
service's explicit `workspace managed identity has AcrPull` error. This is a
current Agent Service compatibility requirement. These settings did not repair
the Foundry remote source-build path, but a known-present image of the official
sample immediately reached `active`. This isolates the remaining failure to
the platform source-build path, not project image pull access.

**Fix.** The public lane now uses a reproducible container release:
`sync_hosted_source.sh` creates the generated agent context,
`Dockerfile.hosted` starts the adapter as `python -m foundry.main`, ACR builds
that context, and `deploy_hosted_container.py` creates the Foundry version with
the image and required non-reserved environment variables. `make foundry-up`
uses `azd` only for infrastructure and Container Apps, then invokes this image
release. The deployment script writes the active SDK version to the AZD
environment so `azd ai agent show` remains accurate. The standalone
`agent.yaml` source-build definition was removed.

**Validation.** The direct official source-code POC still failed as expected;
the direct image POC became active and completed `ORD-1001`. The repository
release then built
`maffndacrpubdev2eus2.azurecr.io/order-resolution-hosted` and activated
`order-resolution-hosted` version `14`. A Responses smoke request completed
`ORD-1001` through Foundry Models and the Azure PostgreSQL FQDN (conversation
`conv_ad0825e2b0ac6dc400W59cDlBuRk8Km64lb5pFzMYMaYWzoppD`, trace
`3ae160e935d56a643fd1d2204c2dcacf`). Disposable POC agents/images and the
temporary blueprint role were deleted.

## Public release gate completion (2026-07-28)

The clean public release completed all required runtime gates with fresh
evidence:

- Deployed browser E2E passed all 7 scenarios, including low-risk completion,
  high-risk approval/resume, rejection escalation, workflow history, and the
  manual test panel.
- Hosted Responses E2E completed low-risk, multi-turn continuity, and
  high-risk approval/resume. The low-risk conversation was
  `conv_533cb6371aeafb4300trdXELCjbKQzOJvW1bL6WTMKPoSOhm1V`; the approved
  high-risk conversation was
  `conv_a77ea962fae1664c00s4H2GgqB00zhP8tKJAGOqM14PJJ1QB1C`.
- Enforced Foundry trace evaluation
  `eval_ba88f785636644758e0027e8be963ed2` /
  `evalrun_9f4964e7e8f14ebdbbec85eb549c4112` completed with 2 passed, 0
  failed, and 0 errored conversations using `task_completion` and
  `coherence` evaluators.
- Application Insights telemetry validation found 51 correlated rows for the
  two hosted E2E conversations and no exception rows.

The obsolete remote source-build fallback was removed with `agent.yaml`. The
remaining compatibility and resilience behavior is intentional and remains:
the AgentServer header shim supports the deployed package combination; the
deterministic model path supports local operation without Foundry settings; and
the MCP/RAG fallbacks preserve hosted workflow behavior while no public remote
MCP/RAG dependency is configured. Removing any of those paths would change a
supported runtime contract rather than eliminate an unnecessary fallback.
