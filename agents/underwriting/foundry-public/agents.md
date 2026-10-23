# Agents Guide

## Project context

- One master Microsoft Agent Framework underwriting workflow with direct risk,
  credit, medical, and driving executors.
- External React/Nginx frontend -> internal FastAPI adapter -> public Foundry
  hosted workflow -> PostgreSQL.
- `backend/foundry/main.py` is the production hosted entrypoint. Responses and
  additive Teams Activity must use the same process and workflow.
- AG-UI and CopilotKit are additive, safe projections of durable run data.
- PostgreSQL owns runs, state, events, results, MAF checkpoints, approvals,
  Teams action bindings, and idempotency.
- Production schema is administrator-owned and runtime DDL is prohibited.

## Non-negotiable behavior

1. Keep one workflow path. Do not add a shadow orchestrator, alternate
   checkpoint store, compatibility workflow, or browser-to-Foundry path.
2. Preserve direct four-way fan-out/fan-in and compute deterministic policy
   before model rationale.
3. Only `REFER_TO_HUMAN_UNDERWRITER` pauses.
   `APPROVED`, `APPROVED_WITH_CONDITIONS`, and `DECLINED` are terminal machine
   recommendations.
4. Keep the machine recommendation immutable. Persist reviewer `APPROVED` or
   `DECLINED` and audit metadata separately.
5. Resume only checkpoints produced by the supported master direct-executor
   graph. Superseded nested-graph checkpoints require a new run.
6. Persist trusted origin server-side. Free-form approval words remain ordinary
   text. API/Responses and Teams checkpoints cannot authorize each other.
7. Teams actions are opaque, expiring, one-time, repository-backed, and bound
   to run, checkpoint, decision, reviewer, conversation, and action batch.
   Claim atomically and supersede the sibling action.
8. Adaptive Cards and assistant projections must not contain applicant
   identity, age, health, income, coverage, credit, driving, raw checks/scores,
   prompts, rationale, model output, checkpoint payloads, token material,
   endpoints, credentials, or secrets.
9. Keep AG-UI additive to durable run/state/events/checkpoints APIs.
10. Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`; startup validates
    schema but performs no DDL.
11. Routine release is always app-only. Reject `FOUNDRY_DEPLOY_MODE`; do not
    add a routine public-backend toggle.
12. Activate and persist the exact hosted image/version before deploying the
    backend that references it.
13. Hosted metadata contains only the Underwriting project `CustomKeys`
    database placeholder, never the resolved URL.
14. Teams Shared publication retains Responses and Entra while adding Activity
    and `BotServiceRbac`. Do not add private-runner, VNet, private endpoint,
    private DNS, Bastion, or NAT resources to this public lane.
15. Automatic GitHub CI is credential-free. Protected manual workflows use
    OIDC for preview/provision, app-only release, package validation,
    observability, and evidence retry. Microsoft 365 publication remains
    interactive.

## Package boundaries

- `backend/app/api/v1/routes/*`: HTTP, AG-UI, and CopilotKit entrypoints.
- `backend/app/api/v1/schemas/*`: API contracts.
- `backend/app/modules/underwriting/*`: domain/service seams, deterministic
  decisions, hosted relay, safe projections.
- `backend/app/core/*`: settings, telemetry, and composition.
- `backend/app/infrastructure/*`: PostgreSQL, Foundry clients, checkpoints,
  approvals, and action repositories.
- `backend/app/maf/*`: workflows, executors, middleware, runner, tools,
  prompts, and AG-UI projection.
- `backend/foundry/main.py`: hosted Responses/Activity composition.

## Required verification

Run the smallest existing applicable gates and report results:

- `make test`
- `make quality` for backend/frontend changes
- `make test-e2e` for UI/API/workflow/history changes
- `make test-scripts` and `make test-deployment-profile` for release/profile
  changes
- `make foundry-iac-build`, `make foundry-release-package`,
  `make foundry-release-build`, `make foundry-postgres-readiness`,
  `make foundry-model-preflight`, and `make foundry-runtime-connection` for
  hosted release/IaC changes
- Activity and Teams contract tests exposed by `make help` when those surfaces
  change
- `make foundry-smoke`, `make foundry-hosted-e2e`, and `make foundry-eval` for
  hosted behavior
- `make foundry-verify`, `make foundry-telemetry`, and
  `make foundry-evidence` after authenticated deployment

Do not run the guarded backend internalization or destructive PostgreSQL
rebuild unless that exact migration is explicitly in scope.

## Baseline scenarios

- happy completion;
- retry then one completion;
- crash/resume;
- all four checks visible at fan-in;
- checkpoint and idempotency-skip visibility;
- referral-only pause;
- immutable machine recommendation plus separate reviewer approve/decline;
- privacy-safe card;
- wrong reviewer/conversation, expiry, replay, sibling concurrency, typed
  text, and cross-channel rejection;
- safe correlated hosted telemetry.

## Documentation contract

When behavior, architecture, release gates, or operator steps change, update
the smallest relevant set:

- `README.md`
- `docs/README.md`
- `docs/design/functional-spec.md`
- `docs/design/business-rules.md`
- `docs/design/technical-spec.md`
- `docs/design/hitl-review.md`
- `docs/design/architecture.md`
- `docs/design/deployment-flow.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/userflow.md`
- `docs/design/e2e-rubric.md`
- `deployment/README.md`
- `frontend/README.md`
- `.github/copilot-instructions.md`
- `agents.md`

Exact release IDs, hosted versions, counts, timings, endpoints, and Azure
target identifiers belong only in `.azure/deployment-plan.md` and the dated
delivery ledger.
