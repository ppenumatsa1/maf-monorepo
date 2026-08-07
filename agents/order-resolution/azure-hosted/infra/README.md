# Infrastructure

`azure-apphosted/` is the single Azure package for the React frontend, FastAPI
MAF backend, PostgreSQL, observability, ACR, and Foundry model and report-only
evaluation resources.

The backend Container App is the only MAF application host. The planned target
is `rg-maf-ora-azure` in North Central US; no deployment is claimed.

Routine release scope is backend/frontend revisions only. The package must
retain the existing PostgreSQL server and `maf_workflow` database. Bicep
reconciliation is a separately reviewed exception with an explicit non-secret
approval reference and preview; changed infrastructure files never authorize
an implicit provision or database recreation.
