# Manual Testing Guide

## Safety

Use synthetic inputs only. Do not paste applicant, customer, tenant, resource,
endpoint, credential, card-token, or secret values into screenshots, test
notes, or the delivery ledger.

## Prerequisites

- Tools listed in the [operator guide](../README.md#prerequisites)
- Local dependencies installed with `make bootstrap`
- Docker available for PostgreSQL-backed tests

## Local full-stack setup

```bash
cp .env.example .env
make up
```

Open:

- frontend: `http://localhost:4173`
- backend health: `http://localhost:8000/health`

Reset local schema only when local data may be discarded:

```bash
make db-reset
```

## CLI workflow scenarios

### Happy path

```bash
make run
```

Confirm all four direct checks are present before the machine recommendation.

### Retry

```bash
make run-fail-once
```

Confirm bounded retry/backoff evidence and one effective result per check.

### Crash and resume

```bash
make run-crash
make resume RUN_ID=<workflow-run-id>
```

Confirm the same run resumes from a supported MAF checkpoint and completed
work is not duplicated.

Inspect:

```bash
make state RUN_ID=<workflow-run-id>
make events RUN_ID=<workflow-run-id>
make checkpoints RUN_ID=<workflow-run-id>
```

## Browser scenarios

1. Start a normal run.
2. Confirm status, events, state, checkpoints, and result update.
3. Run retry and crash/resume scenarios.
4. Refresh the browser and confirm durable state remains available.
5. Ask the selected-run assistant about status/recovery.
6. Confirm the assistant exposes only safe selected-run metadata.

The browser must remain on the frontend origin. It must not call Foundry or a
public backend FQDN directly.

## HITL contract scenarios

Use the checked-in test fixtures or harness that produces each deterministic
recommendation category.

1. `APPROVED` completes without review.
2. `APPROVED_WITH_CONDITIONS` completes without review.
3. `DECLINED` completes without review.
4. `REFER_TO_HUMAN_UNDERWRITER`:
   - persists the immutable machine recommendation;
   - creates a checkpoint and pending approval;
   - accepts separate reviewer `APPROVED`;
   - accepts separate reviewer `DECLINED`;
   - never overwrites the machine recommendation;
   - produces one effective outcome under duplicate/concurrent submission.

If the current UI has no reviewer control, validate through the supported
structured API/Responses harness. Do not use free-form text as a decision.

## Teams acceptance

Run only after checked-in Activity/Bot/Shared publication automation has been
reviewed and deployed.

1. Authorized Shared-catalog user can invoke the agent.
2. Unauthorized user cannot invoke it.
3. A referred case renders a privacy-safe card.
4. Approve records reviewer outcome `APPROVED`.
5. Decline records reviewer outcome `DECLINED`.
6. Typed approval/decline text does not resolve the checkpoint.
7. Wrong reviewer is rejected.
8. Wrong conversation is rejected.
9. Expired token is rejected.
10. Replayed token is rejected.
11. Concurrent sibling clicks produce one effective outcome.
12. Responses cannot resolve the Teams checkpoint.
13. Card JSON and telemetry contain no prohibited fields.
14. Activity rollback leaves Responses and Entra intact.

Controlled publication commands:

```bash
make foundry-activity-plan
make foundry-teams-plan
make foundry-teams-preview
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-teams-deploy-bot
make foundry-activity-apply
make foundry-teams-package
make foundry-teams-publish
make foundry-teams-status
make foundry-teams-rollback-plan
```

## Automated gates

```bash
make test
make quality
make test-e2e
make test-deployment-profile
make test-scripts
```

Run Activity and Teams contract tests:

```bash
make test-foundry-activity-endpoint
make test-foundry-teams-publishing
```

## Hosted release acceptance

After an authenticated app-only release:

```bash
make foundry-smoke
make foundry-hosted-e2e
make foundry-eval
make foundry-telemetry
make foundry-verify
make foundry-evidence
```

Confirm:

- external frontend/internal backend topology;
- no direct public backend;
- exact immutable images and hosted version;
- four-way fan-in;
- retry and crash/resume;
- referral pause and separate reviewer outcome;
- PostgreSQL external-schema and least-privilege boundary;
- runtime connection placeholder rather than resolved secret;
- safe correlated telemetry;
- configured evaluator success;
- release-local, secret-free evidence.

Record exact run IDs, evaluator IDs, counts, timings, target identifiers, and
rollback results only in the ledger/deployment plan.

## Cleanup

```bash
make down
```

Remove any locally generated package, screenshot, log, or evidence file that
contains sensitive operational state. Do not commit release artifacts.
