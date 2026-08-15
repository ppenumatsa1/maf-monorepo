# Azure Deployment Plan

> **Status:** Validated

## 1. Project overview

**Goal:** Make Underwriting Foundry public infrastructure reusable across Azure
subscriptions and environments without per-subscription IaC forks.

**Path:** Modernize existing AZD + Bicep infrastructure. This work prepares
infrastructure only; it does not authorize a deployment.

## 2. Target context

| Attribute | Value |
| --- | --- |
| Classification | POC / Development |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-maf-underwriting` |
| Location | `eastus2` |
| Deployment tool | AZD + Bicep |

`Microsoft.App`, `Microsoft.CognitiveServices`, `Microsoft.DBforPostgreSQL`,
`Microsoft.ContainerRegistry`, `Microsoft.Insights`, and
`Microsoft.OperationalInsights` are registered in the target subscription.
The authorized target resource group was created in East US 2 solely for
validation.

## 3. Architecture and contract

The parameterized Bicep template supports two mutually explicit modes:

| Mode | Behavior |
| --- | --- |
| `bootstrap` | Creates the Foundry account/project and `gpt-4.1-mini` Global Standard model deployment, ACR, Log Analytics, Application Insights, Container Apps environment/apps, managed identities, PostgreSQL, evaluation storage, connections, and role assignments. |
| `reuse` | References a fully existing environment and creates no resources or role assignments. |

The normal release remains app-only. Bootstrap uses temporary Container Apps
images, then the existing backend/frontend release scripts replace them with
the lane images. PostgreSQL runtime credentials and schema remain explicit
post-provision steps.

## 4. Files changed

| Area | Change |
| --- | --- |
| `agents/underwriting/foundry-public/infra/foundry-hosted/iac` | Parameterized bootstrap/reuse Bicep, generated ARM template, and AZD parameter mapping. |
| `agents/underwriting/foundry-public/scripts/foundry` | Bootstrap profile preparation, post-provision hydration, and explicit ACR repository/target-port handling. |
| `agents/underwriting/foundry-public/deployment` | Non-secret bootstrap profile template and operator documentation. |
| `agents/underwriting/foundry-public/docs/design` | Bootstrap versus app-only release operating model. |
| `agents/underwriting/foundry-public/scripts/foundry/tests` | Bootstrap AZD-contract test. |

## 5. Verification evidence

| Check | Result |
| --- | --- |
| `make test-deployment-profile` | Pass |
| `make test-scripts` | Pass: 3 PostgreSQL credential tests and bootstrap contract test |
| `make foundry-iac-build` | Pass |
| `git diff --check` | Pass |
| Target provider registration | Pass |
| Bootstrap preview | Pass after correcting generated resource-name limits; proposes 12 lane resources and applies none. |
| Reuse preview | Pass; skips all 10 existing resources and applies none. |

## 6. All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not an Aspire project)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not an Aspire project)

## 7. Validation proof

`rg-maf-underwriting` was created in the authorized subscription and location.
The bootstrap AZD environment generated a successful preview for Container
Apps, Foundry account/project/model, ACR, PostgreSQL, monitoring, and storage;
it made no changes. The explicit reuse preview against the original
environment skipped every existing resource and made no changes.

The first preview rejected overlength generated Container App and storage
names. Bootstrap derivation was corrected to reserve suffix capacity, then the
preview passed. After Azure CLI device authentication for tenant
`a679d99f-b8f5-4d50-843e-5b73405ce0fc`, `azd auth login --check-status` and
`azd package --no-prompt` passed. The package output is a local image tag only;
no image was pushed.

The target subscription policy assignments are Defender/Security Center
assignments (`DataProtectionSecurityCenter`,
`SqlVmAndArcSqlServersProtection`, and
`OpenSourceRelationalDatabasesProtectionSecurityCenter`); none blocks the
previewed resource types.

## 8. Role assignment verification

**Status:** Verified statically.

- Backend and frontend user-assigned identities receive `AcrPull` only at the
  ACR scope.
- The Foundry project receives ACR pull/repository-reader, Azure OpenAI User,
  and monitoring-reader permissions only at the relevant resource scopes.
- The backend identity receives Foundry User only at the Foundry project.
- The Foundry account/project identities receive Storage Blob Data Owner only
  at the dedicated evaluation-storage account. This is required for evaluation
  artifact write operations and is not assigned at resource-group or
  subscription scope.
- `reuse` declares no role assignments.

## 9. Delivery handoff

Validation is complete. Invoking the validated deployment workflow begins
bootstrap deployment; no separate manual approval checkpoint is required.

## 10. Guardrails

- Do not commit secrets, connection strings, resource IDs, image tags, or
  subscription-specific infrastructure forks.
- Do not bypass the validated deployment workflow or its runtime verification
  gates.
- Preserve the public lane's app-only release boundary.
- Roll this validated contract to Order Resolution only after Underwriting has
  passed the Azure preview and validation gates.
