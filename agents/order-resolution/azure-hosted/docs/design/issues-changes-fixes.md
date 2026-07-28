# Delivery Evidence

## Current status

**Not currently deployed.** The Azure-hosted resources were intentionally
deleted on 2026-07-28. The prior release evidence in
`.azure/deployment-plan.md` is historical only and cannot be used to claim a
current deployment. A fresh provision, deployment, smoke, hosted Playwright,
evaluation, and Application Insights HITL-correlation run is required.

## Source-of-truth correction

The delivery record continued to describe the deleted resources as active.
The root cause was preserving successful 2026-07-27 release evidence without a
teardown status transition. The affected deployment plan and README now label
that evidence historical; a new release must replace it with fresh endpoint
and validation evidence.

## Validation record

Keep the following evidence current for the deployed environment:

- `make test`
- `make eval-backend`
- `make test-e2e`
- `make docker-test`
- `./scripts/skills/design-review-skill.sh`
- Bicep/AZD, IaC, and Azure readiness validation

Do not retain historical deployment ledgers or references to retired hosting
paths in this document.
