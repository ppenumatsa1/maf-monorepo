# Order Resolution Azure-Hosted Documentation

This directory is the documentation entry point for the FastAPI-hosted Order
Resolution application.

## Current status

| Capability | Status |
| --- | --- |
| Local MAF workflow | Implemented |
| FastAPI backend and React frontend | Implemented |
| Durable PostgreSQL workflow and HITL state | Implemented |
| External frontend and internal backend Container Apps topology | Implemented in the deployment contract |
| PostgreSQL managed-identity access | Implemented in the runtime and infrastructure contract |
| Foundry model inference | Optional |
| Foundry evaluation | Report-only and release-blocking |
| Application Insights correlation | Implemented in the release contract |
| Current Azure deployment | Determined only by fresh release evidence; repository configuration alone is not proof |

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

- [Customer demo and operator runbook](customer-demo-runbook.md)
- [Issues, changes, fixes, and release evidence](issues-changes-fixes.md)
- [Deployment plan](../.azure/deployment-plan.md)

## Documentation rules

- Product behavior belongs in the functional specification and business rules.
- Runtime, API, data, identity, deployment, and security details belong in the
  technical specification and architecture.
- Dated validation and release results belong in the evidence ledger.
- Azure target values come from a validated, ignored operator profile. Do not
  commit tenant, subscription, user, resource, endpoint, credential, connection
  string, or operator-network values.
- FastAPI remains the only application runtime. Foundry is limited to model
  inference and report-only evaluation.
- Do not add private-networking, Foundry hosted-agent/Responses, Bot, Activity,
  Teams, or Adaptive Card documentation to this lane.
