# PRD - Customer Order Resolution Demo

## Objective

Deliver a demo-ready, sequential MAF workflow for customer order resolution.

## Core features

- Triage, policy, and resolution stages.
- Local tools and optional MCP integration.
- Deterministic HITL approval, checkpointing, and resume.
- Durable workflow, message, and approval history in PostgreSQL.
- Native SSE timeline with an additive rich stream.
- Optional redacted selected-thread AG-UI and CopilotKit views that cannot
  mutate a workflow or expose raw native rich payloads.
- Configurable telemetry and deterministic evaluation.
- Optional Foundry model inference and report-only evaluation.

## Non-goals

- A second orchestration path.
- Any Foundry application-hosting capability.
- Alternative Foundry application-hosting capability in this Azure-hosted lane.
- PostgreSQL recreation/reset as part of a normal release.
- Production authentication and authorization.

## Acceptance criteria

1. The workflow runs all three stages in order.
2. Low-risk cases complete without HITL.
3. High-risk cases pause and resume after approval or rejection.
4. Native SSE event names remain stable.
5. The evaluation harness reports contract outcomes.
6. Runtime frontend endpoint configuration and disabled CopilotKit inspector
   preserve the same-origin operator boundary.
7. A deployment claim is supported by fresh smoke, hosted E2E, report-only
   evaluation, and telemetry correlation evidence, not source intent.
