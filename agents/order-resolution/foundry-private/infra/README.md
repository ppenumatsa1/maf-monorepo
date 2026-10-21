# Infrastructure Scaffolding

This directory contains deployment scaffolding for the retained private Foundry
hosted lane.

- `foundry-hosted/`: Active private-VNet Foundry-hosted runtime path. The
  shared workflow remains `WORKFLOW_MODE=maf_sdk`; the internal web wrapper
  uses `RUNTIME_TARGET=responses_wrapper`.

This lane remains additive to local Docker/Make workflows.
Private release automation is serialized on `order-resolution-private-release`
and executes only from the retained `foundry-private-ora` runner. See
[`foundry-hosted/README.md`](foundry-hosted/README.md) for the mandatory clean
release sequence, private-only PostgreSQL readiness contract, and the
management-plane recovery path for a deleted private runner. The operator and
customer-demo sequence is in
[`../docs/customer-demo-runbook.md`](../docs/customer-demo-runbook.md).
