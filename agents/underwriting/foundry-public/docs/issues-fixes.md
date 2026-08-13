# Underwriting Public Foundry Delivery Ledger

This is the running delivery record for
`agents/underwriting/foundry-public`. Add an entry whenever work discovers an
issue, applies a correction, verifies a release gate, or leaves a blocker.

## Current architecture

```text
Browser
  -> public frontend Container App (preserved existing workload)
  -> public FastAPI adapter Container App (preserved existing workload)
  -> Foundry Hosted Agent Responses runtime
  -> public PostgreSQL Flexible Server over TLS

Public FastAPI adapter
  -> relays hosted start/resume and projects durable history/AG-UI events
  -> no production MAF runner

Foundry Hosted Agent
  -> master MAF workflow with direct risk, credit, medical, and driving executors
  -> PostgreSQL checkpoints, workflow state, events, and idempotency records
  -> Foundry workflow/model traces
```

The hosted agent is the production durable executor. It receives a dedicated
least-privilege PostgreSQL password only through hosted runtime configuration,
uses TLS, and never exposes that credential to the browser, public adapter,
Bicep parameters, source, or telemetry. The previous version-34 deployment is
an acknowledgement-only historical baseline, not evidence for this topology.

## Delivery status

The direct-executor master-workflow cutover is release-verified. The
version-40 entries below are preserved historical records and must not be read
as current topology or release evidence for this cutover.

| Work | Status | Evidence / next action |
| --- | --- | --- |
| Import upstream underwriting application | Complete | Imported revision `816993969cd16c208a998441582dc4fedebc6b44` into `foundry-public`. |
| Local quality and unit validation | Complete | Targeted backend tests, Ruff, frontend lint/build, and isolated local E2E pass. |
| Local end-to-end validation | Complete | Isolated PostgreSQL, Uvicorn, Vite, Playwright, and a CopilotKit selected-run response pass with the explicit local-only execution mode. |
| Resource-reuse IaC source | Complete | Bicep declares password auth, narrowed firewall posture, and resource reuse without secrets in parameters. |
| Credential provisioning source | Complete | Versioned script provisions/rotates the least-privilege hosted runtime role from secure local input and validates TLS/readiness. |
| Hosted-only executor source | Complete | Public adapter relays Responses work; `backend/foundry/main.py` owns the production MAF runner. |
| CopilotKit runtime route | Complete | Configured-origin REST discovery and named assistant route are E2E-covered; safe selected-run fields only. |
| Architecture review | Complete | Independent review identified and corrected the frontend/backend origin mismatch, proxy-scheme assumption, and missing adapter schema initialization. |
| Hosted architecture IaC provision | Complete | PostgreSQL recreation, schema bootstrap, runtime role, and TLS/firewall posture were applied declaratively in `rg-underwriting-readiness-0731`. |
| Hosted credential provision | Complete | Hosted and public runtimes use the dedicated least-privilege TLS PostgreSQL credential through runtime secrets only. |
| Direct-executor master-workflow cutover | Complete | Agent v41 runs one master graph with direct checks. Version-40 nested-graph checkpoints are unsupported for resume; no compatibility workflow or fallback exists. |
| Hosted agent/public adapter/frontend deployment | Complete | Agent v41, backend revision `azcawhcedyxchnbtmpubbe--0000020`, and frontend revision `azcawhcedyxchnbtmpubfe--0000011` are running. |
| Hosted smoke, E2E, telemetry, evaluation | Complete | Fresh smoke, deployed E2E, report-only Foundry evaluation, and Application Insights validation passed; identifiers are recorded below. |
| Native evaluator generation | Blocked | The organization-enforced storage policy prevents the required public evaluation-storage route. A policy exemption or private networking is required for this optional generation path. |

## 2026-08-06 - Direct-executor master-workflow cutover

**Change.** The supported workflow is one master underwriting workflow with
direct risk, credit, medical, and driving executors that fan out and fan in in
one superstep. Version-40 nested-graph checkpoints are unsupported for resume
after deployment. No compatibility workflow or fallback exists.

**Root cause / learning.** Nested-graph checkpoints encode the former
parent/child topology. The direct-executor master graph has a different
checkpoint shape, so attempting compatibility resume would make recovery
ownership ambiguous. The clean cutover intentionally rejects that ambiguity
instead of preserving a legacy graph.

**Verification.**

- Hosted agent v41 deployed with the direct-executor graph. Backend revision
  `azcawhcedyxchnbtmpubbe--0000020` and frontend revision
  `azcawhcedyxchnbtmpubfe--0000011` report `Running`.
- Hosted smoke approved `run-smoke-20260806214717-357052`.
- Deployed E2E approved
  `run-hosted-happy-20260806214836-359053` and
  `run-hosted-recover-20260806214836-359053`.
- Foundry evaluation `eval_286f9bdf2cab4166accb2422a9292e55` /
  `evalrun_b3d88ed1e9894fa7a8dde76cca9d1817` passed 1 of 1 with no failed or
  errored results.
- Application Insights correlated 64 rows across both E2E runs: 3 request
  rows and 61 dependency rows, with zero correlated exceptions.
- The 43-test backend suite exercised fresh direct-graph crash/resume,
  idempotency, and incremental fan-in behavior. The graph signature differs
  from v40, so the framework rejects a v40 checkpoint rather than executing a
  compatibility path.

**Release note.** The first concurrent hosted-agent build encountered a
transient Central Feed Services pip `BrokenPipeError`. The public backend and
frontend deployments completed; retrying only the failed hosted-agent build
succeeded. The deployed timing is therefore a recovery sample, not a
steady-state release baseline.

## Public PostgreSQL Flexible Server rebuild workflow

### Existing-server update could not recover from an irreversible server reset

**RCA.** The resource-reuse Bicep defined only the authentication and network
posture for `azpgwhcedyxchnbtmpub`. It could update an existing server, but did
not declare the server creation configuration needed to recreate that exact
server after deletion. Bootstrap also queried the server location before
provisioning, which made the normal provision target unusable during the
delete-and-recreate interval.

**Design.** The server is now a normal declarative Bicep resource with the
creation settings read from the live server: North Central US, PostgreSQL 17,
`Standard_D2ds_v5` General Purpose, 128 GiB storage, seven-day backup
retention, and geo-redundant backup disabled. The existing server name,
authentication, public network setting, Azure-services firewall rule, and
`underwriting` database remain declared. Bootstrap pins the discovered North
Central US location, so it works whether the server exists or has just been
deleted.

The versioned `rebuild_postgres_server.sh` is intentionally hard-coded to
subscription `4f18d577-3506-4a11-85e5-a83b14727a84`, resource group
`rg-underwriting-readiness-0731`, and server
`azpgwhcedyxchnbtmpub`. It refuses every confirmation value except
`REBUILD-azpgwhcedyxchnbtmpub`, requires the secure local
`POSTGRES_ADMIN_PASSWORD` before deletion, confirms the active subscription,
deletes only that named server, waits for the deletion operation, and invokes
the ordinary `foundry-provision` target with the captured server name,
North Central US location, and `underwriting` database forced into the
bootstrap environment. Bootstrap does not query PostgreSQL, so this works
while the server is absent. It is retry-safe after a failed provision because
an already-absent fixed server proceeds to Bicep recreation; it never accepts
caller-controlled Azure target identifiers. The runtime
least-privilege credential remains a separate post-provision action.

**Validation.** Source inspection recorded the live server configuration
before implementation. Planned validation is Bicep compilation, Bash syntax
checking, and Make target dry parsing only; this change does not run deletion,
provisioning, or any other Azure deployment.

## Hosted-only standardization and review follow-up

### Public adapter could not reach the CopilotKit bridge in the deployed topology

**RCA.** The UI used a relative CopilotKit URL even though the frontend and
backend are separate Container App origins. The backend also compared the
browser origin to its internally forwarded HTTP URL, which would reject
legitimate HTTPS requests.

**Fix.** CopilotKit now uses the same `VITE_API_BASE_URL` as every other UI API
call. The backend accepts only its declaratively deployed `FRONTEND_ORIGIN`,
uses that value for CORS, exposes REST runtime discovery, and names the
assistant route explicitly. The deployment script obtains the actual frontend
FQDN and sets `FRONTEND_ORIGIN` with the backend image update. No browser
credential is used.

**Validation.** Backend contract tests cover discovery, trusted/untrusted
origins, AG-UI streaming, and allowlisted projection. Local Playwright submits
a selected-run assistant question and receives the deterministic safe status.

### Hosted public adapter omitted schema initialization

**RCA.** The new adapter opened PostgreSQL to project history but did not call
the existing safe `init_db`/legacy schema migration routine. A database created
by an earlier revision could therefore lack `workflow_runs.applicant_name`.

**Fix.** `UnderwritingHostedAdapter` now initializes the shared schema before
serving reads, matching the workflow service path.

**Validation.** Isolated adapter/history tests and the full Playwright
operations-console rubric pass.

### Local E2E needs an explicit non-production executor

**RCA.** A local browser test cannot call the deployed Foundry Responses
endpoint without Azure credentials and a hosted release.

**Fix.** `UNDERWRITING_EXECUTION_MODE` defaults to `hosted`. The Makefile sets
`local` only inside the isolated E2E process; it directly exercises the same
MAF workflow and database schema without changing the deployed default.

**Validation.** The production adapter test proves default hosted mode does
not construct a local runner. The local E2E test proves the isolated override.

### Cross-region resource reuse and password-auth validation blocked IaC

**RCA.** The resource group is in East US 2 while the existing PostgreSQL
server is in North Central US. The initial Bicep update incorrectly used the
resource-group location, so ARM attempted a conflicting server creation.
After the location correction, Azure correctly required the existing server
administrator password to enable password authentication and create its admin
role.

**Fix.** Bootstrap now queries and persists `POSTGRES_SERVER_LOCATION`, and
Bicep uses that value for the existing server update. The existing administrator
password is now a secure Bicep parameter sourced only from the local azd
environment variable `POSTGRES_ADMIN_PASSWORD`; it is absent from source,
parameter files, output, and logs.

**Validation.** The corrected `azd provision --preview` targets the existing
North Central US server and shows only password-auth enablement plus existing
resource updates. Actual provision is blocked until the secure local
administrator password is supplied.

**Final release attempt.** A locally generated replacement password was
supplied as the secure ARM parameter to test whether Azure would rotate the
administrator credential while enabling password authentication. Azure
rejected it with `EngineCredentialsNotProvided`, confirming that this operation
requires the **current** administrator credential. Password authentication
remains disabled and the generated value was cleared from the local azd
environment; no administrator rotation or PostgreSQL access change occurred.

## Source import and local validation

### Upstream branch discrepancy

**RCA.** The migration request described a `foundry-public` source branch, but
GitHub exposed only upstream `main`.

**Research.** Repository metadata and branches were inspected before import.
`main` was confirmed at `816993969cd16c208a998441582dc4fedebc6b44`.

**Fix.** Imported that approved revision into
`agents/underwriting/foundry-public`, excluding repository metadata, local
virtual environments, Node modules, and generated test artifacts. Added
`agents/underwriting/README.md` to identify the public lane and preserve
provenance.

**Validation.** The imported application installs and runs from its monorepo
path.

### Import lint and formatting failures

**RCA.** The upstream test module had a non-canonical import order and
formatting did not match the pinned Ruff version installed in the monorepo.

**Fix.** Sorted the affected imports and ran the repository Ruff formatter.

**Validation.** `make quality` passes after the import.

### Local E2E assumed an already-running backend

**RCA.** The upstream Playwright target launched Vite only, while its browser
API calls require a FastAPI backend and PostgreSQL service.

**Fix.** Updated `make test-e2e` to create an isolated Compose PostgreSQL
service, wait for readiness, launch a temporary Uvicorn backend, run
Playwright, and clean up both processes.

**Validation.** The underwriting rubric scenario passes with happy path,
retry, crash/resume, fan-in state, checkpoint, idempotency, and observability
checks.

### Operations UI did not expose transaction history or execution order

**RCA.** The prototype was optimized for inspecting the most recently created
run. It polled four per-run REST resources, had no run-history endpoint, and
reversed events for display even though operators need to read a selected
run in execution order.

**Research.** `workflow_runs` already held durable identifiers, statuses, and
timestamps; `workflow_events`, `business_state`, `underwriting_results`, and
MAF checkpoints contained the durable detail needed for an operations view.
Applicant name was not stored on the run row, so searching it would otherwise
require unreliable JSON inspection.

**Fix.** Added indexed applicant-name persistence with a safe legacy schema
upgrade, paginated/searchable `GET /api/v1/underwriting/runs`, and operations
summaries containing decision, checkpoint, and resumability data. The local UI
now places newest-first history on the left, chronological events and
state/recovery in the center, and decision/application details on the right.
Raw technical data is collapsed by default.

**Validation.** Repository tests verify legacy schema migration, search,
status filtering, decision projection, resumability, and newest-first order.
Playwright selects an old run from history, searches by run ID, and confirms
chronological event records.

### AG-UI workflow support required an Agent Framework compatibility upgrade

**RCA.** The original `agent-framework-ag-ui==1.0.0b260130` module exposed a
chat-agent wrapper only; it could not wrap a native MAF workflow. The current
workflow AG-UI integration documented by Microsoft requires the newer
`AgentFrameworkWorkflow` adapter.

**Fix.** Locally aligned Agent Framework Core 1.13.0, Azure AI RC6, AG-UI
1.0.1, and FastAPI 0.139. The corresponding workflow-builder, state-context,
function-middleware, and checkpoint-storage APIs were migrated. PostgreSQL
checkpoint serialization now uses the framework's safe checkpoint encoding
with an explicit underwriting type allowlist, preserving crash/resume.

**AG-UI design.** A small Agent Framework bridge workflow wraps the existing
durable runner. It emits standard SSE lifecycle events and safe
`underwriting.event` custom events containing only run ID, event type,
executor, and timestamp. Browser-visible AG-UI activity snapshots are
suppressed so applicant and application payloads are never echoed in the
stream. The existing PostgreSQL checkpoint resume API remains authoritative;
this is not AG-UI human-interrupt resume.

**Validation.** A FastAPI test proves `RUN_FINISHED` and safe custom events
are streamed without applicant data. The expanded backend suite passes 18
tests, and the local browser E2E passes happy path, retry, crash/resume,
history search/selection, chronological timeline, fan-in, checkpoint, and
idempotency coverage.

### Docker Compose naming collision

**RCA.** The imported Compose file assigned global `container_name` values,
which conflicted with an existing underwriting PostgreSQL container.

**Fix.** Removed global names and made the PostgreSQL host port configurable.

**Validation.** Parallel isolated local runs can use distinct Compose project
names and ports.

## Hosted agent deployment

### Foundry reserved environment variables

**RCA.** The first hosted-agent registration rejected
`FOUNDRY_MODEL_DEPLOYMENT_NAME` and `APPLICATIONINSIGHTS_CONNECTION_STRING`;
Foundry reserves `FOUNDRY_*`, `AGENT_*`, and platform telemetry variables.

**Research.** The registration response identified both reserved names.

**Fix.** Renamed the application-owned setting to
`UNDERWRITING_MODEL_DEPLOYMENT_NAME` and rely on Foundry to inject its
Application Insights configuration.

**Validation.** The container image built in ACR and hosted agent version
registration advanced to runtime creation.

### ACR image-pull authorization

**RCA.** The first runtime version failed with `ImageError` because the
Foundry project identity could not pull the hosted image from ACR.

**Research.** Microsoft Foundry hosted-agent permissions documentation
recommends `Container Registry Repository Reader`; the existing public
hosted-agent pattern also uses `AcrPull` for this runtime.

**Fix.** Added both pull-only role assignments at the existing
`azcrwhcedyxchnbtm` registry scope through Bicep.

**Validation.** After provision, version `13` became active.

### Hosted PostgreSQL managed-identity mismatch

**RCA.** The existing Container App uses a user-assigned identity as its
PostgreSQL principal, but the hosted agent receives its own Foundry-managed
identity. The first active agent therefore returned an internal error on
workflow execution.

**Research.** The active version exposed its managed identity:
`azfdwhcedyxchnbtm-azprwhcedyxchnbtm-underwriting-hosted-AgentIdentity`.
The PostgreSQL Entra administrator and official
`pgaadauth_create_principal_with_oid` guidance were verified before changing
database access.

**Fix.** Added managed-identity token authentication to the backend database
engine, created the hosted-agent's non-admin PostgreSQL Entra principal, and
granted schema/table/sequence privileges needed for workflow persistence.
Redeployed with that principal as `DB_USER`.

**Validation.** Version `14` completed a Responses smoke invocation through
the real MAF workflow and PostgreSQL persistence path.

### azd automatic endpoint resolution selected a stale project

**RCA.** `azd ai agent invoke <name>` resolved a prior order-resolution
project despite the selected underwriting azd environment.

**Fix.** Bootstrap now persists the underwriting project endpoint aliases.
The smoke target invokes the explicit Responses endpoint derived from
`AZURE_AI_PROJECT_ENDPOINT`.

**Validation.** The smoke command creates an underwriting Foundry conversation
and returns the completed workflow result.

## Observability and evaluations

### Missing Foundry Application Insights connection

**RCA.** The Foundry project had no project connections, so the initial smoke
failure produced no queryable application telemetry.

**Fix.** Bicep adds the existing `azaiwhcedyxchnbtm` Application Insights
connection to project `azprwhcedyxchnbtm`, plus the necessary project
Log Analytics reader assignments.

**Validation.** A successful smoke invocation recorded Foundry
`azure.ai.agentserver` telemetry with the agent name, version, session ID, and
trace ID in Application Insights.

### Native Foundry evaluation artifact authorization and trace-evaluation fallback

**RCA.** The direct batch evaluation API returned an opaque service error.
The supported azd evaluation generator then surfaced the specific cause:
Azure Storage `AuthorizationFailure`. The Foundry account identity
(`3ca0fee0-5b09-45bf-8cb4-3f3cbdf3938f`) and project identity
(`b92cf7f3-9138-43e4-b21c-a80055358859`) match the two Storage Blob Data Owner
role assignments, so this is not an RBAC propagation or principal mismatch.

**Research.** The project originally had no evaluation artifact connection.
Comparing the order-resolution IaC identified its additional `runtime-storage`
AAD connection, which was added to underwriting. Retrying still failed with
the same Azure Storage `AuthorizationFailure`. Microsoft Foundry's
[evaluation troubleshooting guidance](https://learn.microsoft.com/azure/foundry/observability/how-to/troubleshooting#storage-account-network-access-restrictions)
states that Entra-authenticated evaluation storage must set
`publicNetworkAccess` to `Enabled` and its default network action to `Allow`.
The underwriting account had `publicNetworkAccess: Disabled`; the
order-resolution template has the same incompatible setting.

**Further RCA.** Provisioning and a direct Storage control-plane update both
reported success but retained `publicNetworkAccess: Disabled`. Azure Policy
state identifies the enforcing management-group assignment
`mcapsgovdeploypolicies` and its `StorageAccount_PublicNetwork_Modify` effect.
The policy explains the persisted state and proves this is neither an RBAC
propagation nor an IaC syntax problem.

**Fix applied.** Bicep grants Storage Blob Data Owner to both Foundry
identities and creates the shared `evaluation-artifacts` and private
`runtime-storage` AAD connections. It intentionally preserves the
policy-required storage network setting. Underwriting now also implements the
order-resolution trace-evaluation pattern: `azure-ai-projects`, a checked-in
trace runner, recorded smoke evidence, and a `make foundry-trace-eval` target.

**Trace content RCA and fix.** The initial trace evaluation found the hosted
conversation but no `gen_ai.input.messages` or `gen_ai.output.messages`.
The custom Responses handler emitted platform metadata only. The hosted image
now installs `azure-ai-agentserver-core[tracing]`, enables GenAI content
recording for the synthetic smoke path, and emits an OpenTelemetry
`invoke_agent` span with the required operation, agent, conversation, input,
and output attributes. The span records only the request text and serialized
workflow decision, never the raw underwriting application payload.

**Validation.** Version `17` smoke completed with trace
`6f17e7278e69f572eea6cd7dc7f7f36f`. Foundry trace evaluation
`eval_fc5845346b2547db96b8d726321aef3b` / run
`evalrun_978a74d2068547b5bd3ecfe8c68be510` completed with 1/1 passed and no
failures or errors. Evidence and result IDs are persisted in
`backend/.foundry/results/`.

**Comparison and release-gate correction.** The Order Resolution portal run
that reports 4/4 is a direct, report-only Foundry **trace evaluation**, not
the native `azd ai agent eval run` dataset/suite-generation path. Its runner
creates an `AzureAITraceDataSourcePreview` evaluation from hosted
conversations; the corresponding Underwriting runner has already completed
`eval_43533c4845ce410080fb16d6a3101f31` /
`evalrun_a1ea891c350f41928f485ac3f0debdec` with 1/1 passed. Both projects
have the same project-scoped `ApplicationInsights`, `evaluation-artifacts`,
and `runtime-storage` connections; both evaluation storage accounts have the
same secure public-network-disabled, Azure-services-bypass, Entra-only
posture.

The difference was release wiring: Order Resolution runs its report-only trace
runner as `make eval-foundry`, while Underwriting's `make foundry-eval` still
called native azd suite generation. Underwriting now makes `foundry-eval` the
supported report-only trace-evaluation gate, retains `foundry-trace-eval` as an
alias, and labels `foundry-native-eval` as diagnostic-only.

**Validation.** The corrected primary target completed:
`eval_2a0d37e7e72e4b39a6a6e7f99faa4324` /
`evalrun_99b0c94169fb44f39a7abfb56a8df194`, with 1/1 passed and zero failed
or errored items.

**Remaining native-path blocker.** `make foundry-native-eval` requires either
a policy exemption allowing public network access on
`azstwhcedyxchnbtmeval` or a private-networked Foundry evaluation design. Do
not enable shared-key authentication or replace managed identity with a
secret. This does not block the supported trace-evaluation release gate.

### Shared local PostgreSQL credential drift

**RCA.** A final `make quality` rerun reached the pre-existing local PostgreSQL
instance on port 5432 and failed password authentication for `underwriting`.
This is separate from the isolated E2E environment and does not involve the
hosted-agent tracing changes.

**Research.** Order-resolution avoids developer-database coupling by preparing
a test-specific PostgreSQL instance before its backend test target.

**Fix.** Underwriting `make test-backend` now starts an isolated Compose
PostgreSQL project on a dynamically allocated loopback port, passes its
connection URL only to pytest, waits for readiness, and tears it down on exit.

**Validation.** `make quality` now passes with seven backend tests, backend
and frontend lint, backend format validation, and the frontend production
build. The existing isolated Playwright E2E, hosted version 17 smoke, and
Foundry trace evaluation remain passing.

### Version 17 release regression revalidation

**Scope.** Recompiled the resource-reuse Bicep and reran the isolated
Playwright E2E suite. The browser suite executes the happy-path decision,
one-time risk retry, and crash-after-medical-check followed by checkpoint
resume in one rubric-gated run.

**Validation.** IaC compilation succeeded. The Playwright rubric passed all
happy, retry, crash, resume, fan-in, checkpoint, idempotency, and observability
assertions. A new version 17 Responses smoke completed workflow
`run-7b7f1dee23` with an approved decision. Application Insights recorded 118
correlated telemetry records for conversation
`conv_24feda78737be88d004EEYhgDuoER2bVutJ8wCUlhx9OQzmATn`, tagged with
agent `underwriting-hosted` version `17`. Foundry trace evaluation
`eval_631779d4b822458a885dd80d634bf414` / run
`evalrun_40b76291401a450581cd47e0d1f108f1` completed with 1/1 passed and no
failures or errors.

### Telemetry quality and managed-identity release

**RCA: child workflow stages were missing from the trace waterfall.** The
Agent Framework `@handler` wrapper bypasses executor decorators and child
workflow execution does not preserve the parent trace context. This left the
original trace with only generic orchestration telemetry.

**Research.** Order-resolution's explicit business telemetry was compared with
underwriting. Microsoft Foundry hosted-agent tracing guidance was also checked:
the host injects platform telemetry, while application spans must use a
configured OpenTelemetry exporter and
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` for message content.

**Fix.** The runner now replays safe persisted workflow events after the real
MAF run completes, emitting root-correlated spans for initialization, risk,
credit, medical, driving, fan-in, final decision, and completion. Raw
application, medical, and credit payloads are never copied into span
attributes. Retry details remain in the persisted event trail. The hosted
deployment passes the existing Application Insights connection string through
the application-owned `UNDERWRITING_APPINSIGHTS_CONNECTION_STRING` variable,
avoiding Foundry's reserved-variable restriction.

**RCA: public backend revision was unhealthy after the health-noise change.**
The existing Container App configured `DB_AUTH_MODE=entra`, while the
database engine recognized only `managed_identity` and sent the placeholder
password to PostgreSQL.

**Fix.** The engine now accepts both `entra` and `managed_identity` as
managed-identity modes. Revision `0000005` is healthy at 100% traffic.
The `/health` request bypass remains before manual logging and span creation.

**Deployment note.** The required `azd deploy --no-prompt` attempt could not
complete its local Docker build because that environment could not complete a
TLS handshake with PyPI. The repository's existing remote ACR build path
succeeded for both the hosted image and public backend; this was an
environment-specific local build issue, not an application failure.

**Validation.** Backend lint, formatting, and 13 isolated database-backed
tests passed. The browser E2E rubric passed its happy path, one-time retry,
and crash/resume scenarios. Bicep compiled (with the pre-existing
nested-deployment warning). Version `22` smoke completed:

- Conversation: `conv_b86f56e41e49c50400K2Bal7k5HL5LWaY1wAUPQM6XYncYMScx`
- Trace: `7ec4bc865e41542db553a7f66043d299`
- Workflow: `run-3e244f9094`
- Decision: `APPROVED`
- Trace evaluation: `eval_851d758fca27423688e864d74f0c95b0` /
  `evalrun_18d518bab73e4a51a12d85d8b277403d`, 1/1 passed

Application Insights shows the Responses root, preserved evaluation span,
all eight business stages, and successful
`POST /openai/deployments/underwriting-gpt-4-1-mini/chat/completions`.
Direct post-cutover `traces` and `dependencies` queries return zero
`/health` records.

### Missing model-call node in Application Insights and Foundry

**RCA.** The rationale request reached Azure OpenAI successfully, but appeared
only as the generic HTTP dependency
`POST /openai/deployments/.../chat/completions`. The hand-created model span
was not exported, so it had no `gen_ai.operation.name=chat`, model, token, or
finish-reason data available for Foundry to recognize as a model call.

**Research.** The deployed trace
`7ec4bc865e41542db553a7f66043d299` contained the raw HTTP dependency but no
semantic `chat` dependency. The installed official OpenTelemetry OpenAI v2
instrumentor was verified against `AsyncAzureOpenAI`; it emits the semantic
model span with standard GenAI attributes.

**Fix.** Added `opentelemetry-instrumentation-openai-v2` as a direct runtime
dependency and initialized `OpenAIInstrumentor` once after Azure Monitor
setup. Removed the hand-created model scope so the SDK instrumentation owns
the Azure OpenAI call. Content capture is disabled for this instrumentation;
the new span records only model metadata, token counts, finish reason, and
duration.

**Validation.** Version `23` smoke completed workflow `run-fb20c35df9`:

- Conversation: `conv_8455edced675843c00PVE7HeQz4fx1G743M2tFnSRITfKa8A7C`
- Trace: `1ea0a48c71bffdbf9cb752ec840fe2d9`
- Semantic model span: `chat underwriting-gpt-4-1-mini`
- Response model: `gpt-4.1-mini-2025-04-14`
- Usage: 81 input / 30 output tokens; finish reason `stop`
- Trace evaluation: `eval_0d4c41bf31bc4455a2040869b93c3950` /
  `evalrun_13c9fa04a67b46dcad80c4c768c785d7`, 1/1 passed

### Version 25 operations-console release and telemetry privacy

**RCA.** The local Docker build could not reliably complete npm dependency
resolution, and the prior hosted trace showed that the custom `invoke_agent`
span copied the serialized underwriting decision into
`gen_ai.output.messages`. The latter bypassed the capture-content setting.

**Fix.** Kept builds in ACR and added a repeatable
`make foundry-frontend-deploy` target that compiles the frontend with the
public backend URL. ACR built the frontend successfully. The hosted span now
uses fixed, non-sensitive request/completion text instead of application,
decision, score, or rationale content.

**Validation.** Resource-reuse IaC reported no drift. Hosted version `25`,
public backend revision `azcawhcedyxchnbtmpubbe--0000006`, and public frontend
revision `azcawhcedyxchnbtmpubfe--0000004` are healthy. Hosted smoke completed
workflow `run-7b6e58ded6` for trace
`0479996218d3390bcc72a9c13d2cbe53`; the deployed Playwright rubric passed
happy path, retry, crash/resume, history, fan-in, checkpoint, idempotency, and
observability checks. Foundry trace evaluation
`eval_42fcdf446daf4d6db1155379f5882ce9` /
`evalrun_8f9f47b2ff9843c6b9a8671c347b562c` passed 1/1 with no errors or
failures. Application Insights contains zero `/health` requests for the
post-release backend window.

### Version 29 trace-evaluation completion

**RCA.** Fresh hosted-agent traces can be visible in Application Insights
before Foundry's trace-evaluation service materializes the child
`invoke_agent underwriting-hosted` span. Early evaluation attempts therefore
reported zero supported inputs despite a healthy smoke response.

**Fix.** Restored the accepted non-sensitive user/completion messages and
gated the evaluation submission on confirming the child span in Application
Insights. No underwriting application, decision, score, or rationale data is
recorded in those messages.

**Validation.** Version `29` smoke completed workflow `run-75bc7e1dd4` for
trace `ee962a60a28c0b272b1e8293f3c786c0`. Foundry trace evaluation
`eval_01eb617297384ae0a368992b00a0d505` /
`evalrun_32a8e7b6214a4d5a9e9db1e038508444` completed with 1/1 passed and no
errors or failures.

### UI-to-Foundry trace relay, request classification, and hosted identity boundary

**RCA: UI-originated transactions were absent from Foundry traces.** The
operations console posted to the public AG-UI endpoint, which directly executed
the durable workflow in the public Container App. No request entered the
Foundry hosted-agent Responses endpoint, so Foundry could not show a trace for
new UI transactions.

**RCA: public API traffic was not visible as Application Insights Requests.**
The public middleware created its own OpenTelemetry spans with the default
`INTERNAL` kind. Azure Monitor classified those spans as dependencies rather
than request telemetry. The public process also had the OpenAI v2 instrumentor
installed but did not initialize it.

**Fix.** Public request spans use `SERVER` kind and initialize
`OpenAIInstrumentor` after Azure Monitor configuration. The AG-UI start path
now invokes the hosted agent through
`AIProjectClient(..., allow_preview=True).get_openai_client(agent_name=...)`,
which selects the required per-agent Responses endpoint. The relay sends only
the workflow run ID and `trace_only` marker in Responses metadata; applicant,
health, income, credit, decision, score, and rationale data never leave the
public executor for the Foundry acknowledgement.

**RCA: the initial relay returned 403 and then 400.** `Cognitive Services
OpenAI User` authorizes account-level model access but not agent invocation.
`Foundry Agent Consumer` was insufficient for the Responses protocol in this
configuration. The project-wide OpenAI endpoint also rejects
`agent_reference`; it requires the dedicated agent endpoint.

**Fix.** Bicep now assigns **Foundry User** at the Foundry project scope to
the public backend user-assigned identity
`azidwhcedyxchnbtm`. The bootstrap script persists
`PUBLIC_BACKEND_MANAGED_IDENTITY_NAME`, and the compiled ARM template is
checked in. Resource-reuse IaC provision completed successfully after the
assignment moved from the ineffective account scope to the project scope.

**RCA: the hosted Responses handler returned 500.** The protocol normalizes
input into nested `input_text` envelopes, so the initial string-only parser
lost the request. Even after parsing was corrected, direct hosted execution
could not acquire a PostgreSQL token: the platform-created agent identity is
used by Foundry's tool token-exchange flow, but no IMDS or workload credential
endpoint is exposed to arbitrary container code.

**Fix.** The handler recursively reads supported Responses text envelopes,
accepts the safe metadata marker, and acknowledges trace-only requests without
opening PostgreSQL. The public backend continues to own the durable MAF
workflow, checkpoints, recovery, idempotency, and model call. The agent
identity and its PostgreSQL permissions remain in place for the future
tool-based design.

**Validation.** Focused backend tests cover the agent-specific client,
metadata relay, flat and nested Responses envelopes, trace-only behavior,
AG-UI safety, and Request span kind. Public backend revision
`azcawhcedyxchnbtmpubbe--0000012` and hosted agent version `34` completed
AG-UI smoke run `run-trace153148`:

- The durable run is `COMPLETED` with all initial, fan-in, decision, and
  workflow-completed events.
- Public request `HTTP POST /api/v1/underwriting/ag-ui` is a successful
  Application Insights **Request**, operation
  `02b85fdeeea7adcdcfd56d4eb163f697`.
- Foundry recorded successful `invoke_agent` operation
  `662d8d31e31336f9ec770e9b813c732d` and hosted
  `invoke_agent underwriting-hosted` span.
- `/health` remains excluded from application-created telemetry.

**Remaining blocker and next architecture change.** Foundry agent identities
obtain downstream tokens only when Agent Service invokes a configured MCP or
A2A tool. To move durable PostgreSQL workflow execution into
`underwriting-hosted`, deploy a private tool/proxy that owns the database
connection, assign the agent identity its least-privilege access, and invoke
that tool from the hosted agent. Do not pass PostgreSQL credentials or
database access tokens through Responses input, metadata, prompts, or traces.

**Delivery diagnostic: raw ARM deployment does not expand azd placeholders.**
The checked-in parameters file intentionally contains `${...}` values for azd.
A direct `az deployment group create` treated those values literally and failed
resource lookup. `azd provision` is the supported path and successfully
compiled, substituted, validated, and deployed the Foundry project role
assignment. Do not replace the azd deployment path with a raw ARM command
unless parameters are resolved first.

**Test-only diagnostic: agent-server metrics exporter writes after pytest
closes stdout.** Importing the hosted Responses app starts a background console
metrics exporter. At Python shutdown it can log `ValueError: I/O operation on
closed file` after the test runner has already reported success. The focused
suite exits zero and production uses Application Insights, so this is not a
runtime release blocker. Keep it visible until the agent-server test fixture
can explicitly shut down the provider.

### AG-UI acknowledgement latency delayed operations-console completion

**RCA.** The public AG-UI executor awaited the safe Foundry Responses
acknowledgement before creating the durable workflow run. The acknowledgement
typically takes about 5.6 seconds to first byte. During that interval, the
browser had no run record to refresh and displayed `IDLE`; the deployed
Playwright assertion timed out after five seconds even though the workflow
would eventually complete.

**Fix.** The public backend now starts the trace-only acknowledgement and the
durable PostgreSQL workflow concurrently, then still awaits the
acknowledgement before closing the AG-UI operation so a relay failure remains
visible. The UI immediately reports `IN_PROGRESS`, polls the durable run, and
uses durable status in preference to its temporary client-side status. A
focused test proves the durable runner begins while the relay is deliberately
blocked.

**Validation.** Eight focused relay, Responses-parser, and observability tests
pass; frontend lint and production build pass. The backend was deployed as
`azcawhcedyxchnbtmpubbe--0000014` and the frontend as
`azcawhcedyxchnbtmpubfe--0000006`, both healthy at 100% traffic. The deployed
Playwright rubric passed all happy path, retry, crash/resume, history, fan-in,
checkpoint, idempotency, and observability checks in 16.4 seconds.

**Fresh telemetry and smoke evidence.** The E2E submissions produced successful
public `HTTP POST /api/v1/underwriting/ag-ui` Requests
`a88f574cf4f0d17a981b2a1fa6cb2197`,
`8b805786aa68f80c1ba18a466fd5ddd7`, and
`bb73cdfb57da2ca405b9316938bc5ecf`. Their hosted acknowledgement spans
`b686e537f51f1a5583e04d4ae87d47fa`,
`4c72905b2cb905a7275fe7f790e6ba3b`, and
`c93fa27331e1d724e8dbd6f6ea130c52` succeeded. An explicit hosted Responses
smoke returned `ACCEPTED` for `run-33a38328a2`, conversation
`conv_7242e2e92436d0db00ytV7rVNcCAzDY91adrJzevzAHQT77U0o`, and trace
`127d5a4c72057e57d60508f80b830980`. It is intentionally a safe
acknowledgement, not hosted durable execution. The supported trace-evaluation
fallback completed with 1/1 passed and zero failures or errors:
`eval_2a7a40c8b21543a08183a295a800c147` /
`evalrun_53eb743964b3477c834bd99a8ad8da6d`.

**azd diagnostic.** `azd env get-values` resolves the underwriting project and
active version 34 correctly, but `azd ai agent show` still queried a stale
order-resolution project in this local CLI state. The explicit Responses
endpoint invocation succeeded, so this is a CLI context diagnostic rather
than a deployment blocker. Use the explicit endpoint in the documented smoke
command until the local azd extension cache is corrected.

**Documentation synchronization.** `README.md`, every file under `docs/`, and
this ledger now describe the same deployed topology: the public API executes
the durable workflow; Foundry records a safe hosted acknowledgement; public
Application Insights contains Request and model telemetry; and MCP/A2A is the
explicit next step for hosted PostgreSQL execution. The current release
evidence is hosted version `34`, public backend revision `0000014`, public
frontend revision `0000006`, and safe acknowledgement smoke
`run-33a38328a2`.

### Hosted-only MAF standardization decision (in progress)

**Decision.** Underwriting will adopt the same public PostgreSQL
credential pattern as order-resolution. `underwriting-hosted` becomes the
sole production MAF executor; the public API remains only a browser-safe
invocation, history, and event-projection adapter. This restores rich Foundry
workflow and model traces without forwarding Foundry credentials to the
browser.

**Setup research.** The live server `azpgwhcedyxchnbtmpub` is ready with
public networking enabled, Entra authentication enabled, password
authentication disabled, and an over-broad temporary firewall rule from
`0.0.0.0` through `255.255.255.255`. Underwriting already supports password
database mode, but hosted-agent registration currently hard-codes
managed-identity settings and does not provide `DATABASE_URL` or
`RUNTIME_DATABASE_URL`. Order-resolution instead injects a TLS runtime
connection URL into its hosted agent and runs its MAF workflow within the
Responses handler.

**Approved infrastructure posture.** Bicep/azd—not portal or ad hoc CLI
changes—will enable password and retain Entra authentication, create/rotate a
dedicated least-privilege hosted database user through repeatable release
automation, and narrow the existing firewall rule to the Azure-services
exception (`0.0.0.0` to `0.0.0.0`). No database password, URL, applicant data,
or credential reaches source control, deployment parameters, browser
configuration, logs, or traces.

**UI decision.** Preserve the three-pane operations console. Add CopilotKit as
an embedded, event-aware assistant that receives only safe selected-run state
and uses a same-origin runtime bridge. It will not replace the console, execute
the workflow, or receive Foundry credentials.

**Release gates.** Record the outcome of each IaC, credential, hosted-runtime,
CopilotKit, test, deployment, telemetry, and evaluation phase in this ledger.
Before deployment, an independent Rubber Duck review must challenge firewall
scope, secret handling, resume/idempotency semantics, browser boundaries, and
whether the Foundry trace reflects real execution. A second review covers
deployed evidence.

### Repeatable PostgreSQL server rebuild preparation (in progress)

**RCA.** The existing Flexible Server cannot enable password authentication
in place without its current administrator password. The credential is not in
the selected local azd environment or the resource group's Key Vault, so an
in-place ARM update fails with `EngineCredentialsNotProvided`.

**Decision and fix.** The authorized recovery scope is the fixed
`azpgwhcedyxchnbtmpub` server, not a database-only delete. A separate,
confirmation-gated `make foundry-postgres-rebuild
CONFIRM=REBUILD-azpgwhcedyxchnbtmpub` workflow now verifies the fixed
subscription and resource group, deletes only that named server, waits for
deletion, and recreates it through Bicep. It retains the discovered North
Central US location, PostgreSQL 17, General Purpose
`Standard_D2ds_v5` SKU, 128 GiB storage, seven-day retention, disabled
geo-redundant backup, dual authentication, the Azure-services-only firewall
rule, and the `underwriting` database.

**Recreate safety corrections.** Bootstrap no longer queries the server
between deletion and recreation; it pins the documented server location.
The Bicep resource now includes the required administrator login as well as
its secure password. If no password is already stored in the selected local
azd environment, the guarded workflow generates one and saves it only there;
it never prints the value. The normal runtime-user credential remains a
separate post-provision step.

**Release-time SQL execution fix.** The local Azure CLI has no
`az postgres flexible-server execute` command, so the original credential
automation could not apply schema or grants. Bicep now manages a
single-address `allow-release-operator` firewall rule from the release host's
current public IPv4 address. The schema bootstrap and credential scripts use
TLS-required `psql`, passwords only through process environment variables,
and mode-600 temporary SQL files which are removed on exit. This replaces an
invalid CLI dependency without an ad hoc portal/firewall change.

**Deployed E2E RCA (in progress).** The first deployed UI run remained
`IDLE`. Container App logs showed the public adapter was still configured with
the former managed-identity database user, which does not exist after the
credential-pattern rebuild. The backend deployment now stores the TLS runtime
URL as the Container Apps `runtime-db-url` secret and explicitly sets
`DATABASE_URL`, `RUNTIME_DATABASE_URL`, and `DB_AUTH_MODE=password`. This
keeps the password out of normal container environment output while aligning
the public read-model adapter with the hosted runtime.

**Hosted input parsing and deployed E2E fix.** The first Responses request
reached the hosted agent but its workflow envelope was not present in the
primary Agent Server payload shape, so the agent generated a new rejected run
ID. The parser now reads equivalent input fields from both the Responses
payload and Agent Server context. A deployed AG-UI run then completed with
durable events, checkpoints, and a final decision. Playwright initially used
five-second assertions, while a cold hosted Responses invocation takes just
over five seconds; hosted status and assistant assertions now allow thirty
seconds without changing the UI behavior. The full deployed happy, retry,
crash/resume, history, and CopilotKit rubric passes.

**Evaluation and telemetry evidence.** Native `azd ai agent eval run` remains
blocked by the organization-enforced evaluation-storage network policy:
`Azure Storage access denied: AuthorizationFailure`. The storage account
correctly has public access disabled, shared keys disabled, Azure-services
bypass, and Foundry account/project Blob Data Owner assignments; enabling the
native evaluator needs a policy exception or private evaluator networking.
The supported trace-evaluation fallback passed 1/1:
`eval_43533c4845ce410080fb16d6a3101f31` /
`evalrun_a1ea891c350f41928f485ac3f0debdec`. Application Insights confirms the
deployed `run-deployed-smoke-001` has correlated
`foundry.responses.invoke`, `underwriting.hosted.workflow`,
`workflow.underwriting.initialize`, and `workflow.checkpoint.save`
dependencies under operation `09959325da9d8d4a976c48597816b673`.

**Release evidence.** Hosted agent version `36`, public backend revision
`azcawhcedyxchnbtmpubbe--0000016`, and frontend revision
`azcawhcedyxchnbtmpubfe--0000007` are running. The corrected smoke command
completed `run-hosted-smoke` with `APPROVED` and trace
`03fe1ee03fe876dd66b198820aa9e131`. Both local and deployed Playwright
rubrics pass; the deployed run covers happy path, retry, crash/resume,
history paging, safe CopilotKit assistant response, checkpoints, fan-in,
idempotency, and observability fields.

### Hosted trace completeness remediation (in progress)

**RCA.** Azure Monitor configured the hosted runtime with its default
rate-limited sampler. Under MAF fan-out, short executor-stage spans were
dropped while outer Responses, initialization/resume, and checkpoint spans
survived. This produced an incomplete Foundry trajectory even though the
PostgreSQL `workflow_events` audit trail recorded every transition.

**Fix.** Hosted telemetry now explicitly configures consistent 100% sampling
for the redacted pilot workflow. A context-scoped safe envelope adds
`workflow.run_id`, action, Foundry agent identifiers, and conversation ID to
all nested MAF stage spans. Public adapter mutation requests are correlated by
the same run ID, while health, preflight, and polling reads no longer create
application-owned Request spans. No applicant fields, prompts, rationale,
checkpoint payloads, URLs, or credentials are attached.

**Release validation.** Focused telemetry, HTTP filtering, hosted Responses,
and crash/resume correlation tests pass locally. Hosted version `37` proved
the sampling/context fix with a version-pinned happy workflow
`run-trace-v37`: Application Insights recorded the hosted parents, all four
check executors, retry attempts, fan-in, final decision, and checkpoints in
one operation. Version `38` adds explicit transition spans and is the active
release.

The controlled version-38 retry workflow `run-trace-retry-v38` completed under
operation `aef9f18d5cd10af989b0b6049e69d8fd` and records
`workflow.stage.failure_injected`, `workflow.stage.retry_backoff`, retry
attempt, all four checks, fan-in, final decision, and checkpoints. The
intentional crash/resume workflow `run-trace-crash-v38` produced two
independent Responses roots with the shared run ID:
`3fbbbb75b0205d0f8dfc33960e79cc84` records initialization through the
medical-check crash, and `dc2150df48e1b058a8af9ad9ef8c84b6` records
checkpoint load, idempotency skips, remaining work, fan-in, final decision,
and completion. Every inspected span uses only safe workflow, action,
executor, check-type, attempt, delay, checkpoint, and Foundry identity
attributes.

**Release-test correction.** An earlier smoke command used a fixed run and
application ID and did not explicitly select the newly created immutable
agent version. A passing response could therefore be a historical
idempotency projection or an unpinned routing result rather than proof of the
new release. `make foundry-smoke` now generates fresh run/application IDs and
passes `--version "$AGENT_UNDERWRITING_HOSTED_VERSION"`. The corrected
version-38 smoke `run-hosted-smoke-20260806142557` completed with a matching
output run ID and trace `78dd8c2ea578661bbc5463f4925b8b1b`.

**Validation.** The Bicep template compiles and emits the secure
administrator-login/password properties. Bash syntax, exact-token rejection,
the make dry run, and generated schema DDL pass without invoking Azure
deletion. The DDL uses `CREATE ... IF NOT EXISTS` and creates the migration
column before the runtime role receives DML-only grants.

**Independent review.** Rubber Duck found the fresh-schema grant dependency
and the missing creation-time administrator login; both are fixed. Entra
authentication is deliberately retained but no Entra database administrator
or hosted-agent Entra principal is recreated because the approved hosted
runtime uses the dedicated password role over TLS. This becomes a separate
IaC requirement if the runtime moves back to Entra database authentication.
The destructive workflow deliberately has no data export or rollback; the
user explicitly authorized deletion of this readiness/test server and the
exact confirmation token remains required.

**Remaining release gate.** Confirm SKU availability, then perform the
authorized delete/recreate, schema bootstrap, runtime-credential setup,
readiness validation, deployment, smoke, E2E, trace evaluation, and
Application Insights evidence. The preflight query confirms
`Standard_D2ds_v5` is presently advertised for North Central US; the rebuild
script repeats that check before it permits deletion.

## Maintenance rule

Update this ledger in the same change set as any underwriting migration,
infrastructure, deployment, evaluation, telemetry, or recovery work. Every
entry must capture the observed failure or decision, RCA or research evidence,
the applied fix, validation performed, and any remaining blocker or next
action.

## 2026-08-10 - Existing-target deployment profile standardization

**Change**

- Added the shared version-1 non-secret deployment-profile contract to the
  Underwriting Foundry-public lane. The profile selects only the AZD
  environment, subscription, resource group, location, name prefix, and lane.
- Removed current-environment subscription, resource-group, location, and
  retained-resource-name defaults from the AZD bootstrap helper. It now
  requires those values from the selected AZD environment and obtains the
  PostgreSQL location only after the selected server identity is available.
- Made routine release routing app-only even when runtime or IaC-adjacent
  files change. Full provisioning remains an explicit separately approved
  operation and cannot be triggered by the release router.

**Why**

- A target switch must be a configuration change, not a source edit or an
  implicit reconciliation of PostgreSQL, networking, RBAC, Foundry
  connections, or secrets.

**Local validation**

- `bash deployment/tests/test-profile.sh` passed. It verifies profile
  application uses the Underwriting AZD project, profiles exclude secret and
  retained-resource fields, the release router remains app-only, and bootstrap
  rejects an incomplete selected environment before Azure commands run.
- `bash -n` passed for the changed shell scripts and `make -n
  foundry-profile-apply` parsed successfully.

**Release status**

- No Azure resource was provisioned, changed, or deployed. A future
  authorized target still requires its selected AZD environment's retained
  resource identities and lane-local secrets, followed by smoke, E2E,
  evaluation, and telemetry evidence.

## 2026-08-10 - Existing-target public release completed

**Change**

- Applied the approved resource-reuse provisioning step and released the
  Underwriting Foundry-public app-only lane from the selected
  `underwriting-foundry-public` AZD environment.
- Corrected the PostgreSQL readiness gate for the installed Azure CLI:
  flexible-server firewall-rule and database `show` commands require
  `--server-name` and `--name`; the removed `--rule-name` and
  `--database-name` arguments had stopped the initial release before app
  deployment.

**Validation**

- `make validate-full` passed before the release: lint, 43 backend tests,
  script tests, frontend checks, and local Playwright E2E.
- `az bicep build` passed with only the pre-existing
  `no-deployments-resources` warning. `azd provision --no-prompt` completed
  successfully with no resource changes.
- Live readiness passed for the Ready PostgreSQL server, TLS runtime URL,
  runtime credential, dual authentication, narrowed firewall rules, and
  existing `underwriting` database. The ACR succeeded and the backend managed
  identity retained `AcrPull`.

**Deployment and hosted evidence**

- Hosted agent version `42` deployed. Backend revision
  `azcawhcedyxchnbtmpubbe--0000021` and frontend revision
  `azcawhcedyxchnbtmpubfe--0000012` are Running.
- `https://azcawhcedyxchnbtmpubbe.salmoncliff-e93b7aa4.northcentralus.azurecontainerapps.io/health`
  returned HTTP 200; the frontend returned HTTP 200.
- Hosted smoke passed with
  `run-smoke-20260810195340-158524`.
- Deployed browser E2E passed with
  `run-hosted-happy-20260810195505-160963` and
  `run-hosted-recover-20260810195505-160963`.
- Foundry evaluation `eval_d0e6c3dfb31d44f0bb6b1e3d44cb194f` passed 1 of 1
  with zero failures or errors.
- Application Insights recorded 64 correlated rows for the two hosted E2E
  runs, including 3 requests and 61 dependencies, with zero exceptions.

**Issue and resolution**

- The first release attempt failed safely during PostgreSQL readiness, before
  any application deployment, because the script used obsolete CLI argument
  names. Replacing them with the current CLI contract made readiness pass; the
  subsequent complete release passed every gate. No compatibility runtime,
  secret fallback, infrastructure recreation, or database rebuild was added.

## 2026-08-10 - Final app-only release rerun

**Change**

- Re-ran the selected existing-target app-only release without provisioning or
  changing retained infrastructure.

**Evidence**

- Bicep compilation and live PostgreSQL readiness passed. Hosted agent version
  `43`, backend revision `azcawhcedyxchnbtmpubbe--0000022`, and frontend
  revision `azcawhcedyxchnbtmpubfe--0000013` are Running.
- Smoke passed with `run-smoke-20260810203807-206537`.
- Deployed E2E passed with `run-hosted-happy-20260810203934-208937` and
  `run-hosted-recover-20260810203934-208937`.
- Foundry evaluation `eval_4082061319e44f38b7e1520ae9122c7f` passed 1/1 with
  zero failures or errors.
- Application Insights recorded 64 correlated rows, including 3 requests and
  61 dependencies, for the two E2E runs; zero exceptions were present.
