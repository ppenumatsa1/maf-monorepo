# Order Resolution Deployment Flow

## Purpose

This document is the cross-lane reference for moving Order Resolution from a
validated source revision to deployed, evaluated, and observable workloads. A
lane may omit infrastructure components it does not use, but it must preserve
the same control points and evidence boundaries.

For the Foundry Private lane, PostgreSQL is private-only from creation. The
former temporary public-access, connectivity-proof, lockdown, and
post-lockdown stages are retired.

## End-to-end flow

### Phase 1: Validate and authorize

| Step | Stage | Required outcome |
| ---: | --- | --- |
| 1 | Select target | Load the canonical lane profile and resolve subscription, resource group, region, environment, resource names, and runner requirements. |
| 2 | Validate source | Run lane contracts, tests, linting, workflow validation, infrastructure compilation, and deployment-package checks. |
| 3 | Authenticate deployment | Use the lane's approved GitHub OIDC identity and validate that the selected environment matches the canonical target. |
| 4 | Preview infrastructure | Produce a non-mutating preview and stop on stateful replacement, network weakening, identity drift, or changes outside the selected lane. |

### Phase 2: Prepare the platform

| Step | Stage | Required outcome |
| ---: | --- | --- |
| 5 | Base infrastructure | Create or reconcile networking, DNS, data services, registry, monitoring, Foundry resources, and the application hosting environment. Private lanes create private endpoints and private-only PostgreSQL in this stage. |
| 6 | Deployment runner | Prepare the approved runner with Docker, Azure CLI, AZD, Python, database tooling, and the network path required by the lane. |
| 7 | Deployment identity | Configure GitHub OIDC trust, managed identities, and scoped RBAC for deployment and runtime operations. |
| 8 | Database bootstrap and readiness | Create or reconcile schema objects with the administrator, create the least-privilege runtime role, and verify connectivity and denied runtime DDL. Private readiness must pass before application deployment. |
| 9 | Foundry runtime setup | Create required project connections, grant connection access, configure the capability host where used, and validate runtime-secret resolution. |

### Phase 3: Package and deploy

| Step | Stage | Required outcome |
| ---: | --- | --- |
| 10 | Package applications | Build immutable backend, frontend, and hosted-agent artifacts and publish them to the selected registry. |
| 11 | Deploy application hosts | Deploy backend and frontend revisions with lane-specific networking, identities, secrets, and database settings. |
| 12 | Deploy hosted agent | Create and activate the Foundry hosted-agent version from the selected image and project connections. |
| 13 | Verify deployment | Confirm expected image versions, ready revisions, health endpoints, active hosted-agent version, and a valid smoke response. |

### Phase 4: Prove and observe

| Step | Stage | Required outcome |
| ---: | --- | --- |
| 14 | HITL E2E | Run low-risk, high-risk approval, and damaged-item scenarios, including checkpoint pause/resume and terminal outcomes. |
| 15 | Telemetry and evaluation | Correlate each fresh conversation to eligible Application Insights and Foundry traces, then run the configured evaluators against those exact traces. Every required trace must pass. |
| 16 | Release evidence | Record source revision, target, artifact versions, deployment status, E2E results, trace IDs, evaluator results, and final infrastructure security state in one release window. |

## Lane application

| Lane | Infrastructure path | Deployment path | Evidence path |
| --- | --- | --- | --- |
| Azure Hosted | Public or lane-configured Azure application infrastructure | Backend and frontend hosting defined by the lane | Smoke, E2E, telemetry, and configured evaluations |
| Foundry Public | Public Foundry project and hosted-agent dependencies | ACA applications and Foundry hosted agent | Hosted smoke, HITL E2E, telemetry, and Foundry evaluation |
| Foundry Private | VNet-isolated Foundry, private data services, private ACR, private ACA environment, private-only PostgreSQL, and private runner | ACA applications and hosted agent deployed from the VNet-connected release path | HITL E2E, exact-trace telemetry/evaluation, and final private-state verification |

## Fresh bootstrap versus routine release

**Fresh bootstrap or authorized reconciliation** runs all 16 stages. It creates
or intentionally reconciles infrastructure before packaging and deploying the
application.

**Routine application release** reuses validated infrastructure. It runs source
validation, target/readiness checks, stages 10-16, and any lane-specific
pre-deployment guard. It must not silently reconcile shared or stateful
infrastructure.

## Global stop conditions

Stop the flow when:

- the selected target differs from the canonical profile;
- source validation, preview, or packaging fails;
- a preview replaces stateful resources or weakens network isolation;
- required runners, private DNS, endpoints, identities, or connections are not ready;
- runtime database permissions exceed the least-privilege contract;
- deployed images, health, hosted-agent activation, or smoke checks differ from the intended release;
- any required HITL scenario, telemetry correlation, or evaluator result fails; or
- evidence is stale, incomplete, or assembled from different release windows.

