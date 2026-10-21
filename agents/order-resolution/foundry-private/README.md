# Order Resolution - Foundry Private

## Goal

Run one explainable Microsoft Agent Framework order-resolution workflow in a
private Foundry environment:

- low-risk synthetic cases complete automatically;
- high-risk or damaged-item cases pause for human approval;
- workflow state, checkpoints, approvals, and history remain durable in
  PostgreSQL;
- the same hosted workflow supports the private web application and Microsoft
  Teams;
- release evidence is correlated in Application Insights and evaluated against
  the exact hosted conversations.

This project uses synthetic data only. Do not commit customer information,
tenant or subscription identifiers, live endpoints, credentials, or generated
release artifacts.

## Start here

| Need | Read |
| --- | --- |
| Product behavior and acceptance criteria | [Functional specification](docs/functional-spec.md) |
| Resolution and HITL rules | [Business rules](docs/business-rules.md) |
| Runtime, API, persistence, and deployment contract | [Technical specification](docs/technical-spec.md) |
| Network and component boundaries | [Architecture](docs/architecture.md) |
| Complete documentation map | [Documentation index](docs/README.md) |
| Private deployment and Teams demo operations | [Operator runbook](docs/customer-demo-runbook.md) |
| Current deployment and validation evidence | [Evidence ledger](docs/issues-changes-fixes.md) |
| Instructions for coding agents | [Agents guide](agents.md) |

The current validated Azure release is recorded in
[`.azure/deployment-plan.md`](.azure/deployment-plan.md). Design documents
describe intended behavior; only the deployment plan and evidence ledger
establish what was deployed and verified.

## Project map

| Path | Responsibility |
| --- | --- |
| `backend/` | FastAPI wrapper, shared MAF workflow, hosted Responses/Activity entrypoint, persistence, tests, and evaluations |
| `frontend/` | React/Vite workflow UI and optional read-only selected-thread experience |
| `infra/foundry-hosted/` | Private Foundry, Container Apps, Bot/Teams, and AZD/Bicep deployment assets |
| `scripts/` | Private-runner deployment, release, Teams, E2E, telemetry, and evidence automation |
| `docs/` | Specifications, architecture, operating model, runbooks, and release history |
| `agents.md` | Coding-agent boundaries and required verification |

## Local development

1. Install dependencies.

   ```bash
   make bootstrap
   ```

2. Copy `backend/.env.example` to `backend/.env` and configure the local
   PostgreSQL and model settings.

3. Start the application.

   ```bash
   make up
   ```

   Or run each service separately:

   ```bash
   make run-backend
   make run-frontend
   ```

4. Open:

   - Frontend: `http://localhost:5173`
   - Backend health: `http://localhost:8000/health`

5. Run the local private-lane gate.

   ```bash
   make test
   ```

Baseline scenarios:

- `ORD-1001`: low risk; normally completes without HITL.
- `ORD-1009`: high value; requires HITL.
- A damaged-item request requires HITL regardless of amount.

## Private Foundry deployment

Normal Foundry, model, storage, PostgreSQL, registry, and backend paths remain
private. Microsoft Teams uses the separately authorized Foundry Activity route;
it does not make the normal Responses or data plane public.

Run Azure and Foundry operations from the VNet-connected private runner using
an ignored external deployment profile.

### Routine app-only release

```bash
make foundry-app-only-release
make foundry-evidence
```

This updates existing application revisions and the hosted-agent version. It
must not run full Bicep reconciliation or modify PostgreSQL network access.

### Bootstrap or infrastructure reconciliation

```bash
make foundry-provision-preview
make foundry-release
```

Use this path only after reviewing the current preview. The operator runbook
defines the required stop conditions, private-runner preparation, Teams
publication, rollback, and evidence handling:
[docs/customer-demo-runbook.md](docs/customer-demo-runbook.md).

Generated profiles, AZD state, packages, logs, and release evidence remain
ignored and must not be committed.

## Validation and evidence

- Local code and contract gate: `make test`
- Private release contracts: `make test-foundry-portability`
- Hosted HITL, telemetry, and strict Foundry evaluation:
  `make foundry-evidence`
- Canonical release status:
  [`.azure/deployment-plan.md`](.azure/deployment-plan.md)
- Dated outcomes and root-cause history:
  [docs/issues-changes-fixes.md](docs/issues-changes-fixes.md)

Do not claim deployment success from local tests, source state, or an
infrastructure preview.

## Troubleshooting

- **Private runner or Bastion:** follow the recovery procedure in the
  [operator runbook](docs/customer-demo-runbook.md).
- **PostgreSQL readiness:** run `make foundry-postgres-readiness`; do not open
  public access or add firewall bypasses.
- **Hosted Responses:** verify the active agent uses the Responses protocol and
  invoke plain text with `--protocol responses`.
- **Structured approval decisions:** use the supported structured Responses
  request path; do not pass Responses JSON through AZD `--input-file`.
- **Teams or Adaptive Cards:** use the Activity and publication checks in
  [docs/teams-foundry-integration.md](docs/teams-foundry-integration.md).
- **Release or telemetry failure:** start with the current entry in the
  [evidence ledger](docs/issues-changes-fixes.md).

## Coding agents

Read [agents.md](agents.md) before changing this project. It defines package
boundaries, security and HITL invariants, stable API/event contracts, required
documentation updates, and verification expectations. Repository-level Copilot
instructions are in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).
