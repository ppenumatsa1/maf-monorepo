# Infrastructure

`azure-apphosted/` is the single Azure package for the React frontend, FastAPI
MAF backend, PostgreSQL, observability, ACR, and Foundry model and report-only
evaluation resources.

The backend Container App is the only MAF application host. The planned target
is subscription `7df95e88-701c-4693-af77-3159f83b558d`,
`rg-maf-ora-azure`, in North Central US; no deployment is claimed.

Routine release scope is backend/frontend revisions only. The package must
retain the existing PostgreSQL server and `maf_workflow` database. Bicep
reconciliation is an explicit exception: invoking its validated workflow is
execution intent, and it obtains a fresh what-if that must prove PostgreSQL is
excluded from steady-state deployment before apply. Changed infrastructure files never authorize an
implicit provision or database recreation, and no separate approval/reference
or caller-supplied digest is required.

Target selection is owned by `deployment/profiles/azure-hosted.env`. Routine
release proof is written under `.artifacts/releases/<release-id>/evidence/`
with logs in the sibling `logs/` directory. Infrastructure evidence is emitted
only for an explicitly requested preview or reconciliation.
