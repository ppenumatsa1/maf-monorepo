# Copilot Instructions

This repository implements a public Microsoft Foundry-hosted underwriting workflow using Microsoft Agent Framework (MAF), durable PostgreSQL checkpoints and projections, AG-UI streaming, and a safe CopilotKit assistant surface.

## Primary Goals

- Keep one master underwriting workflow path with direct MAF executors; do not add a shadow orchestrator, alternate workflow engine, or compatibility shim.
- Keep Foundry hosting Responses-native through `backend/foundry/main.py` and `backend/Dockerfile.hosted`.
- Preserve deterministic fan-out/fan-in across risk, credit, medical, and driving checks before any model rationale is attached.
- Keep checkpoint and resume behavior durable through PostgreSQL-backed `maf_checkpoints` plus run, event, and state projections.
- Keep AG-UI and CopilotKit additive and safe; the browser must never talk directly to Foundry or PostgreSQL.
- Keep API, read-model, stream, and telemetry contracts stable for React, Playwright, and hosted release gates.

## Delivery formalization

- **You provide** underwriting rules, operator expectations, and release intent.
- **Skills provide** repository and Microsoft platform guidance.
- **Copilot provides** focused implementation plus matching tests and documentation updates.
- **Gates provide** local, hosted, and telemetry evidence before release handoff.

Canonical contracts live in:

- `docs/design/architecture.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/e2e-rubric.md`

The public deployment lane is `infra/foundry-hosted/` with authenticated local `make foundry-*` commands. The deployed topology is React/Vite frontend -> FastAPI public adapter -> Foundry Responses agent `underwriting-hosted` -> PostgreSQL checkpoints and projections.

## Workflow Guardrails

- Keep canonical ownership strict:
  - `backend/app/api/v1/routes/*` owns HTTP, AG-UI, and CopilotKit route entrypoints only.
  - `backend/app/api/v1/schemas/*` owns API request and response contracts.
  - `backend/app/modules/underwriting/*` owns service and domain seams, hosted relay envelopes, safe run-assistant context, and deterministic decision policy.
  - `backend/app/core/*` owns config, telemetry, and app composition.
  - `backend/app/infrastructure/*` owns PostgreSQL, Foundry clients, checkpoint storage, and repository adapters.
  - `backend/app/maf/*` owns workflows, executors, runner, middleware, tools, prompts, and AG-UI event projection.
- `backend/app/server.py` composes routers; it must not absorb workflow logic.
- `backend/foundry/main.py` is the hosted workflow entrypoint and constructs the real MAF runner. The public adapter relays start and resume requests and reads durable projections; it must not construct a second hosted-only orchestration path.
- Preserve fan-out/fan-in semantics: risk, credit, medical, and driving executors fan out/fan in in one superstep, `fan_in_aggregator` merges incrementally, and `final_decision` remains deterministic before rationale generation.
- Preserve checkpoint and resume behavior keyed by `workflow_run_id`; replay and resume must remain idempotent and observable. Only checkpoints written by the deployed master direct-executor graph are resumable: version-40 nested-graph checkpoints are unsupported after deployment, with no compatibility workflow or fallback.
- Keep AG-UI stream frames additive to durable run, state, events, and checkpoints endpoints. Do not replace durable read-model contracts with transient stream-only state.
- Keep CopilotKit safe and allowlisted. The bridge may expose only selected run id, normalized status, safe event and executor metadata, checkpoint count and timestamp, and categorical final decision. Never expose applicant details, health disclosures, income, credit scores, raw prompts, raw model output, checkpoint payloads, credentials, or secrets.
- Preserve telemetry for `foundry.responses.invoke`, hosted workflow, fan-out/fan-in, retry and backoff, injected failures, checkpoint save/load, idempotency skip, and final decision spans. Start and resume may land in separate hosted traces; correlate by `workflow.run_id`.
- If API, read-model, AG-UI, CopilotKit, or event contracts change intentionally, update frontend, Playwright, and design docs in the same change.

## Local and Release Validation Commands

Use the smallest existing gate set that proves the change:

- `make test`
- `make quality`
- `make test-e2e`

For hosted/public-lane or telemetry changes, also use applicable release gates:

- `make foundry-bootstrap`
- `make foundry-iac-build`
- `make foundry-postgres-readiness`
- `make foundry-smoke`
- `make foundry-eval` (the report-only Foundry trace-evaluation gate)

When the deployed frontend is in scope, run hosted Playwright against it with `PLAYWRIGHT_BASE_URL=<frontend-url> npm run test:e2e` from `frontend/`.

## Repository Skills

- `design-review`: final focused review plus existing validation gates.
- `docs-sync`: keep instruction files and design docs synchronized.
- `backend-boundary-review`: enforce API/modules/core/infrastructure/MAF ownership and no-shim rules.
- `local-validation`: run the full local backend/frontend/e2e gates.
- `quick-validation`: run the smallest existing validation set for low-risk app-only changes.
- `iac-review`: review `infra/foundry-hosted`, Docker, AZD, and release scripts without mutating Azure.
- `azure-validation`: validate Azure readiness and deployed behavior without deployment.
- `azure-deployment`: execute the authenticated release sequence only after validation passes.
- `azure-telemetry-validation`: verify Application Insights and Foundry traces after deployment.
- `foundry-agent-evaluation`: run the report-only hosted trace evaluation and publish evidence.
- `release-readiness`: orchestrate the focused skills for PR or release handoff.

## Stack Implementation Skills

Load only the skills relevant to the change:

- `agent-framework-foundry-py`
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

## Baseline Scenarios

Keep coverage for:

- happy-path completion
- retry then completion
- crash after a configured executor
- resume from a stored MAF checkpoint
- fan-in state showing all four child checks
- checkpoint visibility
- idempotency-skip visibility on replay and resume
- observability fields in event output
- hosted release smoke that correlates the public request with hosted workflow and model traces

## Documentation Contract

When architecture, workflow contracts, release gates, or operator-facing behavior change, update the smallest relevant set of:

- `.github/copilot-instructions.md`
- `agents.md`
- `docs/design/architecture.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/userflow.md`
- `docs/design/e2e-rubric.md`
