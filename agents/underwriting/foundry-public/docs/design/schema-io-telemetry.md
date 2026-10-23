# Schema, I/O, and Telemetry

## Data handling rule

Examples use placeholders only. Do not place real applicant, customer,
policyholder, reviewer, tenant, resource, endpoint, credential, or token data
in documentation, tests, cards, telemetry, or release evidence.

## Stable web API contracts

### Start run

- Method/path: `POST /api/v1/underwriting/runs`
- Request shape:

```json
{
  "application": {
    "application_id": "<synthetic-application-id>",
    "applicant_name": "<synthetic-display-value>",
    "age": 0,
    "income": 0,
    "requested_coverage": 0,
    "health_disclosures": "<synthetic-category>",
    "driving_history": "<synthetic-category>",
    "credit_score": 0
  },
  "workflow_run_id": "<optional-run-id>",
  "fail_risk_once": false,
  "fail_credit_randomly": false,
  "crash_after_executor": "<optional-executor>"
}
```

Application fields are required workflow input but are sensitive. They must
not appear in Adaptive Cards, selected-run assistant projections, Responses
metadata, or content-safe telemetry.

- Response shape:

```json
{
  "workflow_run_id": "<run-id>",
  "status": "<status>",
  "outputs": []
}
```

### Resume run

- Method/path: `POST /api/v1/underwriting/runs/{run_id}/resume`
- The resume request must be authorized for the checkpoint's trusted origin.
- Free-form text is not a reviewer decision.

### Durable read models

- `GET /api/v1/underwriting/runs?search=&status=&limit=&offset=`
- `GET /api/v1/underwriting/runs/{run_id}`
- `GET /api/v1/underwriting/runs/{run_id}/state`
- `GET /api/v1/underwriting/runs/{run_id}/events`
- `GET /api/v1/underwriting/runs/{run_id}/checkpoints`

Read models should expose machine recommendation and reviewer outcome as
different fields.

## AG-UI and CopilotKit

- AG-UI: `POST /api/v1/underwriting/ag-ui`
- CopilotKit discovery and selected-run execution routes live under
  `/api/v1/underwriting/copilotkit`.
- These surfaces are additive projections, not workflow authority.
- Allowlisted data:
  - selected run ID;
  - normalized status;
  - safe event and executor labels/timestamps;
  - checkpoint count/timestamp;
  - categorical machine recommendation;
  - categorical reviewer outcome.
- Prohibited data:
  - application/applicant fields;
  - raw checks or score breakdown;
  - prompts, rationale, and model output;
  - checkpoint payloads;
  - Adaptive Card token material;
  - database values, endpoints, credentials, and secrets.

## Hosted protocol contract

### Responses

Application input belongs only in the request body. Metadata is limited to
safe correlation fields:

```json
{
  "workflow_run_id": "<run-id>",
  "protocol": "underwriting-hosted-workflow/v1",
  "action": "start"
}
```

Structured reviewer input must identify the exact pending checkpoint and may
resolve only an authorized Responses-originated approval.

### Activity and Adaptive Card

Teams uses the same hosted process through Activity. A card action payload
contains an opaque token and requested action shape only. It does not contain
the underlying run, checkpoint, reviewer, or conversation binding.

The server validates bindings from PostgreSQL and never logs the plaintext
token.

## Database surfaces

| Table | Required data |
| --- | --- |
| `workflow_runs` | Run ID, workflow ID/type, non-sensitive case key, trusted `origin_channel`, immutable `machine_recommendation`, lifecycle status, timestamps |
| `business_state` | Incremental state projection keyed by run |
| `workflow_events` | Append-only event type, safe executor label, redacted payload, timestamp |
| `underwriting_results` | Idempotent check and terminal result payloads |
| `idempotency_records` | Stable operation key, status, safe result |
| `maf_checkpoints` | Serialized MAF checkpoint and metadata |
| `underwriting_approvals` | Approval ID, run/checkpoint, pending/completed status, separate reviewer outcome/hash, timestamps |
| `teams_card_actions` | Token hash, batch, run/checkpoint, decision, reviewer/conversation hashes, status, expiry/completion timestamps |

Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`. Startup performs read-only
table/column/index parity validation. Administrator tooling owns schema DDL and
least-privilege grants.

## Recommendation and approval invariants

- `machine_recommendation` is written from deterministic policy and is not
  updated by a reviewer.
- `underwriting_approvals.reviewer_outcome` is `APPROVED`, `DECLINED`, or null
  while pending.
- Only a referral recommendation has a pending approval.
- `origin_channel` is server-selected from `api`, `responses`, or
  `teams_activity`.
- Teams actions store token hashes only.
- One action-batch sibling may complete; the other becomes superseded.

## Telemetry conventions

Safe correlation attributes may include:

- `workflow.run_id`
- `workflow.action`
- `workflow.origin_channel`
- `workflow.checkpoint_id`
- `workflow.executor`
- `workflow.event_id`
- `gen_ai.agent.id`
- `gen_ai.agent.name`
- `gen_ai.conversation.id`
- categorical machine recommendation
- categorical reviewer outcome
- action lifecycle status

Do not record:

- applicant identity or application fields;
- raw check inputs/results or score details;
- prompts, rationale, or model content;
- reviewer identity in plaintext;
- card token or token hash;
- database URL, access token, credential, endpoint secret, or connection
  payload.

OpenTelemetry model-content capture remains disabled for normal operation.
Release-only evaluator input must use the checked-in redaction contract.

## Required spans and events

- public adapter dispatch;
- `foundry.responses.invoke`;
- Activity receive and authorization result;
- master workflow start/complete;
- direct executor invoke/complete;
- fan-out/fan-in;
- retry/backoff/exhaustion;
- checkpoint save/load;
- referral wait;
- card action validate/claim/supersede/complete/reject;
- reviewer resume;
- idempotency skip;
- final machine recommendation and separate reviewer outcome.

Start and resume may use separate hosted traces. Correlate them by run,
checkpoint, and conversation rather than assuming one parent HTTP trace.

## Operator trace lookup

Use the durable run ID:

```kusto
let workflowRunId = "<run-id>";
union isfuzzy=true requests, dependencies, traces, exceptions, customEvents
| where timestamp > ago(24h)
| where tostring(customDimensions["workflow.run_id"]) == workflowRunId
| project timestamp, itemType, name, operation_Id, operation_ParentId,
    success,
    workflowAction = tostring(customDimensions["workflow.action"]),
    originChannel = tostring(customDimensions["workflow.origin_channel"])
| order by timestamp asc
```

Store exact trace references, evaluator IDs, run IDs, counts, and timings only
in the delivery ledger or deployment plan.
