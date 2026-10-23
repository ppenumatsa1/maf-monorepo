# Securely Publish the Public Underwriting Agent to Teams

## Scope

Publish the existing public Underwriting hosted agent to an approved set of
Microsoft Teams users while preserving the web/Responses lane and the
underwriting review security model.

This document defines the design and operator checks. It does not claim that a
Bot, Teams app, Activity endpoint, or catalog publication is currently live.

## Design summary

- Responses and Activity run in the same hosted process and invoke the same
  MAF underwriting workflow.
- Azure Bot Service and `MsTeamsChannel` bridge Teams to the Foundry Activity
  protocol.
- The Bot messaging endpoint pins the Foundry Activity contract to
  `api-version=2025-05-15-preview`; omitting the query parameter causes the
  service to reject channel traffic before the hosted runtime is invoked.
- Endpoint reconciliation retains Responses and Entra and adds Activity plus
  `BotServiceRbac`.
- Because this project intentionally allows public Foundry network access, the
  Activity configuration does not enable the private-network-only
  `enable_m365_public_endpoint` exception. Authentication and
  `BotServiceRbac` remain mandatory.
- Microsoft 365 publication uses Shared scope, not Tenant scope.
- Only `REFER_TO_HUMAN_UNDERWRITER` produces an actionable Adaptive Card.
- Machine recommendation remains immutable; the reviewer records a separate
  `APPROVED` or `DECLINED` outcome.
- Card actions use opaque, expiring, one-time, repository-backed bindings.
- Web/Responses and Teams checkpoints cannot authorize each other.

## Public topology

Teams publication does not import private-lane infrastructure. Do not add:

- a VNet-connected runner;
- private endpoints or private DNS;
- Bastion, VPN, or NAT;
- a second hosted agent or workflow;
- a browser-to-Bot or browser-to-Foundry path.

The normal public web topology remains external frontend -> internal FastAPI
adapter -> Foundry Responses. Teams adds Microsoft 365 -> Azure Bot Service ->
Foundry Activity.

## Publication controls

### Shared distribution

Use `publishScope: "Shared"`. Share/install the app only for approved users.
Tenant publication is not the target.

Distribution is not the sole security boundary. Invocation must also enforce
tenant/channel token validation and `BotServiceRbac`.

### Merge-preserving endpoint configuration

Activity configuration updates must preserve:

- Responses protocol;
- Entra authorization;
- any required existing endpoint configuration.

Add:

- Activity protocol;
- `BotServiceRbac`.

Do not add `enable_m365_public_endpoint` in this public lane. That setting is
the source-IP-filtered exception for projects whose public network access is
disabled; enabling it would prevent the release runner from exercising the
Entra-authorized public Activity route directly.

Rollback removes Activity and Bot authorization only; it must not remove
Responses or Entra.

### Publisher boundary

Azure resource deployment and Microsoft 365 publication are different
authorities:

- an Azure operator previews and deploys Bot/Teams channel resources;
- an interactive Microsoft 365 publisher publishes the explicit Shared app
  version.

Do not place publisher tokens, catalog identifiers, package contents, or
target-specific values in source control or current-state docs.

## Underwriting Adaptive Card

### Allowed fields

- generic review title;
- machine recommendation category;
- non-sensitive run/case reference;
- non-sensitive checkpoint reference;
- `Approve` and `Decline` labels.

### Prohibited fields

- applicant identity;
- age, health disclosures, income, requested coverage, credit score, or
  driving history;
- raw check results or score breakdown;
- prompts, rationale, or model output;
- database values or checkpoint payload;
- endpoint, resource, credential, secret, or token detail.

### Action security

Each card action carries only a random opaque token. PostgreSQL stores its
hash and bindings:

- workflow run;
- checkpoint;
- requested decision;
- reviewer;
- conversation;
- expiry;
- action batch.

The selected action is atomically claimed before resume and its sibling is
superseded. Expired, replayed, wrong-user, wrong-conversation,
wrong-checkpoint, already-resolved, or cross-channel actions fail closed.
Typed approval words remain ordinary conversation text.

## Controlled operator sequence

1. Verify the current web/Responses release and administrator-owned review
   schema.
2. Plan Activity reconciliation and inspect the retained protocols and
   authorization schemes.
3. Preview Bot Service and `MsTeamsChannel` infrastructure.
4. Deploy the reviewed channel resources.
5. Apply Activity configuration.
6. Generate and inspect the sanitized app package.
7. Publish an explicit Shared version with the interactive publisher.
8. Verify sanitized local publication state.
9. Run acceptance and telemetry.
10. Review rollback before handoff.

Checked-in command sequence:

```bash
make test-foundry-activity-endpoint
make test-foundry-teams-publishing
make foundry-activity-plan
make foundry-teams-plan
make foundry-teams-preview
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-teams-deploy-bot
make foundry-activity-apply
make foundry-teams-package
make foundry-teams-publish
make foundry-teams-status
make foundry-teams-rollback-plan
```

Publication is intentionally excluded from GitHub Actions because it requires
delegated interactive user authentication.

## Acceptance

1. Authorized Shared user can invoke the agent.
2. Unauthorized or wrong-tenant user cannot invoke it.
3. Forwarded catalog/link access does not bypass Foundry RBAC.
4. Normal web/Responses invocation still works.
5. Only a referral creates a review card.
6. Machine recommendation remains a referral after reviewer approve/decline.
7. Approve and decline each resolve only their bound checkpoint.
8. Typed decisions do not resolve a checkpoint.
9. Wrong user and wrong conversation fail.
10. Expiry, replay, and concurrent sibling action fail safely.
11. Responses cannot resolve a Teams-originated checkpoint.
12. Card JSON and telemetry contain none of the prohibited fields.
13. Rollback removes Activity/Bot authorization while preserving
    Responses/Entra.

Record exact app versions, catalog state, users/groups, resource identifiers,
run IDs, counts, timings, and acceptance results only in protected operational
state and the secret-free delivery ledger.

## Related documents

- [Human-underwriter review](hitl-review.md)
- [Business rules](business-rules.md)
- [Deployment flow](deployment-flow.md)
- [Schema, I/O, and telemetry](schema-io-telemetry.md)
