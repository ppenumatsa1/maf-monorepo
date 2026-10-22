# Azure-Hosted Deployment Contract

## Profile model

Operational target values belong in a validated, ignored operator profile.
The default path is `.azure/azure-hosted.env`; `AZURE_HOSTED_PROFILE` may select
another ignored regular file. Tracked files under `deployment/profiles/` are
examples only and are not a safe place for live tenant, subscription, user,
resource, endpoint, credential, connection string, image, or operator-network
values.

`profile.sh` parses profile files as data and rejects unsupported keys, shell
syntax, duplicate declarations, invalid identifiers, and symlinks.

## Lifecycle ownership

- Fresh bootstrap creates a new profile-selected target.
- Steady-state reconciliation is explicit and preserves retained PostgreSQL.
- Routine release is app-only and changes backend/frontend revisions.

## Generated release bundle

Each release writes one ignored directory:

```text
.artifacts/releases/<release-id>/
  release.json
  evidence/
    release-context.json
    source-validation.json
    infrastructure.json        # explicit infrastructure actions only
    images.json
    deployment.json
    smoke.json
    domain-e2e.json
    telemetry.json
    evaluation.json
    release-evidence.json
  logs/
    browser-e2e.log
    ...
```

Successful final evidence requires deployment verification, smoke, browser and
three domain scenarios, exact telemetry correlation, completed report-only
evaluation with zero failed/errored rows, and compliance with the
app-only-to-telemetry budget.
