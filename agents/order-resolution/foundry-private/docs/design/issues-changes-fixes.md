# Private Foundry Deployment Evidence

This document records the current private deployment posture and release
evidence. Superseded deployment history and retired topology details are not
part of the operating record.

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
