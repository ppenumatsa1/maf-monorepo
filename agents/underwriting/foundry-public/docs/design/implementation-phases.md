# Implementation Phases

## Phase 1 (completed, superseded workflow shape): Local MAF underwriting core

- Built the original real MAF parent/child workflow orchestration.
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

## Phase 3 (implemented in source; live authority remains the ledger): Direct-executor master-workflow cutover

- Replaced the nested parent/child graph with one master workflow whose risk, credit, medical, and driving executors fan out/fan in in one superstep.
- Kept the PostgreSQL durability boundary in `backend/foundry/main.py`, the hosted Responses entrypoint.
- Converted the internal API to a relay/read-model adapter behind the external
  frontend proxy and preserved AG-UI/history/CopilotKit contracts.
- Kept retry/idempotency, crash/resume, and PostgreSQL checkpoints in the shared workflow rather than replacing them with hosted-lane shims.
- Established the clean-cutover rule that deployed public traffic uses the hosted Responses lane while local execution mode remains validation-only.
- Declared superseded nested-graph checkpoints unsupported for resume after
  deployment. No compatibility workflow or fallback is provided.

## Phase 4 (implemented as the operating contract): Release governance and evidence

- Adopt the canonical operating model in `docs/design/engineering-operating-model.md`.
- Run the checked-in authenticated release sequence and hosted validation gates.
- Verify deployed smoke, E2E, Foundry workflow/model traces, Application Insights correlation, and trace evaluation.
- Record evidence, issues, fixes, and deferrals in `docs/design/issues-changes-fixes.md`.
- Verify a fresh post-cutover crash/resume run proves only the new master direct-executor checkpoint shape is resumed.

## Phase 5 (confirmed design; verify source and live evidence independently): Secure human review and Teams

- Pause only `REFER_TO_HUMAN_UNDERWRITER`.
- Preserve immutable machine recommendation and persist separate reviewer
  `APPROVED`/`DECLINED`.
- Add trusted origin and cross-channel isolation.
- Add administrator-owned approval and card-action schema plus exact
  least-privilege grants.
- Host Responses and Activity in one process.
- Add Bot Service, `MsTeamsChannel`, Shared publication automation, and
  merge-preserving Activity rollback.
- Render privacy-safe Adaptive Cards with opaque, expiring, one-time,
  reviewer/conversation-bound actions.
- Validate approve/decline, typed-text blocking, replay, expiry, concurrency,
  privacy, isolation, telemetry, and rollback.

No source, local test, preview, or documentation update is live deployment or
publication evidence. Record implementation and acceptance status only after
the corresponding gates complete.

## Next phase candidates

- Add production application authentication/authorization and trusted reviewer
  identity.
- Tighten shared typed contracts for review events across backend and frontend.
- Add richer timeline filtering and run-comparison views.
- Expand evidence automation without weakening the no-shims boundary.
