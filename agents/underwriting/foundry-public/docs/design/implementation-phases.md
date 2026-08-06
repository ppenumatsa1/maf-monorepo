# Implementation Phases

## Phase 1 (completed): Local MAF underwriting core

- Built real MAF parent/child workflow orchestration.
- Implemented fan-out/fan-in aggregation with shared state.
- Added idempotency and retry/backoff middleware behavior.
- Added custom PostgreSQL checkpoint storage and resume path.
- Added CLI and backend tests for crash/recovery behavior.

## Phase 2 (completed): API and operator experience

- Added FastAPI run/resume/history/state/events/checkpoints routes.
- Added containerized local stack with PostgreSQL, backend, and frontend.
- Added React operations UI for scenarios and run inspection.
- Added Playwright E2E rubric for operator-path validation.
- Added OpenTelemetry-based request instrumentation.

## Phase 3 (implemented; release validation pending): Hosted durable execution

- Moved the MAF parent/child workflow and PostgreSQL durability boundary into
  `backend/foundry/main.py`, the Hosted Agent Responses entrypoint.
- Converted the public API to a relay/read-model adapter and preserved
  AG-UI/history contracts.
- Declared PostgreSQL password auth and a narrowed Azure-services firewall rule
  in resource-reuse Bicep. Added repeatable credential provisioning, readiness,
  rotation, and deployment scripts.
- Added an explicitly opt-in full-server rebuild path. It pins the discovered
  PostgreSQL creation configuration in Bicep and can delete only the fixed
  public server after an exact confirmation token, then recreates it through
  the normal provision target.
- Added hosted workflow/model telemetry correlation, a selected-run CopilotKit
  assistant, and an explicit local-only E2E execution mode.

## Phase 4 (release validation)

- Provision the declared PostgreSQL authentication/firewall change.
- Provision/rotate the dedicated hosted runtime role using a secure local
  input, then run readiness checks.
- Deploy hosted agent, public adapter, and frontend.
- Verify deployed smoke, E2E, Foundry workflow/model traces, Application
  Insights correlation, and trace evaluation.

## Next Phase Candidates

- Tighten typed AG-UI event payload contracts shared across backend and frontend.
- Add richer timeline filtering and run-comparison views in the operations console.
- Expand CI quality gates for docs + public Request/Foundry trace verification.
