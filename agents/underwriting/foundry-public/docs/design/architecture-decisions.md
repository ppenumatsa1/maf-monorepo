# Architecture Decisions

## Purpose

This record captures the architecture decisions that define the Underwriting
Foundry Public system. It distinguishes the original domain decisions from the
2026-08-06 clean alignment to the standardized engineering and release
model.

## Initial Underwriting Decisions

### ADR-001: Use a MAF parent workflow with four child checks — superseded

**Original decision:** Model underwriting as one parent workflow that fans out
to risk, credit, medical, and driving child workflows, then fans in their
results.

**Why:** Each assessment is independently observable and recoverable, while the
final decision still depends on a complete, shared underwriting state.

**Original result:** The workflow retained explicit executor message contracts
and could show partial progress without emitting a premature decision.

**Status:** Superseded by ADR-011. This record remains for historical
accuracy; it is not the supported deployed workflow design.

### ADR-002: Keep the policy decision deterministic

**Decision:** Compute the underwriting decision and score breakdown from
deterministic policy rules before generating any LLM rationale.

**Why:** Explanation quality must not alter the approval, referral, conditional
approval, or decline outcome.

**Result:** The model enriches the decision with a rationale only; it cannot
override policy.

### ADR-003: Make PostgreSQL the durable workflow record

**Decision:** Store workflow runs, business state, events, terminal results,
idempotency records, and MAF checkpoints in PostgreSQL.

**Why:** Operators need durable history, and crash/resume requires a
restart-safe authoritative checkpoint store.

**Result:** Resume uses the latest `maf_checkpoints` record for the
`workflow_run_id`; replay-safe writes use idempotency protection.

### ADR-004: Provide an operator-facing workflow console

**Decision:** Provide a React UI and FastAPI surface for start, retry, crash,
resume, history, state, events, checkpoints, and observability data.

**Why:** The workflow is operational software, not a black-box model call.
Operators must be able to inspect the lifecycle and recover a failed run.

**Result:** AG-UI streaming and CopilotKit complement durable run projections;
they do not replace persisted history as the source of truth.

### ADR-005: Host production execution through Foundry Responses

**Decision:** Run the production workflow from `backend/foundry/main.py` using
the Foundry Responses protocol.

**Why:** The hosted agent must execute the same MAF workflow and write the same
durable data as the validated local application path.

**Result:** The internal API, reached only through the external frontend proxy,
starts or resumes hosted work, while the hosted agent owns production workflow
execution.

## 2026-08-06 Clean Alignment Decisions

### ADR-006: Adopt the standardized clean-cutover boundary model

**Decision:** Reorganize Underwriting around API routers and schemas,
application modules, core composition, infrastructure adapters, and modular
MAF packages.

**Why:** Explicit dependency boundaries improve testability, keep delivery
concerns separate from domain behavior, and give Underwriting the same
maintainable, independently runnable structure.

**Result:** The supported topology is:

- `backend/app/api/v1/routers` and `schemas` for transport concerns.
- `backend/app/modules/underwriting` for domain contracts, services, ports,
  events, and projections.
- `backend/app/core` for configuration, telemetry, and composition.
- `backend/app/infrastructure` for PostgreSQL and Foundry adapters.
- `backend/app/maf` for workflows, executors, middleware, prompts, tools, and
  runner construction.

### ADR-007: Perform a clean cutover without compatibility shims

**Decision:** Remove former route, repository, checkpointing, workflow, import,
and frontend fallback paths when their replacements are introduced.

**Why:** Parallel interfaces create ambiguous ownership, duplicate
orchestration risk, and an indefinite migration burden.

**Result:** Consumers use the canonical API and command contracts in one
cutover. No legacy endpoint aliases, adapter imports, shadow checkpoint stores,
or client fallback behavior are supported.

### ADR-008: Support native durable events and AG-UI as intentional surfaces

**Decision:** Persist Underwriting domain events as the system record and expose
AG-UI as a supported projection for the operator UI and CopilotKit.

**Why:** Durable events are required for replay, refresh, and auditability;
AG-UI is optimized for interactive streaming and assistant integration.

**Result:** AG-UI is not a compatibility layer or hidden second orchestration
path. Both surfaces derive from the same workflow run and durable projections.

### ADR-009: Keep browser, API, hosted-agent, and data boundaries separate

**Decision:** Use a public browser/UI boundary, an internal FastAPI adapter, a
Foundry hosted execution boundary, and PostgreSQL durable storage.

**Why:** The browser must not receive Foundry or database credentials, and the
internal adapter must not create a second production workflow runtime.

**Result:** Browser traffic is same-origin through the external frontend proxy;
the internal API uses the hosted Responses path for start/resume and reads
durable projections. The backend receives its TLS PostgreSQL URL through an ACA
secret, while the hosted agent resolves the same least-privilege credential
through the project `CustomKeys` connection.

### ADR-010: Make releases evidence-driven and policy guarded

**Decision:** Use one canonical release workflow with targeted local gates,
Foundry smoke/evaluation, telemetry verification, and a delivery ledger.

**Why:** Public-hosted readiness cannot be inferred from source changes or
partial deployment output.

**Result:** `Makefile`, Foundry scripts, validation routing, and repository
skills define the release path. Hosted readiness claims require dated evidence
in [issues-changes-fixes.md](issues-changes-fixes.md). PostgreSQL credential
rotation/readiness remains supported, while a rebuild remains explicitly
confirmed and destructive.

### ADR-011: Use one master workflow with direct underwriting executors

**Decision:** Replace the nested parent/child workflow design with one master
underwriting workflow. Its risk, credit, medical, and driving executors fan
out and fan in in one superstep.

**Why:** The deployed runtime needs one explicit graph and checkpoint shape for
the underwriting decision. Nested graph recovery would otherwise leave
ambiguous checkpoint ownership and a migration burden.

**Result:** Only checkpoints written by the deployed master direct-executor
graph are supported for resume. Version-40 nested-graph checkpoints are
unsupported after deployment. There is no compatibility workflow, checkpoint
migration path, or fallback; an affected pre-cutover run must start again.
This decision documents the cutover only and does not claim release success.

## Related Documents

- [Architecture](architecture.md) describes the implemented logical, process,
  development, and physical views.
- [Engineering operating model](engineering-operating-model.md) defines the
  delivery and release contract.
- [Issues, changes, and fixes](issues-changes-fixes.md) records dated
  operational evidence.
