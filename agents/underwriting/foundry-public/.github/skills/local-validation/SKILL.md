# local-validation

Use this skill before proposing completion.

## Run

1. `make test-backend`
2. `make test-frontend`
3. `make test-e2e` (requires backend + postgres reachable)

## Check

- Crash/resume still works with checkpoints.
- Retry events are visible.
- No duplicate results for same idempotency key.
