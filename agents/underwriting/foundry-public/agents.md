# Agents Guide

This file describes expected behavior for coding agents working in this repository.

## Project Context

- Backend: internal-ingress FastAPI adapter plus one master underwriting MAF workflow with direct executors.
- Foundry hosted entrypoint: `backend/foundry/main.py` packaged by `backend/Dockerfile.hosted`.
- Public lane: authenticated local AZD/Bicep flow under `infra/foundry-hosted/`; use the existing `make foundry-*` commands.
- Frontend: external React + Vite operations console served by an
  Underwriting-owned Nginx same-origin `/api` proxy to the internal backend.
- Workflow pattern: `init_context` fans out directly to risk, credit, medical, and driving executors in one superstep; `fan_in_aggregator` merges shared state; `final_decision` applies deterministic policy before rationale generation.
- Persistence: PostgreSQL-backed `maf_checkpoints`, `workflow_runs`, `business_state`, `workflow_events`, `underwriting_results`, and `idempotency_records`.
- Telemetry: preserve internal-adapter request correlation, hosted Foundry
  spans, retry/backoff, checkpoint save/load, idempotency skip, fan-out/fan-in,
  and final decision spans.
- Backend package boundaries:
  - `backend/app/api/v1/routes/*` owns HTTP, AG-UI, and CopilotKit route entrypoints only.
  - `backend/app/api/v1/schemas/*` owns API contracts.
  - `backend/app/modules/underwriting/*` owns service/domain seams, hosted relay behavior, safe assistant context, and deterministic decision policy.
  - `backend/app/core/*` owns config, telemetry, and composition.
  - `backend/app/infrastructure/*` owns adapters, repositories, Foundry clients, and checkpoint storage.
  - `backend/app/maf/*` owns workflows, executors, middleware, runner, tools, prompts, and AG-UI projection.

## Agent Change Policy

1. Keep changes minimal and focused on the requested surface.
2. Keep one underwriting workflow path; do not add alternate orchestration layers, duplicate adapters, or compatibility shims.
3. `backend/foundry/main.py` constructs the real hosted MAF runner; the internal
   backend adapter relays start/resume and reads durable projections behind the
   external frontend's same-origin proxy.
4. Preserve fan-out/fan-in, checkpoint/resume, retry, and idempotency semantics unless the task explicitly changes them.
   Resume supports only checkpoints written by the deployed master direct-executor graph: version-40 nested-graph checkpoints have no compatibility workflow or fallback.
5. Keep AG-UI additive to durable run/state/events/checkpoints APIs; do not move operator state to stream-only behavior.
6. Preserve the CopilotKit allowlist boundary: only selected run id, normalized status, safe event/executor metadata, checkpoint summary, and categorical final decision may cross the bridge.
7. If API, read-model, AG-UI, CopilotKit, or event contracts change intentionally, update frontend, tests, and docs in the same change set.
8. Never remove coverage for:
   - happy-path completion
   - retry then completion
   - crash and resume from checkpoint
   - fan-in visibility for all four child checks
   - checkpoint visibility
   - idempotency-skip visibility
   - observability fields in emitted events
   - hosted release smoke/evaluation evidence
9. Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`; runtime startup may
   validate schema parity but must not create or alter tables or indexes.
10. Routine release mode is always `app_only`. Never accept
    `FOUNDRY_DEPLOY_MODE` or add a public-ingress toggle.
11. Hosted agent metadata must contain only
    `${{connections.underwritingruntimesecrets.credentials.database_url}}` for
    both database variables. The resolved value belongs only in the
    Underwriting project `CustomKeys` connection.

## Required Verification Before Completing Work

Run the smallest existing applicable gate set and report what happened:

- `make test`
- `make quality` for backend/frontend code changes
- `make test-e2e` for UI, API, AG-UI, CopilotKit, workflow, or durable-history changes
- `make foundry-iac-build`, `make foundry-package`, and
  `make foundry-postgres-readiness`, `make foundry-model-preflight`, and
  `make foundry-runtime-connection` for hosted release/IaC changes
- `make foundry-backend-internalize CONFIRM=INTERNALIZE-<backend>` only for the
  guarded one-time migration of a legacy public-backend environment
- `make foundry-smoke` and `make foundry-eval` for hosted runtime, deployment, or telemetry changes
- `make foundry-verify` and `make foundry-evidence` after an authenticated release

When validating a deployed frontend, run hosted Playwright from `frontend/` with `PLAYWRIGHT_BASE_URL=<frontend-url> npm run test:e2e`.
If a gate cannot run, report the exact blocker and rerun command.

## Repository Skills

Use focused skills instead of one broad review pass:

- `design-review`
- `docs-sync`
- `backend-boundary-review`
- `local-validation`
- `quick-validation`
- `iac-review`
- `azure-validation`
- `azure-deployment`
- `azure-telemetry-validation`
- `foundry-agent-evaluation`
- `release-readiness`

## Stack Implementation Skills

Load only the relevant implementation skill for the task:

- `agent-framework-foundry-py`
- `agent-framework-azure-ai-py`
- `microsoft-foundry`
- `azure-ai-projects-py`
- `azure-identity-py`
- `azure-monitor-opentelemetry-py`
- `fastapi-router-py`
- `pydantic-models-py`
- `postgres-psycopg-py`
- `ag-ui-streaming-fastapi-py`
- `ag-ui-react-integration-ts`
- `typescript-setup`
- `typescript-update`
- `e2e-rubric`

## E2E and Hosted Release Baseline

Use `frontend/tests/e2e/rubric.ts` and `frontend/tests/e2e/underwriting.spec.ts` as the operator-facing baseline.

Required scenarios:

- happy path
- retry path
- crash at `medical_check`
- resume from checkpoint
- fan-in state contains risk, credit, medical, and driving results
- checkpoint list populated
- idempotency-skip event visible after resume/replay
- event payload contains observability fields

Release-only criterion: public hosted smoke and Foundry evaluation must show correlation between the public request, hosted workflow trace, and safe hosted conversation evidence.

## Documentation Update Contract

When architecture, workflow contracts, release gates, or operator-facing behavior change, update the smallest relevant set of:

- `.github/copilot-instructions.md`
- `agents.md`
- `README.md`
- `docs/design/architecture.md`
- `docs/design/deployment-flow.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/userflow.md`
- `docs/design/e2e-rubric.md`
- `deployment/README.md`
