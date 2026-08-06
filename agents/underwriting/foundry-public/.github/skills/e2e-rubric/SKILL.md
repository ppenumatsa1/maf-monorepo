# e2e-rubric

Use this skill when editing UI, API responses, or workflow behavior.

## Rubric contract

The UI must support validating:

1. happy path decision
2. retry behavior
3. crash status and resumable run id
4. resume completion
5. fan-in shared state
6. checkpoint visibility
7. idempotency skip visibility
8. observability fields in event output

Playwright tests live in `frontend/tests/e2e`.
