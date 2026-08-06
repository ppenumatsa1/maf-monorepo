# Schema, IO, and Telemetry

## Stable API I/O contracts

### Start Run

- Method/path: `POST /api/v1/underwriting/runs`
- Request shape:

```json
{
  "application": {
    "application_id": "UW-1001",
    "applicant_name": "Asha Patel",
    "age": 42,
    "income": 125000,
    "requested_coverage": 500000,
    "health_disclosures": "none",
    "driving_history": "minor-violation-2022",
    "credit_score": 742
  },
  "workflow_run_id": "optional-run-id",
  "fail_risk_once": false,
  "fail_credit_randomly": false,
  "crash_after_executor": "optional"
}
```

- Response shape:

```json
{
  "workflow_run_id": "run-1234abcd",
  "status": "COMPLETED",
  "outputs": []
}
```

### Resume Run

- Method/path: `POST /api/v1/underwriting/runs/{run_id}/resume`
- Response shape:

```json
{
  "workflow_run_id": "run-1234abcd",
  "status": "COMPLETED",
  "outputs": []
}
```

### Run History and Read Models

- `GET /api/v1/underwriting/runs?search=&status=&limit=&offset=`
- `GET /api/v1/underwriting/runs/{run_id}`
- `GET /api/v1/underwriting/runs/{run_id}/state`
- `GET /api/v1/underwriting/runs/{run_id}/events`
- `GET /api/v1/underwriting/runs/{run_id}/checkpoints`

## AG-UI stream contract

- Method/path: `POST /api/v1/underwriting/ag-ui`
- Content type: `text/event-stream`
- Usage: stream progress events for start/resume actions while durable run/state/events/checkpoints endpoints remain the source of truth for refresh and replay.

## CopilotKit contract

- Runtime discovery: `GET /api/v1/underwriting/copilotkit/info`
- Run route:
  `POST /api/v1/underwriting/copilotkit/agent/underwriting-run-assistant/run`
- The browser uses the same configured backend base URL as the operations API.
  CORS and the run route accept only `FRONTEND_ORIGIN`; no browser credential or direct Foundry request is used.
- The bridge sends only a selected run ID, normalized status, safe event names, safe executor names/timestamps, checkpoint counts/timestamps, and a categorical final decision. It excludes application, applicant, health, credit, income, prompts, raw model output, checkpoint payloads, and secrets.

## No-shims contract rules

- Browser traffic stays on the public adapter contract above.
- The public adapter starts or resumes hosted Responses work; it must not grow a second production orchestration contract.
- Durable reads for refresh/replay/assistant explanation come from PostgreSQL-backed projections.
- Local-only validation settings must not leak into deployed public-lane behavior.
- Resume accepts only checkpoints produced by the deployed master direct-executor graph. Version-40 nested-graph checkpoints are unsupported after deployment; no compatibility workflow or fallback exists.

## Database surfaces

- `maf_checkpoints`: MAF checkpoint payloads used for workflow resume.
- `workflow_runs`: run lifecycle summary and status.
- `business_state`: projected incremental state.
- `workflow_events`: append-only execution timeline.
- `underwriting_results`: final decision outputs.
- `idempotency_records`: replay and duplicate-side-effect protection.

## Telemetry conventions

- HTTP middleware adds request IDs and `SERVER` OpenTelemetry spans to mutation/dispatch endpoints. Health, CORS preflight, and read-model polling requests remain logged but do not create application-owned Application Insights Request telemetry.
- Key span namespace is `HTTP <method> <path>` with attributes:
  - `http.method`
  - `http.target`
  - `http.request_id`
  - `http.status_code`
  - `http.duration_ms`
- `APPLICATIONINSIGHTS_CONNECTION_STRING` enables Azure Monitor exporter.
- Hosted workflow telemetry uses a 100% sampling ratio so short direct-executor fan-out/fan-in spans are retained consistently with their master workflow.
- `OpenAIInstrumentor` records public-backend model metadata without capturing application or decision content.
- Local fallback supports console tracing when `ENABLE_CONSOLE_TRACING=true`.

### Public UI to Foundry correlation

`FOUNDRY_PROJECT_ENDPOINT` is the canonical Foundry project endpoint
configuration. For start and resume actions, the public adapter derives and
invokes the `underwriting-hosted` agent-specific Responses endpoint from that
project endpoint. Start input carries the validated application only in the
Responses body so the hosted workflow can execute it. Responses metadata
contains only safe identifiers:

```json
{
  "workflow_run_id": "run-1234abcd",
  "protocol": "underwriting-hosted-workflow/v1",
  "action": "start"
}
```

The hosted handler executes MAF and writes PostgreSQL checkpoints, events, state, and final results. The public adapter reads those projections. The browser, public adapter, Responses metadata, and telemetry must never expose a PostgreSQL credential or token. OpenTelemetry model-content capture remains disabled.

The `foundry.responses.invoke` span deliberately provides
`gen_ai.input.messages` and `gen_ai.output.messages` for report-only
evaluation. They contain only redacted action, terminal-status, and decision
summaries; they must not contain applicant input, workflow payloads, raw model
output, or credentials.

Each hosted stage receives the safe context below automatically:

- `workflow.run_id`
- `workflow.action`
- `gen_ai.agent.id` and `gen_ai.agent.name`
- `gen_ai.conversation.id`
- stage-specific executor, retry, and checkpoint identifiers

Retry backoff/exhaustion, injected test failures, and idempotency skips are also separate safe workflow spans. They carry only a categorical failure mode, attempt number, bounded retry delay, executor, and check type; they do not carry exception text, idempotency keys, or application content.

Start and resume are separate Foundry Responses traces. Operators join them by `workflow.run_id`; they must not assume the public wrapper HTTP trace is the parent of the hosted trace.

## Observability signals

- Workflow-level visibility is provided through persisted `workflow_events` and state projections.
- Checkpoint save/load logs include workflow and checkpoint identifiers for recovery diagnostics.
- Frontend/operator views read durable run artifacts rather than relying solely on transient stream frames.
- Foundry shows the hosted master workflow, direct executor, model, retry, fan-in, and checkpoint spans. Application Insights correlates the public AG-UI Request, hosted conversation, and `workflow_run_id`.

### Operator trace lookup

Start from the durable run ID rather than the default Application Insights request list:

```kusto
let workflowRunId = "run-...";
union isfuzzy=true requests, dependencies, traces, exceptions, customEvents
| where timestamp > ago(24h)
| where tostring(customDimensions["workflow.run_id"]) == workflowRunId
| project timestamp, itemType, name, operation_Id, operation_ParentId,
    success, workflowAction = tostring(customDimensions["workflow.action"])
| order by timestamp asc
```

## Release evidence linkage

When hosted validation is run, record the relevant `workflow_run_id` values, evaluation IDs, and trace references in [issues-changes-fixes.md](issues-changes-fixes.md). The telemetry gate requires correlated Application Insights dependency spans named `foundry.responses.invoke` and `workflow.*` for every deployed E2E run; `traces` rows are supplemental evidence. Telemetry is part of the release contract, not optional background evidence.
