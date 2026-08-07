# Foundry Private Deployment Plan

> **Status:** Ready for Validation. Infrastructure provisioning remains blocked
> until its preview contains no unreviewed drift.

## Target

| Setting | Value |
| --- | --- |
| Resource group | `rg-maf-ora-foundry-v2` |
| AZD environment | `foundry-private-env` |
| Region | `eastus2` (PostgreSQL: `centralus`) |
| Hosted agent | `order-resolution-hosted` |
| Canonical PostgreSQL FQDN | `maffndpgv20722.postgres.database.azure.com` |
| Private runner label | `foundry-private-v2` |

## Deployment entry points

- Variant-root `azure.yaml`: hosted-agent definition.
- `infra/foundry-hosted/azure.yaml`: backend/frontend and hosted-agent
  application deployment descriptor.

## Private-network invariants

PostgreSQL public access is disabled and the Azure-services firewall rule has
been removed. The frontend is the only external ingress; it proxies `/api` to
the internal backend. The backend and hosted agent reach Foundry and PostgreSQL
through private networking. Both Container Apps have a minimum replica of one.

## Local configuration

Create ignored AZD state at
`infra/foundry-hosted/.azure/foundry-private-env/` using the retained local
environment without committing or printing values. Keep the runtime database
URL, canonical FQDN, and PostgreSQL server name aligned.

## Release gate

1. Compile Bicep and run `azd provision --preview` only.
2. Block provisioning on any unreviewed change to private networking, database
   access, DNS, firewall rules, identities/RBAC, Foundry connections, or
   observability resources.
3. If infrastructure preview is not safe, deploy only application artifacts
   from the existing entry points.
4. Use the VNet runner for private connectivity proof, hosted E2E, report-only
   evaluation, and correlated telemetry validation.
