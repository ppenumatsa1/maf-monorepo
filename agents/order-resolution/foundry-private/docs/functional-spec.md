# Functional Specification - Private Order Resolution Agent

> Status: Implemented for the private web application, Shared Teams
> invocation, and Adaptive Card approval/rejection.
> Related: [business rules](business-rules.md),
> [technical specification](technical-spec.md),
> [architecture](architecture.md), and
> [user flow](userflow.md).

## 1. Goal

Help a support operator resolve synthetic delivery and product issues through
one explainable workflow. Low-risk actions complete automatically. Risky
actions pause for an explicit human decision and resume from durable state.

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Support operator | Starts an order-resolution workflow, reviews its timeline, reopens history, and asks follow-up questions. |
| Human reviewer | Approves or rejects a pending checkpoint through the web HITL control. |
| Platform operator | Deploys and validates the private Foundry, Container Apps, PostgreSQL, monitoring, and Teams integration. |
| Teams user | Authorized Shared-catalog user of the same hosted workflow; uses an Adaptive Card for pending approval decisions. |

The current web API does not authenticate these application actors. Production
identity, authorization, and reviewer attribution remain future hardening
work.

## 3. Core functions

| ID | Function | Current behavior |
| --- | --- | --- |
| F1 | Start a workflow | The UI submits a message to `POST /api/chat/run` and receives an accepted run/thread identifier. |
| F2 | Triage the issue | The shared MAF workflow classifies the issue and identifies the synthetic order. |
| F3 | Retrieve evidence | The workflow reads local order/policy tools, pgvector-compatible RAG evidence, and the configured MCP knowledge port. |
| F4 | Select a resolution | Deterministic policy chooses the action and decides whether human approval is required. |
| F5 | Complete low-risk work | A non-HITL action is submitted once and produces a terminal `completed` output. |
| F6 | Pause risky work | The workflow persists a checkpoint and pending approval before any gated action is submitted. |
| F7 | Approve or reject | A reviewer resolves the exact checkpoint. Approval resumes and completes; rejection produces an `escalated` outcome. |
| F8 | Preserve history | Runs, events, messages, checkpoints, approvals, RAG records, and idempotency state are stored in PostgreSQL. |
| F9 | Explain a result | A follow-up in the same Foundry conversation can explain why the resolution was selected. |
| F10 | Show operational detail | The UI displays workflow history, event timeline, current output, RAG evidence, run metadata, and pending approvals. |
| F11 | Provide optional selected-thread views | AG-UI and CopilotKit show a redacted read-only projection for one existing thread. |
| F12 | Correlate telemetry | Application Insights shows the hosted invocation, model calls, workflow stages, HITL wait/resume, and resolution submission. |
| F13 | Evaluate quality | Deterministic cases and exact-trace Foundry evaluators gate private releases. |
| F14 | Publish to Teams | Bot/channel, Activity configuration, Shared publication, authentication, and normal invocation are deployed and verified. |
| F15 | Resolve Teams approval card | A pending Teams checkpoint emits Approve/Reject buttons backed by opaque one-time tokens; typed decisions do not resolve it. |

## 4. Supported scenarios

| Scenario | Example | Expected outcome |
| --- | --- | --- |
| Low-risk late delivery | `Order ORD-1001 arrived late by 1 day.` | Completes without HITL. |
| High-value delay | `Order ORD-1009 is delayed by 5 days. I need compensation.` | Pauses for approval; approve completes, reject escalates. |
| Damaged item | `Order ORD-1001 arrived damaged and broken.` | Pauses for approval regardless of amount. |
| Wrong item | `Order ORD-1001 has the wrong item in the box.` | Completes without HITL under the current policy. |
| Explanation follow-up | `Why was that resolution selected?` | Explains the prior result in the same conversation. |
| Duplicate decision | Repeat approve/reject for a resolved checkpoint. | Does not submit the resolution or terminal output twice. |

All order data is synthetic. The current demo maps messages containing `1009`
to `ord-1009`; other order numbers use the `ord-1001` fixture.

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

- **Private runtime:** normal Foundry, PostgreSQL, ACR, backend, and data paths
  remain on private/VNet-connected paths.
- **Browser isolation:** the browser calls only the external frontend's
  same-origin `/api` proxy; it receives no Foundry or database credential.
- **Durability:** process restarts must not lose workflow history or a pending
  approval.
- **Idempotency:** repeated dispatches or decisions must not repeat a
  side-effecting resolution.
- **Explainability:** the durable timeline and correlated telemetry must show
  triage, retrieval, decision, approval, and completion.
- **Privacy:** optional selected-thread projections must omit order/customer
  details, policy and MCP/RAG content, prompts, raw model output, reviewer
  comments, checkpoint payloads, credentials, and secrets.
- **Release quality:** every private release must pass HITL E2E, telemetry
  correlation, and every configured evaluator for every selected trace.

## 7. Out of scope

- Real commerce/order-system integration or real refunds/replacements.
- Production user authentication, authorization, and reviewer identity.
- A generalized order catalog beyond the synthetic fixtures.
- Tenant-wide Teams publication.
- AMPLS/private Application Insights ingestion.
- Full shared-infrastructure reconciliation while recorded drift remains
  unreviewed.

## 8. Acceptance status

| Acceptance criterion | Status |
| --- | --- |
| Low-risk, high-risk approval, damaged-item approval, and rejection flows work in the deployed web UI | Passed |
| History, timeline, RAG evidence, output, metadata, and HITL controls render correctly | Passed |
| Application Insights shows the end-to-end workflow and model flow | Passed |
| Backend, deterministic evaluation, browser E2E, hosted E2E, telemetry, and strict cloud evaluation gates pass | Passed |
| Shared Teams app can be packaged, installed, authenticated, and invoked | Passed |
| Teams Adaptive Card Approve/Reject, typed-decision blocking, replay rejection, and conversation isolation work | Passed |

Current evidence:
[review remediation release](issues-changes-fixes.md#review-remediation-release-2026-10-21).
