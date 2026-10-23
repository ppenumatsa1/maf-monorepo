# Copilot Instructions

This project implements one public Microsoft Foundry-hosted underwriting
workflow with durable PostgreSQL state, an external web frontend/internal API
adapter, safe AG-UI/CopilotKit projections, and additive Shared Teams review.

## Primary goals

- Preserve one master MAF workflow with direct risk, credit, medical, and
  driving executors.
- Keep deterministic scoring authoritative and model rationale explanatory.
- Pause only `REFER_TO_HUMAN_UNDERWRITER`.
- Preserve immutable machine recommendation and separate reviewer
  `APPROVED`/`DECLINED`.
- Keep Responses and Activity in the same hosted process and workflow.
- Preserve PostgreSQL-backed checkpoints, projections, approvals, card-action
  bindings, and idempotency.
- Keep the browser on the external frontend origin; it never calls Foundry or
  PostgreSQL directly.
- Keep release and publication claims evidence-driven.

Canonical contracts:

- `docs/design/functional-spec.md`
- `docs/design/business-rules.md`
- `docs/design/technical-spec.md`
- `docs/design/hitl-review.md`
- `docs/design/architecture.md`
- `docs/design/engineering-operating-model.md`
- `docs/design/deployment-flow.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/e2e-rubric.md`

## Workflow and security guardrails

- Do not add a second orchestration engine, compatibility workflow, shadow
  checkpoint store, or browser-to-Foundry path.
- Resume only checkpoints from the supported master direct-executor graph.
- Keep AG-UI and CopilotKit additive to durable read models.
- Persist trusted origin server-side. Free-form words such as approve,
  decline, yes, or no are ordinary text.
- API/Responses and Teams checkpoints cannot authorize each other.
- Teams actions are random opaque tokens; store only hashes and bind them to
  run, checkpoint, decision, reviewer, conversation, expiry, and batch.
- Claim one action atomically before resume and supersede its sibling.
- Keep machine recommendation and reviewer outcome as different schema, API,
  UI, telemetry, and evaluation fields.
- Adaptive Cards and assistant projections may contain only safe categorical
  and lifecycle metadata. Never expose applicant fields, raw check/score data,
  prompts, rationale, model output, checkpoint payloads, token material,
  database values, endpoints, credentials, or secrets.
- Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`; runtime code validates
  schema and does not execute DDL.
- Hosted metadata contains only the project `CustomKeys` database placeholder,
  never the resolved URL.

## Package ownership

- `backend/app/api/v1/routes/*`: transport entrypoints.
- `backend/app/api/v1/schemas/*`: request/response contracts.
- `backend/app/modules/underwriting/*`: domain/service, deterministic policy,
  hosted relay, and safe projections.
- `backend/app/core/*`: settings, telemetry, composition.
- `backend/app/infrastructure/*`: persistence and Foundry adapters.
- `backend/app/maf/*`: workflow runtime.
- `backend/foundry/main.py`: hosted Responses/Activity composition.

## Public delivery rules

- The topology is external frontend -> internal FastAPI -> public Foundry ->
  PostgreSQL.
- Routine deployment is app-only and rejects `FOUNDRY_DEPLOY_MODE`.
- Activate/persist the exact hosted artifact before backend deployment.
- Keep the configured release-time budget and evidence integrity checks.
- Do not add a routine public backend toggle.
- Teams Shared publication retains Responses/Entra and adds Activity plus
  `BotServiceRbac`.
- Do not port private-runner, VNet, private endpoint, private DNS, Bastion, or
  NAT mechanics.
- Automatic GitHub CI is credential-free. Protected manual workflows use OIDC
  for preview/provision, app-only release, package validation, observability,
  and evidence retry; local Make targets remain equivalents. Microsoft 365
  publication uses an interactive publisher outside GitHub Actions.

## Validation

Use the smallest existing set:

- `make test`
- `make quality`
- `make test-e2e`
- `make test-scripts`
- `make test-deployment-profile`
- hosted/IaC gates from `make help`
- Activity/Teams contract tests from `make help` when present
- `make foundry-smoke`
- `make foundry-hosted-e2e`
- `make foundry-eval`
- `make foundry-telemetry`
- `make foundry-verify`
- `make foundry-evidence`

Required scenario coverage includes happy, retry, crash/resume, four-way
fan-in, referral-only pause, separate reviewer approve/decline, privacy-safe
card rendering, replay/expiry/concurrency, reviewer/conversation isolation,
typed-text blocking, cross-channel isolation, and safe telemetry correlation.

## Documentation contract

Synchronize affected operator and design docs in the same change:

- `.github/copilot-instructions.md`
- `agents.md`
- `README.md`
- `docs/README.md`
- functional, business, technical, HITL, architecture, user-flow,
  schema/telemetry, deployment, and E2E docs
- `deployment/README.md`
- `frontend/README.md`

Keep exact release IDs, hosted versions, counts, timings, endpoints, and Azure
target identifiers out of current-state guidance. They belong only in the
deployment plan and delivery ledger.
