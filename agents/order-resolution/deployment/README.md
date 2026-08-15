# Order Resolution deployment profiles

This is the shared, non-secret target contract for all three deployment lanes:
Azure app-hosted, Foundry public, and Foundry private.

This directory is the canonical profile authority. Azure and Foundry consumers
must prefer `agents/order-resolution/deployment/profiles/*.env`. Lane-local
profile tooling remains only as `legacy_pending_cutover` compatibility and
must not become a second source of truth.

Each profile defines only the values that identify a deployment target:

- Azure subscription
- resource group
- Azure location
- AZD environment name
- resource name prefix
- deployment lane

Profiles deliberately do **not** contain resource IDs, endpoints, database
URLs, passwords, tokens, client secrets, or release images. Those remain in
the lane's existing local AZD environment or protected GitHub Environment.
Changing targets does not copy secrets between subscriptions.

## Switch a target

1. Copy the example for the lane and replace its placeholder values.
2. Validate the target declaration:

   ```bash
   ./profile.sh validate profiles/foundry-public.env
   ```

3. Apply it to that lane's local AZD environment:

   ```bash
   ./apply-azd-profile.sh profiles/foundry-public.env
   ```

The command selects (or creates locally) the named AZD environment and writes
`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, and
`NAME_PREFIX`. It does not authenticate, provision cloud resources, retrieve
secrets, or deploy an application. Run the lane's existing deploy command
after its target-specific AZD configuration and secret references are present.

## Design boundary

This contract standardizes selecting an **existing** deployment target. It
does not bootstrap a new subscription, create private runners, change
database schema behavior, create identities, or alter runtime secret storage.
Those remain separate operational work if needed later.
