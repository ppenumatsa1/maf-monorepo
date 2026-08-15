# Implementation Phases

## Current phase: Standardized Azure-hosted release contract

The application has one MAF workflow hosted by FastAPI. The Azure target is the
Container Apps package in `infra/azure-apphosted/`, with PostgreSQL persistence
and Application Insights. Foundry is used only for model inference and
report-only evaluation.

The target is subscription `7df95e88-701c-4693-af77-3159f83b558d`,
resource group `rg-maf-ora-azure`, in North Central US. East US is
excluded because of the Azure PostgreSQL offer restriction.

## Next steps

1. Use the project-local deployment profile and run the source/Bicep gates.
2. For an authorized app-only release, deploy the tested immutable images.
3. Run deployment verification, smoke, browser E2E, three-scenario domain E2E,
   enforced report-only evaluation, and exact-pair telemetry correlation.
4. Retain the resulting success or failure evidence under one release ID.

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
  IaC drift to explicit guarded Bicep reconciliation, then record fresh
  smoke/E2E/report-only-eval/telemetry correlation rather than historical
  evidence.
- Keep deployment profiles, parsing, and contracts within this project; do not
  create a shared deployment implementation with another lane.
