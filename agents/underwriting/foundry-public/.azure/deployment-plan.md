# Underwriting Foundry Public Deployment Plan

**Status:** Validated

**Approval:** The request to proceed with IaC, deployment, smoke, E2E,
evaluation, and telemetry validation approves this non-destructive release
plan. PostgreSQL rebuild remains excluded.

## Scope

Deploy the clean Underwriting Foundry Public architecture to the selected
`underwriting-foundry-public` AZD environment. The release includes the
Foundry hosted agent, public backend and frontend adapters, and existing
resource-reuse PostgreSQL configuration.

## Azure Context

- Subscription: `4f18d577-3506-4a11-85e5-a83b14727a84`
- AZD working directory: `infra/foundry-hosted`
- AZD environment: `underwriting-foundry-public`
- Deployment model: existing Bicep and AZD resource-reuse configuration

## Deployment Sequence

1. Run `make foundry-release` from the authenticated operator environment.
2. Validate local source and build Bicep concurrently, then use the deployment
   router to select full provisioning or app-only deployment.
3. After shared readiness, deploy the hosted Foundry agent, public backend,
   and public frontend concurrently.
4. Execute hosted smoke, then run deployed browser E2E and report-only Foundry
   evaluation concurrently.
5. Verify Application Insights correlation after E2E writes its evidence.
6. Record dated evidence, run identifiers, evaluation results, and telemetry
   references in `docs/design/issues-changes-fixes.md`.

## Safety and Rollback

- Do not execute the explicit PostgreSQL server rebuild target; it is
  destructive and out of scope.
- Do not store secrets in source, deployment plans, or telemetry.
- Retain the existing resource-reuse posture and approved public-lane
  environment.
- If validation or deployment fails, stop at the failing stage and record the
  safe recovery action. Do not add compatibility shims or parallel runtimes.

## Validation Criteria

- Bicep, scripts, and AZD configuration validate against the selected
  environment.
- Hosted smoke verifies a real Responses workflow run.
- Browser E2E verifies happy path, retry, and crash/resume operator flows
  against the deployed public UI.
- Foundry trace evaluation and Application Insights evidence correlate to the
  deployed workflow run.

## All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not applicable)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not applicable)

## Blocking Issue

`azd package --no-prompt` initially could not build the `underwriting-hosted`
image because
Central Feed Services policy blocks direct access to `pypi.org/simple` and
`files.pythonhosted.org` on Microsoft-managed devices. The resulting
`SSLV3_ALERT_HANDSHAKE_FAILURE` occurs in Docker, Docker host-network mode,
and native Windows Schannel; it is not a Docker Desktop or WSL-specific
failure.

The approved CFS PyPI endpoint,
`https://packagefeedproxy.microsoft.io/pypi/simple`, successfully resolved and
downloaded `setuptools==83.0.0` from both the host and a clean Python
container. Configuring `PIP_INDEX_URL` to that endpoint in
`backend/Dockerfile.hosted` allowed `azd package --no-prompt` to succeed.

No Azure resources were changed during package validation. Continue with the
remaining deployment workflow.

## Section 7: Validation Proof

- `azd version`: Azure Developer CLI 1.28.1 is installed.
- Azure YAML schema validation passed for `infra/foundry-hosted/azure.yaml`.
- The selected environment is `underwriting-foundry-public` in subscription
  `4f18d577-3506-4a11-85e5-a83b14727a84`, region `eastus2`, resource group
  `rg-underwriting-readiness-0731`; Azure authentication is active.
- `azd provision --preview --no-prompt` passed without applying changes. It
  previews only the declared resource-reuse updates.
- Azure Policy assignments were inspected. The applicable management-group
  creation policy did not prevent the successful resource-reuse preview.
- `make -C agents/underwriting/foundry-public validate-full` passed.
- `azd package --no-prompt` passed after the hosted Dockerfile was configured
  to use the approved CFS PyPI index.
- Static Bicep RBAC review passed:
  - the Foundry project identity has ACR pull, log/telemetry reader, and
    Cognitive Services OpenAI User roles at target-resource scope;
  - the public backend managed identity has Foundry User at project scope;
  - the Foundry account and project identities have evaluation-artifact access
    scoped to the evaluation storage account.
- Aspire checks are not applicable.

## Role Assignment Verification

- Status: Verified for the release-performance and trace-evaluation update.
- Identities checked: Foundry project identity, Foundry account identity, and
  public backend managed identity.
- Roles confirmed: repository-scoped ACR pull/reader, Cognitive Services
  OpenAI User, Application Insights and Log Analytics Reader,
  storage-scoped Blob Data Owner for evaluation artifacts, and project-scoped
  Foundry User for the public backend.
- Issues: None. The updated hosted trace messages use the existing telemetry
  export path and require no additional data-plane access.

## 2026-08-06 Release-Performance Update Validation Proof

- `make validate-full` passed after the release-orchestration and trace
  contracts changed, including 45 backend tests, script tests, frontend build,
  and local Playwright E2E.
- `azd provision --preview --no-prompt` completed in 26 seconds without
  mutation. It reports the existing Foundry Application Insights connection and
  PostgreSQL resource-reuse differences, so the release must retain provision
  rather than taking the no-IaC shortcut.
- `scripts/foundry/sync_hosted_source.sh && azd package --no-prompt` passed in
  3 minutes 27 seconds with the approved CFS feed.
- Targeted hosted telemetry tests passed. They prove
  `gen_ai.input.messages` and `gen_ai.output.messages` contain only redacted
  action/status/decision summaries, not applicant input or workflow payloads.
- `make foundry-telemetry` passed against the deployed E2E evidence with 64
  correlated records across both workflow runs. It now validates the actual
  Application Insights dependency-span export shape.

## 2026-08-06 Deployment Completion Evidence

- `azd provision --no-prompt` was a verified no-op immediately before the
  release; no resource configuration changed.
- The public Container Apps use the user-assigned identity
  `azidwhcedyxchnbtm`, whose principal has `AcrPull` on
  `azcrwhcedyxchnbtm`; both registry identity references match that identity.
- Hosted agent `underwriting-hosted` version `40` deployed successfully.
- The backend revision `azcawhcedyxchnbtmpubbe--0000019` and frontend revision
  `azcawhcedyxchnbtmpubfe--0000010` report `Running`.
- Hosted smoke passed with workflow run `run-smoke-20260806204039-292096`.
- Deployed browser E2E passed for
  `run-hosted-happy-20260806204240-294236` and
  `run-hosted-recover-20260806204240-294236`.
- Foundry evaluation `eval_ddc6cba8d07f455fba4ee2f352296780` passed 1 of 1.
- Application Insights telemetry verification passed with 64 correlated
  request/dependency records and zero correlated exceptions.

## 2026-08-06 Direct-Executor Workflow Cutover Validation Proof

- `make validate-full` passed after flattening the underwriting graph: backend
  lint/format, 43 backend tests, frontend lint/build/tests, script tests, and
  local Playwright E2E all completed successfully.
- The new topology regression test proves one master workflow contains the
  four direct check executors and no nested `WorkflowExecutor` wrappers.
- `az bicep build --file infra/foundry-hosted/iac/main.bicep` passed. The
  existing `no-deployments-resources` Bicep warning remains non-blocking.
- `azd provision --preview --no-prompt` passed in 26 seconds without mutation.
  Its Foundry connection and PostgreSQL resource-reuse differences predate
  this backend-only workflow change.
- `azd package --no-prompt` passed in 3 seconds using the approved CFS PyPI
  feed.
- Azure authentication, subscription, environment, Docker build contexts, and
  static least-privilege role assignments were revalidated. The deployment
  uses no IaC, schema, identity, or RBAC change.
- This is a clean graph cutover: checkpoints created by the nested
  version-40 topology are unsupported for resume after deployment. No
  compatibility workflow or fallback will be deployed.

## 2026-08-06 Direct-Executor Deployment Completion Evidence

- `azd provision --no-prompt` was a verified no-op; the existing Container App
  identity retained `AcrPull` on the registry.
- Hosted agent `underwriting-hosted` version `41` deployed from the refreshed
  generated source context. Nested Python bytecode caches are now excluded
  from that context so stale wrapper modules cannot enter the hosted image.
- Public backend revision `azcawhcedyxchnbtmpubbe--0000020` and frontend
  revision `azcawhcedyxchnbtmpubfe--0000011` report `Running`.
- Hosted smoke passed with `run-smoke-20260806214717-357052`.
- Deployed E2E passed for `run-hosted-happy-20260806214836-359053` and
  `run-hosted-recover-20260806214836-359053`.
- Foundry evaluation `eval_286f9bdf2cab4166accb2422a9292e55` passed 1 of 1.
- Application Insights telemetry verification passed with 64 correlated
  request/dependency records and zero correlated exceptions.

## 2026-08-10 Existing-Target Deployment Completion Evidence

- The selected `underwriting-foundry-public` environment passed fresh
  non-secret target, Bicep, live resource, PostgreSQL readiness, and ACR role
  checks. `azd provision --no-prompt` reported no changes.
- The readiness gate was updated for the current Azure CLI
  flexible-server firewall-rule/database show argument contract; it then
  passed before application deployment.
- Hosted agent version `42`, backend revision
  `azcawhcedyxchnbtmpubbe--0000021`, and frontend revision
  `azcawhcedyxchnbtmpubfe--0000012` deployed successfully.
- Hosted smoke passed with `run-smoke-20260810195340-158524`. Deployed E2E
  passed with `run-hosted-happy-20260810195505-160963` and
  `run-hosted-recover-20260810195505-160963`.
- Foundry evaluation `eval_d0e6c3dfb31d44f0bb6b1e3d44cb194f` passed 1 of 1.
  Application Insights telemetry verification returned 64 correlated rows for
  the two E2E runs and zero exceptions.
