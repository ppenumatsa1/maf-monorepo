# Azure-hosted release artifact contracts

Tracked contracts live in `deployment/contracts/`. Generated evidence lives under
`.artifacts/releases/<release-id>/`. New tooling does not mirror releases into
the legacy singular `.artifacts/release/` path.

## Common envelope

All canonical release artifacts use the same envelope:

- `schema_version = 1`
- `evidence_type` in kebab-case
- `lane = azure-hosted`
- `status`
- `release_id`
- `release_started_at`
- `generated_at`
- `target`
- `checks`
- `extensions`

`artifact_type` remains an underscore alias for backward compatibility.

Schema: `azure-hosted-release-artifact-envelope.schema.json`

## Canonical files

- `release.json` (sanitized canonical authority record)
- `evidence/release-context.json`
- `evidence/source-validation.json`
- `evidence/infrastructure.json` (explicit infrastructure actions only)
- `evidence/images.json`
- `evidence/deployment.json`
- `evidence/smoke.json`
- `evidence/domain-e2e.json`
- `evidence/evaluation.json`
- `evidence/telemetry.json`
- `evidence/release-evidence.json`
- `logs/` (including `browser-e2e.log`)

## Secret-free rules

Contracts and generated artifacts must stay secret-free:

- never record secrets, tokens, passwords, connection strings, SAS values, or
  basic-auth URLs
- keep target metadata to non-secret routing/deployment identifiers
- put only relative release-local log paths in `checks[*].log`

The schema enforces the envelope shape and blocks common secret-like keys and
values. Focused contract tests also validate representative good/bad payloads
and the generated release context.
