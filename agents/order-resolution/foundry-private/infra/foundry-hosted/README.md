# Foundry-Hosted Deployment (Private VNet Baseline)

This stack provisions and deploys a Foundry-hosted agent path using `azd` + Bicep from `infra/foundry-hosted`.

Primary target region for this path is **eastus2**.

## Deployment lane

This branch keeps one hosted deployment lane:

1. `ora-foundry-private` (baseline/private): private networking, private endpoints, and private-runner execution path.

## What this stack includes

- `azure.yaml` service hosts: internal `backend`, external `frontend`, and
  `azure.ai.agent` (`order-resolution-hosted`)
- `azure.yaml` deploy source path: `./agent` (generated from `backend/` by sync helper)
- Bicep orchestration in `iac/main.bicep` for:
  - Foundry account/project + model deployments
  - VNet + dedicated Container Apps subnet + agent subnet + private endpoint subnet
  - private DNS zones and private endpoints
  - NAT gateway
  - optional private runner access (runner subnet, Bastion, VM, UAMI, subscription RBAC)
  - Storage, Search, Cosmos, ACR, Log Analytics, App Insights, and PostgreSQL private endpoint/DNS
  - capability-host and connection modules

## Parameter profiles

- `iac/parameters.standard-ni.json`
  First-provision standard profile (eastus2) with DNS links, project connections, and capability-host sequencing enabled.
- `iac/parameters.standard-ni.rerun.json`
  Rerun/repair profile for existing environments (capability-host/connections disabled, runner VM creation disabled).
- `iac/parameters.dev.json`
  Dev profile aligned to eastus2 defaults.
`iac/main.bicep` uses `networkMode=private` for this branch posture.

Provisioning now reads `iac/main.parameters.json`, which maps AZD environment keys (for example `NETWORK_MODE`) into Bicep parameters. The helper script `scripts/foundry/ensure_foundry_azd_defaults.sh` backfills missing keys so ad-hoc `make foundry-provision` and CI runs stay deterministic.

## Private release flow

PR validation is credential-free through
`.github/workflows/order-resolution-private-validation.yml`. Authenticated
infrastructure and application workflows are started by dispatching
`order-resolution-private-provision.yml` or
`order-resolution-private-deploy.yml`; a validated dispatch starts immediately
with no confirmation input, environment approval, or owner approval gate. They
share the
`order-resolution-private-release` concurrency group with the observability
workflow, and run only on
`self-hosted,foundry-private-ora` with Azure OIDC. They use the runner's retained
selected AZD environment, so do not recreate that environment or place its
database credentials in GitHub workflow configuration.
Before the first dispatch, configure repository-scoped nonsecret OIDC and
target variables with `scripts/github/bootstrap_foundry_github_config.sh` and
the `POSTGRES_ADMIN_PASSWORD` repository secret.

The bootstrap/reconciliation release executes this fixed sequence:

1. `make test` and private release preflight;
2. non-mutating provisioning preview, then private core provisioning without
   Foundry connection secrets;
3. project-identity propagation followed by staged Foundry connection
   provisioning;
4. hosted-image construction in parallel with backend/frontend ACA deployment;
5. hosted-agent activation from the validated prebuilt image;
6. private PostgreSQL readiness before application activation;
7. hosted E2E, correlated telemetry, and strict Foundry evaluation in the same
   serialized workflow.

```bash
make foundry-provision-preview  # no Azure resource changes
make foundry-release
```

Deployment workflows start when dispatched. PostgreSQL is private-only from
creation, and the VNet-runner readiness gate prevents application deployment
against an invalid endpoint, DNS mapping, schema, or runtime role. No path
exposes a password-repair, public-access, firewall, or administrator-user
workaround.

Routine app-only releases do not run full Bicep. They preserve the
requirements-hash-validated backend environment and chain evidence by default.
The standalone evidence workflow remains available for retries.

### Staged Foundry project connections

The core target sets `MANAGE_PROJECT_CONNECTIONS=false`, allowing the account,
project identity, private endpoints, and pre-capability-host RBAC assignments
to complete before Foundry stores the protected `ApplicationInsights` and
`orderresolutionruntimesecrets` credentials. The
`foundry-project-connections` target then sets it to `true` and reruns
`main.bicep`; its connection modules depend on those RBAC assignments and the
runtime secret connection depends on the completed project connections. This
avoids creating connection secrets while the restored project's managed
identity is still propagating.

If that explicit second stage still reports a managed-identity/Key Vault token
failure, wait for platform propagation and retry
`make foundry-project-connections`. Do not substitute a public endpoint,
administrator credential, or alternate connection. If PostgreSQL private
endpoint creation reports `OperationNotAllowedWhenLastOperationTypeIsDelete`,
wait for Azure's delete operation to complete and retry the same staged
provision; this is a platform timing condition, not a network-control bypass.

The frontend is the only external ingress and proxies browser `/api` traffic to
the internal backend ACA. Before application deployment,
`make foundry-postgres-readiness` verifies that the canonical server is Ready
with public access disabled, the approved `postgresqlServer` private endpoint
and private-DNS A record target that server, the runner resolves the private
IP, and the runtime role retains its exact least-privilege contract.

### Soft-deleted Foundry account recovery

The current intentional teardown left
`mafprv0722v3ai4aiw7fw5gjdo4` soft-deleted. The retained private AZD
environment defaults `RESTORE_FOUNDRY_ACCOUNT=true`, which maps to
`restoreFoundryAccount` on the `Microsoft.CognitiveServices/accounts@2025-06-01`
resource in `main.bicep`. Keep it true while recovering this account name; set
it false only after purging the soft-deleted account name. This restore setting
does not relax the private network, ACR, or PostgreSQL controls.

## Private runner bootstrap

If the private runner VM has been deleted, first use the management-plane
recovery target from an authorized operator shell:

```bash
RUNNER_SSH_PUBKEY_PATH=/secure/path/id_ed25519.pub make foundry-access-path
```

The target fails before any Azure command when the key path is absent, missing,
or empty. It selects `ora-foundry-private`, runs private-release preflight, and
sets the private runner/VM parameters in the retained AZD environment before
invoking `azd provision`. It also runs the default helper, so the required
Foundry-account restore flag is present. This uses the existing
resource-group-scoped `main.bicep` private-runner module; do not use a separate
access resource group or a nonexistent standalone access-path template. It
creates no public ACR or PostgreSQL firewall exception.

After the VM is available, use Bastion to prepare and register/start the
private self-hosted runner:

```bash
./scripts/github/bootstrap_vm_runner_host.sh
./scripts/github/register_vm_runner.sh
```

Required environment variables include:

- `GH_RUNNER_PAT`
- `REPO` (owner/repo)

Optional defaults:

- `RUNNER_LABEL` (default and required release target: `foundry-private-ora`)
- `RUNNER_VERSION` (default: `2.328.0`)

The private runner is the only GitHub Actions host permitted to run the
provision/deployment lane and remains an in-VNet operator host for the local
release flow. Runner recovery is an explicit management-plane prerequisite,
not a release deployment path. Do not dispatch provision or deploy until the
runner readiness check reports `foundry-private-ora` online.

## Runner readiness check

Verify GitHub sees an online runner for the required label:

```bash
REPO=ppenumatsa1/maf-order-resolution-agent \
RUNNER_LABEL=foundry-private-ora \
./scripts/github/verify_foundry_runner_ready.sh
```

## Existing VM runbook

Run this on the active private runner VM via SSH/Bastion:

```bash
cd /path/to/repo
export GH_RUNNER_PAT=<github_pat_with_repo_workflow_scope>
export REPO=ppenumatsa1/maf-order-resolution-agent
export RUNNER_LABEL=foundry-private-ora

./scripts/github/bootstrap_vm_runner_host.sh
./scripts/github/register_vm_runner.sh
```

Then verify from your operator host:

```bash
gh api repos/ppenumatsa1/maf-order-resolution-agent/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

## Troubleshooting

- VM is running but workflow job is queued:
  - Runner service may be stopped or runner may be offline in GitHub.
  - Run `sudo ./svc.sh status && sudo ./svc.sh start` in runner directory.
- Azure RunCommand reports `Conflict ... execution is in progress`:
  - Use direct SSH/Bastion for bootstrap/register actions.
- Runner label mismatch:
  - Ensure the active runner is configured with
    `self-hosted,foundry-private-ora`.
- Missing tools on runner host:
  - Re-run `./scripts/github/bootstrap_vm_runner_host.sh`.

## Local validation

```bash
az bicep build --file infra/foundry-hosted/iac/main.bicep
az bicep build --file infra/foundry-hosted/iac/modules/private-runner-access.bicep
az bicep build --file infra/foundry-hosted/iac/modules/vnet.bicep
az bicep build --file infra/foundry-hosted/iac/modules/private-dns.bicep
az bicep build --file infra/foundry-hosted/iac/modules/private-endpoint.bicep
```

Repository deterministic gates remain:

- `make test`

For this private release automation change, do not run local evaluations.
Hosted E2E, enforced Foundry evaluation, and telemetry validation are release
evidence collected only from the private runner.

The routine app-only workflow preserves a requirements-hash-validated backend
environment, builds the hosted image concurrently with ACA deployment, and
continues directly into evidence. The standalone evidence workflow is reserved
for retries. Foundry readiness is adaptive: only a zero-row, error-free
ingestion miss is retried; evaluator and service failures remain terminal.

Delivery ownership, required gate mapping, and evidence handoff expectations are documented in `docs/design/engineering-operating-model.md`.
