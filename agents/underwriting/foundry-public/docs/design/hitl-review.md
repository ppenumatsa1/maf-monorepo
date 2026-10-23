# Human-Underwriter Review Contract

## Purpose

Define the only supported human-in-the-loop path for underwriting and the
security boundary for web/Responses and Microsoft Teams review.

## Trigger

Human review is created only when the deterministic machine recommendation is:

```text
REFER_TO_HUMAN_UNDERWRITER
```

`APPROVED`, `APPROVED_WITH_CONDITIONS`, and `DECLINED` are terminal machine
recommendations and must not create an approval checkpoint.

## Recommendation and outcome model

The workflow stores two different facts:

1. **Machine recommendation** — immutable
   `REFER_TO_HUMAN_UNDERWRITER`.
2. **Reviewer outcome** — separately recorded `APPROVED` or `DECLINED`.

The reviewer outcome does not rewrite the recommendation. Audit views and
telemetry must keep the fields distinct.

## Pause and resume sequence

1. Complete all four checks and compute the deterministic recommendation.
2. Persist `machine_recommendation`.
3. Persist a MAF checkpoint and pending `underwriting_approvals` row.
4. Emit a safe review-request event.
5. Wait without producing a reviewer outcome.
6. Accept a structured decision only through the checkpoint's trusted channel.
7. Atomically resolve the pending approval.
8. Resume the same workflow and persist the separate reviewer outcome.

## Channel rules

| Origin | Allowed decision path |
| --- | --- |
| `api` | Hosted mutation is disabled. Non-hosted local execution may use the explicit server-authorized administrative path; caller headers do not establish reviewer identity. |
| `responses` | Production review mutation is disabled; structured and free-form decision attempts are rejected. |
| `teams_activity` | Bound Adaptive Card action only |

Production review is Teams-only. Cross-channel resolution is prohibited. A
web or Responses decision cannot resolve a Teams checkpoint. A Teams token
cannot resolve an API or Responses checkpoint. The optional local
administrative path requires non-hosted local execution,
`ENABLE_LOCAL_REVIEW_MUTATION=true`, and a server-configured
`LOCAL_REVIEW_ACTOR_ID`; it records reviewer type `administrative`.

## Adaptive Card contract

The card may show:

- generic “Underwriting review required” text;
- machine recommendation category;
- a non-sensitive run/case reference;
- a non-sensitive checkpoint reference;
- `Approve` and `Decline` action labels.

The card must not show:

- applicant name or identity;
- age, health disclosures, income, requested coverage, credit score, or
  driving history;
- raw check results, score breakdown, prompts, rationale, or model output;
- database values, Azure endpoints, credentials, or secrets.

## Action-token contract

- Tokens are random and opaque; they do not encode identifiers.
- PostgreSQL stores only a token hash.
- Each token is bound to run, checkpoint, decision, reviewer, conversation,
  expiry, and action batch.
- Approval and decline tokens are siblings in the same batch.
- One atomic claim selects the winning action and supersedes its sibling.
- Expired, replayed, wrong-user, wrong-conversation, wrong-checkpoint, and
  already-resolved actions fail closed.
- Typed words such as “approve” or “decline” remain chat text.

## Required acceptance cases

1. Only a referral-band recommendation pauses.
2. Machine recommendation remains unchanged after either reviewer outcome.
3. Reviewer approve completes the bound checkpoint.
4. Reviewer decline completes the bound checkpoint with a distinct outcome.
5. Wrong reviewer is rejected.
6. Wrong conversation is rejected.
7. Expired token is rejected.
8. Replay is rejected.
9. Concurrent approve/decline produces one effective outcome.
10. Responses cannot resolve Teams-originated review.
11. Teams cannot resolve Responses/API-originated review.
12. Card JSON and telemetry contain none of the prohibited fields.
13. Missing or spoofed web identity headers cannot enable hosted mutation.
14. Local administrative review is rejected outside non-hosted local execution
    and records the server-configured administrative actor when enabled.

Local contract tests are not proof of a live Teams publication. Record deployed
Activity, Adaptive Card, isolation, replay, telemetry, and rollback acceptance
only in the [delivery ledger](issues-changes-fixes.md).
