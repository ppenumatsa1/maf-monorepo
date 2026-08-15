# Infrastructure Scaffolding

This directory contains deployment scaffolding for the retained private Foundry
hosted lane.

- `foundry-hosted/`: Active private-VNet Foundry-hosted runtime path (`WORKFLOW_MODE=foundry_hosted`).

This lane remains additive to local Docker/Make workflows.
Private release automation is serialized on `order-resolution-private-release`
and executes only from the retained `foundry-private-v2` runner. See
[`foundry-hosted/README.md`](foundry-hosted/README.md) for the mandatory clean
release sequence, generated-proof-gated PostgreSQL lockdown, and the
management-plane recovery path for a deleted private runner.
