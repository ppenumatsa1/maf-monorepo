# E2E rubric

Playwright rubric source: `frontend/tests/e2e/rubric.ts`.

## Scored criteria

1. Happy path run completes and decision is shown.
2. Retry scenario records retry events and completes.
3. Crash scenario yields `CRASHED` status and a resumable run id.
4. Resume completes from a checkpointed run.
5. Fan-in state includes all required check results.
6. Checkpoint list is populated.
7. Idempotency skip signal is present in replay/resume path.
8. Event payload includes observability context fields.
9. Public release smoke confirms the AG-UI request is an Application Insights Request and the hosted MAF workflow/model trace is visible in Foundry.
10. Public release smoke confirms browser traffic stays on the frontend origin,
    `/backend-health` reaches the internal adapter, and direct backend public
    reachability is denied.
11. Public release smoke confirms retry and crash/resume evidence correlate on one durable `workflow_run_id` per run.
12. Hosted release evidence is recorded in `docs/design/issues-changes-fixes.md` before readiness is claimed.
13. Deployment verification proves frontend external/backend internal ingress,
    ready revisions/images, hosted version/image, App Insights connection,
    runtime database parity, and external-schema mode.

Criteria 1-8 are automated Playwright coverage. Criteria 9-12 are hosted release checks because they require deployed Azure resources, telemetry materialization, and the delivery ledger. A local rubric pass requires all automated criteria to pass. A full public release pass requires both the automated criteria and the hosted release checks.
