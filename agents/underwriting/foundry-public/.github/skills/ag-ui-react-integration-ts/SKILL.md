---
name: ag-ui-react-integration-ts
description: Implement and review React TypeScript consumers for AG-UI-compatible workflow streaming, including run lifecycle rendering, checkpoint visibility, resume UX, and failure states.
---

# AG-UI React Integration (Underwriting)

Use this skill when changing frontend streaming consumption or UI behavior tied to workflow events.

## Official supporting skills

- Use `typescript-setup` for TypeScript project and tsconfig baseline decisions.
- Use `typescript-update` when upgrading TypeScript versions or addressing new compiler diagnostics.
- Keep AG-UI runtime behavior guidance in this skill; official TypeScript skills are supporting references.

## Scope

- Frontend stream/event consumption in `frontend/src/*`
- Run lifecycle UI and history panels
- Resume, retry, and checkpoint visibility behavior

## Guardrails

- Keep UI state derived from backend stream events and persisted run-history APIs.
- Do not infer hidden workflow state in client-only logic.
- Surface run ids, checkpoint ids, and terminal status clearly for operator verification.
- Handle malformed or non-JSON responses as explicit user-visible errors.

## Required verification

1. Validate `frontend/tests/e2e/underwriting.spec.ts` rubric scenarios.
2. Validate `frontend/src/components/RunHistoryPanel.tsx` and related stream consumers for contract alignment.
3. Update `docs/design/e2e-rubric.md` when UI validation expectations change.
