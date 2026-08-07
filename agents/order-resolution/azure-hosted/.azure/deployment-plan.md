# Azure App-Hosted Deployment Plan

> **Status: Validated.** The package is validated for an app-only cloud release;
> no current deployment evidence is claimed.
> Repository code, Bicep, and local validation describe intended behavior. They
> are not evidence of a live endpoint, revision, model invocation, evaluation,
> or telemetry result.

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
| Required cloud Docker E2E and release evidence | Pending the path-scoped CI run |

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

There is no new ledger entry in this documentation sync because no deployment,
hosted smoke, hosted E2E, evaluation, or telemetry query was performed.
