# Agents guide

## Recommended agent responsibilities

1. **Workflow/MAF agent**
   - Modify parent/child workflow edges and executor message contracts.
   - Keep checkpoint/resume behavior intact.
2. **Persistence agent**
   - Modify repository, SQLAlchemy schema, and checkpoint storage internals.
3. **Frontend agent**
   - UI controls, API client, and state/event/checkpoint rendering.
4. **E2E quality agent**
   - Maintain Playwright tests and rubric alignment with required use cases.
5. **Docs/design agent**
   - Keep docs and instructions synchronized with implemented behavior.

## Coordination rules

- Prefer additive changes over broad refactors.
- Avoid changing API payload shapes without updating frontend + E2E + docs.
- Any workflow behavior change should include event/state visibility updates.
