---
name: iac-review
description: Review Azure and Foundry infrastructure as code without deploying resources.
---

# IaC Review Skill

Use this skill to review Azure/Foundry deployment assets before validation or deployment. Do not run commands that create, update, or delete cloud resources.

## Scope

Review only repository deployment assets, including AZD configuration, Bicep modules, environment parameters, Docker/container settings, and smoke scripts.

## Review checklist

- Verify `azure.yaml`, `.azure/deployment-plan.md`, and Bicep files describe
  one coherent app-only normal release and a separately guarded reconciliation
  path.
- Confirm routine releases deploy only backend/frontend revisions. A changed
  IaC, Docker, or runtime file may require review, but it must not implicitly
  invoke provisioning.
- Review Bicep preview as evidence of proposed reconciliation only when an
  explicit non-secret approval reference is present. It must identify retained
  resource behavior and never authorize PostgreSQL server/database recreation.
- Review Container Apps ingress, health probes, environment variables, secrets references, scaling, CPU/memory, and revision behavior.
- Review ACR integration and image naming; ensure Container Apps can pull images using managed identity/RBAC rather than embedded credentials.
- Review Azure Database for PostgreSQL networking, authentication, connection
  secret handling, backups, SKU, and region assumptions. Reconciliation must
  preserve the one existing server and `maf_workflow` database identity.
- Review Key Vault usage for secrets, RBAC/access model, soft delete, purge protection expectations, and application secret references.
- Review Application Insights and Log Analytics wiring, retention, sampling assumptions, and required app settings.
- Review managed identities and RBAC assignments for least privilege across ACR, Key Vault, PostgreSQL, and observability resources.
- Confirm region and SKU assumptions are explicit, affordable for PoC use, and compatible across Container Apps, ACR, PostgreSQL, Key Vault, and Foundry resources.
- Review any Azure AI Foundry/OpenAI resources for private configuration, model/SKU/region assumptions, and secretless access where possible.
- Check smoke scripts for deterministic health, workflow, HITL, and RBAC assertions without destructive side effects.
- Confirm release images retain the approved CFS package feed
  `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple` and that
  frontend native dependencies are built for the Alpine/musl runtime.
- Check smoke/E2E/evaluation/telemetry scripts pass fresh release and thread
  correlation evidence forward instead of querying an unrelated historical
  time window.
- Flag security issues: plaintext secrets, broad roles, public admin endpoints, permissive CORS, disabled TLS, weak network posture, and destructive cleanup defaults.

## Output

Report only actionable findings with file paths, risk, and recommended fix. If no issues are found, state that IaC review passed without deployment.
