# Private Foundry Deployment Evidence

This document records the current private deployment posture and release
evidence. Superseded deployment history and retired topology details are not
part of the operating record.

## Shared authoritative drift decision (2026-08-07)

**Evidence.** Full-IaC preview run `31198356080` reported shared authoritative
drift in the VNet/subnets, ACA environment, Foundry account/project/models,
ACR, Cosmos, Application Insights, and Search.

**Decision.** The preview is not deployment evidence. No full Bicep apply,
shared-resource reconciliation, PostgreSQL lockdown, or application deployment
success is claimed from this run. Full bootstrap/reconciliation is blocked
until the responsible owners review the changes and explicitly approve the
intended state for every shared resource.

**Safe release boundary.** A routine app-only release may change only existing
ACA backend/frontend revisions and the existing hosted agent, while validating
the existing private dependencies. It must not invoke full Bicep, accept or
repair the reported drift, or change PostgreSQL access. PostgreSQL lockdown is
a separate, explicitly confirmed operation that requires a fresh generated
proof of ACA and hosted-agent connectivity to the canonical FQDN.

**Implementation.** The protected app-only workflow runs
`make foundry-app-only-release`: its read-only preflight verifies the selected
private topology, five required Foundry project connections, and the project
identity's private-ACR roles before it deploys existing ACA revisions and a
hosted-agent version. It then confirms active ACA revisions use the selected
private ACR. The workflow contract rejects full Bicep, connection/RBAC
reconciliation, connectivity proof, lockdown, and evidence collection from
this release class.

**Open blocker/question.** Who owns and approves the intended state for each
previewed shared resource, and which differences (if any) are authorized for
reconciliation? Until that decision is recorded, do not progress a full-IaC
operation. No deployment was performed by this documentation update.

## Foundry Private selected-thread implementation and local evidence (2026-08-07)

**Delivered implementation.** Coordinated private-lane work completed the
redacted, optional selected-thread AG-UI/CopilotKit implementation, strict
frontend quality tooling, focused E2E coverage, and accompanying skills and
documentation. The implementation preserves the private topology and does not
create a second workflow path.

**Invariants captured.**

- The sequential MAF workflow, stable native SSE event types, durable
  PostgreSQL history, and checkpoint-keyed HITL pause/resume remain the
  operator source of truth.
- AG-UI and CopilotKit are additive read-only projections of one existing
  selected thread. They cannot start, resume, approve, reject, or otherwise
  mutate a workflow.
- The selected runtime integration is CopilotKit
  (`@copilotkit/react-core`), not the GitHub Copilot SDK. Only `threadId` is
  meaningful bridge input; compatible messages, state, tool, context, and
  forwarded-property inputs are discarded.
- Projections may expose only safe lifecycle/tool labels, validated checkpoint
  IDs and approval decisions, and generic terminal/error text. Order/customer
  and policy data, policy evidence, MCP/RAG content, tool arguments/results,
  prompts, model output, reviewer comments, checkpoint payloads, credentials,
  and secrets remain backend-only.
- The external frontend -> same-origin proxy -> internal FastAPI wrapper ->
  private Foundry Responses/PostgreSQL topology, dedicated ACA subnet,
  private data planes, managed identity, and connectivity-proof/lockdown
  controls are preserved.

**Local validation evidence.**

- 128 tests passed.
- The deterministic evaluation completed 10/10.
- Seven workflow E2E cases and four selected-thread E2E cases passed.
- The design-review gate passed.

**Protected release status.** The protected `vm-maffnd-runner` deployment has
not run for this implementation. Consequently, hosted E2E, Foundry evaluation,
and telemetry evidence have not run and no current Azure/private release is
claimed. Record those dated, non-secret results here only after the protected
release path completes.

**Release execution blocker (2026-08-07).** Deployment was explicitly
authorized, but the mandatory Azure validation workflow could not run because
this session received `Permission denied and could not request permission from
user` when it attempted to execute the installed validation workflow script,
before any preflight action. This is a session/tool-access failure, not an
Azure Policy, subscription RBAC, Bicep, or resource validation failure; the
root cause cannot be established while the validator is inaccessible. No
direct `azd` or Azure command was substituted for that gate. The protected
release remains pending until the validation workflow can execute and hand off
to the existing `vm-maffnd-runner` path.

## Redeployment baseline

The private Foundry resources were intentionally deleted on 2026-07-28. All
2026-07-27 target details and validation records in this document are
historical only and cannot be used to claim a live deployment. A fresh
private-runner release must produce a current connectivity proof, hosted E2E,
enforced evaluation, and telemetry evidence after PostgreSQL lockdown.

## Soft-deleted private Foundry account recovery (2026-07-28)

**Root cause.** Clean-room runner recovery reached the retained private AZD
environment but Azure rejected the soft-deleted
`mafprv0722v3ai4aiw7fw5gjdo4` account with `FlagMustBeSetForRestore`. The
private account resource used an API schema without the parent-account
`restore` setting, and its parameters/default helper could not supply one.

**Precise fix.** Private `main.bicep` now uses
`Microsoft.CognitiveServices/accounts@2025-06-01` and parameterizes
`restoreFoundryAccount`, including it on the parent account resource.
`main.parameters.json` maps `RESTORE_FOUNDRY_ACCOUNT`, while the retained AZD
default helper sets it to `true` for the current intentional teardown without
overriding a later explicit `false` after purge. The runner-recovery target
runs that helper before its `main.bicep` provision path. No network control,
ACR setting, or PostgreSQL firewall behavior changed.

**Intended validation evidence.** Static validation checks the account schema,
restore parameter, parameters mapping, default helper, and recovery target
ordering. Bicep must compile and the selected private AZD environment must
complete `azd provision --preview` before an authorized operator runs any
actual provision. No actual Azure provision was performed for this fix.

**Preview outcome.** On 2026-07-28 the selected private environment accepted
the restore setting and advanced past the former `FlagMustBeSetForRestore`
validation. Its what-if preview then stopped at
`ServerStoppedError` because PostgreSQL server `maffndpgv20722` is stopped.
Starting that server is a separate operator action; it was not performed by
this change.

## Staged Foundry connection and private-endpoint recovery (2026-07-28)

**Root cause.** A clean recovery created the Foundry account/project and
attempted `orderresolutionruntimesecrets` and `ApplicationInsights` in the
same deployment. Foundry had not finished propagating the restored project
managed identity needed to store those protected connection credentials, so
the platform reported an Azure Key Vault MSI-token failure. The same run
encountered `OperationNotAllowedWhenLastOperationTypeIsDelete` while Azure was
still deleting the prior PostgreSQL private endpoint.

**Precise fix.** Core provisioning now sets
`MANAGE_PROJECT_CONNECTIONS=false`, which preserves the private account,
project, managed identity, endpoints, and pre-capability-host RBAC without
attempting connection secrets. The deploy stage runs
`make foundry-project-connections`, enabling the existing connection modules
only after the project identity path exists. The project principal is sourced
directly from `foundryProject`, pre-RBAC assignments now precede project
connections, the runtime secret connection waits for completed project
connections, and the project capability host waits for those connections.
No connection, private endpoint, or security control was removed.

**Retry handling.** A managed-identity/Key Vault token error remains a
fail-closed signal to wait for propagation and retry
`make foundry-project-connections`. A PostgreSQL private-endpoint delete-in-
progress error likewise requires waiting for Azure to finish deletion and
retrying the staged provision. Neither condition authorizes public access,
firewall exceptions, administrator credentials, or connection removal.

**Intended validation evidence.** Static validation verifies the staging
targets, deploy ordering, direct project identity source, RBAC dependencies,
and gated runtime/capability-host connections. Bicep compilation must pass
before a future private-runner retry. No Azure provision was run for this fix.

## Monorepo deployment access blocker

On 2026-07-27, an application-only deployment initiated from the operator host
could not publish to `mafprv0722v3acr4aiw7fw5gjdo4`. The registry correctly
rejected the public operator IP with HTTP 403. This is expected private ACR
network enforcement, not an identity or application failure.

The private monorepo deployment must run from the VNet-connected
`foundry-private-v2` runner, which has private registry access and retains the
selected `foundry-private-env` AZD environment. No ACR firewall exception,
public endpoint, or admin-user workaround is permitted.

## Private runner recovery correction (2026-07-28)

**Root cause.** The clean-room recovery target `make foundry-access-path`
referenced `iac/access-path.bicep` and an `rg-maf-ora-ni-eus-07080910` default
that no longer exist. The retained `rg-maf-ora-foundry-v2` environment already
contains the source-of-truth `main.bicep` integration for
`private-runner-access.bicep`, but the target did not use its selected AZD
environment or parameters. In addition, the registration script defaulted to
the obsolete `foundry-private` label rather than the release-only
`foundry-private-v2` label.

**Precise fix.** `foundry-access-path` now requires an explicit nonempty
`RUNNER_SSH_PUBKEY_PATH`, selects and preflights `foundry-private-env`, writes
the existing private-runner/VM and SSH-key AZD parameters, and executes
resource-group-scoped `azd provision` through `main.bicep`. It no longer
references a missing template or separate resource group. The recreated VM is
private, reached through Bastion, and must register with the
`foundry-private-v2` label before it can dispatch releases. No public
ACR/firewall exception was added.

**Intended validation evidence.** Static validation confirms the target's
explicit key guard, selected environment, preflight, private-runner parameters,
and absence of the stale template/resource-group references. The runner
registration default is checked for `foundry-private-v2`. An authorized future
recovery must run the target, register the VM through Bastion, and pass the
GitHub runner readiness check before any release dispatch. No Azure deployment
was performed while applying this correction.

## Soft-deleted Foundry account recovery (2026-07-28)

**Root cause.** The intentionally deleted private Foundry account name was
retained by Azure, so a clean recovery failed with
`FlagMustBeSetForRestore`. The initial recovery configuration also retained the
restore flag after the account became active, which would attempt an invalid
second restore on a later provision retry.

**Precise fix.** The account supports a parameterized restore property that is
emitted only while `RESTORE_FOUNDRY_ACCOUNT=true`. The private defaults helper
detects an already active account from the selected project endpoint and
clears that environment flag before the next provision. This preserves the
one-time soft-delete recovery while making subsequent core or staged
connection provisions idempotent.

## Connection-staging entrypoint correction (2026-07-28)

The convenience `foundry-up` and runner-recovery targets called `azd`
directly while project connections defaulted to enabled. That bypassed the
connection-free core stage and could reproduce the Foundry Key Vault
managed-identity timing failure during clean recovery.

`foundry-up` now executes core provision, staged connections, and hosted-agent
deploy in order. Runner recovery disables project connections because it only
establishes private management access; the protected deployment workflow
enables them after identity/RBAC propagation. No network control is weakened.

## Release automation correction (2026-07-28)

**Root cause.** The private provision, deployment, and observability workflows
used different concurrency groups, so they could overlap. The deployment
workflow made hosted-agent refresh and release evidence optional, omitted the
required connectivity-proof and PostgreSQL-lockdown steps, and exposed an
administrator-password repair option. `make foundry-release` likewise skipped
the hosted-agent deploy unless `FOUNDRY_REFRESH_HOSTED_AGENT=true` was supplied.
After all deployments were deleted, those optional branches could leave a
recreated environment without the hosted agent or its required release
evidence.

**Precise fix.** All three workflows now serialize on
`order-resolution-private-release` and retain the
`foundry-private-v2` runner plus its selected AZD environment. The deployment
workflow requires both deployment and explicit lockdown confirmation, then
unconditionally deploys backend/frontend and the hosted agent, generates fresh
ACA/hosted-agent connectivity proof, performs fail-closed PostgreSQL lockdown,
and collects hosted E2E, enforced Foundry evaluation, and telemetry evidence.
The password-repair and optional evidence/refresh paths were removed.
`make foundry-release` now runs `make test` and always invokes
`foundry-deploy` before proof and lockdown.

**Intended validation evidence.** Static validation must show the shared
concurrency group, required ordered deploy targets, and absence of bypass
inputs; workflow YAML and changed shell assets must parse. The sole local
private validation is `make test`. A future manually confirmed private-runner
release must produce the fresh connectivity-proof artifact, hosted E2E
conversation evidence, an enforced zero-error Foundry evaluation, and
correlated telemetry. No Azure resources were deployed while making this fix.

## Current topology

```text
Browser
  -> external frontend Container App
  -> same-origin /api and SSE proxy
  -> internal FastAPI Container App
  -> managed identity and private DNS
  -> private Foundry Responses hosted agent
  -> private PostgreSQL workflow state
```

Only the frontend has external ingress. The Container Apps environment uses a
dedicated VNet-integrated subnet that is distinct from the Foundry agent-host
subnet. Backend, Foundry, PostgreSQL, ACR, and application data planes remain
private.

## Superseded private evidence (2026-07-27)

- Private-runner provisioning and application deployment completed.
- The active frontend and internal backend Container App revisions are healthy;
  frontend health and same-origin `/api/health` both returned HTTP 200.
- Hosted smoke and browser E2E completed for low-risk resolution, high-risk
  HITL/resume, and damaged-item HITL/resume scenarios.
- The private hosted trace evaluation completed with zero errored items.
- Correlated Application Insights telemetry was recorded for all hosted E2E
  conversations.

## Telemetry noise verification (2026-07-27)

Application deployment run
[`30284034863`](https://github.com/ppenumatsa1/maf-order-resolution-agent/actions/runs/30284034863)
refreshed the private backend and hosted agent, then completed smoke, hosted
E2E, trace evaluation, and telemetry verification. A live frontend Playwright
run completed all seven scenarios against the external frontend.

The post-deployment Application Insights query window contained zero
`/api/workflows` request rows while retaining 68 correlated workflow spans,
including model, checkpoint, HITL wait/resume/response, resolution, and output
spans. Browser workflow-history and detail polling are therefore absent from
the transaction view without suppressing end-to-end workflow visibility.

## Telemetry contract

The private project-level `ApplicationInsights` connection is non-shared and
uses the configured protected credential. Hosted agents consume only Foundry's
native `APPLICATIONINSIGHTS_CONNECTION_STRING` injection. Do not add a runtime
connection-string alias, instrumentation-key fallback, or browser telemetry
secret.

## Database network controls

`POSTGRES_SERVER_NAME` and `RUNTIME_DATABASE_URL` must identify the same
canonical PostgreSQL server FQDN. The PostgreSQL private endpoint, private DNS
zone, ACA connectivity, and hosted-agent connectivity must be proven by
`make foundry-connectivity-proof` before `make foundry-postgres-lockdown` can
disable public access and remove the temporary Azure-services firewall rule.
The generated proof artifact is the sole authorization for lockdown and must
be current and match the canonical FQDN.

## Release operation

Protected provision and deployment workflows run on the private self-hosted
runner with Azure OIDC and the retained private AZD environment. Private
Foundry deployment, smoke, evaluation, and telemetry validation must execute
from that private network path; a workstation outside the VNet is not a valid
hosted validation surface.

For private release-automation changes, run the sole applicable local gate:

```bash
make test
```

## Trace-evaluation identity correction (2026-07-29)

**Root cause.** Protected release `30463369625` reached the final Foundry
conversation evaluator after successful deployment, PostgreSQL lockdown, hosted
E2E, and telemetry proof. The evaluator returned `failed` with zero results
and no service error. Its three E2E conversations had four content-bearing
`invoke_agent` spans in Application Insights, but the wrapper overwrote the
Foundry platform identity with the bare value `order-resolution-hosted` for
`gen_ai.agent.id`. Foundry trace evaluation filters `invoke_agent` spans by
that attribute, which must be the platform's `name:version` identity.

**Precise fix.** The wrapper now derives `gen_ai.agent.name`,
`gen_ai.agent.version`, and `gen_ai.agent.id` from the platform-injected
`FOUNDRY_AGENT_NAME` and `FOUNDRY_AGENT_VERSION` values. Evidence collection
reads the active deployed name/version from AZD and telemetry verification now
requires each recorded conversation to have an `invoke_agent` span with exact
conversation ID, content-bearing messages, and the same `name:version`
identity before evaluation submission. This is a source-controlled telemetry
contract correction; it changes no private endpoint, firewall, RBAC, OIDC, or
secret setting.

**Required validation.** Run the focused hosted/evaluation tests and static
private workflow validator, then a fresh protected release. Closure still
requires all three fresh E2E conversations to produce completed Foundry
evaluation results after the locked-down private release path.

## Evidence AZD context correction (2026-07-29)

**Root cause.** The first protected release containing the trace-identity fix,
`30467055999`, completed deployment, connectivity proof, and PostgreSQL
lockdown but stopped before hosted E2E. The new evidence script changed to the
repository root before reading `AGENT_ORDER_RESOLUTION_HOSTED_NAME` and
`AGENT_ORDER_RESOLUTION_HOSTED_VERSION`; `azd env get-value` requires the
selected Foundry AZD project directory, so the command returned no value under
`set -e`.

**Precise fix.** The script now reads both active agent values while still in
`infra/foundry-hosted`, then changes to the repository root for E2E and
telemetry collection. The release remains fail-closed: missing active agent
identity still stops evidence before invoking the agent or evaluator. No Azure
resource, RBAC, OIDC, network, firewall, or secret was changed.

## Exact trace-source evaluation correction (2026-07-29)

**Root cause.** Protected retry `30467829865` proved the corrected
`name:version` identity and all three content-bearing `invoke_agent` spans in
Application Insights, but the preview `conversation_id_source` evaluation
still returned zero items without a service error. The Foundry trace-evaluation
contract documents `gen_ai.conversation.id` as a correlation attribute, while
its exact-selection alternative is Application Insights `operation_Id`.

**Precise fix.** Telemetry verification now selects one eligible
`operation_Id` per required E2E conversation and persists those three IDs.
The evaluator uses Foundry's documented `azure_ai_traces` source with the
persisted IDs and trace-level `query`/`response` mappings. This remains
fail-closed: telemetry must prove all scenario conversations and unique trace
IDs before evaluation, and Foundry must return a result for every selected
trace. The change does not alter private topology, RBAC, OIDC, firewall,
public access, or content-redaction behavior.

**Follow-up RCA.** Protected releases `30469803377` and `30470948019` passed
deploy, connectivity proof, PostgreSQL lockdown, and all hosted E2E scenarios,
then ended after a successful first telemetry query. The subsequent
Application Insights CLI query returned `BadArgumentError: The request had
some invalid properties` before the evaluator was invoked. The release log
therefore did not establish an evaluator API failure. Telemetry verification
now uses the documented `azure-monitor-query` `LogsQueryClient` against the
Application Insights resource ID, with a bounded retry for service responses;
the evidence target installs that declared dependency before use. Separately,
the evaluator uses the official trace-ID request shape:
`data_source={"type": "azure_ai_traces", "trace_ids": ..., "lookback_hours":
...}` passed through the `data_source` argument. This code-only repair changes
no Azure resource, RBAC, OIDC, secret, public access, or network
configuration.

**Execution-context follow-up.** Protected release `30473686601` confirmed
the clean evidence target installed the new SDK and completed hosted E2E, then
stopped because the wrapper invoked `python -m evals.verify_telemetry` from
the private lane root. `evals` is a backend module and is importable only from
`backend` (or when that directory is on `PYTHONPATH`). The wrapper now changes
to `backend` before the module invocation. This corrects repository execution
context only; it does not alter Azure configuration or access controls.

**SDK result-shape follow-up.** Protected release `30475417590` reached the
supported query client after hosted E2E, but the installed
`azure-monitor-query` version returned result-table column names as strings
rather than objects with a `name` property. The parser now accepts both
documented SDK result representations and has a focused regression test. This
is a local result-parsing correction with no Azure control-plane change.

**Trace-ID query follow-up.** Protected release `30476429820` completed the
telemetry eligibility polling and then surfaced an Application Insights KQL
semantic error while selecting trace IDs: `mv-expand` produced a dynamic
`conversationId`, which cannot be used as a `summarize` group key. The trace
query now casts it to string immediately after expansion, with static and
unit-test coverage. The correction is limited to evidence query syntax; all
private topology and access controls remain unchanged.

**Trace-ID projection follow-up.** Protected release `30478359891` passed
hosted E2E and telemetry eligibility, including three selected records, but
the Foundry run received those records' timestamps rather than
`operation_Id` values and correctly produced zero results. The KQL alias on
`arg_max(timestamp, operation_Id)` returned the aggregation timestamp. The
trace-selection query now uses `arg_max` to select the latest row and projects
`operation_Id` explicitly before persisting IDs. This source-only evidence fix
does not alter private resources, access, or data-plane controls.

**Message-schema follow-up.** Protected release `30491730680` then proved the
three persisted IDs were valid but Foundry rejected every span as unsupported:
the emitted message JSON used a legacy direct `content` field. The Foundry
trace-evaluation contract requires OpenTelemetry GenAI message `parts`, so
marked validation spans now emit
`{"role": "...", "parts": [{"type": "text", "content": "..."}]}` for both
input and output. The change remains restricted to explicitly marked private
E2E content and does not enable global content capture or change Azure access
controls.

## Private release closure evidence (2026-07-29)

Protected release
[`30493060929`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30493060929)
completed successfully from `foundry-private-v2` at commit `e64b1ff`.

| Gate | Current evidence |
| --- | --- |
| Deployment | Backend/frontend and hosted agent deployed from private ACR; `order-resolution-hosted` version `23` became active. |
| Connectivity | Fresh ACA/hosted-agent PostgreSQL connectivity proof recorded before lockdown. |
| PostgreSQL | The explicitly confirmed private-access lockdown completed after fresh proof. |
| Hosted E2E | Low-risk, high-risk approval/resume, and damaged-item approval/resume scenarios passed with three fresh conversations. |
| Telemetry | 69 correlated Application Insights rows and four eligible `invoke_agent` spans covered all three E2E conversations without exceptions. |
| Foundry evaluation | `eval_cf1bb4a15cb34dcf8566d3df7fb1ee60` / `evalrun_323d7b1092f64d0ba061e6ab5ac93af4` completed with 3 total, 3 passed, 0 failed, and 0 errored results. |

No ad-hoc RBAC, OIDC, secret, firewall, public-access, or network change was
used to close this release. The temporary runner deallocation was recovered by
starting the existing source-managed VM; the current tracked recovery workflow
keeps that operational action least-privileged and does not use VM Run Command
or runner-administration credentials.

## Private runner deallocation recovery (2026-07-29)

**Root cause.** After protected release `30477645384` completed deployment,
connectivity proof, and PostgreSQL lockdown, its evidence job was canceled
before E2E. GitHub then reported the sole `foundry-private-v2` runner offline,
and read-only Azure VM inspection showed the source-controlled
`vm-maffnd-runner` was `VM deallocated` with provisioning state `Succeeded`.
The next protected release therefore remained queued.

**Precise fix.** A protected, manually confirmed
`order-resolution-private-runner-start.yml` workflow now runs on
`ubuntu-latest` with the existing `foundry-private-env` OIDC identity. It
starts only the existing private runner VM, waits for its running power state,
and leaves GitHub registration proof to the subsequent protected release job.
The environment's `GITHUB_TOKEN` correctly lacks self-hosted-runner
administration permission, so the workflow does not attempt to list runners
through the administrative GitHub API or introduce a token secret. It does not
use Run Command, modify VM extensions, add RBAC/OIDC, recreate the runner,
open a network path, or change secrets. This makes routine
deallocation recovery reproducible from the repository while retaining the
separate Bastion/IaC recovery path for a deleted VM or registration.

## Clean-runner E2E dependency correction (2026-07-28)

GitHub Actions run `30370787132` failed the design-review browser gate on a
clean hosted runner. The script installed Playwright but not the frontend Vite
dependencies, so the local frontend never opened its dynamically selected
port and the proxy readiness check failed.

The private design-review and quick-validation CI jobs now install the
frontend with `npm ci`; quick validation also installs Playwright and Chromium
before it runs `make validate-quick`. The private deployed validation boundary
is unchanged: this correction only makes the local clean-runner E2E harness
reproducible.

## Private release readiness findings (2026-07-28)

Read-only preflight against the recreated private environment found three
release blockers before an application deployment was attempted:

1. The existing VM `vm-maffnd-runner` is running, but its
   `foundry-private-v2` runner registration is offline and belongs to the
   retired `ppenumatsa1/maf-order-resolution-agent` repository. The protected
   workflows are in `ppenumatsa1/maf-monorepo`, so the VM must be re-registered
   there through Bastion with the `foundry-private-v2` label. The readiness
   helper also retained the obsolete `foundry-private` default label; it now
   defaults to `foundry-private-v2`. The registration helper now supports
   `FORCE_RECONFIGURE=1`, which stops and replaces a local registration before
   configuring the required repository; this keeps that repair repeatable
   instead of relying on an ad-hoc VM change. It accepts a short-lived GitHub
   runner registration token, so recovery does not copy a long-lived personal
   access token onto the private VM.

   The first Bastion SSH attempt then exposed a separate IaC mismatch:
   `bas-maffnd` was Basic SKU and Azure rejected native-client SSH. Microsoft
   requires Standard SKU with native-client tunneling for `az network bastion
   ssh`. The runner-access module now declares Standard plus
   `enableTunneling: true`; the existing host is upgraded in place before
   runner re-registration. This changes the management-plane access feature
   only; the runner VM remains private and no public workload endpoint or
   database access is enabled.

   The first registration attempt then found the rebuilt VM did not have
   `jq`. The runner helper required `jq` before calling its own host-bootstrap
   script, even though that bootstrap installs the required command. The
   helper now validates only bootstrap prerequisites first and validates
   `git`, Docker, Azure CLI, AZD, `jq`, and `tar` after bootstrap completes.
2. PostgreSQL private endpoint
   `mafprv0722v3-postgres-pe-4aiw7fw5gjdo4` is `Failed` after the previous
   delete operation. Azure continues to return
   `OperationNotAllowedWhenLastOperationTypeIsDelete`, and the PostgreSQL
   private DNS zone has no A record. Diagnostics confirmed that the PostgreSQL
   server was healthy while this endpoint remained failed, so the failed
   endpoint was deleted by its exact resource name. The next core provision
   owns recreating the endpoint and private DNS state. No public database
   access or firewall exception was permitted.
3. The Foundry project/runtime-secret connection still reports a Key Vault
   managed-identity token failure. This remains an expected post-restore
   propagation condition: run core provisioning without project connections,
   then retry only the staged `foundry-project-connections` target after the
   project identity can acquire its Key Vault token.

The Foundry account is active with public network access disabled and default
network action deny. The source-level private gate also passed on this revision:
Ruff completed cleanly and `make test` passed all 112 tests.

## Declarative GitHub OIDC identity correction (2026-07-28)

The first private release recovery used CLI to create the monorepo GitHub
environment and a federated credential on the historical deployment
application. That was immediately replaced with a source-controlled
`infra/github-actions-identity` Bicep stack and tracked bootstrap script. The
stack creates a dedicated application, its
`repo:ppenumatsa1/maf-monorepo:environment:foundry-private-env` federated
credential, and only the two resource-group roles needed by the protected
workflow: Contributor and User Access Administrator. The bootstrap command
then synchronizes the resulting non-secret client, tenant, and subscription
IDs to the declared GitHub environment.

The first IaC deployment reached application/service-principal creation but
its immediate role assignments failed with `PrincipalNotFound` while Entra
replicated the new principal. The role assignments now explicitly set
`principalType: 'ServicePrincipal'`, which is Azure's documented first-run
replication-safe form. No RBAC assignment or OIDC trust is created manually
after this correction. The bootstrap also removes the temporary monorepo
federated credential from the historical application after the replacement
stack succeeds, leaving one active private-release trust.

During verification, the initial role-definition constant was found to resolve
to `Managed Identity Operator`, not `User Access Administrator`. The identity
stack now uses Azure's `User Access Administrator`
`18d7d88d-d35e-4fb5-a5c3-7773c20a72d9` definition. The bootstrap removes only
the superseded assignment matching the incorrect role definition after the
correct declarative assignment exists.

**Recovery confirmation.** The dedicated deployment application now has one
active GitHub federation subject for the monorepo private environment and
exactly Contributor plus User Access Administrator at
`rg-maf-ora-foundry-v2`; the temporary historical-app trust was removed.
`bas-maffnd` is Standard with native tunneling enabled, and the rebuilt runner
`vm-vm-maffnd-runner-foundry-private-v2` is online in
`ppenumatsa1/maf-monorepo` with the required `foundry-private-v2` label.

The first protected workflow then reached Azure OIDC login but failed with
`AADSTS700213`. GitHub emitted the actual subject
`repo:ppenumatsa1@37847579/maf-monorepo@1314177122:environment:foundry-private-env`,
which includes immutable owner and repository IDs rather than the conventional
`repo:owner/repository` string. The identity Bicep now declares that exact
emitted subject. This is the narrow trust required by the protected
environment; no wildcard subject or broader repository trust was added.

The next provision retry authenticated successfully but the rebuilt VM had no
local `.azure/foundry-private-env` state. The old VM had retained that local
state; relying on it made the release non-reproducible. Every protected private
workflow now runs a tracked AZD bootstrap that recreates the non-secret
environment context from the canonical resource names and requires only
`POSTGRES_ADMIN_PASSWORD` from the protected GitHub environment. A tracked
secret-migration command copies that existing secret into the monorepo
environment without displaying or committing it.

## Hosted-agent deployment RBAC correction (2026-07-28)

**Root cause.** Protected deployment workflow
[`30398046137`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30398046137)
successfully provisioned project connections and deployed both Container Apps
from the private ACR, but `azd deploy order-resolution-hosted` stopped before
agent creation with HTTP 403:
`Identity(object id: c1998355-d834-494f-8fdf-bdc37239b599) does not have
permissions for Microsoft.CognitiveServices/accounts/AIServices/agents/read`.
The dedicated GitHub identity had Contributor and User Access Administrator at
the resource-group scope, which cover Azure resource management and
source-controlled role deployment but do not grant Foundry data-plane agent
permissions.

**Precise fix.** The existing declarative
`infra/github-actions-identity/foundry-project-manager.bicep` stack now
assigns the documented **Foundry Project Manager** role
(`eadc314b-1a2d-4efa-be10-5d325db5065e`) to the GitHub deployment service
principal at the exact `order-resolution` Foundry project scope. The dedicated
template is intentionally Graph-free, so initial identity bootstrap can create
the GitHub OIDC application before a clean environment contains a Foundry
project, while the protected deploy workflow applies the project assignment
only after staged project-connection provision and before hosted-agent
deployment. The tracked deployment helper derives the signed-in service
principal object ID from its ARM token and invokes the Bicep template; no
workflow token receives GitHub-environment or Microsoft Graph admin
permissions and no role is granted through an ad-hoc CLI command.

**Authority and retry boundary.** Microsoft’s current hosted-agent deployment
guidance requires Foundry Project Manager at project scope to create, update,
and read hosted agents and to create needed platform identity assignments:
https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent#prerequisites.
The correction adds only that project-scoped Foundry role; it does not enable
public access, widen the OIDC federation, or add Foundry Owner at resource
group/account scope. Re-run the protected deployment workflow after this
declarative identity stack is applied. The hosted-agent deploy target retries
only the exact `AIServices/agents/read` authorization error with bounded
15/30/60/120-second propagation waits; all other failures remain immediate
failures. Connectivity proof, PostgreSQL lockdown, hosted E2E, evaluation,
and telemetry remain blocked until that retry succeeds.

## Hosted-agent source-build ImageError correction (2026-07-28)

**Root cause.** Protected workflow
[`30400533992`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30400533992)
proved the GitHub release identity can create and read the hosted agent after
the project-scoped Foundry Project Manager assignment. The service then waited
for activation and failed with
`[ImageError] Container image not found`. This is the same Foundry
`remote_build` source-deployment failure previously isolated in the public
lane: the platform did not produce a runnable image from the uploaded Python
source. The private failure occurs after agent creation, so it is not the
earlier OIDC/RBAC issue.

**Precise fix.** The private lane now builds the generated
`backend/Dockerfile.hosted` context locally on the in-VNet private runner,
pushes it through the ACR private endpoint, then uses the supported
`AIProjectClient.agents.create_version` image registration API with the
Responses protocol and preserved private runtime environment. ACR Tasks are
not used because their default build workers cannot reach an ACR with public
network access disabled. The old `agent.yaml` `remote_build` definition is
removed; the supported `make foundry-deploy` path cannot fall back to the
broken source builder. Private Bicep enables ACR ARM Entra authentication and
assigns only the Foundry project identity `AcrPull` and `Container Registry
Repository Reader` at the private ACR scope. Those roles and the registry
policy are provisioned before image registration; no registry public endpoint,
admin user, or firewall exception is enabled. Source synchronization excludes
all local Foundry checkpoints, memory, and result state before the image is
built. The same Graph-free identity template assigns `AcrPush` at the private
ACR scope to the protected deployment identity; image push retries only the
new role's `unauthorized` or `denied` propagation state.

## Private ACR policy lifecycle correction (2026-07-28)

**Root cause.** Workflow
[`30402789003`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30402789003)
applied the staged Foundry project connections but failed its final
infrastructure operation on the ACR
`azureADAuthenticationAsArmPolicy` child resource. ARM reported the child
operation as `BadRequest`/`NotFound` with no message even though the registry
subsequently reported `azureAdAuthenticationAsArmPolicy.status: enabled`.
The policy setting succeeded, but the child-resource API's post-deployment
lifecycle result made `azd provision` fail closed and blocked the release
before image build.

**Precise fix.** The private ACR now declares
`policies.azureADAuthenticationAsArmPolicy.status: enabled` directly on the
registry resource through
`Microsoft.ContainerRegistry/registries@2023-08-01-preview`, the first schema
that exposes this policy property, and no longer deploys the problematic child
policy resource. The prior `2023-07-01` registry schema did not recognize the
inline property; using it would have silently omitted the setting. The selected
schema compiles with the policy present.
This preserves the required ARM-token ACR authentication as IaC while avoiding
the provider's invalid child-resource polling path. No registry network,
admin-user, or RBAC control is weakened. The next guarded release reruns the
staged connection provision, then proceeds to image deployment only if it
succeeds.

**Validation outcome.** Protected workflow
[`30403325196`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30403325196)
completed staged project connections, application deployment, ACR-target
validation, and role synchronization after the lifecycle correction. This
proves the ACR policy is now provisioned declaratively without the former ARM
polling failure. The later hosted-agent deployment failure is recorded
separately below.

## Private runner Python runtime correction (2026-07-28)

**Root cause.** The same protected workflow reached the new image-release
target but failed before Docker build or Foundry registration. The restored
self-hosted runner's system Python lacks Debian's `ensurepip`, so
`python3 -m venv backend/.venv` failed with the documented
`python3-venv` prerequisite error. The release depended on an untracked
machine package despite the workflow owning the Python SDK deployment step.

**Precise fix.** The protected deployment workflow now installs the
source-controlled GitHub `actions/setup-python@v5` Python 3.12 runtime before
any Make target creates the backend virtual environment. This makes `venv`,
the Azure AI Projects SDK, and the deployment scripts available independently
of the base image's `python3-venv` package. No runner package was installed
manually, no Azure role or OIDC configuration changed, and the later
connectivity, lockdown, E2E, evaluation, and telemetry gates remain blocked
until the agent image becomes active.

**Static-contract correction.** The credential-free workflow validator had a
contradictory blanket ban on `secrets.` while the provision workflow
intentionally passes exactly `POSTGRES_ADMIN_PASSWORD` from the protected
environment to reconstruct the retained AZD environment. It now requires that
single documented reference in each protected provision and deployment workflow
and rejects every other secret reference. This is validation-only and does not
alter secret storage, access, or Azure permissions.

## Hosted-agent reserved environment-variable correction (2026-07-28)

**Root cause.** Protected workflow
[`30403945918`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30403945918)
proved the VNet runner can build the `linux/amd64` image and push it to the
private ACR. Foundry then rejected `create_version` with `invalid_payload`
before it created a version because the release payload explicitly supplied
`FOUNDRY_PROJECTS_ENDPOINT`, `FOUNDRY_MODEL_DEPLOYMENT_NAME`,
`FOUNDRY_RUNTIME_DATABASE_URL`, and
`FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT`. Current Foundry reserves all
`FOUNDRY_*` and `AGENT_*` variable names and injects platform-owned values
into hosted containers.

**Precise fix.** The image release passes only custom variables:
`AZURE_AI_MODEL_DEPLOYMENT_NAME` and `TRACE_EVALUATION_RECORD_CONTENT`. Its
`DATABASE_URL` is the supported
`${{connections.orderresolutionruntimesecrets.credentials.database_url}}`
placeholder for the existing source-controlled `CustomKeys` project
connection, rather than a deployment-time secret value. The platform injects
`FOUNDRY_PROJECT_ENDPOINT`; the existing backend startup alias maps that
value and the Azure model variable to the application’s established local
configuration names. Trace-evaluation logic reads the custom variable first
while retaining the old name as a local compatibility fallback. The
application receives no project endpoint or database secret through its image
or agent-version API payload, and no Foundry-reserved variable is included in
the SDK payload.

**Authority and retry boundary.** Microsoft’s hosted-agent container
requirements state that the platform injects `FOUNDRY_PROJECT_ENDPOINT` and
reserves all `FOUNDRY_*` and `AGENT_*` names; custom configuration belongs in
the SDK `create_version` environment map:
https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent#container-requirements.
The next protected release must reach an active agent version before
connectivity proof, PostgreSQL lockdown, E2E, evaluation, or telemetry can
run.

## Hosted-agent version-creation timeout correction (2026-07-28)

**Root cause.** The next protected workflow
[`30404960681`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30404960681)
accepted the corrected payload and completed the private ACR image push, but
the Foundry `create_version` request ended after roughly two minutes with an
HTTP 5xx `Timeout`. The service did not return an agent version or emit agent
container diagnostics, so this was a transient control-plane failure before
the activation polling loop rather than an application, image, ACR, or
connectivity failure.

**Precise fix.** The SDK release now retries only HTTP 5xx
`create_version` failures on a bounded `0/30/60`-second schedule. Client
validation, authorization, and all non-5xx errors still fail immediately.
Each attempt uses the same immutable image and version definition; a retry can
create additional immutable versions, but the workflow records and invokes
only the returned active version. No Azure role, network setting, secret, or
OIDC configuration changed.

**Authority and retry boundary.** Microsoft’s Python SDK guidance for
`HttpResponseError` identifies HTTP 5xx responses as transient service errors
appropriate for retry:
https://learn.microsoft.com/azure/developer/python/sdk/fundamentals/errors#common-error-scenarios.
The next guarded workflow must return a version and then poll it to `active`;
only then may the existing proof, lockdown, E2E, evaluation, and telemetry
gates proceed.

## Foundry trace-ingestion evaluation correction (2026-07-28)

**Root cause.** Protected workflow
[`30407177196`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30407177196)
passed hosted-agent deployment, fresh ACA/hosted-agent PostgreSQL connectivity
proof, PostgreSQL lockdown, and all three hosted Responses E2E conversations.
It then submitted the trace evaluation immediately after E2E. Foundry returned
`failed` with zero result rows and no evaluator error. The project managed
identity already has source-controlled **Log Analytics Reader** assignments on
both Application Insights and its workspace, so the absence of rows directly
after E2E is Application Insights ingestion timing, not missing RBAC.

**Precise fix.** `backend/eval.yaml` now requires a five-minute
`ingestion_delay_seconds` before the trace evaluation is submitted. The
runner computes the remaining delay from the fresh E2E evidence timestamp, so
it waits only as long as necessary and never reuses stale evidence. Enforced
evaluation now additionally requires a completed run to return at least one
result for each of the three recorded conversations; a completed but empty
evaluation cannot satisfy the release gate.

**Follow-up correction.** A subsequent run confirmed that waiting alone did
not create eligible evaluation rows. The E2E helper previously placed its
per-request content marker only in a client header; the hosted Responses path
does not guarantee that header reaches the application context. Each E2E
payload now includes the existing
`metadata.trace_evaluation_record_content=true` marker that the application
already parses, so only those release-validation requests emit the required
GenAI input/output attributes. The evidence sequence now validates
Application Insights correlation before it starts Foundry evaluation. This
keeps ordinary traffic redacted and makes missing trace export a direct,
separate failure instead of an opaque zero-row evaluation.

**Release-order correction.** The first marked-request run
[`30409232845`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30409232845)
proved telemetry correlation first: Application Insights returned 151 rows
covering all three fresh E2E conversations. The workflow was then canceled at
its runner execution boundary while the redundant five-minute evaluator delay
was still sleeping. The private release now sets
`ingestion_delay_seconds: 0`: `verify_telemetry.sh` is the bounded ingestion
wait and an explicit all-conversation proof immediately precedes evaluation.
The runner's reusable default remains conservative for callers that do not
perform that proof. This shortens the release without accepting missing
traces.

**Authority and retry boundary.** Microsoft’s conversation-trace evaluation
guidance states that Application Insights ingestion can delay trace
availability and directs operators to wait a few minutes before retrying:
https://learn.microsoft.com/azure/foundry/how-to/develop/cloud-evaluation#conversation-level-evaluation-preview.
The next protected release waits before one clean submission; any later
non-completed or incomplete result remains a fail-closed release failure for
investigation.

## Trace-evaluation message-schema correction (2026-07-29)

**Initial root-cause hypothesis.** Protected workflow
[`30455291617`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30455291617)
completed image deployment, fresh ACA and hosted-agent PostgreSQL
connectivity proof, PostgreSQL lockdown, all three hosted Responses E2E
scenarios, and the telemetry correlation gate (91 rows across all three
conversations). Foundry then returned `failed` for
`eval_52da614d6bc54621afbacc26136e10ef` /
`evalrun_2af8d799eecf4d2eb53ede4f7756c3b1`, with zero results and no service
error. The marked invocation spans emitted their `gen_ai.input.messages` and
`gen_ai.output.messages` using a nested `parts` structure. Foundry's
conversation-trace evaluation guidance documents message records as
role/content objects; its trace extractor uses those fields to form the
evaluator `messages` input. The existing telemetry check proved correlation,
but it did not validate that payload schema.

**Precise fix.** The hosted Responses entrypoint now emits the documented
`{"role": ..., "content": ...}` message objects for marked input and output
spans. The trace evaluator persists the complete terminal run representation
in its sanitized local report, alongside result counts and the service error,
so any future fail-closed evaluation has actionable evidence. No fallback,
retry, RBAC, OIDC, networking, data-retention, or PostgreSQL control changed.

**Validation outcome.** The focused hosted telemetry unit test passed.
Protected workflow
[`30456529681`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30456529681)
then emitted the corrected schema and again passed all deployment,
connectivity, lockdown, E2E, and telemetry gates (67 rows across all three
conversations), but its evaluation immediately returned zero results. The
payload correction standardizes the documented schema but is not sufficient
evidence that Foundry's evaluation service has ingested the traces. The
release-timing correction below is now the required gate.

## Trace-evaluation release-window correction (2026-07-29)

**Root cause.** The prior telemetry-first shortcut set
`ingestion_delay_seconds: 0` after `verify_telemetry.sh` found correlated App
Insights rows. Two protected releases (`30455291617` and `30456529681`) prove
that this query does not establish availability to Foundry's separate
conversation-trace evaluator: both evaluator submissions failed immediately
with zero results and no service error. Restoring the documented five-minute
delay in the former single `deploy` job is not reliable either. Workflow
`30409232845` was terminated seven seconds before its delay elapsed because
the private runner's 15-minute job boundary was consumed by provisioning,
deployment, proof, lockdown, and E2E.

**Precise fix.** The protected workflow now has two serialized jobs on the
same sole `foundry-private-v2` runner. `deploy` retains all source-controlled
core stages through fresh connectivity proof and PostgreSQL lockdown.
`evidence` has an explicit `needs: deploy` dependency and performs fresh
hosted E2E, telemetry correlation, the restored five-minute ingestion delay,
and enforced Foundry evaluation. It re-authenticates through the same
environment-scoped GitHub OIDC identity, restores the required Azure CLI/AZD
tooling, and validates the retained selected AZD environment before evidence
collection. This gives evaluation its own private runner time budget without
loosening release ordering, relying on a public host, enabling a network
exception, or allowing an optional evidence path.

**Validation required.** The static workflow contract must verify this
dependent evidence job and the exact release order. A new protected release
must finish the final evaluation with one or more results for every fresh E2E
conversation; earlier releases remain failed evidence.

## Foundry trace-content marker correction (2026-07-29)

**Root cause.** The split workflow
[`30458177108`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30458177108)
completed its dependent `deploy` job, then passed hosted E2E, generic telemetry
correlation (88 rows), and the restored 272-second remaining ingestion wait in
its `evidence` job. Foundry nevertheless returned zero evaluation results.
The direct Application Insights inspection for the three E2E conversations
showed the root `request` spans had `gen_ai.operation.name=invoke_agent` but
empty `gen_ai.input.messages` and `gen_ai.output.messages`. The E2E helper put
the record-content marker in `metadata`; the hosted Responses protocol strips
that unsupported field before it reaches the handler, so the application
correctly preserved content redaction.

**Follow-up correction.** Workflow
[`30459963564`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30459963564)
proved that `structured_inputs` alone is also absent from the hosted handler:
the strengthened gate found zero content-bearing spans after its full bounded
wait and stopped before submitting evaluation. The platform's root `request`
span carries the official hosted-agent identity but remains content-redacted;
the application-owned child span is the intended content-bearing evaluation
surface.

**Precise fix.** Every private hosted E2E invocation now includes the
Responses-supported `x-client-trace-evaluation-record-content: true` header
through `azd ai agent invoke --client-header`, which its current CLI contract
explicitly forwards to responses handlers. The structured input marker remains
an explicit protocol payload signal. The telemetry gate now requires every
recorded conversation to have any content-bearing `invoke_agent` span with
both `gen_ai.input.messages` and `gen_ai.output.messages`; generic
correlation alone can no longer advance to evaluation. This retains content
redaction for non-validation traffic and changes no RBAC, OIDC, network,
database, or retry behavior.

**Final root cause and configuration correction.** Workflow
[`30461657003`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30461657003)
still observed zero eligible spans after forwarding the header. The release
payload maps `FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT` into the hosted
container's custom `TRACE_EVALUATION_RECORD_CONTENT` variable, but the
retained AZD environment was created while the defaults helper set that source
value to `false`. The application therefore correctly rejected every marker
before inspecting its header or structured input. The defaults helper now
unconditionally sets `FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT=true` before
each source-controlled hosted-agent deployment. This enables only the
application's request-level marker path; ordinary traffic still omits
`gen_ai.input.messages` and `gen_ai.output.messages`. No secret, RBAC, OIDC,
network, or public-access configuration changes.

**Validation required.** Run the focused hosted telemetry tests and shell
syntax validation, then a fresh protected release. It must show three
content-bearing evaluation spans before it submits evaluation, and Foundry
must return result coverage for all fresh E2E conversations.

## Hosted-agent release token-lifetime correction (2026-07-28)

**Root cause.** Protected workflow
[`30405737376`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30405737376)
did not reach image deployment. Its preceding staged connection and Container
App operations consumed more than the initial GitHub OIDC client assertion's
five-minute validity window. The later declarative Foundry Project Manager
role synchronization then failed with `AADSTS700024` because Azure CLI tried
to exchange that expired assertion. This is a workflow token-lifetime issue,
not missing Foundry RBAC; previous runs had already passed the same
source-controlled assignment.

**Precise fix.** The protected workflow now performs a second, declarative
`azure/login@v2` OIDC exchange immediately before Foundry role synchronization
and hosted-agent deployment. It uses the same protected-environment client,
tenant, subscription, narrow federated subject, and workflow permissions as
the initial login. No CLI login, persistent credential, role assignment, or
identity setting is added outside the workflow.

**Retry boundary.** The refresh occurs after potentially long application
deployment and before every Azure CLI/SDK operation that needs the deployment
identity. A future run must complete role synchronization and hosted-agent
activation before it can advance to proof, lockdown, E2E, evaluation, and
telemetry.

## Private ARM token-exchange transport retry (2026-07-28)

**Root cause.** Protected workflow
[`30408929591`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30408929591)
reached the fresh identity stage but the Azure CLI ARM-token request in the
declarative project-role synchronization helper failed with
`Connection reset by peer`. The retry followed a successful OIDC login, and
the same helper had completed in earlier runs, so this is a transient
transport reset rather than an RBAC, OIDC-subject, or Bicep failure.

**Precise fix.** The tracked helper retries only an ARM token exchange whose
output contains that exact reset error, using bounded `0/15/30`-second
delays. It immediately surfaces every other Azure CLI error and then uses the
derived ARM-token object ID with the existing Bicep role-assignment template.
No Azure CLI login, manually created role assignment, persistent secret, or
identity scope is added.

**Authority and retry boundary.** Microsoft’s hosted-agent SDK documentation
supports `HostedAgentDefinition` with a full tagged ACR
`ContainerConfiguration.image` and polling the created version to `active`:
https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent#deploy-using-the-python-sdk.
Microsoft’s current hosted-agent deployment guidance also identifies project
registry-reader access as required for image deployment. The next guarded
workflow run must complete the ACR image build and agent activation before
connectivity proof, PostgreSQL lockdown, hosted E2E, evaluation, and telemetry
can proceed.

**Core-stage confirmation.** Protected workflow
[`30397620770`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30397620770)
completed successfully on the recovered private runner. It recreated
`mafprv0722v3-postgres-pe-4aiw7fw5gjdo4`; the endpoint is succeeded, the
private DNS record resolves `maffndpgv20722` to `10.90.2.13`, and PostgreSQL
public access remains disabled. The next stage is the separate project
connection provision followed by application/hosted-agent deployment and
connectivity proof.
