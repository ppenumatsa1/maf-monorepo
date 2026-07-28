# Delivery Evidence

## Current status

**Deployed and validated on 2026-07-28.** The Azure-hosted lane was
reprovisioned from this package after the intentional teardown. The backend and
frontend are live at the endpoints recorded in `.azure/deployment-plan.md`.
Fresh smoke, hosted Playwright, Foundry evaluation, and Application Insights
workflow/HITL evidence passed.

## Source-of-truth correction

The delivery record continued to describe the deleted resources as active.
The root cause was preserving successful 2026-07-27 release evidence without a
teardown status transition. The affected deployment plan and README now label
that evidence historical; a new release must replace it with fresh endpoint
and validation evidence.

## Clean-provision recovery (2026-07-28)

The clean Azure preview initially failed with `FlagMustBeSetForRestore` because
the deterministic Foundry account name remained soft-deleted after the
intentional teardown. The deleted account was purged so the clean Bicep plan
could create it again. The subsequent provision created all resources but the
post-provision PostgreSQL grant attempted token authentication before the newly
created Microsoft Entra administrator had propagated. The same grant succeeded
after propagation, confirming a timing issue rather than an identity mismatch.

The post-provision hook now retries the first Entra-authenticated PostgreSQL
connection for a bounded interval before granting the backend managed identity.
Clean release validation must run preview, provision, backend/frontend deploy,
smoke, hosted Playwright, evaluations, and telemetry against the newly assigned
endpoints.

The local `make eval-foundry` target correctly defaults to localhost for
developer use. `make eval-foundry-deployed` now reads only the selected AZD
environment's non-secret `API_URL` and passes it as `FOUNDRY_EVAL_API_URL`,
making the deployed Foundry report a reproducible release gate.

## Validation record

Keep the following evidence current for the deployed environment:

- `make test`
- `make eval-backend`
- `make eval-foundry-deployed`
- `make test-e2e`
- `make docker-test`
- `./scripts/skills/design-review-skill.sh`
- Bicep/AZD, IaC, and Azure readiness validation

Do not retain historical deployment ledgers or references to retired hosting
paths in this document.

## Clean-runner E2E dependency correction (2026-07-28)

GitHub Actions run `30370787270` failed the quick-validation E2E gate even
though the same target passed on a prepared workstation. The job installed
Node.js but did not install either the frontend Vite dependencies or the
Playwright package/browser. Consequently, the local Vite process never opened
its dynamically assigned port and the proxy readiness check failed.

The design-review and quick-validation CI jobs now install the frontend with
`npm ci`; quick validation also installs the Playwright package and Chromium
before running `make validate-quick`. This makes the clean GitHub runner
contract match the documented local E2E target without relying on ignored
`node_modules` directories.
