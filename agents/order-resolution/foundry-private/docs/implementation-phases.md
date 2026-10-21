# Implementation Phases

## Phase 1 (Completed)

- Backend orchestration scaffold complete.
- SSE event model complete.
- HITL + checkpoint + memory complete.
- Evals baseline complete.
- Design docs complete.

## Phase 2 (Completed)

- Private Foundry hosted parity with VNet/private endpoint networking, PostgreSQL runtime configuration, App Insights telemetry, and HITL trace correlation.
- Keep `WORKFLOW_MODE=maf_sdk`, `STORE_PROVIDER=postgres`, `RAG_PROVIDER=pgvector`, and `MEMORY_PROVIDER=postgres` for local/hosted parity.
- Keep HITL rules deterministic and preserve frontend/API event contracts.

## Phase 3 (Completed)

- Compatibility shims have been removed now that local and private-hosted parity is green.
- Add a MAF middleware seam for telemetry/correlation, event enrichment/redaction, streamed model usage observation, session/run context, and explicit failure-event behavior.
- Added additive, redacted selected-thread AG-UI and CopilotKit projections
  while preserving native SSE as the stable workflow contract.
- Foundry-hosted runtime uses one dual-protocol Responses and Activity host.
- Keep hosted/runtime namespaces limited to the current package layout; do not reintroduce legacy `backend/app/foundry/*` adapter namespaces.
- Keep Azure AI Search deferred until Foundry-hosted retrieval architecture is proven.

## Phase 4 (Completed)

- Completed and manually accepted the private browser-to-Foundry workflow.
- Added app-only release separation, private PostgreSQL readiness, hosted
  activation, browser/hosted HITL E2E, telemetry correlation, and strict
  per-evaluator release gates.
- Added current documentation index, functional specification, business rules,
  technical specification, and validated architecture diagrams.

## Phase 5 (Completed)

- Bot Service, `MsTeamsChannel`, Activity configuration, Shared publication,
  authentication, and normal Teams invocation are deployed and verified.
- Adaptive Card approvals are deployed and verified with
  checkpoint, user, conversation, decision, expiry, and replay binding.
- Responses and Activity acceptance, telemetry, strict evaluation, and
  rollback preservation are release-verified.

## Phase 6 (Completed)

- Frontend dependencies are modernized to React 19.3, CopilotKit 1.79, Zod 4,
  Vite 8.3, and TypeScript 7 with the TypeScript 6 API retained for
  `typescript-eslint`.
- Clean install, lint, production build, focused selected-thread Playwright,
  container build, HTTP smoke, Azure deployment, hosted E2E, telemetry, and
  strict evaluation passed.
- The security/architecture review findings are remediated and documented in
  the current evidence ledger.

## Later phases

- Keep the multi-agent monorepo catalog direct and each deployable project
  self-contained, with local ownership of code, IaC, CI/CD, SRE/runbooks, and
  documentation.
- Keep Foundry-hosted parity gates (conversation/history parity, HITL resume parity, traces, and rollback validation) aligned with the single shared workflow behind both protocols.
- Implement Azure AI Search only if the post-Foundry retrieval architecture still needs it.
- Harden auth/security, add richer evaluation metrics, and expand CI gating.

## Project Milestone History (Quick Pickup)

| Milestone                               | Project history summary                                                                                                                                                                  |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M0: Product intent defined              | Demo objective finalized: sequential multi-agent order-resolution flow with deterministic HITL safety, checkpoint/resume, memory continuity, SSE timeline, telemetry, and eval coverage. |
| M1: Local workflow foundation complete  | Local runtime path became the default (`WORKFLOW_MODE=maf_sdk`), with durable Postgres-backed run/event/checkpoint/approval history and stable frontend/API event contracts.             |
| M2: Private Foundry-hosted parity      | Hosting and persistence moved to the private Foundry lane while preserving local behavior and contracts to minimize migration risk.                                                     |
| M3: Architecture hardening              | Compatibility shims removed; middleware and rich-stream seams added without breaking legacy SSE; backend/package boundaries standardized.                                                |
| M4: Foundry-hosted runtime              | Dual-protocol Responses and Activity entrypoint is the current hosted path; stable workflow/event contracts remain unchanged.                                                               |
| M5: Safe operational policy             | Postgres projection remains the source of truth for UI/test contracts; deterministic HITL and replay rules stay enforced.                                                                   |
| M6: Private web release accepted        | The private web release passed browser, hosted HITL, telemetry, and strict evaluation gates and was manually accepted.                                                                     |
| M7: Teams publication                   | Shared publication, normal invocation, and secure Adaptive Card approve/reject are verified.                                                                                                |
| M8: Dependency modernization            | Python 3.13 locks and the TypeScript 7/Zod 4 frontend graph are deployed and release-verified with hosted-agent version 17.                                                               |

## Current Chapter (What To Assume Today)

- User-facing contracts stay stable: event names, HITL semantics, pagination/read models, and workflow history APIs.
- Foundry hosting is dual-protocol; keep rollback discipline and parity gates for behavior, HITL, and telemetry.
- Treat traces as observability only; do not use traces as workflow state or approval source of truth.
- Treat Teams as a separate channel journey over the same hosted workflow; do
  not create a second business workflow.

Delivery ownership and gate authority are documented in
`engineering-operating-model.md`.
