---
name: docs-sync
description: Keep repository documentation synchronized with focused code and IaC changes while preserving contracts.
---

# Docs Sync Skill

Use this skill when a change touches code, infrastructure as code, scripts, examples, or behavior that may affect repository documentation.

## Guardrails

- Review only the code, IaC, scripts, examples, and docs affected by the current change.
- Keep changes surgical and simplicity-first; do not rewrite unaffected documentation.
- Preserve documented API, event, HITL, validation, and deployment contracts unless the task explicitly changes them.
- Separate source intent from deployed evidence. Do not copy historical
  deployment, endpoint, telemetry, or evaluation claims into a new change.
- For Azure app-hosted release documentation, preserve FastAPI as the sole MAF
  host, Foundry as inference/report-only evaluation, app-only normal releases,
  explicit reconciliation, PostgreSQL preservation, and fresh evidence
  requirements.
- When selected-thread surfaces change, update the native `/rich` distinction,
  redaction boundary, existing-thread selector behavior, runtime endpoint
  configuration, and disabled-inspector guidance together.
- Update only docs whose instructions, examples, diagrams, or behavior descriptions would become stale.
- Do not introduce new validation tooling or broad documentation structure changes.

## Required execution

1. Identify changed code/IaC/scripts/examples and map them to affected docs.
2. Update the smallest relevant documentation sections.
3. Preserve stable contracts called out in repository guidance and update required contract docs when behavior intentionally changes.
4. Run existing relevant checks only when documentation affects runnable scripts, commands, examples, or generated artifacts.

## Reporting

- List docs updated and the code/IaC change each update follows.
- If no docs needed changes, state why.
- Report any checks run, skipped checks, and blockers.
