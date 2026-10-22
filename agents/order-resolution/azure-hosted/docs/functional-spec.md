# Functional Specification - Azure-Hosted Order Resolution

> Status: Implemented for the FastAPI-hosted web application. A current Azure
> deployment claim requires fresh evidence in the
> [evidence ledger](issues-changes-fixes.md).
> Related: [business rules](business-rules.md),
> [technical specification](technical-spec.md),
> [architecture](architecture.md), and [user flow](userflow.md).

## 1. Goal

Help a support operator resolve synthetic delivery and product issues through
one explainable MAF workflow. Low-risk actions complete automatically. Risky
actions pause for an explicit human decision and resume from durable state.

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Support operator | Starts a workflow, reviews its timeline, reopens history, and asks follow-up questions. |
| Human reviewer | Approves or rejects a pending checkpoint through the native web HITL control. |
| Platform operator | Selects a target profile, bootstraps or reuses infrastructure, releases the app, and validates evidence. |

The current API does not authenticate these application actors. Production
identity, authorization, and reviewer attribution remain future hardening work.

## 3. Core functions

| ID | Function | Current behavior |
| --- | --- | --- |
| F1 | Start a workflow | The UI submits a message to `POST /api/chat/run` and receives accepted run/thread identifiers. |
| F2 | Triage the issue | The MAF workflow classifies the issue and identifies the synthetic order. |
| F3 | Retrieve evidence | The workflow reads local order/policy tools and the configured MCP/RAG seams. |
| F4 | Select a resolution | Deterministic policy chooses the action and decides whether human approval is required. |
| F5 | Complete low-risk work | A non-HITL action is submitted once and produces terminal `completed` output. |
| F6 | Pause risky work | The workflow persists a checkpoint and pending approval before any gated action is submitted. |
| F7 | Approve or reject | A reviewer resolves the exact checkpoint. Approval resumes and completes; rejection produces an `escalated` outcome. |
| F8 | Preserve history | Runs, events, messages, checkpoints, approvals, and idempotency state are stored in PostgreSQL. |
| F9 | Explain a result | A follow-up in the same thread explains why the resolution was selected. |
| F10 | Show operational detail | The UI displays history, native event timeline, current output, run metadata, and pending approvals. |
| F11 | Provide selected-thread views | AG-UI and CopilotKit show a redacted read-only projection for one existing thread. |
| F12 | Correlate telemetry | Application Insights correlates workflow stages, model calls, HITL wait/resume, and resolution submission. |
| F13 | Evaluate quality | Deterministic cases and report-only Foundry evaluators gate releases without invoking the workflow. |

## 4. Supported scenarios

| Scenario | Example | Expected outcome |
| --- | --- | --- |
| Low-risk late delivery | `Order ORD-1001 arrived late by 1 day.` | Completes without HITL. |
| High-value delay | `Order ORD-1009 is delayed by 5 days. I need compensation.` | Pauses for approval; approve completes, reject escalates. |
| Damaged item | `Order ORD-1001 arrived damaged and broken.` | Pauses for approval regardless of amount. |
| Wrong item | `Order ORD-1001 has the wrong item in the box.` | Completes without HITL under the current policy. |
| Explanation follow-up | `Why was that resolution selected?` | Explains the prior result in the same thread. |
| Duplicate decision | Repeat approve/reject for a resolved checkpoint. | Does not repeat resolution submission or terminal output. |

All order data is synthetic.

## 5. User-visible contracts

### Start response

```json
{
  "run_id": "opaque-id",
  "thread_id": "opaque-id",
  "status": "accepted"
}
```

### Stable workflow events

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

### Terminal states

| State | Meaning |
| --- | --- |
| `completed` | Resolution finished successfully. |
| `waiting_approval` | A durable checkpoint is awaiting a decision. |
| `escalated` | The reviewer rejected the proposal or human support is required. |
| `failed` | The workflow stopped because an execution dependency failed. |

## 6. Non-functional requirements

- **Single runtime:** FastAPI is the only MAF application host.
- **Browser isolation:** the browser calls only the external frontend's
  same-origin `/api` proxy; the backend remains internal.
- **Durability:** process restarts must not lose history or a pending approval.
- **Managed identity:** Azure PostgreSQL access uses the backend identity, not a
  stored application password.
- **Idempotency:** repeated dispatches or decisions must not repeat a
  side-effecting resolution.
- **Privacy:** optional selected-thread projections omit business payloads,
  prompts, model output, tool data, checkpoint state, and secrets.
- **Release quality:** every release must pass the required browser/domain,
  telemetry, report-only evaluation, and final evidence gates.

## 7. Out of scope

- Real commerce/order-system integration or real refunds/replacements.
- Production application authentication and authorization.
- A generalized order catalog beyond the synthetic fixtures.
- Private networking or private runners.
- Foundry hosted-agent or Responses application hosting.
- Bot Service, Activity protocol, Teams, or Adaptive Cards.

## 8. Acceptance status

| Acceptance criterion | Status |
| --- | --- |
| Low-risk, high-risk approval, damaged-item approval, rejection, and duplicate-decision flows are covered | Implemented |
| Durable history and checkpoint resume survive process boundaries | Implemented |
| Optional selected-thread views are read-only and redacted | Implemented |
| External frontend/internal backend topology is enforced by the release contract | Implemented |
| Foundry evaluation is report-only | Implemented |
| Current Azure release is valid | Requires fresh evidence for the exact source revision |
