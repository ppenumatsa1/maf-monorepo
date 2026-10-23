# Underwriting Agent

The underwriting agent currently has one deployment lane:

| Variant | Path | Description |
| --- | --- | --- |
| Foundry public | [foundry-public](foundry-public/README.md) | Public Foundry-hosted MAF underwriting workflow with durable web operations and referral-only Shared Teams review |

## Start Here

1. Underwriting lane entrypoint: [foundry-public/README.md](foundry-public/README.md)
2. Functional specification: [foundry-public/docs/design/functional-spec.md](foundry-public/docs/design/functional-spec.md)
3. Business and HITL rules: [foundry-public/docs/design/business-rules.md](foundry-public/docs/design/business-rules.md)
4. Architecture: [foundry-public/docs/design/architecture.md](foundry-public/docs/design/architecture.md)
5. Deployment and Teams operations: [foundry-public/docs/design/deployment-flow.md](foundry-public/docs/design/deployment-flow.md)
6. Documentation index: [foundry-public/docs/README.md](foundry-public/docs/README.md)

The application was imported from
[`ppenumatsa1/maf-underwriting-agent`](https://github.com/ppenumatsa1/maf-underwriting-agent)
at revision `816993969cd16c208a998441582dc4fedebc6b44`.

Track release evidence, incidents, research, and remediations in the
[project delivery ledger](foundry-public/docs/design/issues-changes-fixes.md).

The project README and design documents do not claim that an Azure deployment
or Teams publication is currently live. Exact target and release evidence
belongs in the project deployment plan and dated project ledger.

## Current Release Status

**Pending as of 2026-10-23.** Release `uw-public-20261023210604` was intentionally
stopped during pre-deployment validation and did not build or deploy a new
hosted-agent version. The evaluation-compatible trace-message fix is committed
on `main` at `e06bc71`.

When work resumes, start a fresh immutable release and rerun smoke, deployed web
E2E, strict trace evaluation, deployment verification, and rollback
verification. Native Teams approval and decline remain manual acceptance steps;
strict telemetry correlation and final evidence follow those actions.
