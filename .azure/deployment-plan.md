# Azure Deployment Plan

> **Status:** Deployed

Generated: 2026-08-04T15:41:18-05:00

---

## 1. Project Overview

**Goal:** Improve underwriting Foundry trace hierarchy, suppress public API
health-check telemetry noise, enable managed-identity Azure OpenAI rationale
generation, and release the change to the existing underwriting environment.

**Path:** Modernize Existing

## 2. Requirements

| Attribute | Value |
|---|---|
| Classification | POC / Development |
| Scale | Small |
| Budget | Cost-optimized; reuse existing resources |
| **Subscription** | `4f18d577-3506-4a11-85e5-a83b14727a84` (`ME-MngEnvMCAP328033-ppenumatsa-1`) |
| **Location** | `eastus2` |

The user authorized implementation and deployment to the existing resource
group `rg-underwriting-readiness-0731` on 2026-08-04.

## 3. Components Detected

| Component | Type | Technology | Path |
|---|---|---|---|
| Foundry Responses host | Hosted agent | Python, Agent Framework, OpenTelemetry | `agents/underwriting/foundry-public/backend/foundry` |
| Underwriting workflow | Worker | Python, Agent Framework, PostgreSQL checkpoints | `agents/underwriting/foundry-public/backend/app/maf` |
| Public API | API | FastAPI | `agents/underwriting/foundry-public/backend/app/server.py` |
| Public frontend | Frontend | React / Vite | `agents/underwriting/foundry-public/frontend` |
| Deployment definition | IaC | Bicep + azd | `agents/underwriting/foundry-public/infra/foundry-hosted` |

## 4. Recipe Selection

**Selected:** AZD + Bicep resource reuse

**Rationale:** The existing Foundry project, ACR, PostgreSQL server, Container
Apps, Application Insights, and Log Analytics workspace are intentionally
reused. Bicep manages required identity/connection wiring; the existing
container deployment script registers a new immutable hosted-agent version.

## 5. Architecture

**Stack:** Hosted agent container and existing Container Apps

| Component | Azure Service | SKU |
|---|---|---|
| `underwriting-hosted` | Foundry hosted agent | Existing project runtime |
| Public backend / frontend | Azure Container Apps | Existing environment |
| Workflow state and checkpoints | PostgreSQL Flexible Server | Existing server |
| Agent image | Azure Container Registry | Existing registry |
| Traces / logs | Application Insights + Log Analytics | Existing workspace |

## 6. Provisioning Limit Checklist

No new durable compute, network, or data resources are planned. The release
creates one immutable agent version in the existing Foundry project and
reconciles existing-resource role assignments/connections.

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---|---:|---:|---:|---|
| `Microsoft.App/managedEnvironments` | 0 | 2 | 50 | `azure-quotas` CLI: East US 2 `ManagedEnvironmentCount`, 2 used, 48 available. |
| Foundry hosted-agent version | 1 | Existing agent plus one version | Existing project service capacity | No new Azure resource quota is consumed; deployment targets existing project `azprwhcedyxchnbtm`. |
| Storage / network / database resources | 0 | Unchanged | Not applicable | Existing evaluation storage and PostgreSQL resources are reused. |

**Status:** ✅ All required capacity is available for this release.

## 7. Execution Checklist

### Phase 1: Planning

- [x] Analyze workspace and existing deployment
- [x] Resolve active subscription and resource-group location
- [x] Check capacity with `azure-quotas`
- [x] Select AZD + Bicep resource-reuse recipe
- [x] User approved implementation and release

### Phase 2: Execution

- [x] Add hosted-agent telemetry bootstrap and business-stage spans
- [x] Suppress `/health` logs and spans in the public API
- [x] Enable managed-identity Azure OpenAI client and its RBAC
- [x] Add targeted tests and update operational documentation
- [x] Update status to **Ready for Validation**

### Phase 3: Validation

- [x] Invoke `azure-validate`
- [x] Bicep build and deployment preview pass
- [x] Local quality and browser E2E pass
- [x] Record validation proof and update status to **Validated**

### Phase 4: Deployment

- [x] Invoke `azure-deploy`
- [x] Deploy IaC and a new hosted-agent version
- [x] Run smoke, trace evaluation, and Application Insights correlation query
- [x] Update status to **Deployed**

## 8. Validation Proof

| Check | Command Run | Result | Timestamp |
|---|---|---|---|
| Dependency and script checks | `make install && bash -n scripts/foundry/*.sh` | ✅ Pass | 2026-08-04 |
| Static source validation | `make quality` and targeted backend rerun | ✅ Pass: backend lint, format, 11 tests, frontend lint/build | 2026-08-04 |
| Browser E2E | `make test-e2e` | ✅ Pass: happy path, retry, crash/resume rubric | 2026-08-04 |
| IaC compilation | `az bicep build --file infra/foundry-hosted/iac/main.bicep` | ✅ Pass; existing nested-deployment lint warning retained | 2026-08-04 |
| IaC preview | `AZURE_ENV_NAME=underwriting-foundry-public azd provision --preview --no-prompt` | ✅ Pass: existing-resource reuse only; Application Insights connection reconciliation | 2026-08-04 |
| RBAC review | Reviewed `infra/foundry-hosted/iac/main.bicep` | ✅ Least privilege: ACR pull, Log Analytics Reader, Storage Blob Data Owner, and Cognitive Services OpenAI User for the project; deployment script grants the runtime identity its OpenAI User role after it exists | 2026-08-04 |

**Validated by:** azure-validate skill  
**Validation timestamp:** 2026-08-04

## 9. Files to Generate or Update

| File | Purpose | Status |
|---|---|---|
| `.azure/deployment-plan.md` | Release plan and validation proof | Complete |
| `backend/app/core/telemetry.py` | Hosted-agent telemetry setup and safe span helpers | Complete |
| `backend/app/maf/**` | Workflow, executor, retry, and resume span boundaries | Complete |
| `backend/foundry/main.py` | Foundry Responses root invocation span | Complete |
| `backend/app/core/observability.py` | Health telemetry exclusion | Complete |
| `backend/app/infrastructure/llm/foundry_client.py` | Managed-identity model authentication | Complete |
| `infra/foundry-hosted/*` | Identity RBAC and hosted runtime configuration | Complete |
| `README.md`, `issues-fixes.md` | Deployment and RCA evidence | Complete |

## 10. Next Steps

1. Keep native batch evaluator generation blocked until the organization policy
   permits the required evaluation-storage network route or a private
   evaluation design is available.

## 11. Deployment Evidence

| Gate | Result |
|---|---|
| Hosted agent | `underwriting-hosted` version `23` active |
| Public backend | Revision `azcawhcedyxchnbtmpubbe--0000005`, 100% traffic, healthy |
| Smoke | Conversation `conv_8455edced675843c00PVE7HeQz4fx1G743M2tFnSRITfKa8A7C`; trace `1ea0a48c71bffdbf9cb752ec840fe2d9`; workflow `run-fb20c35df9`; `APPROVED` |
| Browser E2E | Happy path, retry, and crash/resume rubric passed |
| Foundry trace evaluation | `eval_0d4c41bf31bc4455a2040869b93c3950` / `evalrun_13c9fa04a67b46dcad80c4c768c785d7`: 1/1 passed |
| App Insights | Correlated Responses, workflow initialization, risk, credit, medical, driving, fan-in, final-decision, completion, and a semantic OpenAI `chat` span captured |
| Health noise | Direct post-cutover `traces` and `dependencies` queries return zero `/health` records |
