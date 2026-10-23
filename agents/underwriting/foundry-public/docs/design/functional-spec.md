# Functional Specification - Underwriting Foundry Public

> Status: product and operator contract. Source implementation and live
> deployment status must be verified independently; dated proof belongs only
> in the [delivery ledger](issues-changes-fixes.md).
>
> Related: [business rules](business-rules.md),
> [technical specification](technical-spec.md),
> [human-underwriter review](hitl-review.md), and
> [user flow](userflow.md).

## 1. Goal

Provide an explainable insurance-underwriting workflow that evaluates a
synthetic application through independent risk, credit, medical, and driving
checks; persists workflow and audit state; survives interruption; and sends
only the machine referral outcome to a human underwriter.

This project is a reference implementation. Do not use real applicant,
customer, policyholder, or production decision data.

## 2. Actors

| Actor | Responsibility |
| --- | --- |
| Underwriting operator | Starts a synthetic case, observes progress, inspects durable history, and resumes a supported crashed run. |
| Human underwriter | Resolves a pending `REFER_TO_HUMAN_UNDERWRITER` checkpoint with a separate `APPROVED` or `DECLINED` outcome. |
| Platform operator | Selects the Azure runtime profile, deploys and verifies the public lane, publishes the Shared Teams app when supported, and records evidence. |
| Authorized Teams reviewer | Uses the privacy-safe Adaptive Card for the bound conversation and checkpoint. |

## 3. Core functions

| ID | Function | Required behavior |
| --- | --- | --- |
| F-01 | Start a case | Accept a validated synthetic application and create or reuse one `workflow_run_id`. |
| F-02 | Fan out assessments | Dispatch risk, credit, medical, and driving checks directly from one master MAF workflow. |
| F-03 | Fan in results | Merge each `CheckResult` into shared state and wait until all four checks are present. |
| F-04 | Compute recommendation | Apply deterministic score rules before generating explanatory model text. |
| F-05 | Complete terminal recommendations | `APPROVED`, `APPROVED_WITH_CONDITIONS`, and `DECLINED` finish without a human-review pause. |
| F-06 | Pause a referral | Only `REFER_TO_HUMAN_UNDERWRITER` creates a durable review checkpoint and pending approval. |
| F-07 | Preserve the machine result | Store the machine recommendation unchanged for the lifetime of the run. |
| F-08 | Record reviewer outcome | Store `APPROVED` or `DECLINED`, reviewer audit metadata, and resolution time separately from the machine recommendation. |
| F-09 | Resume safely | Resume the exact pending checkpoint through the channel authorized for that checkpoint. |
| F-10 | Prevent duplicate effects | Make check persistence, terminal results, and review decisions idempotent across retry, replay, and resume. |
| F-11 | Preserve durable history | Persist run state, events, results, checkpoints, recommendation, reviewer outcome, and action-token state in PostgreSQL. |
| F-12 | Stream progress | Provide AG-UI progress while retaining durable read models as the refresh and replay authority. |
| F-13 | Explain safely | Let the selected-run assistant use only allowlisted run metadata and categorical outcomes. |
| F-14 | Support public web delivery | Keep the browser on the external frontend origin; proxy API calls to the internal FastAPI adapter. |
| F-15 | Support Shared Teams review | Use the same hosted workflow through the Activity protocol, Azure Bot Service, and Shared Microsoft 365 publication. |
| F-16 | Protect Teams actions | Use opaque, expiring, one-time actions bound to decision, checkpoint, user, conversation, and action batch. |
| F-17 | Correlate operations | Correlate web, Responses, Activity, workflow, persistence, and review telemetry by safe identifiers. |
| F-18 | Verify releases | Require local gates and fresh hosted smoke, E2E, evaluation, telemetry, topology, and rollback evidence before a readiness claim. |

## 4. Supported scenarios

| Scenario | Expected outcome |
| --- | --- |
| Low-risk application | Machine recommendation `APPROVED`; no HITL pause. |
| Medium-risk application | Machine recommendation `APPROVED_WITH_CONDITIONS`; no HITL pause. |
| Referral-band application | Machine recommendation remains `REFER_TO_HUMAN_UNDERWRITER`; workflow waits for a separate reviewer outcome. |
| High-risk application | Machine recommendation `DECLINED`; no HITL pause. |
| Injected transient check failure | Bounded retry evidence is recorded and the run completes once. |
| Injected crash | A supported checkpoint remains available and resume does not duplicate completed work. |
| Teams reviewer approves | The bound referral checkpoint records reviewer outcome `APPROVED`. |
| Teams reviewer declines | The bound referral checkpoint records reviewer outcome `DECLINED`. |
| Typed “approve” or “decline” | Ordinary text; it does not resolve a checkpoint. |
| Wrong user, wrong conversation, expired action, replay, or competing click | Rejected without a second effective reviewer outcome. |

## 5. Non-functional requirements

- **Explainability:** deterministic score components and the immutable machine
  recommendation remain inspectable independently from model rationale.
- **Durability:** process restart or channel interruption must not lose the
  latest supported checkpoint or a pending review.
- **Privacy:** no applicant identity, health disclosure, income, credit score,
  raw check result, prompt, rationale, model output, database value, endpoint,
  credential, or secret appears in an Adaptive Card or selected-run assistant
  projection.
- **Isolation:** production web and Responses mutation is disabled; only a
  bound Teams Activity card may resolve a production review. Teams actions are
  also isolated by reviewer and conversation. Explicit local administrative
  review is non-hosted, server-authorized, and audited separately.
- **Public-network posture:** the public lane uses controlled public Azure
  service endpoints. It does not add private-runner, VNet, Bastion, or private
  endpoint requirements.
- **Operational proof:** repository configuration, source validation, or a
  preview is not deployment evidence.

## 6. Out of scope

- Real insurance underwriting or real applicant data.
- A production application authentication and authorization design unless it
  is added and verified separately.
- A second orchestration engine, shadow checkpoint store, or browser-to-Foundry
  call path.
- Resume compatibility for checkpoints produced by the superseded nested graph.
- Tenant-wide Teams publication.
- Treating model rationale as decision authority.

## 7. Legacy PRD requirement mapping

This table maps every requirement formerly held in `prd.md`.

| Former PRD requirement | New authority |
| --- | --- |
| Checkpointing and resume after crash | F-09, F-11; [BR-11 through BR-13](business-rules.md) |
| Fan-out/fan-in aggregation | F-02, F-03; BR-01 through BR-03 |
| Shared workflow state versus message passing | F-03; [technical specification](technical-spec.md#5-workflow-and-state-contract) |
| One master workflow with four direct executors | F-02; BR-01 |
| Retry, backoff, and failure handling | F-10; BR-14 |
| PostgreSQL persistence for checkpoints and business/audit state | F-11; BR-11 |
| Idempotency across replay and resume | F-10; BR-13 |
| Python/FastAPI/MAF backend | [technical specification](technical-spec.md#2-technology-and-runtime-surfaces) |
| React/Vite operator dashboard | F-12 through F-14; technical specification |
| Backend and Playwright tests | F-18; [E2E rubric](e2e-rubric.md) |
| Local Make and Docker Compose runtime | [operator guide](../../README.md#local-development) |
| Container Apps, hosted agent, telemetry, CopilotKit, and Bicep public deployment | F-12 through F-18; [deployment flow](deployment-flow.md) |
| Authentication/authorization originally out of scope | Remains out of scope for the web application; Teams channel authorization is a transport boundary, not full application auth |
| Production-grade multi-tenancy originally out of scope | Remains out of scope |
| HITL UX originally limited to demonstration | Replaced by F-06 through F-10 and F-15 through F-16 |
| No browser access to Foundry/PostgreSQL credentials | F-14; BR-18 |
| Local execution not a production deployment mode | BR-17; technical specification |
| CLI happy/retry/crash/resume success | [manual testing](../manual-testing.md) |
| Backend/frontend/E2E gates pass | F-18; E2E rubric |
| Distinguish MAF checkpoint state from business/audit state | F-11; [schema contract](schema-io-telemetry.md) |
| Correlate public request, durable run, and hosted traces without sensitive content | F-17; BR-23 through BR-25 |
| Four direct executors fan out/fan in in one superstep | F-02, F-03; BR-01 |
| Unsupported nested-graph checkpoint resume after cutover | BR-12 |
