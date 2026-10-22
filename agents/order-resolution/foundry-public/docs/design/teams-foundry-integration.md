# Public Foundry Agent in Microsoft Teams

**Status:** Implemented in source with credential-free contract coverage.
Reviewed Bot/Teams deployment, Shared publication, live Activity acceptance,
telemetry, and rollback evidence are pending.

## Runtime and topology

The public hosted image runs one process that composes
`ResponsesAgentServerHost` and `ActivityAgentServerHost`. Both adapters call the
same order-resolution application service and the same sequential MAF workflow.
Adding Teams is additive:

- Responses remains the browser/wrapper and programmatic protocol.
- Activity handles Teams messages and Adaptive Card invokes.
- Native SSE, durable history, AG-UI, and CopilotKit remain unchanged.
- The public lane adds no VNet, private endpoint, capability host, private
  runner, or alternate workflow path.

Azure Bot Service and its `MsTeamsChannel` child are deployed from
`infra/foundry-hosted/iac/teams/main.bicep`. The bot is single-tenant, uses the
active hosted-agent identity client ID, points to the Foundry Activity Protocol
endpoint, and sends `BotRequest` logs and `AllMetrics` to the lane's existing
Log Analytics workspace.

The Teams module is target-agnostic. It takes tenant, hosted identity, Foundry
resource/project/agent, resource group, and Log Analytics values from the
active deployment context rather than committed defaults. The Bot Service and
channel use Azure's required `global` resource location; the workload region
remains selected by the parent deployment profile. No subscription, tenant,
operator identity, or regional resource identifier is committed in this
module.

## Why Activity cannot remove Responses

`scripts/foundry/reconcile_activity_endpoint.py` first GETs the complete agent
document. It refuses to continue unless both the Responses protocol and Entra
authorization already exist. It then copies every current protocol and
authorization scheme, changes only the Activity/Bot authorization entries, and
PATCHes the two replacement fields with a merge-preserving payload. An ETag is
sent as `If-Match` when available, so concurrent endpoint changes fail rather
than being overwritten.

Shared apply adds:

```json
{
  "activity": {
    "enable_m365_public_endpoint": true
  }
}
```

and one `BotServiceRbac` scheme. Rollback removes only `activity`,
`BotServiceRbac`, and `BotServiceTenant`; Responses, Entra, and unrelated
protocols/schemes remain.

## Shared Microsoft 365 publication

Publication metadata is reviewed in
`infra/foundry-hosted/teams-publication.json`. Every catalog update requires an
explicit semantic `appVersion` increment. Shared package generation and
publication require an interactive Azure CLI user; service-principal and
managed-identity contexts are rejected before Activity is changed.

```bash
make foundry-activity-plan
make foundry-teams-plan
make foundry-teams-deploy-bot
make foundry-teams-package
make foundry-teams-publish
make foundry-teams-verify-local-state
```

Generated ZIPs and sanitized version/hash/status evidence are stored under the
ignored `.artifacts/teams-publication/` directory. The Bot ARM ID is validated
in memory and is not persisted. A returned Microsoft 365 `titleId` is stored
separately with mode `0600` and never printed. Tokens, tenant IDs, endpoints,
resource IDs, and customer data are excluded from sanitized state.

Tenant publication is not the default. It replaces `BotServiceRbac` with
`BotServiceTenant` and requires the external Microsoft 365 administrator
approval process.

## Teams message and card behavior

A normal Teams message uses the Teams conversation ID as the workflow thread
and session ID and persists `origin_channel=teams_activity`. A completed turn
returns customer-facing text. A pending approval returns an Adaptive Card with
Approve and Reject `Action.Execute` buttons.

The pending card contains no checkpoint ID, workflow state, order ID, amount,
user ID, or conversation ID. Each button contains only an opaque random token.
The repository stores only hashes and binds each token to:

- workflow thread and exact checkpoint;
- approve or reject decision;
- Teams user and conversation;
- one action batch; and
- expiration time.

Free-form `Approve`, `Reject`, `yes`, or `no` never resolves a pending Teams
checkpoint. The user is directed to the card instead. Responses structured
decisions cannot resolve a Teams-origin checkpoint, and Teams cards cannot be
issued for API/Responses-origin checkpoints.

## Why two concurrent card actions cannot both resume

Approve and Reject share one PostgreSQL batch. `claim_action` performs one
conditional statement against a still-pending approval and still-pending token
rows. The winning token moves to `processing` while its sibling moves to
`superseded`. A concurrent claimant finds no eligible pending row and receives
`action_already_used`; it never reaches workflow resume.

After a successful resume, `complete_action` marks the processing row consumed.
If resume fails, `release_action` restores the batch only while the approval is
still pending. This permits a safe retry without reopening an already resolved
checkpoint. The successful invoke returns a resolved Adaptive Card, replacing
the original pending card in place.

## Rollback

```bash
make foundry-teams-rollback-plan
make foundry-activity-rollback
```

The automated rollback removes Activity and Bot authorization only. Microsoft
documents package and publish operations but no Foundry unpublish API, so
catalog removal remains an explicit Microsoft 365 governance action. Bot
Service deletion or retention is a separately reviewed ARM/Bicep lifecycle
decision. Rollback must not delete the hosted agent, Responses protocol, Entra
authorization, PostgreSQL state, or the public browser topology.

## Credential-free validation

```bash
make test-foundry-activity-endpoint
make test-foundry-teams-publishing
make foundry-iac-build
```

The contracts cover merge preservation, missing Responses/Entra refusal, ETag
handling, sanitized failures, manifest/version rules, package inspection,
interactive Shared publication, local-state redaction, Bot Service and
`MsTeamsChannel` shape, Adaptive Card approve/reject, wrong user/conversation,
replay, resolved-card replacement, and atomic competing claims.

These local contracts do not establish that the Bot, channel, endpoint merge,
or Microsoft 365 catalog version is live.
