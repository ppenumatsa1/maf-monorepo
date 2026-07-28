# Azure Hosted Deployment Plan

> **Status:** Deployed and validated from the monorepo on 2026-07-28. The
> previous target was intentionally deleted, then reprovisioned from this
> package. The prior 2026-07-27 evidence remains historical only.

## Target

| Setting | Value |
| --- | --- |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Region | `northcentralus` |
| Deployment package | `infra/azure-apphosted/iac` |
| Frontend | `https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io` |
| Backend API | `https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io` |

## Scope

Provision the FastAPI MAF backend and React frontend from this variant, then
deploy them into the newly created Container Apps resources. Foundry remains
limited to model inference and report-only evaluation; it is not an application
host in this lane.

## Local configuration

Create ignored AZD state at `.azure/maf-ora-azure/` from the existing local
environment without committing or printing values. Use `backend/.env.example`
and `infra/azure-apphosted/runtime/.env.example` only as configuration
templates; they are not deployment credentials.

## Release gate

1. Compile Bicep and run `azd provision --preview` from this variant.
2. Review the preview against the existing resource group.
3. Deploy backend and frontend only after the preview is accepted.
4. Verify HTTPS health, same-origin API/SSE behavior, hosted Playwright,
   deterministic evaluation, report-only Foundry evaluation, and correlated
   Application Insights telemetry.

## Fresh monorepo deployment evidence (2026-07-28)

- `azd provision --no-prompt` recreated the resource group, Foundry account and
  project, PostgreSQL, Container Apps environment, ACR, monitoring, backend,
  and frontend.
- `azd deploy --no-prompt` deployed backend and frontend from this variant.
- The application-hosted smoke validated low-risk completion and high-risk HITL.
- Hosted Playwright passed all seven UI flows through the frontend proxy.
- `make eval-foundry-deployed` completed two Foundry-evaluated cases with two
  passed, zero failed, and zero errored.
- Application Insights recorded 32 recent workflow/HITL dependency spans.
