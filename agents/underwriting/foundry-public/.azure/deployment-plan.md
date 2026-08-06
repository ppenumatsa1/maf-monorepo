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

1. Validate local source, Bicep, script syntax, AZD environment, identity, and
   resource prerequisites.
2. Build the Bicep template and provision approved resource configuration.
3. Apply PostgreSQL schema and rotate/provision the least-privilege runtime
   credential using local authenticated secrets.
4. Validate PostgreSQL TLS, authentication, firewall, and hosted runtime
   readiness.
5. Deploy the hosted Foundry agent, public backend, and public frontend.
6. Execute hosted smoke, browser E2E, report-only Foundry trace evaluation,
   and Application Insights correlation verification.
7. Record dated evidence, run identifiers, evaluation results, and telemetry
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
