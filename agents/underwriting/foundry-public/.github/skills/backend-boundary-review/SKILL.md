# backend-boundary-review

Use this skill when reviewing backend changes for architectural boundary violations.

## Verify

- Workflow logic stays in `workflows`/`executors`.
- Middleware concerns stay in `maf/middleware`.
- Persistence concerns stay in repository/checkpointing modules.
- API handlers avoid embedding business workflow logic directly.
