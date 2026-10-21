# Business Rules - Private Order Resolution Agent

> This file is the behavior source of truth. Implementation and test documents
> should link here instead of restating rules differently.

## Issue and order resolution

- **BR-1 Issue classification.**
  - Text containing `damage` or `broken` is `damaged_item`.
  - Text containing `wrong` is `wrong_item`.
  - Other supported requests are `late_delivery`.
- **BR-2 Synthetic order mapping.**
  - Text containing `1009` maps to `ord-1009` with amount `185.0`.
  - Other order numbers currently map to `ord-1001` with amount `79.0`.
  - This is a demo fixture limitation, not a production lookup rule.
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
  - A gated resolution must persist a checkpoint and pending approval before
    resolution submission.
- **BR-6 Exact checkpoint decision.**
  - Approve/reject resolves only the referenced pending checkpoint.
  - Approval resumes the same thread and submits the proposed action.
  - Rejection does not submit the action and ends in `escalated`.
- **BR-7 Idempotency.**
  - A checkpoint resolves once.
  - Repeated approval/rejection cannot emit another effective decision or
    terminal outcome.
  - Resolution submission is protected by a workflow/step/business
    idempotency key.

## Conversation and history

- **BR-8 Stable thread identity.**
  - A new private hosted request creates a Foundry `conv_...` conversation.
  - Follow-ups and HITL decisions reuse that conversation/thread.
- **BR-9 Durable history.**
  - PostgreSQL, not the Foundry conversation or an in-memory event bus, is the
    application source of truth for runs, events, messages, approvals, and
    checkpoints.
- **BR-10 Explanation follow-up.**
  - An explanation request in an existing thread describes the prior
    resolution and does not start a second order-resolution action.

## UI and projection boundaries

- **BR-11 Stable native contract.**
  - Native SSE and durable history are authoritative.
  - Rich SSE, AG-UI, and CopilotKit are additive.
- **BR-12 Selected-thread projection is read-only.**
  - It can select one existing thread and show safe lifecycle/approval state.
  - It cannot start, resume, approve, reject, or change a workflow.
- **BR-13 Sensitive execution context stays server-side.**
  - Order/customer and policy data, policy evidence, MCP/RAG payloads, tool
    arguments/results, prompts, raw model output, reviewer comments,
    checkpoint payloads, credentials, and secrets are excluded from optional
    selected-thread projections.

## Network and release boundaries

- **BR-14 Browser boundary.**
  - The browser calls only the frontend's same-origin `/api` path.
  - The backend alone calls private Foundry and PostgreSQL.
- **BR-15 Teams exception.**
  - Teams may use only the service-managed, source-filtered Activity route
    with Bot and tenant/RBAC authorization.
  - Normal Foundry Responses/project/data paths remain private.
- **BR-16 Release evidence.**
  - A private release is successful only when all required gates pass,
    including every configured evaluator for every selected trace.
  - A run-level pass summary cannot mask an individual evaluator error.
- **BR-17 Infrastructure authority.**
  - Routine app-only releases do not apply full Bicep or reconcile recorded
    shared-resource drift.

## Current security limitation

- **BR-18 Application authentication is not implemented.**
  - Chat, HITL, workflow-history, and selected-thread endpoints currently have
    no application user authentication/authorization layer.
  - The request-supplied reviewer is not a trusted identity.
  - Private networking is not a substitute for production application auth.
