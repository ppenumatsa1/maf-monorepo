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
9. Only `REFER_TO_HUMAN_UNDERWRITER` pauses for review.
10. Machine recommendation remains immutable and reviewer `APPROVED` or
    `DECLINED` is persisted separately.
11. Duplicate/concurrent review attempts produce one effective outcome.
12. Public release smoke confirms the AG-UI request is an Application Insights Request and the hosted MAF workflow/model trace is visible in Foundry.
13. Public release smoke confirms browser traffic stays on the frontend origin,
    `/backend-health` reaches the internal adapter, and direct backend public
    reachability is denied.
14. Public release smoke confirms retry and crash/resume evidence correlate on one durable `workflow_run_id` per run.
15. When Teams is in scope, authorized Shared invocation and privacy-safe
    Adaptive Card rendering pass.
16. Wrong-user, wrong-conversation, expiry, replay, concurrent sibling,
    typed-text, and cross-channel decisions fail closed.
17. Card and telemetry privacy assertions find no prohibited underwriting data,
    token material, credentials, or secrets.
18. Hosted release evidence is recorded in `docs/design/issues-changes-fixes.md` before readiness is claimed.
19. Deployment verification proves frontend external/backend internal ingress,
    ready revisions/images, hosted version/image, App Insights connection,
    runtime database parity, and external-schema mode.

Criteria 1-8 are the existing Playwright baseline. Criteria 9-11 require
focused workflow/repository coverage and should become browser coverage when
the review UI is in scope. Criteria 12-19 are hosted release/publication checks
because they require deployed Azure resources, telemetry materialization,
Teams, or the delivery ledger. A full public release pass requires all
applicable criteria; a local pass does not prove deployment or publication.
