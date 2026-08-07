# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the repository.

- **You provide** architecture intent, business rules, and acceptance criteria.
- **Skills provide** current platform and SDK guidance.
- **Copilot provides** implementation, tests, infrastructure, and documentation.
- **Gates provide** correctness, recovery, telemetry, and evaluation evidence.

## Application-hosted policy

The FastAPI Container App is the only application host for the MAF workflow.
Foundry is limited to model inference and report-only evaluation of FastAPI
workflow captures. Do not introduce a Foundry application runtime or an
alternate orchestration path.

The deployment target is `rg-maf-ora-azure` in North Central US. East US is
not a target because of the current Azure PostgreSQL offer restriction.

Native SSE is the stable operator contract. `/rich` is a stable,
native-payload envelope for its existing consumers. The additive
`/api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` surfaces select
one existing durable thread and expose only a redacted projection. CopilotKit
GET discovery is static, its inspector is disabled, and its POST bridge
discards messages, state, tools, context, and other compatibility fields. None
of these optional views may execute or alter the workflow.

## Delivery status

The current deployment plan is **Validated for an app-only cloud release**. It
must not claim a deployed or validated release until fresh evidence is recorded
in `.azure/deployment-plan.md` and `docs/design/issues-changes-fixes.md`.

## Definition of done

1. Acceptance criteria are met without changing stable HTTP, SSE, HITL, or
   persistence contracts unintentionally.
2. Applicable local tests and deterministic evaluation pass.
3. HITL checkpoint/resume and idempotency behavior remain correct.
4. Telemetry preserves correlated workflow and approval identifiers without
   recording content by default.
5. `make eval-foundry`, when applicable, is retained as report-only evidence.
6. Affected documentation is updated with the change.
7. A release is not called validated without fresh smoke, hosted E2E,
   report-only evaluation, and telemetry correlation evidence from one release
   window.

## Gate matrix

| Change type | Required evidence |
| --- | --- |
| Application or contract change | `make test`, `make eval-backend`, applicable `make test-e2e*`, design review, and successful cloud Docker E2E for full-validation changes |
| HITL rule change | Applicable tests/eval cases and `hitl-approval-conditions.md` |
| Selected-thread/assistant change | Projection/boundary tests, selected-thread E2E, runtime endpoint and disabled-inspector checks |
| Azure/IaC change | Local evidence, Bicep build and `iac-review`; reconciliation preview only with explicit owner confirmation |
| Normal authorized deployment | `make release-app`: app-only smoke, hosted E2E, report-only evaluation, and fresh telemetry correlation |

## Baseline scenarios

- `ORD-1001`: low risk, no HITL expected.
- `ORD-1009`: high risk, HITL expected and resumable.
- Damaged item: HITL expected.

## Release and reconciliation policy

Normal releases are application-only. On `main`, the path-scoped
**Required cloud Docker E2E** job builds the backend/frontend release images
once, tests those exact images, pushes their immutable ACR digests, updates
only the two Container Apps, then runs smoke, hosted E2E, report-only
evaluation, and telemetry correlation. It retains the existing PostgreSQL
server and `maf_workflow` database, CFS Python package feed, and
Alpine/musl-compatible frontend build.

Infrastructure reconciliation is exceptional. It requires
`INFRA_RECONCILIATION_APPROVED=true`, a non-secret owner change reference, and
an owner-reviewed `make release-infra-preview`; apply must pass the exact
preview and template/parameter hashes emitted by that preview. The reconciliation guard verifies the pre-existing
PostgreSQL identity and refuses recreation/replacement. Source intent and
historical results are not deployed evidence.

Local Docker E2E is optional where managed-device policy blocks Docker npm
egress. The GitHub Actions **Required cloud Docker E2E** job is the
authoritative Docker image and browser evidence; full changes cannot substitute
host npm results or a skipped local Docker run for that cloud result.

The Azure-hosted workflow triggers only for changes under
`agents/order-resolution/azure-hosted/**` or to its own workflow definition.
Other monorepo paths do not start this release lane.
