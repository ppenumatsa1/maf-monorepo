# Business Rules - Azure-Hosted Order Resolution

> This file is the behavior source of truth. Implementation, testing, and
> operations documents should link here instead of restating rules differently.

## Issue and order resolution

- **BR-1 Issue classification.**
  - Text containing `damage` or `broken` is `damaged_item`.
  - Text containing `wrong` is `wrong_item`.
  - Other supported requests are `late_delivery`.
- **BR-2 Synthetic order mapping.**
  - Text containing `1009` maps to the high-value synthetic fixture.
  - Other supported order numbers map to the low-value synthetic fixture.
  - This is a demo limitation, not a production order lookup rule.
- **BR-3 Policy mapping.**
  - `late_delivery` -> `refund_allowed_if_delay_exceeds_3_days`
  - `damaged_item` -> `replacement_or_full_refund_with_photo_proof`
  - `wrong_item` -> `free_replacement_and_return_label`
  - Unknown issue -> `manual_review_required`

## Human approval

- **BR-4 HITL trigger.** Approval is required when at least one condition is
  true:
  - amount is `>= 100`;
  - issue type is `damaged_item`; or
  - policy contains `manual_review`.
- **BR-5 Pause before side effect.**
  - A gated resolution persists a checkpoint and pending approval before
    resolution submission.
- **BR-6 Exact checkpoint decision.**
  - Approve or reject resolves only the referenced pending checkpoint.
  - Approval resumes the same durable workflow and submits the proposed action.
  - Rejection does not submit the action and ends in `escalated`.
- **BR-7 Idempotency.**
  - A checkpoint resolves once.
  - Replayed decisions cannot emit another effective decision or terminal
    result.
  - Resolution submission is protected by a workflow/step/business idempotency
    key.

## Conversation and history

- **BR-8 Stable thread identity.**
  - A workflow and its follow-ups retain one durable thread identifier.
- **BR-9 Durable history.**
  - PostgreSQL, not browser memory or an in-memory event bus, is the source of
    truth for runs, events, messages, approvals, and checkpoints.
- **BR-10 Explanation follow-up.**
  - An explanation request in an existing thread describes the prior
    resolution and does not start another order-resolution action.

## UI and projection boundaries

- **BR-11 Stable native contract.**
  - Native SSE and durable history are authoritative.
  - Rich SSE, AG-UI, and CopilotKit are additive.
- **BR-12 Selected-thread projection is read-only.**
  - It can select one existing thread and show safe lifecycle and approval
    state.
  - It cannot start, resume, approve, reject, or change a workflow.
- **BR-13 Sensitive execution context stays server-side.**
  - Order and policy data, MCP/RAG payloads, tool arguments/results, prompts,
    raw model output, checkpoint state, credentials, and secrets are excluded
    from optional selected-thread projections.

## Hosting, identity, and release boundaries

- **BR-14 Browser boundary.**
  - The browser calls only the external frontend's same-origin `/api` path.
  - The internal FastAPI backend alone calls PostgreSQL and optional Foundry
    model endpoints.
- **BR-15 Application host.**
  - FastAPI is the only MAF application runtime.
  - Foundry evaluation consumes captured HTTP workflow results and cannot start,
    resume, or mutate application workflows.
- **BR-16 Database identity.**
  - Azure PostgreSQL runtime access uses managed identity.
  - Normal application releases never replace the retained server or database.
- **BR-17 Release evidence.**
  - A release is successful only when deployment verification, smoke, browser
    and domain E2E, telemetry, report-only evaluation, and final evidence all
    pass in one release window.
  - A run-level pass cannot mask an individual evaluator error.
- **BR-18 Infrastructure authority.**
  - Fresh bootstrap, steady-state infrastructure reconciliation, and app-only
    release are distinct operator actions.
  - Routine app-only releases do not apply full infrastructure templates.

## Current security limitation

- **BR-19 Application authentication is not implemented.**
  - Chat, HITL, workflow-history, and selected-thread endpoints do not yet have
    a production user authentication and authorization layer.
  - A request-supplied reviewer value is not a trusted identity.
