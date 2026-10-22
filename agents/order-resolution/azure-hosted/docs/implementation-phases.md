# Implementation Phases

## Current phase: documentation and release-contract alignment

The application has one MAF workflow hosted by FastAPI. The Azure package uses
an external frontend Container App, an internal backend Container App, retained
PostgreSQL with managed-identity access, Application Insights, and optional
Foundry model/evaluation resources.

Target-specific values come from an ignored operator profile. Documentation
uses only generic profile-based wording.

## Delivery phases

1. **Local correctness**
   - Validate backend boundaries, workflow behavior, deterministic evaluation,
     frontend build, and browser contracts.
2. **Fresh bootstrap**
   - Validate the target profile, preview the platform, provision only after
     authorization, establish managed-identity PostgreSQL, and transition to
     steady state.
3. **Steady-state operations**
   - Retain PostgreSQL and application state. Reconcile infrastructure only
     through an explicit reviewed command.
4. **App-only release**
   - Deploy immutable backend/frontend revisions and gather fresh smoke,
     browser/domain, telemetry, report-only evaluation, and final evidence.
5. **Ongoing maintenance**
   - Keep documentation, instruction files, release contracts, and evidence
     rules synchronized with behavior.

## Ongoing constraints

- Preserve native SSE events and deterministic HITL behavior.
- Keep `/rich` as a native additive contract; do not route raw payloads into an
  assistant UI.
- Keep AG-UI and CopilotKit read-only, redacted, selected-existing-thread
  projections.
- Do not create a second workflow path when model configuration is absent.
- Do not add private networking, Foundry hosted-agent/Responses, Bot, Activity,
  Teams, or Adaptive Card surfaces.
- Preserve managed-identity PostgreSQL and the external frontend/internal
  backend topology.
