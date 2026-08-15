# Order Resolution Azure-Hosted Deployment Flow

## Current design

This lane keeps the same four-phase release vocabulary used by the
Foundry-public reference, but its runtime is different:

- The FastAPI Container App is the only MAF application host.
- Foundry provides model deployments and report-only evaluation only.
- There is no hosted-agent component, capability host, or Foundry application
  runtime.
- Bootstrap IaC creates the initial Azure platform; `steadyState` excludes
  PostgreSQL and the two application Container Apps from reconciliation.
- Normal releases are app-only and deploy immutable backend/frontend images to
  the existing Container Apps.

The repository keeps tracked deployment inputs and contracts in
`deployment/profiles/`, `.azure/deployment-plan.md`, and the checked-in design
docs. Each authorized release generates a fresh evidence bundle under
`.artifacts/releases/<release-id>/`, with JSON evidence under `evidence/` and
diagnostic/browser output under `logs/`. The target profile and parser are
owned by this project; there is no shared deployment implementation.

## Common standardized stages vs. Azure-hosted differences

### Common standardized stages

- Select one approved target and validate source before any deployment claim.
- Review a fresh non-mutating IaC preview before infrastructure mutation.
- Verify database readiness before application deployment.
- Package immutable release artifacts, then verify exact deployed revisions.
- Prove the release with fresh domain E2E, telemetry correlation, evaluation,
  and one final evidence bundle.

### Azure-hosted differences

- The workflow enters through HTTP to FastAPI and persists durable threads in
  PostgreSQL; it does not hand off execution to a hosted agent.
- Foundry evidence is derived from HTTP workflow captures; evaluation is
  report-only and cannot alter workflow results.
- The bootstrap-to-`steadyState` handoff is a first-class stage because the
  lane retains PostgreSQL and excludes it from normal reconciliation.
- Deployment proof is the exact backend/frontend Container App revisions,
  smoke/domain correlations, and Application Insights thread/workflow evidence.

## Deployment stages

The flow is grouped into four phases and 14 stages.

### Phase 1: Validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Load the approved Azure-hosted profile and resolve the fixed subscription, resource group, location, AZD environment, and release target. Tracked profiles remain secret-free. |
| 2 | Source validation | Run the required local and CI-aligned validation gates for the selected change scope, including backend/frontend contracts, evaluation, browser coverage, and design review as applicable. |
| 3 | Local deployment authentication | Validate Azure CLI/AZD authentication, confirm the selected subscription/environment, and hydrate the local release context for this lane only. |
| 4 | Infrastructure preview | Review a fresh subscription-scope preview. Bootstrap may create the initial platform; `steadyState` preview must exclude PostgreSQL and the application Container Apps. Any unexpected mutation stops the flow. |

### Phase 2: Provision the Azure-hosted platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base infrastructure | Authorized bootstrap creates the Container Apps environment, ACR, monitoring, PostgreSQL, identities, and Foundry model/evaluation resources. Later routine releases reuse those retained resources. |
| 6 | Database bootstrap and readiness | The administrator creates or reconciles schema objects and grants the runtime identity only the approved access. Readiness verifies connectivity, retained server identity, and denied privilege expansion. |
| 7 | Bootstrap-to-steadyState transition | After bootstrap, verify the retained PostgreSQL identities, delete and verify removal of the exact `allow-bootstrap-runner` firewall rule, then switch the local AZD environment to `steadyState`. Future IaC previews exclude PostgreSQL and the application Container Apps. |

### Phase 3: Deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 8 | Release preflight and immutable packaging | Confirm the selected Foundry model deployments are the intended inference/evaluation inputs, prepare the release context, and build the backend/frontend images once for immutable digest deployment. |
| 9 | Container App deployment | Deploy only the backend and frontend revisions. The frontend stays same-origin through `/api`; the backend remains the sole MAF host and preserves durable PostgreSQL workflow state. |
| 10 | Hosted-agent component | None. This stage is intentionally a no-op in the Azure-hosted lane because Foundry does not host workflow execution, secrets, or agent versions here. |
| 11 | Deployment verification and smoke | Verify the exact backend/frontend digests and revisions, ingress/health behavior, low-risk and high-risk smoke responses, and release-window correlation capture before moving to broader evidence. |

### Phase 4: Prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 12 | Hosted browser E2E | Run the deployed browser workflow and selected-thread suite against the same release window and retain `logs/browser-e2e.log` plus Playwright artifacts under the canonical release directory. |
| 13 | HTTP and durable domain E2E | Run exactly three HTTP workflow scenarios through the durable thread history: low-risk no HITL, high-risk approval/resume, and damaged-item approval/resume. Capture the exact `thread_id`/`workflow_run_id` pairs for later telemetry validation. |
| 14 | Evaluation, telemetry, and final evidence | Run report-only Foundry evaluation against the deployed HTTP capture set and require a completed run with zero failed or errored rows. Verify all three exact domain-scenario correlation pairs in Application Insights with zero relevant exceptions. Aggregate the secret-free bundle, and write a failed final evidence record when any intermediate validation gate stops the release. |

## Release paths

### Fresh bootstrap

Run all 14 stages:

1. Select the bootstrap profile and review the bootstrap preview.
2. Provision the initial Azure platform and complete database readiness.
3. Transition the local AZD environment from bootstrap to `steadyState`.
4. Build immutable backend/frontend images, deploy them app-only, then collect
   fresh smoke, hosted browser E2E, three-scenario HTTP/durable E2E,
   evaluation, telemetry, and final evidence.

### Routine app-only release

Do not reprovision infrastructure:

1. Reuse the approved target and validate the current source.
2. Review the `steadyState` preview only when reconciliation is intentionally
   being considered.
3. Build backend/frontend images, deploy the exact digests app-only, and gather
   fresh smoke, HTTP/durable E2E, telemetry, evaluation, and final evidence.

## Stop conditions

Stop the release if:

- the selected subscription, resource group, location, or AZD environment does
  not match the tracked profile;
- a bootstrap or `steadyState` preview proposes unexpected stateful mutation;
- PostgreSQL identity, connectivity, privilege, or firewall cleanup checks fail;
- deployment attempts to add a hosted-agent component or alternate MAF host;
- backend/frontend image, revision, health, smoke, or durable-thread checks fail;
- telemetry cannot correlate the exact release-window thread/workflow pairs;
- evaluation mutates application state, cannot be tied to the HTTP capture set,
  does not complete, or contains failed/errored rows; or
- final evidence is stale, incomplete, secret-bearing, or assembled from
  different release windows.
