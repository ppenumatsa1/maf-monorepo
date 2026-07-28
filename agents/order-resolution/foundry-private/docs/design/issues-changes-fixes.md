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
`infra/github-actions-identity/main.bicep` stack now conditionally assigns
the documented **Foundry Project Manager** role
(`eadc314b-1a2d-4efa-be10-5d325db5065e`) to the GitHub deployment service
principal at the exact `order-resolution` Foundry project scope. The
assignment is intentionally disabled during initial identity bootstrap, so
the GitHub OIDC identity can be created before a clean environment contains a
Foundry project. The protected deploy workflow enables the assignment only
after its staged project-connection provision and before hosted-agent
deployment. It invokes the tracked bootstrap with GitHub-environment
synchronization and one-time legacy-identity retirement disabled; no workflow
token receives GitHub-environment or Microsoft Graph admin permissions and no
role is granted through an ad-hoc CLI command.

**Authority and retry boundary.** Microsoft’s current hosted-agent deployment
guidance requires Foundry Project Manager at project scope to create, update,
and read hosted agents and to create needed platform identity assignments:
https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent#prerequisites.
The correction adds only that project-scoped Foundry role; it does not enable
public access, widen the OIDC federation, or add Foundry Owner at resource
group/account scope. Re-run the protected deployment workflow after this
declarative identity stack is applied. Connectivity proof, PostgreSQL
lockdown, hosted E2E, evaluation, and telemetry remain blocked until that
retry succeeds.

**Core-stage confirmation.** Protected workflow
[`30397620770`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30397620770)
completed successfully on the recovered private runner. It recreated
`mafprv0722v3-postgres-pe-4aiw7fw5gjdo4`; the endpoint is succeeded, the
private DNS record resolves `maffndpgv20722` to `10.90.2.13`, and PostgreSQL
public access remains disabled. The next stage is the separate project
connection provision followed by application/hosted-agent deployment and
connectivity proof.
