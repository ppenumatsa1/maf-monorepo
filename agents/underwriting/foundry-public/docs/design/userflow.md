# User Flow

## Scope

This document describes the supported operator, recovery, and
human-underwriter flows. It is a behavior contract, not a live deployment
claim. Fresh evidence belongs in the
[delivery ledger](issues-changes-fixes.md).

## Web underwriting flow

1. An operator submits a synthetic application from the external frontend.
2. The frontend sends a same-origin request to the internal FastAPI adapter.
3. FastAPI validates the request, assigns or reuses one `workflow_run_id`, and
   invokes the Foundry Responses agent.
4. The hosted process starts the one master MAF workflow and persists the run.
5. `init_context` fans out risk, credit, medical, and driving requests.
6. Each direct executor persists an idempotent result and emits a
   `CheckResult`.
7. `fan_in_aggregator` merges results and waits until all four are present.
8. `final_decision` applies deterministic policy and persists the immutable
   machine recommendation.
9. Optional model rationale explains the recommendation without changing it.
10. The UI reads status, events, state, results, and checkpoints from durable
    PostgreSQL-backed APIs.

## Terminal machine recommendations

The following recommendations complete without human review:

- `APPROVED`
- `APPROVED_WITH_CONDITIONS`
- `DECLINED`

The completed result remains visible in durable history. The selected-run
assistant may explain only allowlisted status and categorical metadata.

## Referred-case review flow

1. Deterministic policy produces `REFER_TO_HUMAN_UNDERWRITER`.
2. The workflow stores that recommendation as immutable machine output.
3. The workflow persists a MAF checkpoint and a pending
   `underwriting_approvals` record.
4. The run enters a review-waiting state without a reviewer outcome.
5. An authorized reviewer submits structured `APPROVED` or `DECLINED` input
   through the checkpoint's trusted channel.
6. The system atomically resolves the approval and resumes the same checkpoint.
7. The separate reviewer outcome and audit metadata are persisted.
8. The machine recommendation remains
   `REFER_TO_HUMAN_UNDERWRITER`.

See [human-underwriter review](hitl-review.md).

## Teams Adaptive Card flow

1. An authorized Shared-catalog user reaches the same hosted process through
   Azure Bot Service and the Foundry Activity protocol.
2. The server selects `teams_activity` as the trusted run origin.
3. A referred run produces a privacy-safe Adaptive Card.
4. The card contains generic context, categorical recommendation,
   non-sensitive references, and opaque `Approve`/`Decline` actions.
5. The reviewer invokes one action.
6. The server hashes the supplied token and validates decision, checkpoint,
   reviewer, conversation, expiry, pending status, and origin.
7. One atomic claim selects the action and supersedes its sibling.
8. The workflow resumes and records the separate reviewer outcome.
9. Replay, competing clicks, expired actions, wrong reviewer, wrong
   conversation, or cross-channel attempts fail without a second outcome.

Typed “approve” or “decline” messages never resolve the checkpoint.

## Crash and resume flow

1. An operator starts a controlled crash scenario.
2. The workflow persists completed work and a supported checkpoint.
3. The run reports `CRASHED` with the same `workflow_run_id`.
4. The operator requests resume.
5. The hosted workflow loads the latest checkpoint produced by the master
   direct-executor graph.
6. Remaining work completes without duplicate persistence.

Checkpoints from the superseded nested graph are unsupported. Start a new run
instead of adding a compatibility workflow.

## Operator inspection flow

1. Search or filter durable run history.
2. Open the selected run.
3. Inspect:
   - normalized status;
   - machine recommendation;
   - separate reviewer outcome, when present;
   - ordered safe events;
   - incremental state;
   - checkpoint count and timestamps;
   - retry, crash, resume, and idempotency evidence.
4. Use the selected-run assistant only for safe execution explanation.

Applicant fields, raw checks, prompts, rationale, checkpoint payloads, tokens,
credentials, and secrets must not cross the assistant boundary.

## Release and publication flow

1. Select and validate an external public runtime profile.
2. Run local source gates.
3. For bootstrap, review a fresh infrastructure preview before applying it.
4. For normal changes, run the app-only release path.
5. Verify hosted smoke, happy/retry/crash-resume/referral flows, strict
   evaluation, telemetry, and topology.
6. When Teams is in scope, review Bot/Activity/Shared publication, then run
   normal invocation and Adaptive Card security acceptance.
7. Verify rollback boundaries.
8. Record only secret-free dated evidence in the ledger.

## Expected outcomes

- Four direct checks are present before the machine recommendation.
- Retry and resume do not duplicate durable writes.
- Only the referral category pauses.
- Machine recommendation and reviewer outcome remain distinct.
- Web/Responses and Teams checkpoints cannot authorize each other.
- Adaptive Cards and telemetry contain no applicant or secret content.
- Browser traffic stays on the frontend origin.
- A readiness claim is made only from fresh live evidence.
