# Private Foundry to Teams Customer Demo Runbook

## Purpose and current status

This runbook prepares and demonstrates the Responses-native order-resolution
agent from a clean private Foundry environment through Microsoft Teams.

Current state:

- The private web application is deployed, release-verified, and manually
  accepted.
- Bot Service, `MsTeamsChannel`, and the Activity endpoint configuration are
  deployed, including `BotRequest` and `AllMetrics` diagnostics to the existing
  Log Analytics workspace.
- Shared publication, title-ID installation, user authentication, Teams
  invocation, and concise response rendering are verified end to end.
- Adaptive Card approval/rejection is implemented in the dual-protocol hosted
  runtime and accepted in fresh conversations. Before a new demo, still use a
  fresh conversation so it binds to the active hosted-agent version.

Commands remain operator instructions. Completion evidence belongs in
`issues-changes-fixes.md`.

The selected demo topology is **East US 2** with runner SKU
`Standard_D4s_v7`. Canada Central had the required service support, but the
exact runner SKU was unavailable for this topology. Do not silently substitute
a region or SKU.

The upstream private-network audit is pinned to template 15. Existing
monitoring remains unchanged; AMPLS is out of scope.

## Security and architecture boundaries

- Foundry Responses, normal project/data/management APIs, PostgreSQL, ACR,
  model/tool traffic, and secrets remain private or on authenticated control
  paths.
- Teams requires a service-managed public Activity route because Microsoft 365
  cannot call Private Link. The route is source-IP filtered and scoped to
  Activity Protocol.
- Public reachability is not anonymous. Bot token, tenant, and RBAC
  authorization remain mandatory.
- `iac/teams/main.bicep` owns Bot Service, `MsTeamsChannel`, and the Bot
  diagnostic setting.
- `reconcile_activity_endpoint.py` owns the controlled Foundry data-plane
  endpoint plan/apply/rollback because the endpoint is not an ARM resource.
- `publish_teams_agent.py` performs the Foundry data-plane package/catalog
  operations. The catalog POST cannot be pure Bicep today.
- Validate `Shared` first. Tenant-wide `Tenant`/`BotServiceTenant` promotion
  and Microsoft 365 administrator approval happen only after Shared succeeds.
- The current Teams handler sends complete responses and cards. Native Teams
  streaming is a separate direct-Activity enhancement and is not enabled in
  this increment. File and image behavior is channel-specific.

## 1. Prepare a private local profile

From `agents/order-resolution/foundry-private`, copy the sanitized template to
an external secure location or to the ignored `*.local.env` path:

```bash
cp ../deployment/profiles/foundry-private.local.env.example \
  ../deployment/profiles/foundry-private.local.env
chmod 600 ../deployment/profiles/foundry-private.local.env
export DEPLOYMENT_PROFILE_FILE="$PWD/../deployment/profiles/foundry-private.local.env"
```

Replace every placeholder locally. Never commit or paste tenant, subscription,
user, customer, resource, password, endpoint, or SSH values into documentation,
issues, chat, screenshots, or evidence.

For this demo, set all applicable regional fields to `eastus2` and set
`RUNNER_VM_SIZE=Standard_D4s_v7`. Keep the clean-room resource names unique but
local to the profile.

Load and validate without printing values:

```bash
source ../deployment/profile.sh
deployment_profile_load "$DEPLOYMENT_PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

AZD_PROJECT_DIR="$PWD/infra/foundry-hosted" \
  ../deployment/apply-azd-profile.sh "$DEPLOYMENT_PROFILE_FILE"
```

The explicit `DEPLOYMENT_PROFILE_FILE` is supported. When a Make target has a
`foundry-profile` prerequisite, also pass:

```text
PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

### Password and SSH key handling

- Generate/store the PostgreSQL administrator password in an approved password
  manager. Read it interactively; do not place it in the profile or shell
  history.
- Keep the SSH private key outside Git with mode `0600`. Only load the public
  key into the ignored AZD environment.
- AZD state under `.azure/` and `*.local.env` files are ignored, but still
  treat the workstation and runner as sensitive operator hosts.

```bash
read -rsp "PostgreSQL administrator password: " POSTGRES_ADMIN_PASSWORD
echo
export POSTGRES_ADMIN_PASSWORD

read -r RUNNER_VM_SSH_PUBLIC_KEY < /secure/path/runner_id_ed25519.pub

(
  cd infra/foundry-hosted
  azd env select "$AZURE_ENV_NAME" --no-prompt
  azd env set POSTGRES_ADMIN_PASSWORD "$POSTGRES_ADMIN_PASSWORD"
  azd env set RUNNER_VM_SSH_PUBLIC_KEY "$RUNNER_VM_SSH_PUBLIC_KEY"
)

unset POSTGRES_ADMIN_PASSWORD RUNNER_VM_SSH_PUBLIC_KEY
```

## 2. Login and verify the requested Azure context

Use an interactive operator login. The following checks compare local values
without displaying them:

```bash
az login --tenant "$AZURE_TENANT_ID" --use-device-code \
  --only-show-errors --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

actual_tenant="$(az account show --query tenantId --output tsv)"
actual_subscription="$(az account show --query id --output tsv)"

if [[ "$actual_tenant" != "$AZURE_TENANT_ID" ||
      "$actual_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "STOP: Azure CLI does not match the selected local profile." >&2
  exit 1
fi
echo "Azure tenant and subscription match the selected local profile."
unset actual_tenant actual_subscription
```

Do not include `az account show` JSON or user details in demo evidence.

## 3. Run capacity preflight and honor stop conditions

Apply the explicit profile to local AZD state and run the read-only preflight:

```bash
make foundry-preflight \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

The preflight validates:

- required provider registration;
- regional support for each service and configured SKU;
- the exact `Standard_D4s_v7` runner SKU and compute quota;
- Container Apps environment quota;
- AI Services SKU support;
- Search and PostgreSQL configuration/quota; and
- configured chat and embeddings model SKU/capacity.

**Stop** on any failure, warning that invalidates the demo, region/SKU
mismatch, missing provider registration, or insufficient quota. Do not
provision, switch to Canada Central, choose another SKU, disable private
networking, or reduce required capacity without a reviewed profile change and
a new successful preflight.

## 4. Preview and provision the clean room

First capture and review the non-mutating preview. It is not deployment proof:

```bash
make foundry-provision-preview \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

Proceed only when the preview matches the clean-room profile:

```bash
make foundry-provision \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

Provisioning keeps `MANAGE_PROJECT_CONNECTIONS=false` until the project
identity and required RBAC exist. If identity propagation or private-endpoint
deletion is still in progress, wait and retry the same stage. Never add a
public-access, firewall, administrator, or alternate-connection bypass.

## 5. Connect through Bastion and prepare the private runner

Use Azure Bastion with the private key held outside the repository. Resolve VM
and Bastion names locally from the selected resource group; do not paste them
into evidence.

On the VM:

```bash
cd /path/to/repository/agents/order-resolution/foundry-private
./scripts/github/bootstrap_vm_runner_host.sh
```

Registering the GitHub runner is optional for an operator-led local demo. If
release workflows will be used, supply the repository and registration token
through the approved secret channel, run
`scripts/github/register_vm_runner.sh`, and verify the
`foundry-private-ora` label is online before dispatch.

Securely copy the same local profile to the runner or create a new ignored
local copy from the sanitized template. Never transfer the SSH private key to
the repository.

## 6. Bootstrap runner state, deploy, and verify private Responses first

On the private runner, reload the profile, repeat the non-printing tenant and
subscription check, and set the PostgreSQL password in the ignored AZD
environment. Then hydrate live resource outputs:

```bash
export DEPLOYMENT_PROFILE_FILE="/secure/path/foundry-private.local.env"
source ../deployment/profile.sh
deployment_profile_load "$DEPLOYMENT_PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

read -rsp "PostgreSQL administrator password: " POSTGRES_ADMIN_PASSWORD
echo
export POSTGRES_ADMIN_PASSWORD
./scripts/foundry/bootstrap_private_azd_environment.sh
unset POSTGRES_ADMIN_PASSWORD
```

Complete the staged private deployment:

```bash
make foundry-postgres-bootstrap \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
make foundry-postgres-readiness \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
make foundry-project-connections \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
make foundry-app-only-release \
  PRIVATE_DEPLOYMENT_PROFILE="$DEPLOYMENT_PROFILE_FILE"
```

Verify the Responses path before enabling Activity:

```bash
make foundry-smoke SMOKE_MESSAGE="Resolve delayed order ORD-1001"
```

Stop if private DNS, PostgreSQL readiness, image pull, hosted activation,
Responses, or Entra authorization fails. Teams is not a workaround for a
broken private runtime.

## 7. Establish the interactive user context on the runner

Shared publication cannot use the GitHub OIDC/service-principal context. After
private Responses succeeds:

```bash
az logout
az login --tenant "$AZURE_TENANT_ID" --use-device-code \
  --only-show-errors --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

user_type="$(az account show --query user.type --output tsv)"
if [[ "${user_type,,}" != "user" ]]; then
  echo "STOP: Shared publication requires an interactive user login." >&2
  exit 1
fi
unset user_type
```

Repeat the tenant/subscription comparison from step 2 without printing values.

## 8. Plan, deploy Bot/channel, inspect, and publish Shared

Review `infra/foundry-hosted/teams-publication.json`. It must remain sanitized,
use `publishScope: "Shared"`, and use an intentional semantic `appVersion`.

```bash
make foundry-teams-plan
make foundry-teams-deploy-bot
make foundry-teams-package
```

`deploy-bot` creates the single-tenant Bot Service and `MsTeamsChannel` through
Bicep with `publicNetworkAccess: Disabled`, the versioned Foundry Activity URL,
and `BotRequest`/`AllMetrics` diagnostics targeting the deployment's single
Log Analytics workspace.
`package` applies the controlled Activity state while preserving Responses and
Entra, then writes an ignored ZIP.

Inspect package structure without printing manifest identifiers:

```bash
python3 - <<'PY'
import json
import zipfile
from pathlib import Path

manifest = json.loads(
    Path("infra/foundry-hosted/teams-publication.json").read_text()
)
package = Path(
    f".artifacts/teams-publication/packages/appPackage-{manifest['appVersion']}.zip"
)
if not package.is_file():
    raise SystemExit("No Teams package was generated.")
with zipfile.ZipFile(package) as archive:
    names = sorted(archive.namelist())
    if "manifest.json" not in names:
        raise SystemExit("Teams package is missing manifest.json.")
    json.loads(archive.read("manifest.json"))
print("Teams package ZIP and manifest JSON are structurally valid.")
PY
```

Review icons, descriptions, URLs, permissions, and scope locally. Do not attach
the ZIP or raw manifest to evidence. Publish and verify only local sanitized
state:

```bash
make foundry-teams-publish
make foundry-teams-verify-local-state
```

The publishing user can locate the Shared app under **Your agents**. Another
project-authorized tenant user must use the Teams v2 launcher built from the
publish response's sensitive `titleId`; the package manifest ID is not a valid
initial-acquisition link for this Shared catalog title. Keep the title ID only
in ignored sensitive state. If tenant app policy blocks installation, stop and
use the troubleshooting section; do not promote to Tenant to bypass policy.

## 9. Demonstrate invocation and Adaptive Card approval

Send:

```text
Resolve delayed order ORD-1001
```

Complete the Foundry sign-in card with the project-authorized tenant account.
Open each newly generated sign-in URL once; authorization codes are one-time.
Verify Teams displays only the final customer-facing resolution sentence, not
the internal workflow event JSON.

Run a high-risk scenario that pauses at human review. Verify Teams displays one
Adaptive Card with **Approve** and **Reject** buttons and no instruction to type
an approval command.

1. Select **Approve** and verify the same workflow checkpoint resumes and the
   card updates in place to **Approved**.
2. Start a fresh high-risk conversation, select **Reject**, and verify the card
   updates to **Rejected** and the workflow escalates.
3. Type `Approve` or `Reject` in a pending conversation and verify it does not
   resolve the checkpoint.
4. Reuse a stale card action and verify it is rejected.
5. Verify a card from conversation A cannot resume conversation B.

Expect complete replies rather than streamed tokens. Validate any file/image
behavior separately in Teams.

## 10. Retain only sanitized evidence

Run:

```bash
make foundry-teams-verify-local-state
git status --short
```

Retain only a generic checklist with UTC time, pass/fail status, app semantic
version, publication scope, and package hash from sanitized
`.artifacts/teams-publication/state.json`.

Do not retain or publish:

- tenant/subscription/user/customer identifiers;
- resource IDs, resource names, endpoints, conversation IDs, or title IDs;
- tokens, passwords, SSH material, local profiles, AZD state, raw CLI output,
  raw package manifests, or package ZIPs; or
- screenshots containing Azure/Teams identity or administration details.

The sensitive title state, package ZIP, local profile, AZD state, and generated
artifacts are ignored. Confirm none appears in `git status`.

## 11. Troubleshooting

| Failure | Operator action |
| --- | --- |
| Wrong tenant/subscription | Stop, log out, reload the local profile, perform interactive login, set the subscription, and rerun the non-printing comparison. |
| Shared publish rejects identity | Confirm `az account show --query user.type` is `user`; service principal, managed identity, and GitHub OIDC contexts are unsupported for Shared. |
| Foundry data-plane call cannot connect | Run from the VNet-connected runner; verify private DNS and endpoint reachability. Do not enable general public access. |
| `401`/`403` on Activity or catalog | Refresh interactive login, verify tenant context and RBAC, and confirm the Bot authorization scope matches `Shared`. Source-IP filtering does not replace authorization. |
| Bot/channel deployment fails | Review the Bicep deployment error and agent identity/tenant inputs locally. Do not print Bot or resource IDs into evidence. |
| Bot diagnostics are missing | Redeploy `iac/teams/main.bicep`; it declaratively enables `BotRequest` and `AllMetrics` against the resource group's single Log Analytics workspace. |
| Package/version rejected | Increment `appVersion` intentionally after a prior publication; do not reuse or decrease a published version. Re-run plan before package/publish. |
| App cannot be installed | Check Teams custom-app and app-permission policies for the publishing user. Validate Shared before requesting broader policy or tenant changes. |
| Manifest-ID link says the app cannot be found | Use the Teams v2 launcher with the sensitive Shared publication `titleId`, not the package manifest ID. |
| Sign-in says the authorization code was redeemed | Stop the waiting turn, send a fresh message, and open the newly generated sign-in link exactly once. Do not refresh or reopen the callback URL. |
| Teams still shows behavior from an older hosted version | Inspect the hosted session's `version_indicator`. Sessions are pinned to the version selected at creation. For a completed disposable demo session, delete only that session through the documented Foundry session API, then send a new Teams message so the platform creates a session on the active version. |
| Teams displays internal workflow JSON | Confirm the active image returns the final workflow message through `TextResponse`. Then inspect whether the Teams session is pinned to a pre-fix agent version before redeploying or republishing. |
| Tenant publication awaits approval | Expected after later `Tenant` promotion. A Microsoft 365 administrator must approve it externally; the script cannot self-approve. |
| Teams response is not streamed | Expected for the current handler. Native Teams streaming requires a separate streaming implementation inside the direct Activity handler and is not enabled here. |
| Approval card action returns `409` | The action was already used, replaced, expired, or the checkpoint is no longer pending. Start from the current pending card. |
| Approval card action returns `403` | The card belongs to a different Teams user or conversation. Use the card in the conversation where it was issued. |
| File/image differs from web/Responses | Treat as channel-specific behavior and validate the exact Teams client capability. |
| Capacity preflight fails | Stop. Resolve provider, service/SKU availability, or quota and rerun. Do not silently switch region/SKU. |

## 12. Roll back without harming Responses

1. Remove the Shared catalog entry through Microsoft 365 governance. No
   documented Foundry unpublish API is automated.
2. Review the generated rollback plan:

   ```bash
   make foundry-teams-rollback-plan
   ```

3. Remove Activity and Bot Service authorization while preserving Responses,
   Entra, and unrelated endpoint state:

   ```bash
   make foundry-activity-rollback
   ```

4. Decide whether to retain or delete Bot Service and `MsTeamsChannel`. Their
   lifecycle remains ARM/Bicep. Any deletion must be a separately reviewed
   Bicep/ARM lifecycle action; there is no implicit script deletion.
5. Re-run the private Responses smoke:

   ```bash
   make foundry-smoke SMOKE_MESSAGE="Resolve delayed order ORD-1001"
   ```

Rollback is incomplete if catalog removal remains pending, but catalog cleanup
must never trigger deletion of the Foundry agent, project, Responses protocol,
private dependencies, or durable workflow data.
