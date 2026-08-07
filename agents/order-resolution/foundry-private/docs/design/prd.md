# PRD - Customer Order Resolution Multi-Agent Demo

## Objective

Build a demo-ready multi-agent orchestration using Microsoft Agent Framework-aligned patterns with sequential workflow execution and production-style capabilities.

## Core Features

- Sequential multi-agent orchestration (triage -> policy -> resolution).
- Tools integration (local deterministic tools).
- MCP integration (remote when configured, local fallback otherwise).
- Human-in-the-loop (HITL) approval before sensitive actions.
- Memory/session state for multi-turn continuity.
- Checkpointing and resume for durable pauses.
- Observability with OTEL and App Insights-ready exporters.
- Evals with baseline dataset and report.
- Stable native SSE, plus approved optional redacted AG-UI selected-thread
  projections and a read-only CopilotKit bridge.
- React + Vite UI consumes the stable FastAPI API/SSE contract locally and,
  in the private lane, through the external frontend's same-origin proxy to
  the internal wrapper.

## Non-Goals (v1)

- Production auth/RBAC.
- Full cloud deployment automation.
- Parallel/branching orchestrations.

## Acceptance Criteria

1. User request triggers all 3 agent stages in order.
2. A policy-lookup `tool.call` event is emitted while order/customer and
   policy data, MCP/RAG execution content, and credentials remain backend-only
   for selected-thread consumers.
3. HITL request is emitted for high-risk actions and can be approved/rejected.
4. Workflow resumes from checkpoint and produces final output.
5. Follow-up messages within the same thread use prior memory.
6. OTEL traces are created and configurable for App Insights export.
7. Eval harness produces report with pass/fail metrics.
8. Private browser traffic remains same-origin through the wrapper; it never
   receives a Foundry or database credential.

## Delivery contract

Implementation authority and release evidence requirements are defined in `docs/design/engineering-operating-model.md`.
