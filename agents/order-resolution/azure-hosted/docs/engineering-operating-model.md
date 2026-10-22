# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the Azure-hosted lane.

- **You provide** architecture intent, business rules, and acceptance criteria.
- **Skills provide** current platform and SDK guidance.
- **Copilot provides** implementation, tests, infrastructure, and documentation.
- **Gates provide** correctness, recovery, telemetry, and evaluation evidence.

## Application-hosted policy

The internal FastAPI Container App is the only MAF application runtime.
Foundry is limited to optional model inference and report-only evaluation of
captured FastAPI workflow results. Do not introduce a hosted agent, Responses
runtime, second orchestrator, Bot, Activity endpoint, Teams integration, or
Adaptive Card path.

The browser reaches only the external frontend Container App. Nginx proxies
same-origin `/api` to the internal backend. The backend uses managed identity
for PostgreSQL and optional Foundry calls.

Native SSE is the stable operator contract. `/rich` remains a native-payload
envelope for existing consumers. AG-UI and CopilotKit can select only an
existing durable thread and expose only an allowlisted redacted projection.

## Target and documentation policy

Azure target values are supplied through a validated, ignored operator profile.
Tracked documentation may show placeholders and profile keys but must not
contain concrete tenant, subscription, user, resource, endpoint, credential,
connection string, or operator-network values.

Repository configuration expresses implementation intent. Only a fresh
release bundle proves the current source is deployed.

## Definition of done

1. Acceptance criteria are met without unintentionally changing stable HTTP,
   SSE, HITL, or persistence contracts.
2. Applicable local tests and deterministic evaluation pass.
3. HITL checkpoint/resume and idempotency behavior remain correct.
4. Telemetry preserves correlated workflow and approval identifiers without
   recording content by default.
5. Foundry evaluation remains report-only and release-blocking.
6. Affected documentation and instructions are updated.
7. A deployment claim has fresh verification, smoke, browser E2E, three HTTP
   domain scenarios, telemetry, evaluation, and final evidence from one
   release window.
8. Failed validation still produces a failed final evidence record.

## Gate matrix

| Change type | Required evidence |
| --- | --- |
| Documentation only | Link, stale-path, scope, and sensitive-identifier checks |
| Application or contract | Backend/frontend tests, deterministic evaluation, applicable browser coverage, and design review |
| HITL rule | Business rules, HITL docs, workflow tests, and evaluation cases |
| Selected-thread view | Projection/boundary tests, selected-thread E2E, runtime endpoint precedence, disabled inspector |
| Infrastructure | Bicep build, review, and fresh non-mutating preview before explicit apply |
| App release | Deployment verification, smoke, browser/domain E2E, telemetry, report-only evaluation, final evidence |

## Baseline scenarios

- `ORD-1001`: low risk, no HITL expected.
- `ORD-1009`: high risk, HITL expected and resumable.
- Damaged item: HITL expected.

## Release and reconciliation policy

- **Fresh bootstrap** creates a new profile-selected platform and establishes
  managed-identity PostgreSQL access.
- **Steady-state reconciliation** is explicit and must preserve PostgreSQL and
  application state.
- **Routine app-only release** updates only backend/frontend revisions and
  proves the application through a new release window.

Normal releases retain PostgreSQL, the approved Python package feed, and the
Alpine/musl-compatible frontend build. Telemetry is verified before
report-only evaluation; finalization enforces the app-only-to-telemetry budget.

Generated JSON belongs under
`.artifacts/releases/<release-id>/evidence/`; logs belong under the sibling
`logs/` directory. Exact release-local identifiers stay in generated evidence,
not tracked documentation.
