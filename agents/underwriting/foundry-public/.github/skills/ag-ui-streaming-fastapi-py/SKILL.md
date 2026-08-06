---
name: ag-ui-streaming-fastapi-py
description: Implement and review FastAPI streaming endpoints that project MAF workflow events into AG-UI-compatible event envelopes for frontend and CopilotKit-style consumers.
---

# AG-UI Streaming for FastAPI (Underwriting)

Use this skill when changing streaming APIs, event envelopes, or backend-to-frontend event projection.

## Scope

- Endpoint surface: POST /api/v1/underwriting/ag-ui
- Backend sources: workflow events emitted by MAF runner/executors
- Projection target: AG-UI-compatible stream envelopes consumed by frontend

## Guardrails

- Treat native MAF events as source-of-truth; AG-UI events are additive projections.
- Do not break existing event types without coordinated frontend/test/doc updates.
- Keep payload fields stable for run identifiers, stage names, checkpoint ids, and idempotency markers.
- Preserve stream ordering expectations for start, stage progress, terminal output, and failures.

## Required verification

1. Validate backend stream contract tests in `backend/tests/test_agui.py`.
2. Validate frontend E2E assertions in `frontend/tests/e2e/underwriting.spec.ts`.
3. Validate docs parity in `docs/design/schema-io-telemetry.md` and `docs/design/e2e-rubric.md`.
