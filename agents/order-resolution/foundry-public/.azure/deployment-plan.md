# Foundry Public Deployment Plan

> **Status:** Validated for monorepo application deployment on 2026-07-27.
> The preview blocker that would have enabled evaluation Storage public access
> was corrected; a fresh preview now skips that account.

## Target

| Setting | Value |
| --- | --- |
| Resource group | `rg-maf-ora-foundry-public-dev2` |
| AZD environment | `foundry-public-dev2` |
| Foundry project | `order-resolution-public-managed-dev2` |
| Hosted agent | `order-resolution-hosted` |
| Deployment descriptor | `infra/foundry-hosted/azure.yaml` |

## Scope

Deploy the external frontend, internal FastAPI backend, and Foundry-hosted
agent defined by `infra/foundry-hosted/azure.yaml` into the existing public
Foundry target. PostgreSQL is public in this deployment model; no configuration
from the private lane is reused.

## Local configuration

Create ignored AZD state at
`infra/foundry-hosted/.azure/foundry-public-dev2/` using the retained local
environment without committing or printing values. `backend/.env.example`
remains a template only.

## Release gate

1. Compile `infra/foundry-hosted/iac/main.bicep` and run a non-mutating AZD
   provision preview from `infra/foundry-hosted`.
2. Review the preview before deploying backend, frontend, and hosted agent.
3. Verify public smoke, low- and high-risk HITL paths, hosted E2E, Foundry
   report evaluation, and Application Insights correlation.
