# Azure-hosted deployment contract

This directory is retained as `legacy_pending_cutover` compatibility while
the canonical secret-free target is
`agents/order-resolution/deployment/profiles/azure-hosted.env`.

## Tracked inputs

- `profile.sh` parses legacy compatibility profiles as data.
- `profiles/azure-hosted.env` is a compatibility copy, not target authority.
- `profiles/azure-hosted-bootstrap.env` is the bootstrap compatibility target.
- `contracts/` defines the secret-free release evidence envelope.

Profiles contain only target-selection values. Credentials, connection strings,
operator IPs, image references, generated resource IDs, and endpoints remain
outside tracked profiles.

## Generated release bundle

Each release writes one gitignored directory:

```text
.artifacts/releases/<release-id>/
  release.json
  evidence/
    release-context.json
    source-validation.json
    infrastructure.json        # only for an explicit infrastructure action
    images.json
    deployment.json
    smoke.json
    domain-e2e.json
    evaluation.json
    telemetry.json
    release-evidence.json
  logs/
    browser-e2e.log
    ...
```

`release-evidence.json` is written on both successful and failed validation
paths. A successful release requires deployment verification, three deployed
domain scenarios, a completed evaluation with no failed or errored rows,
exact-pair telemetry correlation, and zero relevant exceptions.

Infrastructure remains separate from routine release execution:

- `make release-app` deploys backend/frontend revisions only.
- `make release-infra-preview` is non-mutating.
- `make release-infra-reconcile` is an explicit guarded action and rejects
  PostgreSQL mutation in `steadyState`.
