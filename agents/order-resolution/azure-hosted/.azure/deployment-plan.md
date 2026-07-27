# Azure Hosted Deployment Plan

> **Status:** Deployed and validated from the monorepo on 2026-07-27.
> Bicep compilation, a non-mutating AZD preview, HTTPS health/proxy checks, and
> hosted Playwright UI parity passed against the existing target. Fresh
> post-deployment evidence remains required.

## Target

| Setting | Value |
| --- | --- |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Region | `northcentralus` |
| Deployment package | `infra/azure-apphosted/iac` |
| Frontend | `https://maf-frontend-puzsry.kindpebble-e634081a.northcentralus.azurecontainerapps.io` |
| Backend API | `https://maf-backend-puzsry.kindpebble-e634081a.northcentralus.azurecontainerapps.io` |

## Scope

Deploy the FastAPI MAF backend and React frontend from this variant into the
existing Container Apps resources. Foundry remains limited to model inference
and report-only evaluation; it is not an application host in this lane.

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

## Monorepo deployment evidence

- `azd deploy --no-prompt` deployed backend and frontend from this variant.
- The application-hosted smoke validated low-risk completion and high-risk HITL.
- Hosted Playwright passed all seven UI flows through the frontend proxy.
- The deterministic evaluation passed 10/10 cases.
- Application Insights recorded 21 recent workflow/HITL dependency spans.
