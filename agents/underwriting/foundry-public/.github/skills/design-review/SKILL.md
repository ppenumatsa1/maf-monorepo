# design-review

Use this skill for design-level review before major refactors.

## Focus points

- MAF concepts are represented accurately (message passing, shared state, checkpoints).
- Postgres usage is clearly split between checkpoint storage and app projection tables.
- Failure/retry/idempotency paths are deterministic and observable.
- Frontend exposes evidence for each required behavior.
