# Azure App-Hosted Deployment Plan

> **Status: Validated.** The package is validated and was released through the
> app-only cloud lane on 2026-08-07. The evidence ledger records the deployed
> immutable images and completed cloud gates. Infrastructure reconciliation
> remains blocked by the PostgreSQL mutation shown in the provision preview.

## Intended target

| Setting | Source intent |
| --- | --- |
| Resource group | `rg-maf-ora-azure` |
| AZD environment | `maf-ora-azure` |
| Region | North Central US (`northcentralus`) |
| Package | `infra/azure-apphosted/` |
| Application topology | React/Nginx frontend Container App -> same-origin `/api` -> FastAPI/MAF backend Container App |
| Model/evaluation boundary | Foundry model inference and report-only evaluation only |

East US is excluded for this target because of the Azure PostgreSQL offer
restriction. FastAPI is the sole sequential MAF host. Do not add or document an
alternative Foundry application-hosting surface in this Azure-hosted lane.

## Normal release: app-only

Use the existing release path after applicable local gates:

```bash
make release-app
```

It deploys backend/frontend revisions only and then runs
`make release-validate`. It must not call `azd provision`, implicitly
reconcile infrastructure, recreate PostgreSQL, or reset the `maf_workflow`
database. Preserve the approved CFS Python package feed and the frontend
Alpine/musl-compatible image build.

The release validation must capture a fresh `release_run_id`,
`release_started_at`, low/high-risk thread IDs, and workflow run IDs. In the
same evidence window it must pass:

1. HTTPS/frontend/proxied-API health and smoke;
2. `ORD-1001` completion without HITL and `ORD-1009` HITL behavior;
3. hosted Playwright E2E through the frontend proxy;
4. report-only Foundry evaluation; and
5. Application Insights telemetry/HITL correlation for those identifiers.

Record non-secret results and endpoint identities here only after they run.
Local test results, source inspection, historical records, or broad telemetry
lookbacks do not satisfy this evidence requirement.

## Azure validation checklist

All validation checks pass only when the following evidence exists:

1. Azure Developer CLI and Azure authentication resolve the selected
   `maf-ora-azure` environment and its subscription.
2. Release source guards, mocked reconciliation guards, Bicep compilation, and
   static least-privilege role review pass.
3. The subscription-scope IaC preview is reviewed. A preview that reports any
   PostgreSQL mutation blocks reconciliation; it does not block the normal
   app-only image release.
4. The **Required cloud Docker E2E** job builds the exact backend/frontend
   release images, tests them, pushes their immutable ACR digests, and only
   then updates the Container Apps.
5. The same CI job runs fresh smoke, hosted Playwright, report-only Foundry
   evaluation, and exact-pair Application Insights correlation validation.

## Validation proof

| Check | Result |
| --- | --- |
| Azure CLI/AZD authentication and selected environment | Passed locally on 2026-08-07 |
| Release source guards and mocked reconciliation boundary | Passed locally on 2026-08-07 |
| Bicep compilation | Passed locally on 2026-08-07 |
| Subscription-scope provision preview | Completed on 2026-08-07; it reports PostgreSQL `Modify`, so infrastructure reconciliation is blocked |
| Static role review | Passed: app identities retain ACR pull and Foundry data-plane roles; the CI identity has scoped app deployment, ACR push, and Foundry evaluation roles |
| Required cloud Docker E2E and release evidence | Passed in GitHub Actions run `31204487857` on 2026-08-07 |

## Exceptional infrastructure reconciliation

An infrastructure change is review-required, not an automatic full release.
Before even previewing reconciliation, obtain explicit non-secret approval:

```bash
INFRA_RECONCILIATION_APPROVED=true \
INFRA_RECONCILIATION_REFERENCE="<approved-pr-or-work-item>" \
make release-infra-preview
```

Review the Bicep/AZD preview and retained-resource boundary. Apply only under
the additional explicit reconciliation authorization:

```bash
INFRA_RECONCILIATION_APPROVED=true \
INFRA_RECONCILIATION_APPLY=true \
INFRA_RECONCILIATION_REFERENCE="<approved-pr-or-work-item>" \
make release-infra-reconcile
```

The reconciliation guard must find exactly the pre-existing PostgreSQL server
and verify its identity after the operation. It never creates, replaces,
drops, or rebuilds the server or `maf_workflow` database.

## Evidence ledger

Add a dated entry only after a release has completed. Include:

- AZD environment/resource group and non-secret frontend/backend endpoints;
- revision/image identifiers when available;
- release/thread/workflow-run correlation IDs;
- smoke, hosted E2E, report-only evaluation, and telemetry results;
- exceptions or blockers, including an unresolved Docker E2E TLS
  trust/handshake failure if one actually occurred.

### 2026-08-07 app-only cloud release

- **GitHub Actions:** [run `31204487857`](https://github.com/ppenumatsa1/maf-monorepo/actions/runs/31204487857), release ID `ci-31204487857-1`.
- **Endpoints:** backend [https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-backend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io) and frontend [https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io](https://maf-frontend-puzsry.greensky-96a4c481.northcentralus.azurecontainerapps.io).
- **Immutable images:** backend `sha256:91c6879de9f8f50431f33669605a5476ff3997174a942b309845c6701c56abcf`; frontend `sha256:a61ff2249f01d2f49d0c9e0fea42e275e4ad7238722a9cc549ff639e3657e081`.
- **Gates:** Docker E2E, smoke, hosted workflow and selected-thread browser E2E, and report-only Foundry evaluation all passed. Foundry evaluation `eval_565e438b61934c209250de2516a2acdf` / `evalrun_4497efc4ce6f4ba6aba8c74ce2d66d6b` passed both cases.
- **Telemetry:** exact fresh pairs for low- and high-risk smoke threads recorded 6 and 5 telemetry items respectively, with zero exceptions; their App Insights correlation evidence is validated.
- **Infrastructure:** no reconciliation ran; PostgreSQL and the `maf_workflow` database were not changed.
