# Order Resolution Azure-Hosted Deployment Flow

## Current design

This lane uses one FastAPI-hosted MAF runtime:

- the external frontend Container App proxies same-origin `/api` to the
  internal backend Container App;
- the backend executes the MAF workflow and uses managed identity for Azure
  PostgreSQL;
- Foundry supplies optional model inference and report-only evaluation only;
- there is no Foundry hosted-agent, Responses, Bot, Activity, Teams, or
  Adaptive Card deployment stage; and
- every deployment claim comes from one fresh release evidence window.

Target values come from a validated, ignored operator profile. Tracked docs and
examples describe the schema only and contain no tenant, subscription, user,
resource, or endpoint values.

## Lifecycle paths

### Fresh bootstrap

Use only when the profile-selected platform does not exist.

1. Validate the profile and active Azure/AZD context.
2. Supply untracked bootstrap inputs through the operator environment.
3. Review a fresh subscription-scope preview.
4. Provision the base platform.
5. Establish PostgreSQL schema and least-privilege managed-identity access.
6. Verify the two Container Apps, identities, monitoring, and optional Foundry
   model/evaluation resources.
7. Remove temporary bootstrap access.
8. Transition the selected AZD environment to steady state.
9. Run an app-only release to deploy and prove the application.

### Steady-state infrastructure

Steady state retains PostgreSQL and application data. Infrastructure
reconciliation is exceptional:

1. run a fresh non-mutating preview;
2. reject unexpected stateful mutation, identity expansion, replacement, or
   public exposure;
3. apply only through the explicit reconciliation command; and
4. verify retained PostgreSQL identity and access after apply.

Changed files never authorize infrastructure execution.

### Routine app-only release

Use for normal application, dependency, runtime-configuration, and release
automation changes.

1. Initialize the release record from the selected profile.
2. Run source and target preflight.
3. Build and validate immutable backend/frontend images.
4. Deploy backend and frontend revisions.
5. Verify the backend is internal, the frontend is external, image digests are
   exact, and the frontend proxy reaches the backend.
6. Run health and smoke checks.
7. Run hosted browser E2E.
8. Run the three durable HTTP domain scenarios: low-risk, high-risk
   approval/resume, and damaged-item approval/resume.
9. Verify exact Application Insights correlation for those scenario
   thread/workflow pairs and zero relevant exceptions.
10. Run report-only Foundry evaluation over the captured HTTP results and
    require zero failed or errored rows.
11. Aggregate final secret-free evidence.

Telemetry completes the app-only timing window; evaluation and finalization may
finish afterward. A failed intermediate gate must still emit failed final
evidence.

## Stage ownership

| Stage | Authority |
| --- | --- |
| Target selection | Ignored operator profile validated as data |
| Bootstrap/reconciliation | Bicep/AZD preview and explicit operator command |
| Application deployment | Lane-local app-only release scripts |
| Database runtime access | Backend managed identity |
| Browser contract | External frontend and same-origin proxy |
| Workflow runtime | Internal FastAPI backend |
| Telemetry | Exact release-window Application Insights correlation |
| Evaluation | Report-only Foundry evaluation of captured HTTP results |
| Final claim | `.artifacts/releases/<release-id>/evidence/release-evidence.json` |

## Stop conditions

Stop when:

- the profile, Azure CLI, or AZD target does not match;
- the preview proposes unexpected mutation;
- PostgreSQL identity, schema, or managed-identity readiness fails;
- the backend is externally reachable;
- deployment attempts to add another application runtime;
- image, health, proxy, browser, domain, telemetry, or evaluator checks fail;
- evidence is stale, incomplete, sensitive, or assembled from different
  release windows; or
- the app-only-to-telemetry budget is exceeded.
