# Order Resolution Foundry Public Deployment Plan

**Status:** Validated
**Scope:** `agents/order-resolution/foundry-public` only
**Azure execution:** Bootstrap provisioned; PostgreSQL initialized; selected
steady-state reuse preview is non-mutating
**Release execution:** Completed on 2026-08-15; validation status remains
`Validated`

## 2026-08-15 release completion

The least-privilege database contract is restored without granting schema
ownership or `CREATE` to the runtime role. Production application deployments
set `DB_SCHEMA_MANAGED_EXTERNALLY=true`, so administrator-owned schema
bootstrap remains separate from runtime startup. The focused database tests,
102 backend tests, 10/10 deterministic evaluation cases, and all 10 browser
tests passed before release.

The app-only release completed with healthy backend revision
`orderresoluta63e7c16-backend--0000004`, healthy frontend revision
`orderresoluta63e7c16-frontend--0000002`, and active hosted agent
`order-resolution-hosted` version `4`. Immutable images were:

- backend `sha256:50dc3c9d389ebb3a466aa665de49162be43ee0cdd4284dbd90b5ff4672c7dcec`;
- frontend `sha256:ae5d7b781208d3862d382507708171a76e42a35d22c342b898843447afc2012c`.

Fresh smoke and hosted low-risk/HITL approval-resume E2E passed for
conversations
`conv_1d9ab08b460389b200uEl7q3qJs6kPYvEH73yeHVDQFEn983m0` and
`conv_5dcbb41299bf0d3000VrhU3ZPjH7SSRR7eyola4Fki1ar3f6QB`.
Trace evaluation `eval_8476b52b167a47ce85e228beb00c67bf` /
`evalrun_f0320e561eab401991156088b6e26318` completed with 2 passed,
0 failed, and 0 errored conversations. Application Insights correlated
66 rows for the two fresh conversations with zero exceptions.

## 2026-08-14 blocked release history

The app-only release is blocked. At `2026-08-15T03:39:46Z`, backend revision
`orderresoluta63e7c16-backend--0000002` failed startup with
`psycopg.errors.InsufficientPrivilege: permission denied for schema public`
while `PostgresDatabase.ensure_schema()` executed `CREATE TABLE IF NOT EXISTS`.
The prior readiness gate proved TLS connectivity and canonical-schema read
access but did not prove that production startup avoids DDL. The runtime role
intentionally lacks schema ownership and broad `CREATE`; those permissions must
not be added to work around the failure.

Frontend revision `orderresoluta63e7c16-frontend--0000001` is healthy on its
immutable image. Hosted agent `order-resolution-hosted` version `2` is active
on its immutable image with the expected runtime/telemetry environment, and
the Foundry project Application Insights connection targets
`orderresoluta63e7c16-ai`. The backend is not successfully released, so no
fresh smoke, hosted low-risk/HITL approval-resume E2E, report-only trace
evaluation, or current-conversation telemetry gate is accepted.

Next execution must keep administrator-only schema bootstrap separate from
runtime startup, add a runtime-credential startup test that performs no DDL,
verify required tables explicitly, redeploy the application legs, and rerun
the complete fresh evidence chain. No PostgreSQL/network/RBAC or evaluation
threshold may be weakened.

## Approved target

| Setting | Value |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-maf-ora-foundry-public` |
| Location | `eastus2` |
| Bootstrap environment | `order-resolution-bootstrap` |
| Reuse environment | `order-resolution-foundry-public` |
| Name prefix | `orderresolution` |
| Hosted agent | `order-resolution-hosted` |

Profiles select only subscription, resource group, location, environment, and
name prefix. Generated names and non-secret Azure outputs are hydrated into the
operator's local AZD environment. Credentials, connection strings, resource
IDs, endpoints, and image tags must never be committed to a profile.

## Shared Azure preflight findings

- Subscription/tenant authentication is valid and required providers are
  registered.
- The first `azd provision --preview` created and tagged the initially empty target
  resource group before ARM what-if. The user approved that empty group as the
  intended AZD bootstrap boundary. The resumed preview performed no further
  mutation. The authorized bootstrap has now completed and reuse outputs are
  hydrated.
- `gpt-4.1-mini` `GlobalStandard` quota is exhausted (5000/5000).
  `Standard` has 5000 available and is the bootstrap default;
  `DataZoneStandard` has 2000 available as an explicit alternative.
- PostgreSQL capability data includes `Standard_D2ds_v5` in the target region.
- The Container Apps quota extension check was permission-denied. Do not
  bypass it. Require a reviewed `azd provision --preview --no-prompt` and stop
  on any Container Apps capacity or configuration failure.

## Architecture and ownership

The steady-state path remains:

`browser -> external frontend Container App -> internal FastAPI adapter
-> hosted Foundry Responses agent -> PostgreSQL`

Bootstrap mode declaratively creates the Foundry account/project and chat,
embeddings, and evaluator deployments; ACR; Log Analytics and Application
Insights; Container Apps environment and both apps; separate backend/frontend
managed identities; PostgreSQL Flexible Server/database/firewall rules;
evaluation storage; Foundry monitoring/storage connections; and resource-scoped
RBAC.

Reuse mode references deterministic existing names only. Every resource,
connection, and role assignment declaration is conditional on bootstrap mode,
so a reuse provision emits outputs but creates no resources or assignments.
Evaluation storage uses public network access with `defaultAction: Deny` and
the `AzureServices` trusted-service bypass. This is the narrow reachable
selected-network posture required by the Foundry AAD storage connections; no
anonymous blob access or shared-key access is enabled.

Reuse hydration queries and persists the complete Bicep output contract,
including project/account/model values, registry endpoint, monitoring IDs,
PostgreSQL FQDN, Container Apps environment/app IDs, internal/external URLs,
identity names, and image repositories. A mock-Azure contract test prevents
partial hydration from reaching release commands.

## PostgreSQL bootstrap contract

1. `make foundry-bootstrap-env` derives portable names and records only
   non-secret bootstrap inputs.
2. The operator supplies `POSTGRES_ADMIN_PASSWORD` and
   `POSTGRES_HOSTED_PASSWORD` through the local AZD environment or secure
   process input.
3. `make foundry-provision` creates bootstrap infrastructure, then hydrates
   generated non-secret outputs and switches the environment to reuse mode.
4. `make foundry-postgres-schema` applies
   `backend/app/sql/schema.sql` with the administrator credential.
5. `make foundry-postgres-credentials` creates or rotates a dedicated
   `order_resolution_runtime` login, grants DML only on the runtime tables and
   the required sequence, verifies that DDL/role creation is denied, and stores
   the TLS runtime URL only in the local AZD environment.
6. `make foundry-postgres-readiness` verifies URL parity, TLS, hostname,
database, runtime credential connectivity to the canonical schema, Ready
state, dual authentication, and the Azure-services/operator firewall rules.

No credential is emitted as Bicep output or stored in a target profile.

## Release boundary

`make foundry-release` remains app-only. It selects the existing local AZD
environment, hydrates the reuse contract, runs local validation and Bicep
compilation, checks PostgreSQL readiness once, securely converges the
deterministic project `CustomKeys` runtime connection, then publishes the
frontend, backend, and hosted-agent application legs. It does not call
`azd provision`.

`make foundry-provision` is the explicit infrastructure command. In bootstrap
mode it creates the lane; after hydration, subsequent use is reuse mode and
non-mutating by template construction.

### Standardized app-only release contract

Future releases retain the approved target and do not accept
`FOUNDRY_DEPLOY_MODE` overrides. Before application mutation,
`make foundry-model-preflight` validates the existing Order Resolution chat,
embeddings, and evaluator deployments plus regional quota without changing live
SKU or capacity. Application scripts deploy immutable ACR digest references and
persist only safe gitignored image/version metadata.

Hosted deployment reads the active version's platform principal and
idempotently converges only `Cognitive Services OpenAI User` at the Foundry
account scope. Both hosted database variables use the literal
`${{connections.orderresolutionruntimesecrets.credentials.database_url}}`;
the resolved URL is never passed to `HostedAgentDefinition` or persisted in
agent/deployment metadata. `make foundry-verify` then proves one healthy active
ACA revision per expected digest, external frontend/internal backend ingress,
frontend and same-origin backend health, hosted version/image/RBAC and
placeholders, the project runtime/App Insights connections, backend database
parity, and `DB_SCHEMA_MANAGED_EXTERNALLY=true`.

Hosted E2E now emits one fresh evidence object for three conversations:
ORD-1001 low-risk completion, ORD-1009 approval/resume, and damaged-item
ORD-1001 approval/resume. Telemetry and the preserved Task Completion and
Coherence evaluators consume those exact IDs. `make foundry-evidence` rejects
stale, cross-window, incomplete, or secret-bearing input and writes one
gitignored release-window report under `backend/.foundry/results/`.

## Local validation

### All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not an Aspire project)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not an Aspire project)

- [x] Bicep compiled and generated ARM JSON refreshed.
- [x] Shell syntax checks passed for deployment and Foundry scripts.
- [x] PostgreSQL credential-helper tests passed.
- [x] Bootstrap/reuse static contract passed, including conditional scoped
  role assignments and internal-backend/external-frontend topology.
- [x] Secret-free bootstrap/reuse profile contracts passed.
- [x] Mock-Azure reuse hydration proved every Bicep output is persisted.
- [x] Evaluation storage contract proved trusted-service reachability with
  selected-network denial as the default.
- [x] Package metadata and Azure YAML contracts remained unchanged.
- [x] `azd package --no-prompt` completed locally for the hosted Responses
  package without provisioning or deployment.
- [x] The deterministic design-review gate passed: backend lint, 102 backend
  tests, 10/10 workflow eval cases, 7 Playwright workflow cases, and 3
  selected-thread integration cases.
- [x] Scoped diff check confirmed changes are confined to this lane.
- [x] Authenticated bootstrap preview against the approved empty resource group
  generated only the expected fresh resource plan and performed no mutation.
- [x] Authorized bootstrap provisioning, PostgreSQL setup, and reuse preview
  completed; application deployment was not performed.

## 7. Validation Proof

- The Microsoft Foundry dependency check passed: `azd` and the
  `microsoft.foundry` extension are ready.
- `make test-deployment-profile test-scripts foundry-iac-build foundry-package`
  passed. Packaging created only a local hosted-agent image tag and pushed
  nothing.
- `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd auth login --check-status`
  passed for tenant `a679d99f-b8f5-4d50-843e-5b73405ce0fc`.
- The selected AZD environment is `order-resolution-bootstrap`, with
  subscription `7df95e88-701c-4693-af77-3159f83b558d`, resource group
  `rg-maf-ora-foundry-public`, location `eastus2`, bootstrap mode, and
  `Standard` model SKU.
- The resumed `AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision
  --preview --no-prompt` passed in 25 seconds. It proposed 14 top-level lane
  resources:
  two Container Apps, one Container Apps environment, Foundry account/project,
  three model deployments, Foundry monitoring connection, ACR, PostgreSQL,
  Application Insights, Log Analytics, and evaluation storage. Every reported
  change was `Create`; there were no deletions, replacements, or modifications.
- The generated ARM template contains 10 conditional role assignments; all 10
  have resource-level scopes. No resource-group or subscription role
  assignment is declared.
- Chat, embeddings, and evaluator deployments inherit the approved `Standard`
  SKU. The preview did not use exhausted `GlobalStandard` quota.
- Evaluation storage is reachable through the Azure-services bypass while
  retaining `defaultAction: Deny`, disabled anonymous blob access, disabled
  shared-key access, and TLS 1.2.
- PostgreSQL uses `Standard_D2ds_v5` General Purpose, which is available in
  zones 1-3 in East US 2; it has seven-day backups, no geo-redundant backup,
  dual authentication, an Azure-services rule, and a single operator-IP rule.
  Credentials remain local secure values.
- Required providers are registered. The three subscription policy assignments
  are Defender/Security Center assignments and did not block the preview.
- The target group was absent before the first preview. Azure Activity Log
  records the AZD preview bootstrap side effect
  `Microsoft.Resources/subscriptions/resourcegroups/write` at
  `2026-08-15T02:25:41.4009925Z`, caller
  `ppenumatsa@microsoft.com`, correlation ID
  `cfad8e86-98e0-ba2c-c159-c03f2663e4ae`. The group has AZD environment tag
  `order-resolution-bootstrap`. This is recorded as an AZD preview side effect
  and approved bootstrap prerequisite; the group was not deleted.
- Before and after the resumed preview, the resource count was zero. Azure
  Activity Log from preview start `2026-08-15T02:31:24Z` contains only the
  expected `Microsoft.Resources/deployments/whatIf/action` events and policy
  `modify/action` evaluation events for the hypothetical Foundry account and
  evaluation storage. It contains no resource-group write, provider resource
  write, deployment write, or delete operation; no resource was persisted.

## 8. Provisioning proof

- The first two provisioning attempts exposed concurrent Foundry parent writes:
  model deployments returned `RequestConflict`, and the first attempt also
  observed project-role propagation before the project was visible.
- Chat, embeddings, and evaluator resources are now serialized in Bicep. The
  subsequent `azd provision --no-prompt` completed successfully.
- Live inventory contains the account/project, three succeeded `Standard`
  model deployments, ACR, Container Apps environment and two apps, two
  user-assigned identities, PostgreSQL, Application Insights, Log Analytics,
  evaluation storage, and Foundry monitoring/storage connections.
- Live RBAC queries confirmed all ten assignments at resource scopes. ACR
  exposes propagated `AcrPull` for backend, frontend, and project principals.
- Schema bootstrap, least-privilege runtime credential provisioning, and
  PostgreSQL readiness passed. Secrets remain only in local AZD environments.
- `order-resolution-foundry-public` is selected and fully hydrated. Its final
  reuse preview reported `Skip` for all ten established top-level resources,
  with no PostgreSQL or other mutation.
- Azure Policy changed evaluation storage's effective
  `publicNetworkAccess` to `Disabled`; connections and AAD roles exist, but
  reachability remains a later evaluation-gate check.
- At the time of initial provisioning validation, no application release,
  smoke, hosted E2E, evaluation, or telemetry command had run. The later
  completed release is recorded at the top of this plan and in
  `docs/design/issues-changes-fixes.md`.

## Guardrails

- Routine releases remain app-only; infrastructure provisioning is a separate,
  explicitly approved operation.
- The selected steady state is reuse; future infrastructure checks must remain
  non-mutating unless a new bootstrap is explicitly authorized.
- Keep `AZURE_DEV_USER_AGENT=microsoft_foundry_skill` inline for every `azd`
  command; do not persist it.
