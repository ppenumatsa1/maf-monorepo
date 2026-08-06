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
9. Public release smoke confirms the AG-UI request is an Application Insights
   Request and the hosted MAF workflow/model trace is visible in Foundry.

Criteria 1-8 are automated Playwright coverage. Criterion 9 is a release
smoke check because it requires deployed Azure resources and telemetry
materialization. A rubric pass requires all automated criteria to pass.
