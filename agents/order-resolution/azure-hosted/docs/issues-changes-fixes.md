# Issues, Changes, Fixes, and Release Evidence

This newest-first ledger records profile-independent outcomes. Concrete tenant,
subscription, user, resource, endpoint, image, thread, workflow, evaluation,
and correlation identifiers remain in ignored/generated release evidence.

## Current status

- FastAPI is the only MAF application runtime.
- The browser topology is external frontend -> same-origin proxy -> internal
  backend.
- Azure PostgreSQL runtime access uses managed identity.
- Foundry evaluation is report-only and cannot mutate workflow state.
- Fresh bootstrap, steady-state reconciliation, and app-only release are
  separate operations.
- The current East US 2 release is live-validated: deployment, smoke, hosted
  browser, domain scenarios, telemetry, Foundry evaluation, and final evidence
  passed.
- CI source validation is aligned with Python 3.13 and ignored external target
  profiles. The remaining CI blocker is Azure RBAC for the GitHub OIDC release
  identity, not an application or deployment failure.
- Historical release evidence does not prove the current source revision is
  deployed; every release requires a fresh evidence window.

## 2026-10-22 - CI parity follow-up; OIDC RBAC pending

- Azure Hosted CI now installs Python 3.13 for backend, browser, design-review,
  release, and quick-validation jobs, matching the lane's runtime contract.
- The tracked concrete Azure target profile was removed. CI generates an
  ignored profile from the protected GitHub environment and validates the
  complete PostgreSQL and Foundry chat, embedding, and evaluator selector
  contract before release preflight.
- The protected GitHub environment location was corrected to East US 2 so
  capacity validation targets the live deployment region.
- Shared profile tests, generated-profile resolution, release source
  contracts, and the Bicep build pass. Backend, frontend, browser E2E,
  design-review, and image-cache jobs also pass in the authoritative workflow.
- The read-only preflight stops at Azure OIDC login with `No subscriptions
  found`. The configured federated identity needs reviewed least-privilege
  subscription/resource assignments before capacity preflight or app-only CI
  deployment can run. This authentication gate is not bypassed; the already
  validated live application remains healthy.

## 2026-10-22 - Fresh East US 2 deployment and release validated

### Regional and registry recovery

- Canada Central rejected the required chat/evaluator model version for both
  requested deployment SKUs, so the previously approved East US 2 fallback was
  selected after service, model, quota, and policy preflight.
- The first deterministic registry name was already globally allocated. A
  collision-free environment and registry name were generated without adding
  target identifiers to tracked files.
- The registry, application identities, and `AcrPull` assignments were staged
  before Container Apps provisioning so image-pull authorization could
  propagate.
- ACR Tasks dependency scanning could not parse the backend's parameterized
  `FROM --platform` expression. The already validated local images were pushed
  through authenticated Docker, preserving the Dockerfile and its platform
  safeguards.

### Infrastructure and database fixes

- Foundry project creation initially conflicted with concurrent account child
  deployment operations. The project now depends on all model deployments, so
  account updates are serialized.
- PostgreSQL SKU, tier, and version were hardcoded instead of consuming the
  ignored profile. The selectors now flow through the AZD environment,
  parameters, root template, and PostgreSQL module.
- Live burstable capacity was unavailable despite regional capability
  metadata. The approved General Purpose fallback provisioned successfully.
- The database schema is now applied by the Entra administrator. Runtime owns
  no application relations, cannot create schema objects, and retains only the
  table DML and sequence permissions required by the application.
- Bootstrap-only firewall access was removed, and steady-state infrastructure
  reconciliation excludes PostgreSQL and application Container Apps.

### Release and evaluation fixes

- The portability contract test inherited the live AZD environment and stopped
  being synthetic. It now unsets the inherited environment before exercising
  its fake AZD harness.
- Generic `azd deploy` completed both application services, after which the
  canonical app-only release pinned immutable image digests and converged the
  backend to internal ingress and the frontend to external ingress.
- Cloud judge evaluation asset creation returned
  `Microsoft.CognitiveServices/accounts/AIServices/assets/write` authorization
  failures when the interactive operator had project-scoped `Foundry User`.
  The assignment is now declared and provisioned at the Foundry account scope,
  which is the minimum scope that passed strict evaluation.
- The redundant legacy project-scoped operator assignment was removed after
  the account-scoped role and successful evaluation were verified. The
  operator now retains only the required account-scoped `Foundry User`.

### Final evidence

- Source validation, immutable image verification, deployment verification,
  smoke, hosted browser E2E, and all three domain scenarios passed.
- The low-risk flow completed without HITL. High-risk and damaged-item flows
  paused for approval, resumed, and completed.
- Exact Application Insights correlation passed for all three domain
  scenarios with zero relevant exceptions.
- App-only start through successful telemetry took `397635` ms, below the
  15-minute release budget.
- Foundry report-only evaluation passed all three conversations. Task
  Completion and Coherence each passed `3/3`, with zero failed or errored rows.
- Final evidence aggregation passed, the release status is `succeeded`, and
  immutable digests plus revision evidence preserve rollback traceability.

### Learnings

- Treat advertised regional capability as preflight evidence, not a guarantee
  of live SKU capacity.
- Serialize Foundry account child mutations that can otherwise conflict.
- Judge/evaluation assets may require account-scoped data-plane authorization
  even when project-scoped access is sufficient for other Foundry operations.
- Keep database bootstrap privileges, network access, and runtime permissions
  as separate, explicitly verified lifecycle phases.
- Preserve successful release stages and resume only failed gates so telemetry
  timing and prior evidence remain authoritative.

## 2026-10-22 - Documentation structure aligned

### Changes

- Flattened canonical documentation from the legacy nested design directory
  into the documentation root.
- Split the former PRD into business rules, functional specification, and
  technical specification.
- Added a documentation index and Azure-hosted operator/demo runbook.
- Aligned root, component, deployment, infrastructure, instruction, and agent
  documentation with the FastAPI-only lane.
- Replaced tracked target values with generic ignored-profile wording.

### Guardrails retained

- no private networking;
- no Foundry hosted-agent or Responses runtime;
- no Bot, Activity, Teams, or Adaptive Cards;
- no password-based PostgreSQL fallback; and
- no deployment claim without fresh generated evidence.

## 2026-08-16 - App-only release timing evidence

The then-current release completed the app-only-to-telemetry interval within
the 15-minute budget. Packaging and deployment overlap were measured, followed
by deployment verification, smoke, browser E2E, domain E2E, telemetry,
report-only evaluation, and final evidence.

This historical timing is retained as operational context only. It is not
evidence for another source revision.

## 2026-08-15 - Fresh app-only release validated

- Backend and frontend immutable images passed local/cloud image validation.
- Only application revisions changed.
- The backend remained internal and the frontend remained external.
- Low-risk, high-risk approval/resume, and selected-thread browser scenarios
  passed.
- Report-only evaluation completed with zero failed or errored rows.
- Exact release-window telemetry correlation passed with zero relevant
  exceptions.
- PostgreSQL, schema, data, and RBAC were not recreated or broadened.

## 2026-08-14 - Fresh bootstrap and steady-state transition

- A new profile-selected Azure platform was previewed and provisioned.
- PostgreSQL schema and least-privilege backend managed-identity access were
  established.
- Bootstrap-only network access was removed and verified.
- The selected environment transitioned to steady state.
- Later reconciliation excluded PostgreSQL and the application Container Apps.

## 2026-08-13 - Portability and release hardening

- Target selection moved behind validated profile parsing.
- Release checks fail closed on target mismatch.
- Approved package feeds and frontend Alpine/musl compatibility were retained.
- Failed validation paths were changed to preserve final failed evidence.
- Infrastructure preview/reconciliation was separated from routine app
  delivery.

## 2026-08-10 - PostgreSQL and release recovery

- Recovery retained the existing PostgreSQL server and workflow database.
- Runtime identity and schema readiness were verified before application
  deployment.
- Database recreation, public bypasses, and privilege expansion were rejected
  as recovery shortcuts.

## 2026-08-07 - Selected-thread and evidence boundary

- AG-UI and CopilotKit were constrained to read-only projections of existing
  durable threads.
- Raw native/rich payloads were excluded from assistant surfaces.
- The CopilotKit inspector remained disabled.
- Release evidence was standardized under one release-local directory with
  JSON under `evidence/` and diagnostics under `logs/`.
