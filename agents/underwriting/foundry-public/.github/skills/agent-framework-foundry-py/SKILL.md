---
name: agent-framework-foundry-py
description: Maintain underwriting MAF workflows with agent-framework-foundry, streamed workflow events, checkpoint resume flows, and hosted Foundry execution paths.
---

# Microsoft Agent Framework Foundry Workflows for Underwriting

Use this repository-owned skill for underwriting workflow implementation and review.

## Runtime ownership

- backend/app/maf/workflows/\* owns master-workflow orchestration.
- backend/app/maf/executors/\* owns underwriting stage logic.
- backend/app/maf/middleware/\* owns resilience and failure shaping.
- backend/app/maf/runner.py owns run execution and streaming behavior.
- backend/app/maf/agui.py owns AG-UI projection helpers.
- backend/app/api/v1/routes/underwriting.py owns HTTP route boundaries only.

## Workflow guardrails

- Keep orchestration in MAF workflows; do not move decision flow into API routes.
- Keep risk, credit, medical, and driving as direct executors that fan out and fan in in one master-workflow superstep; do not reintroduce nested workflows.
- Emit additive stream projections for AG-UI consumers; keep native workflow events stable.
- Preserve deterministic checkpoint and resume behavior for crash/restart handling. Only checkpoints produced by the deployed direct-executor graph are resumable; version-40 nested-graph checkpoints have no compatibility workflow or fallback.
- Keep idempotency and retry semantics explicit and observable in emitted events.

## Required verification

1. Validate `backend/tests/test_resume.py` for checkpoint/resume behavior.
2. Validate `backend/tests/test_idempotency.py` for duplicate suppression behavior.
3. Validate `backend/tests/test_agui.py` for stream contract stability.
4. Update design docs when workflow event semantics change.
