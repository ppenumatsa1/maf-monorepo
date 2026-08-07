# Engineering Operating Model

## Purpose

This is the canonical delivery contract for this repository.

It formalizes the split:

- **You provide** architecture intent, business rules, and acceptance criteria.
- **Skills provide** current Microsoft platform and SDK guidance.
- **Copilot provides** implementation, tests, and infra/doc updates.
- **Gates provide** release evidence for correctness, recovery, telemetry, and Foundry parity.

This model is Pareto-first: start with the minimum enforceable contract and expand gates only when risk increases.

## Current lane policy

Hosted validation and deployment are private-lane-first in the current operating posture:

- **Default hosted lane:** private Foundry (`foundry-private-env` / private runner path).
- **Deployment control plane:** PR/static validation is credential-free. The
  protected manual provision/deploy workflows run only on
  `self-hosted,foundry-private-v2` in `foundry-private-env` using Azure OIDC;
  no Azure or database secret is stored in the workflow.
- No additional hosted lane is part of the required gate path unless explicitly re-enabled by a documented decision update.
- **Private web ingress:** one external frontend ACA and one internal FastAPI
  ACA share a VNet-integrated environment on a dedicated subnet. Foundry,
  PostgreSQL, ACR, and application data planes remain private; Azure Monitor
  uses managed ingestion for telemetry.
 - **Private Foundry monitoring:** the project-level `ApplicationInsights`
  connection remains non-shared and holds its protected connection-string
  credential. Hosted agents rely only on the platform-injected
  `APPLICATIONINSIGHTS_CONNECTION_STRING`; application manifests and runtime
  secret connections must not introduce an instrumentation-key fallback.
- **PostgreSQL cutover:** target the canonical Flexible Server FQDN, bind its
  `postgresqlServer` private endpoint to
  `privatelink.postgres.database.azure.com`, and retain public access plus the
  Azure-services firewall rule until documented ACA and hosted-agent
  connectivity proof is supplied. `POSTGRES_SERVER_NAME` and
  `RUNTIME_DATABASE_URL` must resolve to that same canonical FQDN; do not reuse
  a historical server name.
- **Lockdown authority:** only `make foundry-connectivity-proof` may create the
  proof consumed by `make foundry-postgres-lockdown`. By default it must be no
  more than one hour old, name the canonical FQDN, and record passed ACA and
  hosted-agent connectivity. Lockdown then verifies the approved private
  endpoint, `postgresqlServer` group, private-DNS A record, and VNet link before
  disabling public access and deleting `allow-azure-services`.
- **Release serialization:** provision/reconciliation, app-release, and
  observability workflows share `order-resolution-private-release` concurrency
  and execute only on `foundry-private-v2`. Each dispatch must declare one
  release class; concurrency does not make the classes interchangeable.
  Optional agent refresh, password repair, public-access, firewall, and
  administrator-user bypasses are not valid release paths.
- **Foundry connection staging:** core provisioning creates the private
  account/project identity and required service RBAC with
  `MANAGE_PROJECT_CONNECTIONS=false`. The later private deploy stage enables
  project connections only after that identity path exists; retries wait for
  Azure identity or private-endpoint deletion propagation rather than weakening
  network controls or removing the required connections.

## Safe private release boundaries (2026-08-07)

Every protected private operation has exactly one of these scopes:

| Release class | Scope | Required evidence and prohibition |
| --- | --- | --- |
| Routine app-only release | Existing ACA backend/frontend revisions and the existing hosted agent. | Validate existing private dependencies before and after the artifact release. Do not run full Bicep, reconcile shared resources, alter networking/identity, or change PostgreSQL access. |
| Explicit bootstrap/reconciliation | Full Bicep management plane, including shared dependencies. | Capture a current preview, review every proposed change, and obtain explicit approval of the reconciliation plan before execution. A preview is not a deployment or a health proof. |
| PostgreSQL lockdown | Canonical PostgreSQL private endpoint/DNS, public-access, and firewall controls. | Run separately, with explicit confirmation, only after the current generated connectivity proof shows both ACA and hosted-agent access to the canonical FQDN. It is never an app-only-release side effect. |

Full-IaC preview run `31198356080` showed shared authoritative drift in the
VNet/subnets, ACA environment, Foundry account/project/models, ACR, Cosmos,
Application Insights, and Search. The operating decision is fail closed:
full-Bicep bootstrap/reconciliation is blocked pending owner-approved intended
state for those resources. Do not normalize, accept, or deploy that drift under
the routine app-only release label, and do not claim deployment success from
the preview.

## Approved selected-thread and frontend alignment

The approved selected-thread design is an additive private-lane operator view,
not a new workflow, deployment route, or browser-to-private-data-plane path:

- Native SSE, durable workflow history, and checkpoint-keyed HITL remain the
  operator source of truth. AG-UI and CopilotKit must fail independently
  without making those contracts unavailable.
- The external frontend continues to call only its same-origin `/api` proxy.
  The internal FastAPI wrapper tails durable PostgreSQL events after its
  non-streaming initial Foundry Responses dispatch. The browser never calls
  private Foundry, PostgreSQL, or MCP/RAG services.
- `GET /api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` select
  one existing thread and return only allowlisted lifecycle/tool labels,
  validated checkpoint IDs and approval decisions, and generic terminal/error
  text. `GET /api/copilotkit/info` (and its `GET /api/copilotkit` alias) is
  static, redacted discovery.
- CopilotKit means `@copilotkit/react-core`, not the GitHub Copilot SDK.
  `runId`, `messages`, `state`, `tools`, `context`, and `forwardedProps` are
  compatibility input only and must be discarded. No selected-thread
  projection can start, resume, approve, reject, or otherwise mutate a run.
- Order/customer and policy data, policy evidence, MCP/RAG content, tool
  arguments/results, prompts, raw model output, reviewer comments, checkpoint
  payloads, credentials, and secrets remain backend-only.

The private frontend implementation and its strict TypeScript/lint/build
scripts and focused selected-thread browser tests are complete and locally
validated: 128 tests passed, the deterministic evaluation completed 10/10,
seven workflow and four selected-thread E2E cases passed, and design review
passed. This is not protected-release evidence. The `vm-maffnd-runner`
deployment, hosted E2E, Foundry evaluation, and telemetry verification have
not run for this implementation.

## Inputs and authority

### 1) Product and architecture inputs (user/team authority)

Required inputs before implementation:

- Architecture boundaries and explicit non-goals
- Business-rule truth conditions (including HITL triggers)
- Acceptance criteria in observable terms (events, outputs, state)
- Deployment lane scope (local runtime and private Foundry hosted lane)

### 2) Skill authority (implementation constraints)

Skills define current best-practice patterns for Microsoft services/SDKs and deployment guidance.

Skills do **not** override business rules or accepted contracts on their own. If skill guidance conflicts with accepted behavior/contracts, capture the delta as a documented decision and apply the smallest approved change.

### 3) Copilot delivery responsibilities

For each approved change, Copilot must deliver:

- Smallest complete code/IaC/script update that satisfies acceptance criteria
- Matching tests and contract-safe updates (API, SSE, HITL, persistence)
- Required documentation sync for changed behavior or operations
- Evidence artifacts from required gates

## Source-of-truth hierarchy

When guidance conflicts, resolve in this order:

1. `docs/design/engineering-operating-model.md` (this contract)
2. Architecture and behavior docs (`architecture.md`, `userflow.md`, `hitl-approval-conditions.md`, `prd.md`)
3. Repository instructions (`.github/copilot-instructions.md`, `agents.md`)
4. Skill guidance (stack/repository skills)
5. Inline comments/examples

## Definition of Done (minimum)

A change is done only when all applicable items are true:

1. Acceptance criteria are met without breaking stable contracts.
2. Required tests/gates pass for the change type.
3. Recovery behavior remains correct for stateful/HITL flows.
4. Telemetry remains correlated and free of new unhandled workflow exceptions.
5. Evaluation evidence is present: deterministic eval is green; Foundry evaluator run is published for hosted/runtime-impacting changes.
6. Required docs are updated in the same change set.
7. Evidence is recorded in `docs/design/issues-changes-fixes.md` when deploy/runtime behavior is involved.

## Change-to-gate matrix (Phase 1)

| Change type | Required local gates | Required hosted gates |
| --- | --- | --- |
| App-only behavior (no hosting/IaC change) | `make test`, `make eval-backend`, `make test-e2e`, `./scripts/skills/design-review-skill.sh` | None |
| Routine app-only release | Applicable application gates and validation of existing private dependencies | Private-runner ACA revision and hosted-agent release only; no full Bicep or PostgreSQL lockdown |
| Bootstrap/reconciliation | IaC review and a current full-Bicep preview with an approved reconciliation decision | Approved private-runner full-Bicep execution, then applicable deployment and telemetry evidence |
| PostgreSQL lockdown | Fresh generated ACA/hosted-agent connectivity proof for the canonical FQDN | Separately confirmed lockdown; record proof, access result, and subsequent applicable release evidence |
| HITL/business-rule change | local gates + targeted HITL rule assertions | Hosted smoke for `ORD-1001`, `ORD-1009` (+ approve/reject when applicable) |
| MAF/Foundry runtime change | local gates + focused hosted-entry tests + `make eval-backend` | Private Foundry deploy + smoke + E2E evidence + enforced conversation trace evaluation + correlated telemetry verification |
| IaC/network/identity/deploy workflow change | local gates as applicable + IaC review | `azure-validation` -> `azure-deployment` -> `azure-telemetry-validation` |
| Persistence/checkpoint/idempotency change | local gates + restart/resume/idempotency assertions | Hosted smoke for resume and duplicate HITL response behavior |
| Private browser/ACA/network change | local gates + IaC review + Bicep preview | Private-runner deployment, external-frontend Playwright, private DNS/public-access checks, and telemetry correlation |
| Selected-thread AG-UI/CopilotKit frontend implementation | Strict TypeScript check, frontend build/lint, focused selected-thread Playwright, and `make test-e2e` | Private-runner release evidence only when the change affects the hosted private browser/wrapper contract |

`make eval-foundry` remains report-only for ad hoc/local use. The private release
workflow first exercises low-risk and HITL scenarios once, then enforces Foundry
judgement and Application Insights correlation over those same conversation IDs;
it does not generate a second evaluator traffic pass. Release-automation
changes use `make test` as their only local private validation; the hosted
evaluation is collected only in the private release sequence.

## Operationalization (automated)

The CI workflow (`.github/workflows/ci.yml`) enforces this model in two lightweight stages:

1. **Routing** via `scripts/skills/deployment-mode-router.sh` to select `validation_mode` (`quick` or `full`) from changed surfaces.
2. **Guardrail enforcement** via `scripts/skills/operating-model-enforcement.sh`:
   - HITL decision-surface changes require `docs/design/hitl-approval-conditions.md` updates plus workflow-test or hosted-eval updates.
   - Hosted runtime/deploy surface changes require an update to `docs/design/issues-changes-fixes.md`.

## Evidence handoff template

For each release-impacting change, capture:

- Release class (routine app-only, bootstrap/reconciliation, or PostgreSQL
  lockdown) and why that scope is sufficient
- Commit SHA and changed surfaces
- Gate results (pass/fail + command or run ID)
- For full Bicep, the preview run, reviewed drift decision, and approval; for
  PostgreSQL lockdown, the separately confirmed generated connectivity proof
- Hosted version and conversation/thread identifiers
- Foundry trace evidence (version-scoped)
- App Insights correlation evidence (`workflow_run_id`, `thread_id`, exception status)
- Deferred items (explicitly marked deferred, not implied complete)

## Current baseline scenarios

- `ORD-1001`: low-risk path, no HITL expected.
- `ORD-1009`: high-risk path, HITL expected and resumable.
- Damaged item: HITL expected.

## Evidence record

The local selected-thread evidence is 127 passing tests, a 10/10 deterministic
evaluation, seven workflow E2E cases, four selected-thread E2E cases, and a
passing design review. The protected `vm-maffnd-runner` deployment, hosted E2E,
Foundry evaluation, and telemetry evidence remain unrun. Record those results
only after they occur; do not infer a private release from local evidence.
