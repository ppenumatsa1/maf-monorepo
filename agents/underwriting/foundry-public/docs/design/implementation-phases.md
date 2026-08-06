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

## Phase 3 (completed in repo): Hosted durable execution clean cutover

- Moved the MAF parent/child workflow and PostgreSQL durability boundary into `backend/foundry/main.py`, the hosted Responses entrypoint.
- Converted the public API to a relay/read-model adapter and preserved AG-UI/history/CopilotKit contracts.
- Kept retry/idempotency, crash/resume, and PostgreSQL checkpoints in the shared workflow rather than replacing them with hosted-lane shims.
- Established the clean-cutover rule that deployed public traffic uses the hosted Responses lane while local execution mode remains validation-only.

## Phase 4 (required for live-readiness claims): Release governance and evidence

- Adopt the canonical operating model in `docs/design/engineering-operating-model.md`.
- Run the checked-in authenticated release sequence and hosted validation gates.
- Verify deployed smoke, E2E, Foundry workflow/model traces, Application Insights correlation, and trace evaluation.
- Record evidence, issues, fixes, and deferrals in `docs/design/issues-changes-fixes.md`.

## Next phase candidates

- Tighten typed AG-UI event payload contracts shared across backend and frontend.
- Add richer timeline filtering and run-comparison views in the operations console.
- Expand automation around release-evidence capture without weakening the no-shims hosted boundary.
