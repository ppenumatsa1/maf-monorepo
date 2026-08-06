# User Flow

## Delivery Journey and Status

| Stage | Status | What is currently wired |
| --- | --- | --- |
| Local MAF runtime | Implemented in repo | CLI and isolated E2E mode execute the shared workflow against local PostgreSQL |
| Foundry hosted runtime | Implemented in repo | Hosted Responses agent executes MAF with durable PostgreSQL state and rich traces |
| Operations console | Implemented in repo | React UI relays hosted runs, reads paged history, consumes AG-UI progress, and embeds a safe run assistant |
| Release governance | Canonical docs added | README + engineering operating model + delivery ledger define how hosted readiness is claimed |

Fresh hosted release evidence belongs in [issues-changes-fixes.md](issues-changes-fixes.md); this document describes the supported flow, not a current deployment claim.

## Current Runtime User Flow

1. Operator selects a scenario (happy path, retry, crash) and submits an application.
2. UI starts a hosted run and opens AG-UI stream updates.
3. Public adapter creates or reuses one `workflow_run_id` and invokes the hosted Responses agent.
4. Hosted agent starts parent workflow orchestration and persists the durable run.
5. Parent workflow fans out to risk, credit, medical, and driving child workflows.
6. Fan-in aggregator updates shared state as each check completes.
7. Final decision computes deterministic score and approval outcome.
8. Optional model rationale is attached to the final decision output.
9. UI reads run details, events, state, and checkpoints from durable APIs; its embedded assistant can explain the selected run using allowlisted metadata.

## Crash and Resume Flow

1. Operator runs crash scenario (`crash_after_executor` set by scenario).
2. Backend returns `CRASHED` status with the same `workflow_run_id`.
3. UI invokes resume for that run.
4. Resume loads latest persisted MAF checkpoint.
5. Remaining checks and final decision complete.
6. Idempotency prevents duplicate side effects during replayed execution steps.

## Operator Inspection Flow

1. Operator uses history search/filter (`GET /api/v1/underwriting/runs`).
2. Operator opens run details (`GET /api/v1/underwriting/runs/{run_id}`).
3. Operator inspects:
   - incremental state (`/state`),
   - ordered events (`/events`),
   - checkpoint snapshots (`/checkpoints`).
4. Operator confirms completion status, decision output, and recovery evidence.

## Clean cutover user flow

The public lane follows one production path:

1. Browser calls the public adapter only.
2. Public adapter starts or resumes the hosted Responses workflow.
3. Hosted workflow writes checkpoints, events, state, and results.
4. Browser refresh, replay, AG-UI, and CopilotKit explanation all come from the same durable run identity.

No public-lane shim should bypass the hosted workflow, replace checkpointing, or expose Foundry credentials to the browser.

## Release governance flow

1. Operator runs local gates.
2. Operator runs the checked-in authenticated Foundry release sequence.
3. Operator validates happy path, retry, and crash/resume behavior in hosted smoke and browser E2E.
4. Operator checks Foundry and Application Insights correlation using the durable `workflow_run_id`.
5. Operator records evidence and any deferrals in [issues-changes-fixes.md](issues-changes-fixes.md).

## Expected Outcomes

- Happy path: completed run with decision output and persisted checkpoints/events.
- Retry path: retry-related events are present and final result appears once.
- Crash/resume path: resumable crashed run completes without duplicate persistence.
- Public cutover path: browser, public adapter, hosted Responses workflow, and PostgreSQL all correlate on one `workflow_run_id`.
