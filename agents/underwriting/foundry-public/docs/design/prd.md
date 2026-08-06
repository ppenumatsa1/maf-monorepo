# Product requirements: underwriting MAF prototype

## Goal

Deliver a local-first prototype that demonstrates real Microsoft Agent Framework workflow behavior for insurance underwriting:

1. Checkpointing and resume after crash.
2. Fan-out/fan-in aggregation.
3. Shared workflow state vs message passing.
4. One master workflow with direct risk, credit, medical, and driving executor execution.
5. Retry/backoff/failure handling via MAF middleware.
6. PostgreSQL persistence for checkpoints and business/audit state.
7. Idempotency across replay/resume.

## In scope

- Backend: Python 3.11+ FastAPI + MAF workflow runtime.
- Frontend: React + Vite dashboard to run scenarios and inspect state/events/checkpoints.
- Tests: backend tests and Playwright E2E rubric.
- Local runtime via Makefile and Docker Compose.
- Public deployment: Container Apps operations console/API adapter, Foundry
  Hosted Agent durable execution, Application Insights correlation, embedded
  CopilotKit selected-run assistance, and resource-reuse Bicep.

## Out of scope

- Authentication/authorization.
- Production-grade multi-tenant deployment.
- HITL approval UX beyond state/event demonstration.
- Browser access to Foundry or PostgreSQL credentials.
- Production use of `UNDERWRITING_EXECUTION_MODE=local`; it is restricted to
  isolated local validation.

## Success criteria

- `make run`, `make run-fail-once`, `make run-crash`, and `make resume` demonstrate expected behavior.
- `make test-backend`, `make test-frontend`, and Playwright E2E rubric pass.
- Docs clearly separate MAF checkpoint state from app business/audit state.
- Public release smoke correlates the AG-UI Request, durable run, and hosted
  Foundry workflow/model trace without emitting message content or secrets.
- The four direct executors fan out and fan in in one master-workflow superstep.
- After deployment, resume accepts only checkpoints written by that graph;
  version-40 nested-graph checkpoints are unsupported, with no compatibility
  workflow or fallback.
