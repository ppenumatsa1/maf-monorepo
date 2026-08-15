# Engineering Operating Model

## Purpose

This is the canonical delivery contract. Architecture intent and business rules
come from the team; skills provide current platform guidance; implementation
includes code, IaC, tests, and documentation; gates provide evidence.

## Runtime policy

This branch has three supported execution surfaces:

1. **Local full stack:** React, FastAPI, SSE, and PostgreSQL run through Docker
   or Make targets. This is the authoritative UI/API/event-contract surface.
2. **Public Foundry hosted agent:** `backend/foundry/main.py` exposes the same
   MAF service through the Responses protocol. It is intentionally not an HTTP
   replacement for the local FastAPI/SSE UI.
3. **Public hosted UI/API wrapper:** an external frontend Container App proxies
   same-origin API/SSE traffic to an internal FastAPI Container App. The wrapper
   uses its managed identity to call the Foundry Responses endpoint and shares
   PostgreSQL durable state with the hosted agent.

The portable public target is subscription
`7df95e88-701c-4693-af77-3159f83b558d`, resource group
`rg-maf-ora-foundry-public`, in `eastus2`. Resource names and endpoints are
deterministically bootstrapped and hydrated into the selected local AZD
environment. PostgreSQL remains the application-owned durable
workflow/checkpoint store. No GitHub deployment workflow is part of this
branch.

The dated, identifier-backed smoke, hosted Responses E2E, trace-evaluation, and
telemetry record is maintained in
[issues-changes-fixes.md](issues-changes-fixes.md). Repository configuration
describes the supported target; only the generated release-window verification
and reviewed ledger entry are evidence that a deployment is live.

## Non-negotiable contracts

- One MAF business workflow; deterministic triage is allowed only when Foundry
  model configuration is absent and never replaces orchestration.
- Stable local API/SSE event types remain `workflow.stage`, `tool.call`,
  `checkpoint.created`, `hitl.request`, `hitl.response`, and `workflow.output`.
- HITL rules remain deterministic and resumable. Approval completes; rejection
  escalates; duplicate responses are idempotent.
- Infrastructure permissions are declarative Bicep role assignments. The
  hosted-agent platform identity is created only after version deployment, so
  its sole runtime grant is converged idempotently as `Cognitive Services
  OpenAI User` at the Foundry account scope.
- Foundry trace evaluation requires the supported project-scoped
  `ApplicationInsights` connection in addition to runtime telemetry settings;
  `make foundry-up` verifies that connection after provisioning.
- Hosted PostgreSQL credentials are stored only in the deterministic
  project-scoped `CustomKeys` connection. Hosted versions contain the literal
  `${{connections.orderresolutionruntimesecrets.credentials.database_url}}`
  placeholder for both database variables; GET metadata, release metadata, and
  evidence must never contain the resolved URL.
- Foundry evaluation judges the exact conversations emitted by hosted E2E only
  after the configured minimum trace age, mitigating incomplete HITL-resume
  conversations reaching conversation-level evaluators.
- Foundry hosting remains Responses-native through `backend/Dockerfile.hosted`
  and `backend/foundry/main.py`.
- The browser never receives a Foundry endpoint credential or token. Native SSE
  event names remain stable; wrapper-mode SSE tails persisted events because the
  hosted agent and API wrapper run in separate processes.
- `GET /api/chat/stream/{thread_id}/ag-ui` and `POST /api/copilotkit` are
  optional, read-only selected-thread projections. They emit an allowlisted,
  redacted view of durable events: lifecycle names, safe tool categories and
  completion state, opaque valid checkpoint IDs, approval state, and generic
  terminal status. They never start, approve, reject, or resume a workflow.
  Order/policy data, MCP/RAG request or result content, prompts, raw model
  output, checkpoint payloads, credentials, and secrets stay behind the backend
  boundary. CopilotKit is the application integration, not the GitHub Copilot
  SDK.
- The native SSE timeline and durable workflow APIs remain the source of truth.
  Rich/AG-UI-compatible streams are additive views; they cannot rename or
  replace native event types or the checkpoint-keyed HITL contract.
- FastAPI health and SSE request telemetry is excluded in the public lane to
  avoid probe/long-lived-request noise; Foundry invocation, workflow, model, and
  HITL spans remain the required Application Insights signal.

## Delivery and validation

| Change | Required local gates | Required public hosted gates |
| --- | --- | --- |
| Application behavior | `make test`, `make eval-backend`, `make test-e2e` | None unless hosted behavior changes |
| HITL or persistence | Local gates plus targeted resume/idempotency coverage | Fresh ORD-1001 low-risk, ORD-1009 approval/resume, and damaged-item approval/resume E2E |
| Foundry runtime, IaC, release script | Local gates plus Bicep/script/profile validation | Azure preview, explicit bootstrap or non-mutating reuse, model/quota preflight, PostgreSQL schema/credential/readiness, app release, exact verification, smoke, hosted E2E, Foundry eval, telemetry, aggregate evidence |
| Documentation | Link and command accuracy checks | Update execution evidence when operations change |

GitHub Actions is credential-free CI only. It runs repository checks on
`ubuntu-latest` and never provisions or deploys Azure. The authenticated local
release command is:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE=../deployment/profiles/foundry-public.env
make foundry-bootstrap
make foundry-release
```

It runs local gates, performs a read-only model/quota preflight, securely
converges the runtime-secret project connection, deploys exact immutable image
digests, converges hosted identity RBAC, and runs
`foundry-verify` before hosted smoke/E2E, enforced Foundry evaluation,
Application Insights telemetry, and aggregate evidence. Provision is separate:
bootstrap creates the complete lane; output hydration then makes reuse
non-mutating. Schema creation, runtime credential provisioning, and readiness
are explicit PostgreSQL gates. Administrator bootstrap exclusively owns DDL;
production runtime startup sets `DB_SCHEMA_MANAGED_EXTERNALLY=true` and uses
only the required table DML and sequence privileges.

The release DAG keeps every gate while removing only unnecessary serial waits:
the selected local validation and Bicep compilation run together; the router
always chooses `app_only` while independently selecting quick or full
validation; one PostgreSQL readiness check precedes
runtime-connection convergence and backend/frontend/hosted parallel deployment;
exact deployment verification follows convergence; and evaluation waits for
fresh E2E evidence while E2E runs. The evaluator keeps its configured minimum
trace age for all three fresh conversations and requires explicit completion.
Telemetry starts only after E2E has persisted that evidence, and
`foundry-evidence` requires every artifact to share one release ID/window. See
`.azure/deployment-plan.md` for the validation recipe and proof template.

## Evidence handoff

For every deployment-impacting change, record in
`docs/design/issues-changes-fixes.md`:

- commit and changed surfaces;
- local gate results;
- model/quota preflight, exact Container App revisions/images, hosted
  version/image/RBAC, and conversation IDs;
- Foundry evaluation ID/run/result counts;
- App Insights trace/dependency/exception evidence;
- any evaluation-quality learning and the remediation chosen without weakening
  the configured evaluator threshold;
- known deferrals.

## Baseline scenarios

- `ORD-1001`: low risk, completes without HITL.
- `ORD-1009`: high amount (`185.0`), pauses for HITL and completes after approval.
- damaged item: pauses for HITL and completes after approval in hosted release
  E2E; rejection remains covered by the deterministic local contract suite.
