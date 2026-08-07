---
name: e2e-rubric
description: Preserve the Azure app-hosted Order Resolution operator rubric for native SSE, durable HITL, optional AG-UI, CopilotKit safety, and evidence correlation.
---

# E2E Rubric

Use this skill when editing workflow UI, API events, HITL, AG-UI, CopilotKit, or
selected-thread contracts.

## Required coverage

1. `ORD-1001` completes without HITL unless the message is damaged/manual-review.
2. `ORD-1009` creates a durable checkpoint/HITL request and completes after
   one checkpoint-keyed approval or rejection.
3. Native SSE event names, ordering, and durable-history replay remain stable.
4. The `/rich` contract remains native and additive; it is never routed into
   the assistant panel.
5. The optional AG-UI and CopilotKit views select an existing thread, redact
   all raw payloads, and cannot affect workflow state.
6. Runtime-injected frontend endpoint configuration works and no
   `cpk-web-inspector` is rendered.
7. Failure of an optional view leaves native timeline/history/HITL controls
   usable, without browser access to Foundry, PostgreSQL, MCP/RAG, credentials,
   or secrets.
8. A hosted release proves fresh smoke, E2E, evaluation, and telemetry
   correlation from the same release evidence window; source and local results
   are not deployed evidence.

## Verification

```bash
make test-e2e-selected
make test-e2e
make docker-test
```

Use hosted Playwright only after an authorized app-only release. If Docker E2E
cannot complete TLS trust/handshake setup, report that blocker rather than
claiming hosted or Docker validation passed.
