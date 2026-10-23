# Business Rules - Underwriting Foundry Public

> This file is the behavior source of truth. Other documents should link to
> these rules instead of restating them with different semantics.

## Workflow and scoring

- **BR-01 One master graph.** One MAF workflow fans out directly to risk,
  credit, medical, and driving executors in one superstep.
- **BR-02 Complete fan-in.** The aggregator may merge results incrementally,
  but the final decision cannot run until all four check results are present.
- **BR-03 Shared-state authority.** Explicit messages drive control flow;
  recovery-critical aggregation state belongs to the MAF checkpoint and
  PostgreSQL-backed projections.
- **BR-04 Deterministic decision.** Let `average_score` be the average of the
  four normalized check scores:
  - `APPROVED` when `average_score >= 0.8`, risk `>= 0.6`, and credit `>= 0.65`;
  - otherwise `APPROVED_WITH_CONDITIONS` when `average_score >= 0.65`;
  - otherwise `REFER_TO_HUMAN_UNDERWRITER` when `average_score >= 0.45`;
  - otherwise `DECLINED`.
- **BR-05 Rationale is non-authoritative.** Model-generated rationale may
  explain a recommendation but cannot modify the score or category.

## Human-underwriter review

- **BR-06 Referral-only pause.** Only
  `REFER_TO_HUMAN_UNDERWRITER` creates a human-review checkpoint.
  `APPROVED`, `APPROVED_WITH_CONDITIONS`, and `DECLINED` are terminal machine
  recommendations.
- **BR-07 Immutable machine recommendation.** The persisted machine
  recommendation is never replaced by a human result.
- **BR-08 Separate reviewer outcome.** A reviewer records only `APPROVED` or
  `DECLINED` plus audit metadata in the approval record.
- **BR-09 Pause before resolution.** The workflow must persist its checkpoint,
  pending approval, and recommendation before exposing an actionable review.
- **BR-10 One effective decision.** A checkpoint can acquire one effective
  reviewer outcome. Repeated, replayed, or concurrent actions cannot produce a
  second outcome or terminal side effect.

## Durability, recovery, and idempotency

- **BR-11 PostgreSQL authority.** PostgreSQL is authoritative for workflow
  runs, business state, events, results, checkpoints, approvals, action tokens,
  and idempotency records.
- **BR-12 Supported checkpoint shape.** Resume accepts only checkpoints
  produced by the deployed master direct-executor graph. A checkpoint from the
  superseded nested graph requires a new run; there is no migration shim.
- **BR-13 Replay safety.** Every side-effecting persistence operation uses a
  stable idempotency boundary.
- **BR-14 Retry scope.** Retry/backoff is allowed for transient read or model
  work. Side-effecting writes are not blindly retried.

## Channel and action authorization

- **BR-15 Trusted origin.** The server, not the caller, selects and persists
  one origin: `api`, `responses`, or `teams_activity`.
- **BR-16 Cross-channel isolation.**
  - Hosted web and Responses requests cannot resolve a review checkpoint,
    including when a caller supplies an identity-looking header.
  - A Teams-originated checkpoint requires its bound Adaptive Card action.
  - Explicit local administrative resolution is available only in non-hosted
    local execution with a server-configured actor and is audited with reviewer
    type `administrative`.
  - An API path cannot use a Teams token, and Teams cannot resolve a web or
    Responses-originated checkpoint.
- **BR-17 Structured decisions only.** Free-form text such as “approve,”
  “decline,” “yes,” or “no” is ordinary conversation content. It never becomes
  a review decision.
- **BR-18 Browser boundary.** The browser calls only the external frontend's
  same-origin API. It receives no Foundry, PostgreSQL, Bot, or publication
  credential.

## Adaptive Card privacy and replay protection

- **BR-19 Minimal card content.** A review card may contain only:
  - a generic underwriting-review title;
  - the categorical machine recommendation;
  - a non-sensitive case/run reference;
  - a non-sensitive checkpoint reference or short display token;
  - action labels.
- **BR-20 Prohibited card content.** A card must not contain applicant name or
  identity, age, health disclosures, income, requested coverage, credit score,
  driving history, raw check results, score details, prompts, rationale, raw
  model output, database values, endpoints, credentials, or secrets.
- **BR-21 Opaque bound actions.** Each action uses a cryptographically random
  opaque token. Only a hash is stored. The record is bound to workflow run,
  checkpoint, decision, reviewer, conversation, expiry, and action batch.
- **BR-22 Atomic claim.** The selected action is atomically claimed before
  resume; its sibling is superseded. Completion follows successful resume.
  Release after failure is allowed only while the same approval is still
  pending and policy permits a safe retry.

## Projection, telemetry, and release evidence

- **BR-23 Safe projections.** AG-UI and CopilotKit are additive projections of
  durable state. They expose only allowlisted identifiers, status, safe event
  and executor labels, checkpoint summary, machine recommendation category,
  and reviewer outcome category.
- **BR-24 Content-safe telemetry.** Correlation attributes may include run,
  conversation, checkpoint, event, executor, channel, action status, and
  categorical outcomes. They exclude applicant fields, raw check payloads,
  prompts, model content, token material, and secrets.
- **BR-25 Evidence authority.** A live-readiness claim requires fresh,
  release-local smoke, E2E, evaluation, telemetry, topology, Teams acceptance
  when in scope, and rollback evidence recorded in the delivery ledger.
- **BR-26 Public topology.** The lane keeps public Azure service access and an
  external frontend/internal backend topology. Teams adds the controlled
  Activity/Bot path without importing private-runner, VNet, Bastion, or private
  endpoint mechanics.
- **BR-27 Shared publication.** Teams publication uses Shared scope.
  Tenant-wide publication is not the target.
- **BR-28 No deployment inference.** Source, configuration, local tests, or an
  infrastructure preview do not prove that Azure deployment or Microsoft 365
  publication succeeded.
