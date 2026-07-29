# Order Resolution Deployment Report

**Report date:** 2026-07-29
**Repository:** `ppenumatsa1/maf-monorepo`
**Scope:** Current source-controlled Order Resolution release gates.

## Overall status

| Lane | Status | Current evidence |
| --- | --- | --- |
| Local | Complete | Parallel lane validation is source controlled; Foundry-private local scope is `make test` and now passes **122 tests**. Private local hosted E2E/evaluation remains intentionally deferred. |
| Azure-hosted | Complete | Fresh deployment, smoke, 7/7 hosted Playwright scenarios, Foundry evaluation (2 passed, 0 failed, 0 errored), and 32 telemetry workflow/HITL dependency spans passed. |
| Foundry-public | Complete | Infrastructure/application deployment, hosted agent version 14, 7/7 browser E2E scenarios, hosted Responses E2E, evaluation (2 passed, 0 failed, 0 errored), and 51 correlated telemetry rows passed. |
| Foundry-private | Complete | Protected release [`30493060929`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/30493060929) completed deployment, connectivity proof, PostgreSQL lockdown, hosted E2E, telemetry, and enforced exact-trace evaluation. |

## Foundry-private release evidence

| Gate | Result |
| --- | --- |
| Source commit | `e64b1ff` |
| Resource group / runner | `rg-maf-ora-foundry-v2` / `foundry-private-v2` |
| Hosted agent / image | `order-resolution-hosted` version 23 / `mafprv0722v3acr4aiw7fw5gjdo4.azurecr.io/order-resolution-hosted:e64b1ffc6dbc-20260729214300` |
| Connectivity and lockdown | Fresh ACA/hosted-agent PostgreSQL proof completed before explicitly confirmed lockdown. |
| Hosted E2E | Three fresh low-risk, high-risk approval/resume, and damaged-item approval/resume conversations passed. |
| Telemetry | 69 correlated Application Insights rows, four eligible `invoke_agent` spans, three covered conversations, zero exceptions. |
| Foundry evaluation | `eval_cf1bb4a15cb34dcf8566d3df7fb1ee60` / `evalrun_323d7b1092f64d0ba061e6ab5ac93af4`: 3 total, 3 passed, 0 failed, 0 errored. |

## Private issues closed

| Issue | Root cause | Source-controlled fix |
| --- | --- | --- |
| Evaluation selected no useful traces | Preview conversation selection and bare agent identity were not the documented trace-evaluation contract. | Emit platform `name:version` identity; select one eligible Application Insights `operation_Id` per E2E conversation. |
| Telemetry evidence query failed intermittently | Azure CLI query behavior obscured KQL diagnostics. | Use declared `azure-monitor-query` `LogsQueryClient`, with bounded fail-closed retries. |
| Exact-trace IDs were wrong | KQL `arg_max` alias persisted timestamps rather than `operation_Id`. | Select the latest row, then explicitly project `operation_Id`. |
| Evaluator rejected trace content | Marked messages used a legacy direct `content` field. | Emit GenAI message `parts` with typed text content, only for explicitly marked private E2E requests. |
| Runner became unavailable | The existing private runner VM was deallocated after an earlier evidence cancellation. | Add a protected runner-start workflow that starts only the existing VM via the environment OIDC identity; the following protected release proves runner registration. |

The authoritative detailed private RCA ledger is
[`issues-changes-fixes.md`](../agents/order-resolution/foundry-private/docs/design/issues-changes-fixes.md).

## Reproducibility and control posture

- Private provisioning and release remain serialized on
  `order-resolution-private-release`.
- The private lane runs only from the VNet-connected
  `foundry-private-v2` runner.
- PostgreSQL lockdown requires fresh connectivity proof and explicit workflow
  confirmation.
- No ad-hoc RBAC, OIDC, secret, firewall, public-access, or network
  configuration was used for this closure. The runner-start workflow does not
  use VM Run Command, VM extensions, or runner-administration credentials.
