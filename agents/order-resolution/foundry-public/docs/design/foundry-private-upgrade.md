# Foundry Private Upgrade Inventory for Order Resolution Public

> Temporary working document. Delete it after the Order Resolution public project
> has reached verified parity and the resulting contracts have been moved into
> its normal design, release, and issues/fixes documentation.
>
> **2026-10-21 status:** shared source parity has been implemented and the
> canonical public documentation is synchronized. This inventory is retained
> pending comprehensive local validation, reviewed public IaC/app-only
> execution, live Responses and Teams acceptance, evaluation, telemetry,
> aggregate evidence, and rollback verification. It is pending final removal,
> not current release evidence.

## Purpose

This document records the changes made to
`agents/order-resolution/foundry-private`. The same application and release
hardening work must be implemented in
`agents/order-resolution/foundry-public`.

The target is implementation parity, not a selective adoption exercise.
Topology-specific code can differ where public and private networking require
different mechanics, but shared behavior, package versions, security
boundaries, schema semantics, tests, and release evidence must remain aligned.
Order Resolution public must also preserve:

- one sequential `FoundryChatClient` / `SequentialBuilder` MAF workflow;
- durable checkpoint-keyed HITL pause/resume;
- PostgreSQL-backed checkpoints and projections;
- the internal FastAPI adapter and same-origin public frontend;
- Responses-native Foundry hosting;
- the existing app-only two-phase release contract;
- stable native SSE plus additive, redacted AG-UI and CopilotKit boundaries.

No environment-specific identifiers, endpoints, credentials, customer data,
or real operational values are included here.

## Parity contract

The two projects must perform the same work and produce the same user-visible
and operational behavior.

### Must remain in exact parity

- direct backend and frontend package versions;
- Python 3.13 application images and dependency-lock/wheelhouse policy;
- MAF workflow business rules and HITL outcomes;
- Responses behavior and structured `function_call_output` resume;
- Activity/Teams behavior, Adaptive Cards, action-token security, and replay
  handling;
- PostgreSQL schema semantics, external-schema mode, least-privilege grants,
  and hosted pool retirement;
- trusted workflow origin and cross-channel authorization;
- Azure AI Projects hosted-version APIs and protocol versions;
- evaluation retry/status handling;
- clean-build, smoke, E2E, evaluation, observability, and evidence gates;
- documentation of the shared implementation contract.

### Allowed differences

- private endpoints, VNet injection, Bastion, and private-runner execution
  versus the public network path;
- public/private Bicep modules and capacity checks that exist only because of
  the selected topology;
- environment profiles, resource names, identities, endpoints, and evidence;
- release command wiring required by each lane, provided both lanes enforce
  the same build, activation, test, evaluation, telemetry, and rollback gates;
- adapter placement required to preserve the public project's modular
  sequential MAF/SSE/AG-UI architecture.

Any other difference requires an explicit documented justification.

## Executive summary

The private project work creates the following public-project parity
requirements:

| Area | Order Resolution public action |
| --- | --- |
| Python and Foundry dependency modernization | Match direct versions, Python 3.13 images, lock policy, and hash-verified wheelhouse delivery. |
| Frontend modernization | Match React 19.3, CopilotKit 1.79, Zod 4, Vite 8.3, Playwright 1.64, ESLint 10.12, and the TypeScript 7/6 arrangement. |
| PostgreSQL runtime hardening | Match external-schema enforcement, least-privilege grants, pool retirement, schema parity tests, and applicable additive migrations. |
| Hosted runtime compatibility | Match Azure AI Projects APIs, AZD 1.36 output handling, evaluation polling hardening, and strict evidence status handling. |
| Release portability | Match clean-build wheelhouse prerequisites, Linux AMD64 targeting, profile validation, supported runner Python, and no-secret evidence. |
| Capacity and Azure validation | Match the incremental-capacity algorithm and preview safety rules; only topology-specific resource checks may differ. |
| Security review fixes | Match trusted origin, structured decisions, replay protection, and atomic card-action claims. |
| Teams, Bot Service, Activity, and Adaptive Cards | Implement the same connectivity and approval behavior while preserving public Responses/browser contracts. |
| Documentation model | Document the same implementation contract while retaining the public project's `docs/design/` organization. |

## 1. Backend and Foundry dependency modernization

### Runtime package baseline

The private project upgraded its direct runtime dependencies to:

| Package | Version |
| --- | ---: |
| `fastapi` | `0.156.3` |
| `uvicorn[standard]` | `0.54.0` |
| `pydantic` | `2.14.1` |
| `python-dotenv` | `1.2.4` |
| `httpx` | `0.28.1` |
| `aiohttp` | `3.14.5` |
| `azure-monitor-opentelemetry` | `1.8.11` |
| `azure-monitor-query` | `2.0.0` |
| `psycopg[binary]` | `3.3.6` |
| `psycopg-pool` | `3.3.3` |
| `agent-framework-core` | `1.22.0` |
| `agent-framework-orchestrations` | `1.3.2` |
| `agent-framework-foundry` | `1.15.0` |
| `azure-ai-agentserver-core` | `2.2.0` |
| `azure-ai-agentserver-activity` | `1.0.0b4` |
| `azure-ai-agentserver-responses` | `2.3.0` |
| `azure-ai-projects` | `2.7.0` |
| `azure-identity` | `1.26.0` |
| Microsoft Agents packages | `1.9.0` |

The development baseline became:

| Package | Version |
| --- | ---: |
| `pytest` | `9.1.1` |
| `pytest-asyncio` | `1.4.0` |
| `pytest-cov` | `7.1.0` |
| `ruff` | `0.17.1` |
| `black` | `26.10.1` |

### Compatibility decisions

- `azure-ai-projects` is intentionally held at `2.7.0`.
  `agent-framework-foundry==1.15.0` requires
  `azure-ai-projects>=2.2,<2.8`.
- Do not upgrade `azure-ai-projects` independently to the absolute latest
  release until Agent Framework expands its supported range.
- Transitive OpenTelemetry constraints can hold packages such as `wrapt`
  below their absolute latest releases. Treat this as a compatibility result,
  not automatically as an upgrade defect.
- The application and hosted images now use Python 3.13.
- The private runtime graph is captured in a 112-package hash-locked
  `requirements.lock`.
- Development dependencies are captured separately in
  `requirements-dev.lock`.

### Source changes

Private-project source files:

- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/requirements.lock`
- `backend/requirements-dev.lock`
- `backend/Dockerfile`
- `backend/Dockerfile.hosted`
- `scripts/foundry/ensure_backend_venv.sh`
- `scripts/foundry/build_python_wheelhouse.sh`

### Order Resolution public parity requirements

- Match the private direct dependency versions unless the resolver proves an
  unavoidable public-only conflict.
- Generate public lock files from the public requirement inputs rather than
  copying private lock bytes, but enforce the same direct versions and runtime
  policy.
- Run the complete public backend, hosted, evaluation, and release test
  suites before accepting the versions.
- Validate persisted MAF checkpoint compatibility before deploying a newer
  Agent Framework runtime. Preserve the current direct sequential workflow and
  do not introduce a compatibility workflow or alternate orchestration path.

## 2. Python 3.13 images and offline wheelhouse

### Changes

- Both backend and hosted Docker images were standardized on Python 3.13.
- Docker builds install from an ignored local wheelhouse with:
  - `--no-index`;
  - `--find-links`;
  - `--require-hashes`.
- Wheel generation explicitly targets:
  - platform `manylinux2014_x86_64`;
  - CPython `3.13`;
  - ABI `cp313`.
- This prevents an operator running macOS, Windows, ARM64, or another Linux
  variant from producing incompatible deployment wheels.
- The generated wheelhouse is ignored and is never committed.
- Every target that can build a backend or hosted image now prepares the
  wheelhouse first.

### Clean-build fix

The review found that clean app-only or Docker builds could fail because
`.wheels/` was not guaranteed to exist. `foundry-python-wheelhouse` was added
as a prerequisite to:

- `up`;
- `docker-test`;
- `foundry-app-deploy`;
- `foundry-hosted-app-deploy`;
- `foundry-app-only-release`.

### Order Resolution public parity requirements

- Order Resolution public already has a two-phase immutable image release. Integrate the
  same wheelhouse policy into the existing build stage without changing
  release ordering.
- Keep backend and hosted image construction concurrent if that is part of the
  current public release budget.
- Do not commit wheel files.
- Keep the Microsoft package proxy as the primary index and use the approved
  fallback only where the repository already permits it.
- Add a clean-worktree build test that proves the Docker contexts do not rely
  on ignored artifacts left by a developer.

## 3. Private runner Python toolchain

### Problem found during the current release

The upgraded development graph no longer installs on the private runner's
Ubuntu Python 3.10. The release stopped before deploying any revision when a
dependency requiring Python 3.11 or newer could not resolve.

### Fix

- `scripts/foundry/ensure_backend_venv.sh` now selects:
  1. explicit `BACKEND_PYTHON_BIN`;
  2. Python 3.13, 3.12, or 3.11 on `PATH`;
  3. a user-managed Python under `$HOME/.local/bin`;
  4. system `python3` only as a final candidate.
- It fails clearly if the selected interpreter is older than Python 3.11.
- `scripts/github/bootstrap_vm_runner_host.sh` installs `uv` through the
  approved Python package feeds and installs an isolated Python 3.13 runtime
  when the host has no supported interpreter.
- The release portability contract now verifies this runner requirement.

### Order Resolution public parity requirements

- Check the public release host before copying this change. If it already
  guarantees Python 3.13, only the version guard may be needed.
- Do not silently continue on Python 3.10.
- Keep the runner's application/evaluation Python separate from the Python
  version inside deployed images.

## 4. FastAPI and PostgreSQL runtime hardening

### FastAPI lifecycle

- Deprecated startup-event handling was migrated to FastAPI lifespan.
- Startup continues to validate external database schema and connectivity.
- Production does not execute DDL.

Private source:

- `backend/app/main.py`

### PostgreSQL pool retirement

Foundry-hosted sessions previously retained too many idle PostgreSQL
connections. The private project added configurable pool limits and hosted
defaults:

| Setting | Hosted default |
| --- | ---: |
| Minimum connections | `0` |
| Maximum connections | `2` |
| Maximum idle seconds | `30` |

Private source:

- `backend/app/core/database.py`
- `backend/tests/test_database.py`
- `scripts/foundry/deploy_hosted_container.py`

### External schema and runtime grants

- The administrator-owned schema is applied before activating the new hosted
  version.
- Runtime receives only:
  - database `CONNECT`;
  - schema `USAGE`;
  - required table DML;
  - required sequence `USAGE`.
- Runtime sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Tests enforce exact agreement between canonical schema tables and the
  runtime grant allowlist.

Private source:

- `backend/app/sql/schema.sql`
- `scripts/foundry/postgres_runtime_credentials.py`
- `scripts/foundry/provision_postgres_runtime_credentials.sh`
- `scripts/foundry/verify_private_postgres_readiness.sh`
- `scripts/foundry/tests/test_postgres_runtime_credentials.py`

### Order Resolution public parity requirements

- Preserve the public project's `orderresolutionruntimesecrets` CustomKeys connection
  and connection-placeholder contract.
- Never place the resolved database URL in hosted-agent environment metadata.
- Use the same hosted pool defaults `0/2/30` unless load testing documents a
  required lane-specific override.
- Preserve the existing public-project rule that production runtime validates
  schema but performs no DDL.

## 5. Current Azure AI Projects and hosted deployment APIs

### Changes

- Hosted deployment uses current `AIProjectClient` APIs.
- Immutable hosted versions use `agents.create_version`.
- Image registration uses `HostedAgentDefinition`,
  `ContainerConfiguration`, and protocol records.
- The exact image is pushed to ACR and verified by digest before activation.
- Active hosted version metadata is persisted only after successful
  activation.
- No prior hosted version is deleted during a routine release.

Private source:

- `scripts/foundry/deploy_hosted_container.py`
- `scripts/foundry/deploy_hosted_container.sh`
- `infra/foundry-hosted/azure.yaml`

### Order Resolution public parity requirements

- Order Resolution public already persists exact hosted digest/version state.
  Port the same current Azure AI Projects API behavior into its release
  orchestrator.
- Preserve the public project's requirement that the hosted version is activated
  and recorded before backend/frontend deployment.
- Keep routine mode hard-coded to `app_only`.

## 6. AZD 1.36 and release-harness compatibility

### Hosted invocation output

AZD 1.36 returns customer-facing response text instead of the older embedded
workflow JSON shape. The private E2E harness was updated to:

- parse the assigned conversation ID from AZD output;
- query durable PostgreSQL workflow state;
- verify approvals, checkpoints, and required events from the authoritative
  persistence model;
- avoid exposing internal workflow JSON to the client.

Private source:

- `scripts/github/foundry_hosted_e2e.sh`

### Evaluation polling

Foundry evaluation polling occasionally returned a transient empty or malformed
in-progress response. The evaluator now retries only the recognized transient
`JSONDecodeError` condition inside the existing timeout. Authorization,
service, configuration, and other failures still fail immediately.

Private source:

- `backend/evals/foundry_eval_runner.py`
- `backend/tests/test_foundry_eval_runner.py`

### Successful evaluation status

The current API reports a successful evaluation run as `completed`, not
`passed`. Evidence reuse and strict gating were updated accordingly.

Private source:

- `scripts/foundry/collect_private_release_evidence.sh`

### Order Resolution public parity requirements

- Check whether the public-project E2E harness still depends on embedded AZD
  response JSON.
- Prefer durable workflow projections for business assertions.
- Port only the narrowly classified evaluation polling retry.
- Keep strict zero-failed, zero-errored, and zero-skipped evaluator gates.

## 7. Frontend modernization

### Package baseline

The private frontend now uses:

| Package | Version |
| --- | ---: |
| `@copilotkit/react-core` | `1.79.0` |
| `react` / `react-dom` | `19.3.0` |
| `zod` | `4.6.7` |
| `@playwright/test` | `1.64.0` |
| `@types/node` | `24.19.2` |
| `@types/react` / `@types/react-dom` | `19.3.0` |
| `@vitejs/plugin-react` | `6.1.2` |
| `eslint` | `10.12.0` |
| `eslint-plugin-react-hooks` | `7.1.1` |
| `eslint-plugin-react-refresh` | `0.5.7` |
| `globals` | `17.13.0` |
| `typescript-eslint` | `8.71.2` |
| `vite` | `8.3.4` |

### TypeScript 7 compatibility arrangement

Current `typescript-eslint` requires the TypeScript 6 compiler API. The private
frontend therefore uses:

- `@typescript/native` as an alias of TypeScript 7 to provide `tsc`;
- `typescript` as an alias of `@typescript/typescript6` for
  `typescript-eslint` compiler API compatibility.

This is intentional. Do not replace the TypeScript 6 alias with TypeScript 7
until the ESLint ecosystem officially supports the new compiler API.

### Zod 4 and CopilotKit

- Zod moved from version 3 to version 4.
- No private application source migration was needed because the frontend did
  not directly call Zod APIs.
- CopilotKit's existing `/v2` API usage remained compatible.
- All practical packages resolved through the Microsoft npm proxy.
- The optional musl Rolldown binding remains optional on glibc systems.
- Forced npm audit remediation was rejected because it proposed an incorrect
  CopilotKit downgrade.

Private source:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/README.md`

### Validation performed

- clean Microsoft-feed `npm ci`;
- ESLint;
- TypeScript 7 production build;
- four focused CopilotKit/AG-UI Playwright tests;
- complete local browser E2E;
- Docker build and HTTP smoke.

### Order Resolution public parity requirements

- Order Resolution public has stable native SSE and a redacted
  selected-thread AG-UI/CopilotKit boundary. Run its complete
  allowlist, selected-run, streaming, and browser suites.
- Search public-project source for direct Zod usage before upgrading.
- Preserve the browser rule that Foundry and PostgreSQL are never called
  directly.
- Regenerate the public lock through its approved `.npmrc`; do not copy
  the private lockfile.

## 8. Teams, Activity Protocol, Bot Service, and Adaptive Cards

This section is the primary connectivity delta between private and public
Order Resolution. The public project currently uses Responses for browser/API
traffic. Adding Teams must remain additive: preserve Responses, native SSE,
durable history, AG-UI, CopilotKit, and the same business workflow.

### Infrastructure and publication changes

- Added Bot Service and `MsTeamsChannel` Bicep.
- Added Responses plus Activity protocol declaration.
- Added controlled, merge-preserving Activity endpoint reconciliation.
- Preserved Responses and Entra authorization while adding Activity and
  `BotServiceRbac`.
- Added Shared Microsoft 365 package generation/publication automation.
- Added rollback planning that removes Teams/Activity access without damaging
  the public Responses deployment.
- Added publication manifests, fixture tests, and sanitized local evidence.

Private source:

- `infra/foundry-hosted/iac/teams/`
- `infra/foundry-hosted/teams-publication.json`
- `scripts/foundry/reconcile_activity_endpoint.py`
- `scripts/foundry/publish_teams_agent.py`
- `scripts/foundry/tests/test_activity_endpoint_reconciler.py`
- `scripts/foundry/tests/test_teams_publishing.py`
- `docs/teams-foundry-integration.md`

### Dual-protocol runtime

- One hosted process composes Responses and Activity hosts.
- Business workflow logic remains shared.
- Teams-specific behavior stays in the channel adapter.
- Responses remains available for private programmatic invocation.

Private source:

- `backend/foundry/main.py`
- `backend/foundry/teams_cards.py`
- `infra/foundry-hosted/azure.yaml`

### Adaptive Card security

- Cards contain opaque random action tokens only.
- Token persistence stores token, user, and conversation hashes.
- Tokens are bound to workflow, checkpoint, decision, user, and conversation.
- Tokens expire and are one-time.
- Wrong-user/conversation actions fail.
- Replay fails.
- Resolved cards replace the pending card in place.
- Real Microsoft SDK model tests cover the required serialized
  `Attachment.contentType` alias.

### Order Resolution public decision

Teams parity is mandatory. Implement it as a reviewed workstream while keeping
the public browser/API path unchanged. The design must define:

- who is authorized to approve an order-resolution action;
- what order/customer information is allowed in Teams;
- channel-specific privacy and retention;
- checkpoint/action binding;
- tenant publication and administrator approval;
- telemetry content restrictions.

## 9. HITL authorization and structured-decision hardening

The full private code review found six actionable issues. Four were HITL or
release-security defects.

### Trusted workflow origin

Workflow runs now persist a server-selected origin:

- `api`;
- `responses`;
- `teams_activity`.

The client cannot choose or override this value.

### Cross-channel approval boundary

- Responses can resume only Responses-originated approvals.
- Responses cannot resolve Teams Activity checkpoints.
- Teams Activity checkpoints require the bound card action.

### No free-form approval inference

- Free-form conversational text never becomes an approval decision.
- Structured decision metadata or `function_call_output` is required for the
  Responses approval path.
- Standalone Teams decision words are blocked only when a checkpoint is
  pending and direct the user to the card.
- Ordinary messages containing words such as `yes`, `no`, `approve`, or
  `reject` remain normal conversation text.

### Structured Responses wire and persistence contract

- Parse structured decisions from the Agent Server request and from
  `ResponseContext.get_input_items()`; the latter is the supported SDK surface
  when the reduced handler payload does not retain all request items.
- Send `function_call_output` as an actual Responses JSON body. Do not pass
  that JSON through AZD 1.31 `ai agent invoke --input-file`, which wraps the
  document as ordinary text.
- Use named dictionary-row access when reading persisted workflow origin. This
  authorization lookup must fail closed rather than bypassing the
  cross-channel boundary or raising after a valid structured decision.
- Contract tests must cover the SDK input-item path, origin lookup, raw
  structured request, exact checkpoint resume, and persisted approval state.

### Atomic card-action claim

The previous validation-then-consume flow had a race. It was replaced with:

1. `claim_action`;
2. workflow resume;
3. `complete_action`;
4. failure-safe `release_action` only while the approval remains pending.

Approve and Reject share an action batch. One PostgreSQL statement moves the
winner to `processing` and the sibling to `superseded`. Concurrent requests
cannot both resume the same checkpoint.

Private source:

- `backend/app/sql/schema.sql`
- `backend/app/modules/order_resolution/ports.py`
- `backend/app/modules/order_resolution/service.py`
- `backend/app/infrastructure/persistence/workflow_run_repository.py`
- `backend/app/infrastructure/persistence/teams_card_action_repository.py`
- `backend/foundry/main.py`

### Order Resolution public parity requirements

- The public project already has a Responses-native path. Add trusted origin
  only when Teams/Activity becomes a second approval channel.
- Keep browser/API approvals on the existing structured
  `function_call_output` path and bind Teams approvals to card actions.
- Independently review the current public resume API for:
  - server-selected decision authority;
  - idempotent concurrent resume;
  - no free-form approval inference;
  - checkpoint/run/user binding;
  - replay protection.

## 10. Database migration added for Teams authorization

The private schema added:

- `workflow_runs.origin_channel`;
- `teams_card_actions.batch_id`;
- card status `processing`;
- idempotent migration statements for existing databases.

Existing action rows receive generated batch IDs. The old status constraint is
replaced to include `processing`.

The migration must run through the administrator-owned private-runner schema
step before activating a hosted version that expects it.

Port the same multi-channel card schema semantics into the public schema and
apply the additive migration before activating a Teams-capable hosted version.

## 11. Capacity preflight and existing-resource awareness

### Problem

Preflight previously required unused quota even when the exact healthy
resource already existed. This could block a no-growth app-only release at
fully consumed quota.

### Fix

Preflight now calculates incremental need:

- matching healthy existing resource: no additional quota required;
- missing, replaced, resized, or expanded resource: capacity/quota required.

Covered resource types include:

- Search;
- runner VM;
- Container Apps environment;
- AI Services account;
- exact model deployments.

It still validates:

- providers;
- region and SKU availability;
- exact runner SKU restrictions;
- model version/SKU availability;
- quota for actual incremental capacity.

Private source:

- `scripts/foundry/capacity_preflight.py`
- `scripts/foundry/tests/test_capacity_preflight.py`
- `scripts/foundry/preflight_private_release.sh`

### Order Resolution public parity requirements

- Port the same incremental-capacity logic into the public project's model,
  PostgreSQL, ACA, and release readiness gates.
- The public lane does not need private-runner or private-endpoint checks for
  routine release, but Teams and model capacity checks must still be
  resource-aware.
- Preserve the core rule: app-only release validation should not demand quota
  for an already deployed resource that is not changing.

## 12. Deployment profiles, confidentiality, and portability

### Changes

- Target-specific values come from ignored external deployment profiles.
- Shared loaders validate and export profile inputs.
- Generic code no longer carries target-specific fallback identifiers.
- Missing required values fail closed.
- Logs and evidence avoid tenant, subscription, user, host, secret, and
  customer values.
- Generated packages, wheelhouses, release artifacts, and evidence are ignored
  or sanitized.
- Profile tests verify explicit local profiles and canonical profile behavior.

Private source:

- `scripts/foundry/private_profile.sh`
- `scripts/foundry/bootstrap_private_azd_environment.sh`
- `scripts/foundry/validate_private_runner_environment.sh`
- `scripts/foundry/tests/test_private_profile_selection.py`
- `scripts/foundry/tests/test_release_portability_contract.sh`
- deployment profile templates under the shared deployment folder.

### Order Resolution public parity requirements

- The current public README still names a concrete public target.
  Decide separately whether that remains intentional repository configuration
  or should move to an ignored profile.
- Never copy the private environment's profile or values.
- Retain public-project resource names and release modes.

## 13. App-only release and Azure validation

### Private release rules

- Routine release is app-only.
- Full Bicep reconciliation is not part of an app-only release.
- A non-mutating preview is reviewed before release.
- Preview must contain no unexpected create, delete, replace, network, RBAC,
  scaling, or stateful-resource operation.
- Database migration/readiness runs before app activation.
- Backend/frontend Container App revisions and the hosted version are immutable.
- Prior hosted versions remain available for rollback.

### Current validation behavior

- Existing-resource capacity preflight passed without requiring duplicate
  quota.
- The non-mutating preview completed with zero Create, Delete, or Replace
  operations.
- Azure API/default-property readback differences were recorded but not
  applied.
- No infrastructure reconciliation was authorized.

### Order Resolution public parity requirements

- Order Resolution public already enforces app-only release and a two-phase immutable
  flow. Add every private release hardening gate to that workflow without
  replacing the public lane's command structure.
- Preserve its 15-minute app-only-to-telemetry budget.
- Preserve backend internal ingress and the same-origin frontend proxy.

## 14. Smoke, E2E, evaluation, and observability evidence

### Private validation matrix

The completed local/private validation included:

- backend Ruff;
- 170 backend tests;
- real concurrent PostgreSQL Approve/Reject claim test;
- deterministic evaluation `10/10`;
- release portability contracts;
- upstream Foundry private-sample baseline contract;
- Activity endpoint tests;
- Teams publication tests;
- Bot/Teams Bicep tests;
- clean frontend Microsoft-feed install;
- frontend ESLint and TypeScript 7 build;
- focused CopilotKit/AG-UI Playwright tests;
- complete local browser E2E;
- backend and hosted Docker builds;
- 112 Linux AMD64 wheel verification;
- Bicep compilation;
- official `azure.yaml` schema validation;
- packaging of all AZD services;
- live capacity and policy review;
- static least-privilege RBAC review.

Prior deployed modernization acceptance also verified:

- Responses low-risk and multi-turn completion;
- approval checkpoint resume;
- Activity Approve/Reject, wrong-conversation, replay, and card creation;
- Application Insights correlation;
- PostgreSQL dependency spans;
- no unexpected exceptions;
- Foundry `task_completion` and `coherence` strict evaluation.

### Evidence principles to reuse

- Generate fresh release-specific conversation IDs.
- Correlate request, hosted workflow, model, PostgreSQL, and evaluation spans.
- Keep message content and database details redacted.
- Accept evidence only when its timestamps are newer than the release start.
- Do not silently reuse stale evidence.
- Distinguish report-only evaluator execution from strict release pass/fail
  aggregation.
- Record exact artifacts in an ignored release directory and summarize only
  sanitized results in the tracked issues/fixes ledger.

## 15. Documentation synchronization

The private project documentation was comprehensively synchronized:

- `agents.md`;
- root and component READMEs;
- `.github/copilot-instructions.md`;
- deployment plan;
- functional, business-rule, technical, architecture, schema, flow, stack,
  HITL, operations, testing, and demo documents;
- Teams integration documentation;
- Mermaid sources and renders.

Important documentation decisions:

- Product/design documents describe current contracts.
- Exact release IDs, test counts, timing, and telemetry counts belong in one
  dated evidence ledger rather than being duplicated across every document.
- Local validation must not be described as deployed behavior.
- Historical evidence remains labeled as historical.
- Tracked documentation contains no environment-specific identifiers.

The private project flattened `docs/design/` into `docs/`. Order Resolution
public should retain `docs/design/`, where its canonical contracts currently
live.

## 16. New and materially changed private-project files

### New runtime/security files

- `backend/app/infrastructure/persistence/teams_card_action_repository.py`
- `backend/foundry/teams_cards.py`
- `backend/tests/test_teams_card_action_repository.py`

### New dependency/release files

- `backend/requirements.lock`
- `backend/requirements-dev.lock`
- `scripts/foundry/build_python_wheelhouse.sh`
- `scripts/foundry/capacity_preflight.py`
- `scripts/foundry/tests/test_capacity_preflight.py`
- `scripts/foundry/tests/test_private_profile_selection.py`
- `scripts/foundry/tests/test_upstream_baseline_contract.py`

### New Teams/Activity files

- `infra/foundry-hosted/iac/teams/`
- `infra/foundry-hosted/teams-publication.json`
- `scripts/foundry/reconcile_activity_endpoint.py`
- `scripts/foundry/publish_teams_agent.py`
- Activity/publication fixtures and tests under
  `scripts/foundry/tests/`.

### Major modified areas

- `Makefile`
- backend and hosted Dockerfiles
- hosted entrypoint
- persistence repositories and schema
- Foundry deployment/evaluation/evidence scripts
- private profile, preflight, PostgreSQL, image, runner, and portability scripts
- frontend dependency files
- Azure YAML and Bicep
- repository instructions and documentation.

## 17. Recommended Order Resolution public alignment sequence

### Phase 1: Parity audit

- [x] Diff every shared application, package, schema, test, and release
  contract against the private baseline.
- [x] Resolve public-project runtime and development graphs independently.
- [x] Identify current Python versions on local, CI, and release hosts.
- [x] Match frontend direct dependency versions and review audit results.
- [x] Search for direct Zod API usage.
- [x] Match Azure AI Projects and AZD invocation behavior.
- [x] Match evaluation result status and polling behavior.

### Phase 2: Dependency and image modernization

- [x] Upgrade compatible Python direct dependencies.
- [x] Add/rebuild hash-locked runtime and development locks.
- [x] Standardize application images on Python 3.13.
- [x] Add a Linux AMD64 CPython 3.13 wheelhouse.
- [x] Make every image-building target depend on wheelhouse generation.
- [x] Upgrade frontend packages through the Microsoft npm proxy.
- [x] Adopt TypeScript 7 plus the TypeScript 6 compiler API alias if still
  required by `typescript-eslint`.

### Phase 3: Runtime and persistence hardening

- [x] Migrate deprecated FastAPI lifecycle hooks.
- [x] Match PostgreSQL hosted pool sizing and idle retirement.
- [x] Verify `DB_SCHEMA_MANAGED_EXTERNALLY=true` everywhere in production
  configuration and contract tests.
- [x] Verify runtime grants exactly match required schema objects.
- [x] Review concurrent checkpoint/resume and idempotency behavior.
- [x] Add trusted origin and action-token logic as part of the Teams/Activity
  workstream.

### Phase 4: Release portability

- [x] Ensure release hosts use Python 3.11+; prefer an isolated Python 3.13
  toolchain.
- [x] Validate clean-worktree image-build prerequisites and wheelhouse
  portability contracts.
- [x] Remove target-specific fallback values from generic scripts.
- [x] Adopt external ignored deployment
  profiles.
- [x] Make capacity checks incremental for existing matching resources.
- [x] Preserve the app-only, exact-digest, hosted-first deployment sequence.

### Phase 5: Acceptance and evidence

- [x] Run `make test`.
- [ ] Run the remaining comprehensive local-validation matrix.
- [ ] Run `make test-e2e`.
- [ ] Run the existing public package/build/readiness/model/runtime
  connection gates.
- [ ] Run app-only deployment.
- [ ] Run hosted smoke.
- [ ] Run Foundry evaluation.
- [ ] Run deployed browser E2E.
- [ ] Verify Application Insights request, hosted workflow, model, PostgreSQL,
  retry, checkpoint, HITL, sequential-stage, and workflow-output correlation.
- [ ] Verify no sensitive order/customer or model content is recorded.
- [ ] Record fresh evidence in the public project's normal issues/fixes ledger.

### Phase 6: Teams connectivity

- [x] Add Bot Service and `MsTeamsChannel` through Bicep.
- [x] Add merge-preserving Activity reconciliation while retaining Responses
  and Entra authorization.
- [x] Add Shared publication/package automation and rollback planning.
- [x] Add opaque, expiring, one-time card actions bound to workflow,
  checkpoint, user, and conversation.
- [x] Add trusted workflow origin and cross-channel approval isolation.
- [ ] Run approve, reject, wrong-conversation, replay, concurrent-decision,
  fresh-conversation, and telemetry acceptance.
- [x] Keep sensitive order/customer data out of Teams cards and telemetry.

## 18. Permitted lane differences

- Keep the public project's modular sequential MAF workflow, native SSE,
  selected-thread AG-UI, and CopilotKit file boundaries while matching private
  runtime behavior and tests.
- Do not copy private network topology into the public lane.
- Do not copy private resource names, profile values, release IDs, endpoints,
  or evidence.
- Omit only database objects that are demonstrably private-topology-specific;
  Teams/HITL security objects are shared parity requirements.
- Retain the public `docs/design/` organization.
- Retain the public release command structure while adding the same build,
  activation, verification, rollback, and evidence gates.
- Generate lane-specific frontend and Python locks from identical direct
  version requirements; do not copy lock bytes across projects.

## 19. Current private-release status at document creation

- All six code-review findings are implemented.
- Local backend, frontend, Docker, packaging, Bicep, capacity, policy, and RBAC
  validation passed.
- PostgreSQL migration and least-privilege readiness passed from the private
  runner.
- The release preview contained no Create, Delete, or Replace operation.
- A runner Python 3.10 compatibility failure was found before deployment and
  fixed by adding isolated Python 3.13 runner support.
- Final app-only release `20261021T180156Z-4e57d58ce4df` activated hosted-agent
  version 17 and new backend/frontend revisions without infrastructure
  reconciliation.
- Hosted Responses E2E passed for three fresh conversations. Application
  Insights correlated 279 rows, four evaluation-eligible spans, all three
  conversations, and zero exceptions.
- Foundry `task_completion` and `coherence` each passed 3/3 with zero failed,
  errored, or skipped results.
- Telemetry was accepted in about 6m 06s and the final evidence bundle in about
  6m 30s, within the 15-minute app-only release budget.
