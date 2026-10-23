# Underwriting - Foundry Public

## Goal

Run one explainable Microsoft Agent Framework underwriting workflow through a
public Microsoft Foundry lane:

- risk, credit, medical, and driving checks fan out and fan in;
- deterministic policy produces the machine recommendation;
- only `REFER_TO_HUMAN_UNDERWRITER` pauses for review;
- the machine recommendation remains immutable while a reviewer records a
  separate `APPROVED` or `DECLINED` outcome;
- PostgreSQL preserves workflow checkpoints, audit history, approvals, and
  replay protection;
- the external web application and Shared Microsoft Teams publication use the
  same hosted workflow;
- release evidence is correlated in Application Insights without exposing
  applicant data or secrets.

Use synthetic data only. Do not commit applicant/customer information, tenant
or subscription identifiers, user identities, resource names, endpoints,
credentials, generated Teams packages, or release artifacts.

This README is the human-and-agent operator entry point. It describes portable
commands and contracts; it does not claim that a current Azure deployment or
Teams publication exists. Dated proof belongs only in the
[delivery ledger](docs/design/issues-changes-fixes.md).

## Choose a path

| Goal | Start here |
| --- | --- |
| Understand behavior | [Functional specification](docs/design/functional-spec.md) and [business rules](docs/design/business-rules.md) |
| Install and run locally | [Local development](#local-development) |
| Run local validation | [Local test and quality gates](#local-test-and-quality-gates) |
| Select an Azure environment | [Azure runtime profile](#azure-runtime-profile) |
| Create a clean public environment | [Clean bootstrap](#clean-bootstrap) |
| Release application changes | [Routine app-only release](#routine-app-only-release) |
| Publish or validate Shared Teams access | [Teams Shared publication](#teams-shared-publication) |
| Understand automation ownership | [CI/CD ownership](#cicd-ownership) |
| Operate an existing environment | [Operations](#operations) |
| Recover or roll back | [Rollback](#rollback) and [Troubleshooting](#troubleshooting) |

## Architecture at a glance

1. The browser calls only the external React/Nginx Container App.
2. Nginx proxies same-origin `/api` and `/backend-health` requests to an
   internal FastAPI Container App.
3. FastAPI relays start/resume work to the public Foundry Responses endpoint
   with managed identity and serves PostgreSQL-backed durable projections.
4. The hosted process constructs the one master MAF workflow.
5. Risk, credit, medical, and driving executors fan out directly; the
   aggregator waits for all four results.
6. Deterministic policy computes the machine recommendation before any model
   rationale.
7. Only a referral recommendation creates a durable human-review checkpoint.
8. Teams reaches the same hosted process through Azure Bot Service and the
   Foundry Activity protocol; Shared publication and `BotServiceRbac` limit
   distribution and invocation.
9. Application Insights receives content-safe correlation for web, Responses,
   Activity, workflow, checkpoint, and reviewer-decision operations.

This is a public-network topology. It intentionally does not add private
runner, VNet, private endpoint, private DNS, Bastion, or NAT requirements.
Only the frontend has public Container Apps ingress; the backend remains
internal to the Container Apps environment.

See the complete [architecture](docs/design/architecture.md) and
[technical specification](docs/design/technical-spec.md).

## Human-underwriter contract

The review model distinguishes two facts:

| Field | Meaning |
| --- | --- |
| Machine recommendation | Deterministic, immutable result from underwriting policy |
| Reviewer outcome | Separate `APPROVED` or `DECLINED` result for a referred case |

Only `REFER_TO_HUMAN_UNDERWRITER` pauses. Machine `APPROVED`,
`APPROVED_WITH_CONDITIONS`, and `DECLINED` recommendations complete without a
review checkpoint.

Teams cards are privacy-safe. They contain a generic review summary,
categorical recommendation, non-sensitive references, and opaque action
tokens. They do not contain applicant identity, health disclosures, income,
coverage, credit score, driving history, check details, score breakdown,
prompts, rationale, model output, endpoints, credentials, or secrets.

Each card action is expiring, one-time, and bound to the exact workflow,
checkpoint, decision, reviewer, conversation, and action batch. Wrong-user,
wrong-conversation, expired, replayed, cross-channel, or competing actions fail
closed. Typed words such as “approve” or “decline” are ordinary chat text.

Production reviewer mutation is Teams-only. The web API and Responses handler
reject review decisions even when a caller supplies an identity-looking
header. A local administrative review path exists only for non-hosted local
execution when `ENABLE_LOCAL_REVIEW_MUTATION=true` and a server-configured
`LOCAL_REVIEW_ACTOR_ID` are both present; its audit row is marked
`administrative`.

See [human-underwriter review](docs/design/hitl-review.md).

## Prerequisites

### Local development

- Git
- Make
- Python 3.13
- Node.js and npm compatible with `frontend/package.json`
- Docker with Docker Compose

### Azure operations

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- Docker
- Bicep support through Azure CLI
- Access to the selected subscription and resource group
- Permission to create or update the public-lane resources for bootstrap
- GitHub CLI (`gh`) for protected workflow dispatch/inspection

### Teams publication

- Permission to manage the selected Azure Bot Service and Teams channel
- An interactive Microsoft 365 publisher identity for Shared catalog
  publication
- An approved Microsoft Entra group or equivalent RBAC assignment for intended
  reviewers
- A reviewed publication manifest and app version

Foundry lifecycle commands set or must preserve
`AZURE_DEV_USER_AGENT=microsoft_foundry_skill`.

## Local development

### 1. Configure environment

From this project directory:

```bash
cp .env.example .env
```

The checked-in defaults use synthetic local data and local PostgreSQL. Do not
place a production connection string, applicant data, or long-lived Azure
credential in `.env`.

### 2. Install dependencies

```bash
make bootstrap
```

`make bootstrap` creates `.venv`, installs the Python project and development
tools, and installs frontend packages.

### 3. Start the full stack

```bash
make up
```

Open:

- Frontend: `http://localhost:4173`
- Backend health: `http://localhost:8000/health`

Inspect or stop the stack:

```bash
make logs
make down
```

For separate development servers:

```bash
make backend-dev
make frontend-dev
```

The Vite development server uses its configured development origin; the
containerized frontend uses port `4173`.

### 4. Exercise workflow recovery

```bash
make run
make run-fail-once
make run-crash
make resume RUN_ID=<workflow-run-id>
```

Inspect the durable projections:

```bash
make state RUN_ID=<workflow-run-id>
make events RUN_ID=<workflow-run-id>
make checkpoints RUN_ID=<workflow-run-id>
```

The crash target defaults to `medical_check`. Override it only with a valid
executor name:

```bash
CRASH_TARGET=risk_check make run-crash
```

## Local test and quality gates

Run the smallest gate that covers the change:

```bash
make test
make quality
make test-e2e
```

Useful focused gates:

```bash
make test-backend
make test-frontend
make test-scripts
make test-deployment-profile
make lint
make format-check
make validate-quick
make validate-full
```

`make test-backend` and local `make test-e2e` require Docker because they
start isolated PostgreSQL services. A local pass validates source behavior; it
does not prove Azure deployment, Teams publication, or live telemetry.

## Azure runtime profile

Azure target selection belongs in an operator-owned, non-secret file outside
the repository. Copy the sanitized template and replace every placeholder:

```bash
install -d -m 700 "$HOME/.config/maf"
export FOUNDRY_DEPLOYMENT_PROFILE="$HOME/.config/maf/underwriting-foundry-public.env"
install -m 600 deployment/profiles/foundry-public.env.example \
  "$FOUNDRY_DEPLOYMENT_PROFILE"
```

The profile contract begins with:

```dotenv
CONTRACT_VERSION=1
DEPLOYMENT_LANE=foundry-public
AZURE_ENV_NAME=<local-azd-environment-name>
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=<resource-group-name>
AZURE_LOCATION=<supported-region>
NAME_PREFIX=<portable-name-prefix>
```

The profile must not contain passwords, connection strings, endpoints,
generated resource IDs, image tags/digests, operator IP addresses, credentials,
or publication state. The template includes required non-secret existing
resource names for reuse mode; these remain only in the external profile.

Apply the selected profile:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
```

Authenticate and verify context without copying command output into docs:

```bash
az login --tenant "<tenant-id>" --use-device-code \
  --only-show-errors --output none
az account set --subscription "<subscription-id>"

az account show --query '{tenant:tenantId,subscription:id}' --output table
azd auth login
```

Stop if the authenticated context does not match the selected external
profile. See the [runtime profile guide](deployment/README.md).

## Clean bootstrap

Use bootstrap only for an explicitly approved new public environment or
reviewed infrastructure reconciliation. It is not a routine application
release.

### 1. Prepare and validate

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap-env
make validate-full
make foundry-iac-build
```

### 2. Review the infrastructure preview

Preferred protected workflow:

```bash
gh workflow run underwriting-public-provision.yml -f operation=preview
gh run watch
```

Local equivalent:

```bash
make foundry-provision-preview
```

Review for unexpected create, delete, replace, network, RBAC, scaling, or
stateful-resource changes. Reuse mode must not silently create resources or
role assignments. Bootstrap preview uses only the explicit bootstrap profile;
it does not hydrate or query resources that do not exist yet. A preview is
planning evidence, not deployment proof.

### 3. Provision the public lane

After the preview is approved under the repository operating model, use the
protected workflow:

```bash
gh workflow run underwriting-public-provision.yml -f operation=provision
gh run watch
```

Or run the local equivalent from the authenticated operator environment:

```bash
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-provision
```

`make foundry-provision` keeps `INFRASTRUCTURE_MODE=bootstrap` through the
Bicep apply, hydrates existing-resource outputs only after creation, then
applies the administrator-owned schema, converges the least-privilege runtime
credential and project `CustomKeys` connection, and runs PostgreSQL readiness.
The protected provision workflow runs the same infrastructure and convergence
stages. Application runtimes set `DB_SCHEMA_MANAGED_EXTERNALLY=true` and must
not perform DDL.

### 4. Release and prove the application

Continue with the [routine app-only release](#routine-app-only-release). Do not
treat provisioning success as application acceptance.

## Routine app-only release

Use this path for normal backend, frontend, hosted-agent, dependency, or
release-automation changes against an existing public environment.

### 1. Select and validate the target

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap
make validate-full
make foundry-reuse-preview
```

### 2. Create a release-local identifier

```bash
export RELEASE_ID="uw-public-$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)"
```

The identifier is operational metadata. Do not copy a concrete release ID,
version, count, or timing into design documents.

### 3. Run the app-only release

Preferred protected workflow:

```bash
gh workflow run underwriting-public-deploy.yml
gh run watch
```

The workflow generates its own release-local identifier, uses OIDC, loads the
protected profile and runtime secrets from the
`underwriting-foundry-public` environment, and uploads sanitized evidence.
Shared Microsoft 365 publication is deliberately excluded.

Local equivalent:

```bash
RELEASE_ID="$RELEASE_ID" make foundry-release
```

The release must:

- validate PostgreSQL, model capacity, and the runtime-secret connection;
- build immutable artifacts;
- activate and persist the exact hosted-agent image/version before backend
  deployment;
- deploy the internal backend and external frontend without changing ingress
  topology;
- run hosted smoke, recovery/referral E2E, native Teams approval and decline,
  evaluation, telemetry, deployment verification, rollback verification, and
  evidence aggregation;
- reject stale, cross-release, secret-bearing, or incomplete evidence.

Routine release must not run full provisioning, rebuild PostgreSQL, weaken the
firewall, add private-network resources, or accept a deployment-mode override.

Useful diagnostic targets:

```bash
make foundry-release-readiness
make foundry-release-package
make foundry-release-build
make foundry-release-hosted-activate
make foundry-release-app-deploy
make foundry-smoke
make foundry-hosted-e2e
make foundry-teams-native-acceptance
make foundry-eval
make foundry-telemetry
make foundry-verify
make foundry-rollback-verify
make foundry-evidence
```

Run individual targets only to diagnose or safely resume the same release
window. Record final results in the ledger.

## Teams Shared publication and native acceptance

Teams publication is a controlled operator operation, and native Teams
acceptance is a canonical release gate. The configuration must preserve the
existing Responses protocol and Entra authorization while adding Activity and
`BotServiceRbac`. It must not introduce private-network resources into this
public lane. The Bot endpoint must use the Foundry Activity Protocol API
version `2025-05-15-preview`; Azure Bot Service public network access remains
disabled.

Before publication:

1. Confirm the hosted web/Responses release has fresh evidence.
2. Confirm the administrator-owned review schema and runtime grants are ready.
3. Review Bot Service and `MsTeamsChannel` changes.
4. Confirm the publication manifest contains no tenant, user, applicant,
   endpoint, credential, or generated catalog state.
5. Confirm `publishScope` is `Shared`, not `Tenant`.
6. Confirm intended reviewers have the required Foundry permission.

The expected controlled sequence is:

1. Plan merge-preserving Activity endpoint reconciliation.
2. Preview Bot and Teams channel infrastructure.
3. Deploy Bot Service and `MsTeamsChannel`.
4. Apply Activity while retaining Responses and Entra.
5. Generate and inspect the Microsoft 365 package.
6. Publish the explicit Shared app version with an interactive publisher.
7. Verify sanitized local publication state.
8. Start the canonical release and wait for its native Teams observer.
9. In the published agent, send `start sample underwriting review` twice;
   approve one privacy-safe card and decline the other.
10. Let the release correlate those Teams-origin runs through PostgreSQL and
    Application Insights, then complete evaluation, rollback, and aggregate
    evidence.

The observer never posts directly to the Activity endpoint. Wrong-user,
wrong-conversation, typed-text, replay, expiry, concurrency, cross-channel, and
privacy behavior remain mandatory automated contract/integration tests; live
channel evidence is accepted only from real Teams-origin card actions.

Run the checked-in sequence:

```bash
make foundry-activity-plan
make foundry-teams-plan
make foundry-teams-preview

FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-teams-deploy-bot
make foundry-activity-apply
make foundry-teams-package
make foundry-teams-publish
make foundry-teams-status
```

Package generation and publication only verify that the required Activity,
Responses, Entra, and `BotServiceRbac` state is already applied. They never
patch endpoint protocols or authorization; only the explicit Activity
reconciler commands do that.

Publication uses an interactive Microsoft 365 publisher and is intentionally
not run from GitHub Actions. Review rollback before handoff:

```bash
make foundry-teams-rollback-plan
```

See [secure Foundry-to-Teams design](docs/design/secure-foundry-agent-to-teams.md).

## CI/CD ownership

| Surface | Owner | Allowed responsibility |
| --- | --- | --- |
| Developer/local validation | Contributor | Dependency, lint, unit, script, profile, Bicep build, packaging, and Playwright checks |
| `underwriting-public-ci.yml` | Automatic credential-free CI | Locks/wheelhouse, backend/frontend, contracts, Bicep, package, and Teams contracts |
| `underwriting-public-provision.yml` | Protected OIDC workflow | Preview or explicitly selected provision operation |
| `underwriting-public-deploy.yml` | Protected OIDC workflow | Hard-enforced app-only release and sanitized evidence upload |
| `underwriting-public-package-validation.yml` | Protected OIDC workflow | Authenticated AZD package validation |
| `underwriting-public-observability.yml` | Protected OIDC workflow | Hosted E2E, evaluation, and telemetry |
| `underwriting-public-evidence.yml` | Protected OIDC workflow | Retry live evidence gates without rebuilding the application |
| Teams publication | Interactive Microsoft 365 publisher | Publish reviewed Shared app version and retain sanitized evidence |

Protected workflows share one serialized release concurrency group and load
target values/secrets from the protected GitHub environment. They must verify
that OIDC subscription and external profile agree. Teams publication remains
interactive and outside GitHub Actions.

## Operations

### Health and topology

- Frontend health and API calls remain on the frontend origin.
- `/backend-health` proves the proxy can reach the internal backend.
- Direct public backend reachability must be denied.
- Backend and hosted agent must use the same runtime database contract.
- Hosted metadata contains only the Foundry `CustomKeys` placeholder, never
  the resolved database URL.

Run:

```bash
make foundry-verify
```

### PostgreSQL

```bash
make foundry-postgres-readiness
```

Readiness must verify TLS, expected public firewall posture, schema parity,
runtime connectivity, and denial of runtime DDL/role creation.

Schema migration and credential rotation are administrator operations:

```bash
make foundry-postgres-schema
make foundry-postgres-credentials
```

Do not use the administrator credential as an application runtime credential.

### Telemetry and evaluation

```bash
make foundry-appinsights-connection
make foundry-telemetry
make foundry-eval
```

Start trace investigation with `workflow_run_id`. Web start and review resume
may be separate traces; join them with run, checkpoint, conversation, and safe
channel attributes.

### Evidence

```bash
RELEASE_ID="$RELEASE_ID" make foundry-evidence
```

Release artifacts are local operational state, not documentation authority.
Record only secret-free outcomes in the ledger.

## Rollback

Rollback is a controlled operation, not a new release claim.

### Application rollback

1. Stop the failing release and preserve its evidence.
2. Identify the previous verified hosted-agent image/version and previous
   backend/frontend image digests from release-local records.
3. Reactivate the prior hosted version before routing the backend back to it.
4. Restore the prior backend and frontend revisions without changing ingress.
5. Run smoke, topology verification, referral/HITL acceptance, telemetry, and
   evidence aggregation.
6. Record the rollback and any unresolved data migration concern in the
   ledger.

Never roll back schema blindly after a review table has accepted data. Use a
forward-compatible application rollback or an explicitly reviewed data plan.

### Teams rollback

1. Stop new publication or distribution.
2. Review `make foundry-teams-rollback-plan`.
3. Run `make foundry-teams-rollback`. This automates **Activity-only**
   rollback: it removes Activity and Bot authorization without deleting
   Responses or Entra configuration. It deliberately reports
   `fullRollbackComplete=false`.
4. Remove or supersede the Shared catalog version through the supported
   Microsoft 365 governance process and record verified completion.
5. Delete or retain Bot Service and `MsTeamsChannel` through a reviewed
   ARM/Bicep lifecycle action and record the verified result.
6. Verify the web/Responses lane still works and no pending action can replay.

Do not report full Teams rollback success until both recorded manual external
steps are complete.

## Troubleshooting

### `make bootstrap` or Python install fails

- Confirm the Python version satisfies `pyproject.toml`.
- Remove only the project `.venv`, rerun `make install`, then rerun the failed
  gate.
- Do not weaken hash or wheelhouse checks in release images to bypass a local
  toolchain issue.

### Frontend install, build, or Playwright fails

```bash
make frontend-install
make test-frontend
make test-e2e
```

Confirm Node/npm compatibility with `frontend/package.json`. If browser
binaries are missing, install them through the Playwright command appropriate
to the local environment, then rerun the exact failed test.

### PostgreSQL is not ready

- Confirm the runtime profile selects the intended environment.
- Check TLS hostname and firewall posture.
- Apply administrator schema migration if required.
- Rotate/provision the runtime credential and rerun readiness.
- Do not grant schema ownership or broad `CREATE` to the runtime role.

### Hosted activation succeeds but the backend fails

- Verify the hosted version metadata was persisted before backend deployment.
- Verify backend and hosted runtime resolve the same database contract.
- Run `make foundry-verify`.
- Roll back to the prior verified hosted/backend pair instead of creating a
  compatibility shim.

### Telemetry is missing

- Verify the Foundry project Application Insights connection.
- Use the durable `workflow_run_id`, not applicant information, as the lookup.
- Allow bounded ingestion retry through checked-in tooling.
- Treat authorization, configuration, and service errors as failures, not as
  reasons for an unbounded sleep.

### A referral did not pause

- Confirm the machine recommendation is exactly
  `REFER_TO_HUMAN_UNDERWRITER`.
- Confirm the deployed schema supports approvals and trusted origin.
- Inspect safe workflow events and checkpoints.
- Do not change terminal machine categories into HITL triggers.

### An Adaptive Card action is rejected

Expected failures include expired token, replay, wrong reviewer, wrong
conversation, wrong checkpoint, sibling supersession, resolved approval, and
cross-channel origin mismatch. Inspect status and safe token/action metadata;
never log or query the plaintext token.

### Teams normal chat works but no card appears

- Confirm the recommendation is a referral.
- Confirm the active hosted version includes Activity and review support.
- Confirm Activity reconciliation retained Responses/Entra and added
  `BotServiceRbac`.
- Confirm administrator schema/grants were applied before activation.
- Do not place applicant details into diagnostic cards.

### Azure target mismatch

Stop. Reapply the external runtime profile, verify `az account show` and AZD
environment context, and rerun preflight. Do not silently change subscription,
resource group, region, or resource names.

## Project map

```text
foundry-public/
├── README.md                         operator guide
├── agents.md                         coding-agent contract
├── .github/copilot-instructions.md  Copilot implementation guidance
├── backend/
│   ├── app/                          API, domain, MAF, persistence, telemetry
│   ├── foundry/main.py               hosted Responses/Activity entrypoint
│   └── tests/                        backend and contract tests
├── frontend/                         React/Vite/Nginx operator console
├── deployment/                       external-profile loader and contracts
├── infra/foundry-hosted/             AZD/Bicep hosted application
├── scripts/foundry/                  release, verification, evidence tooling
└── docs/
    ├── README.md                     documentation index
    ├── manual-testing.md             operator acceptance guide
    └── design/                       product, architecture, rules, delivery
```

## Documentation map

- [Documentation index](docs/README.md)
- [Functional specification](docs/design/functional-spec.md)
- [Business rules](docs/design/business-rules.md)
- [Technical specification](docs/design/technical-spec.md)
- [Human-underwriter review](docs/design/hitl-review.md)
- [Architecture](docs/design/architecture.md)
- [Architecture decisions](docs/design/architecture-decisions.md)
- [User flow](docs/design/userflow.md)
- [Schema, I/O, and telemetry](docs/design/schema-io-telemetry.md)
- [Deployment flow](docs/design/deployment-flow.md)
- [Engineering operating model](docs/design/engineering-operating-model.md)
- [Technology stack](docs/design/techstack.md)
- [Manual testing](docs/manual-testing.md)
- [E2E rubric](docs/design/e2e-rubric.md)
- [Delivery ledger](docs/design/issues-changes-fixes.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
