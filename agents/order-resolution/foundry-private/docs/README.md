# Order Resolution Documentation

This directory is the documentation entry point for the private Microsoft
Foundry order-resolution application.

## Current status

| Capability | Status |
| --- | --- |
| Local MAF workflow | Implemented |
| Private Foundry hosted agent | Implemented and release-verified |
| Private web application | Implemented and manually verified |
| Application Insights correlation | Implemented and manually verified |
| Teams Bot/channel and Activity configuration | Deployed |
| Microsoft 365 package and Shared publication | Deployed and manually verified |
| Adaptive Card approvals | Deployed and accepted for Approve, Reject, typed-decision blocking, replay rejection, and conversation isolation |
| Frontend dependency modernization | React 19.3, CopilotKit 1.79, Zod 4, Vite 8.3, and TypeScript 7 deployed and release-verified |

The current private web release and sanitized evidence are recorded in the
[review remediation release](issues-changes-fixes.md#review-remediation-release-2026-10-21).

## Product and behavior

- [Functional specification](functional-spec.md)
- [Business rules](business-rules.md)
- [User flow](userflow.md)
- [HITL approval conditions](hitl-approval-conditions.md)
- [Manual testing](manual-testing.md)

## Engineering

- [Technical specification](technical-spec.md)
- [Architecture](architecture.md)
- [API, event, and telemetry contracts](schema-io-telemetry.md)
- [Technology stack](techstack.md)
- [Project structure](projectstructure.md)
- [Implementation phases](implementation-phases.md)
- [Current codebase review](codebase-review.md)
- [Deployment flow](deployment-flow.md)
- [Engineering operating model](engineering-operating-model.md)

## Operations

- [Private Foundry and Teams runbook](customer-demo-runbook.md)
- [Private Foundry to Teams security and runtime design](teams-foundry-integration.md)
- [Issues, changes, fixes, and release evidence](issues-changes-fixes.md)

## Documentation rules

- Product behavior belongs in the functional specification and business rules.
- Runtime, API, data, deployment, and security details belong in the technical
  specification and architecture.
- Dated test/deployment results belong only in the evidence log; design
  documents link to the current evidence instead of duplicating run history.
- Customer data, tenant/subscription/user identifiers, live endpoint values,
  credentials, and secrets must not be committed to documentation.
- Mermaid source files live in `diagrams/` and must use a white
  background so they remain readable in dark previews.
