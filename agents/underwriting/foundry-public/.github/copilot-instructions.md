# Copilot instructions for this repository

## Core expectations

- Keep workflow orchestration in real Microsoft Agent Framework workflows/executors.
- Do not replace MAF checkpointing with custom workflow engine logic.
- Treat `maf_checkpoints` as the authoritative persisted checkpoint backend.
- Keep message passing and shared workflow state semantics explicit.

## Boundaries

- `backend/app/workflows` + `backend/app/executors`: orchestration logic.
- `backend/app/maf/middleware`: cross-cutting resilience behavior.
- `backend/app/repository` + checkpointing: persistence adapters only.
- `frontend/src`: presentation and API calls only.

## Change hygiene

- Preserve API route contracts used by frontend and Playwright tests.
- Update docs under `docs/design/` when architecture/flow changes.
- Keep idempotency behavior replay-safe (no duplicate business writes).

## Validation baseline

- Backend: `make test-backend`
- Frontend build: `make test-frontend`
- E2E rubric: `make test-e2e`
