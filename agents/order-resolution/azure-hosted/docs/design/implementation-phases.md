# Implementation Phases

## Current phase: Preparing Azure validation

The application has one MAF workflow hosted by FastAPI. The Azure target is the
Container Apps package in `infra/azure-apphosted/`, with PostgreSQL persistence
and Application Insights. Foundry is used only for model inference and
report-only evaluation.

The target resource group is `rg-maf-ora-azure` in North Central US. East US is
excluded because of the Azure PostgreSQL offer restriction.

## Next steps

1. Validate the current code, tests, and Bicep/AZD package.
2. Mark `.azure/deployment-plan.md` **Ready for Validation** only when that
   evidence is current.
3. Complete Azure readiness validation before any authorized deployment.
4. After deployment, collect smoke, evaluation, and telemetry evidence.

## Ongoing constraints

- Preserve native SSE events and deterministic HITL behavior.
- Keep `/rich` as its stable native additive contract; do not route raw rich
  payloads into the assistant UI.
- Keep `/ag-ui` and the CopilotKit bridge read-only, selected-existing-thread,
  durable-event redacted projections. The frontend endpoint configuration is
  runtime-injected and the inspector stays disabled.
- Do not create a second workflow path when model configuration is absent.
- Do not add Foundry application-hosting surfaces.
- Default release work to `make release-app`; preserve PostgreSQL. Escalate
  IaC drift to explicit reviewed Bicep reconciliation, then record fresh
  smoke/E2E/report-only-eval/telemetry correlation rather than historical
  evidence.
