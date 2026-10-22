# Azure-Hosted Release Artifact Contracts

Tracked schemas live in `deployment/contracts/`. Generated artifacts live
under `.artifacts/releases/<release-id>/`.

## Common envelope

Canonical artifacts use:

- `schema_version = 1`
- kebab-case `evidence_type`
- `lane = azure-hosted`
- `status`
- `release_id`
- `release_started_at`
- `generated_at`
- `target`
- `checks`
- `extensions`

`artifact_type` remains a compatibility alias where existing consumers require
it.

## Canonical files

- `release.json`
- `evidence/release-context.json`
- `evidence/source-validation.json`
- `evidence/infrastructure.json` for explicit infrastructure actions
- `evidence/images.json`
- `evidence/deployment.json`
- `evidence/smoke.json`
- `evidence/domain-e2e.json`
- `evidence/telemetry.json`
- `evidence/evaluation.json`
- `evidence/release-evidence.json`
- `logs/`

## Secret-free and portability rules

- Never record secrets, tokens, passwords, connection strings, SAS values,
  customer data, or basic-auth URLs.
- Do not copy concrete target identifiers or endpoints into tracked docs.
- Generated evidence may contain the minimum non-secret target identity needed
  for release verification and must remain ignored.
- Store only relative release-local log paths in evidence.
- Failed validation must still write final failed evidence.
- FastAPI topology fields must reject hosted-agent/Responses and Teams runtime
  metadata.
