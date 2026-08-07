# Order Resolution Azure-Hosted Release Report

**Report date:** 2026-08-07  
**Repository:** `ppenumatsa1/maf-monorepo`  
**Scope:** Path-scoped Azure-hosted app-only CI releases.

## Current status

| Area | Status | Evidence |
| --- | --- | --- |
| IaC reconciliation | Not run | The reviewed preview reports PostgreSQL `Modify`; the safety guard blocks reconciliation. |
| Application deployment | Complete | Existing backend and frontend Container Apps were updated only by immutable ACR image digest. |
| Validation | Complete twice | Runs [31204487857](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31204487857) and [31205554910](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31205554910) passed every required gate. |
| Database safety | Preserved | PostgreSQL and `maf_workflow` were not recreated, reconciled, or mutated. |

## Endpoints and release evidence

| Item | Value |
| --- | --- |
| Backend | [https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io) |
| Frontend | [https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io) |
| Backend image | `sha256:91c6879de9f8f50431f33669605a5476ff3997174a942b309845c6701c56abcf` |
| Frontend image | `sha256:a61ff2249f01d2f49d0c9e0fea42e275e4ad7238722a9cc549ff639e3657e081` |
| Foundry evaluation | `eval_565e438b61934c209250de2516a2acdf` / `evalrun_4497efc4ce6f4ba6aba8c74ce2d66d6b`: 2 passed, 0 failed, 0 errored |
| Telemetry | Fresh exact low- and high-risk pairs: 6 and 5 correlated items, respectively; zero exceptions |

## Release learning timeline

| Run | Elapsed | Outcome | Root cause or confirmation |
| --- | ---: | --- | --- |
| [31200931382](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31200931382) | 7m 25s | Failed | Docker browser runtime lacked `crypto.randomUUID()` at the insecure Compose origin; added the monotonic client-ID fallback. |
| [31201647898](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31201647898) | 6m 23s | Failed | Container App discovery used invalid Azure CLI JMESPath syntax; resolved targets by `azd-service-name` tag. |
| [31202280276](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31202280276) | 11m 19s | Failed | Docker Playwright wrote root-owned bind-mounted results; the later hosted browser test could not clean them. |
| [31203347203](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31203347203) | 12m 47s | Failed | Azure CLI flattened KQL output to dictionaries, while telemetry validation expected REST table-and-row output. |
| [31204487857](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31204487857) | 11m 53s | Passed | First complete app-only release with Docker E2E, deploy, smoke, hosted E2E, Foundry evaluation, and telemetry evidence. |
| [31205554910](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31205554910) | 11m 26s | Passed | Independent repeat of every required release gate after the evidence documentation update. |

The detailed issue and remediation ledger is maintained in
[`azure-hosted/docs/design/issues-changes-fixes.md`](../azure-hosted/docs/design/issues-changes-fixes.md).

## Repeated successful release timeline

Times below are UTC from run `31205554910`; parallel source-validation jobs are
excluded from the app-release critical path.

| Azure phase | Start–end | Elapsed | Result |
| --- | --- | ---: | --- |
| IaC reconciliation | Not invoked | — | PostgreSQL safety boundary preserved |
| Build immutable images | 18:11:52–18:13:51 | 1m 59s | Passed |
| Docker E2E | 18:13:51–18:14:45 | 54s | 7 workflow and 3 selected-thread tests passed |
| App-only deployment | 18:14:45–18:15:37 | 52s | Existing Container Apps updated by digest |
| Validation configuration | 18:15:37–18:16:09 | 32s | Passed |
| Smoke | 18:16:09–18:16:50 | 41s | Passed |
| Hosted workflow E2E | 18:16:51–18:17:58 | 1m 06s | 7 passed |
| Hosted selected-thread E2E | 18:17:59–18:18:02 | 4s | 3 passed |
| Foundry evaluation | 18:18:03–18:19:03 | 1m 00s | 2 passed |
| App Insights correlation | 18:19:03–18:19:31 | 28s | Two exact pairs, zero exceptions |
| **Cloud app-release job** | **18:11:00–18:19:37** | **8m 37s** | **Passed** |
| **End-to-end CI workflow** | **18:08:12–18:19:38** | **11m 26s** | **Passed** |
