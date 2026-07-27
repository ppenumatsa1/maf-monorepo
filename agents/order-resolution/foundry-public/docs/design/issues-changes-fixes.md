# Public Foundry Delivery Ledger

## Current architecture

The supported hosted path is:

```text
Browser
  -> external React/Nginx frontend Container App
  -> same-origin /api and SSE proxy
  -> internal FastAPI responses-wrapper Container App
  -> managed-identity Foundry Responses agent
  -> shared PostgreSQL workflow/checkpoint/approval/event state
```

The browser never receives a Foundry endpoint credential. The wrapper creates a
Foundry `conv_...` conversation before the first request, persists that thread
identifier, dispatches the initial Responses request without remote streaming,
and resumes HITL using checkpoint-keyed `function_call_output`. Browser live
updates come from persisted PostgreSQL projections through polling and stable
native SSE; the rich stream is additive.

## Current public target

- Resource group: `rg-maf-ora-foundry-public-dev2`
- Foundry project: `order-resolution-public-managed-dev2`
- Hosted agent: `order-resolution-hosted`
- Public frontend:
  `https://ora-public-dev2-frontend.greentree-dc9ce897.eastus2.azurecontainerapps.io/`
- Backend: internal-only Container App; it is not a browser endpoint.

## Verified release evidence

- Local backend tests, deterministic evaluation, local Playwright, Docker
  Playwright, and the deterministic review gate passed.
- Hosted browser Playwright passed all seven workflow scenarios, including
  low-risk completion, approval/resume, damaged-item rejection, workflow
  history, and native/rich event presentation.
- Direct Foundry Responses E2E passed for low-risk and HITL approval/resume.
- Enforced Foundry trace evaluation
  `eval_e41c203d70bd4a0782778954f7d73db4` /
  `evalrun_958cceeac33848b693928863e957e41b` completed with two passed, zero
  failed, and zero errored conversations.
- Application Insights correlation verified workflow and HITL spans for the
  hosted E2E conversations.

## Monorepo redeployment blocker and fix

On 2026-07-27, the monorepo Foundry Public `azd provision --preview` showed
that `maffndevaljaq57wl77uqws` would change from
`publicNetworkAccess: Disabled` to `Enabled`. The live account was already
working with public access disabled, `allowBlobPublicAccess: false`, and
`allowSharedKeyAccess: false`; enabling its public endpoint would weaken the
proven security posture without being required for deployment.

The cause was the evaluation artifact Storage account declaration in
`infra/foundry-hosted/iac/main.bicep`, which set
`publicNetworkAccess: 'Enabled'`. It now declares `Disabled`, matching the
live account. Its existing Azure Services bypass and `defaultAction: Allow`
settings are unchanged because public network access is disabled. Provisioning
and application deployment remain blocked until a fresh preview confirms that
this public-access drift is gone.

The first monorepo `azd deploy` then failed because the clean repository does
not track the generated `infra/foundry-hosted/agent/` deployment source. This
is expected generated input, not missing application code. Running the existing
`scripts/foundry/sync_hosted_source.sh` helper recreated it from `backend/`;
the retry deployed the backend, frontend, and hosted agent successfully.

## PostgreSQL startup incident and recovery

After the monorepo deployment, backend revision
`ora-public-dev2-backend--azd-1785186052` failed activation and the frontend
`/api/health` proxy timed out. Container Apps console logs identified
`psycopg_pool.PoolTimeout` during `postgres_db.ensure_schema()`. The root cause
was the public Flexible Server `maffndpgbfscpfhjr7sp4cu` being in the `Stopped`
state; its FQDN, public-access setting, and Azure-services firewall rule were
otherwise correct.

Starting the existing server restored backend health. Hosted workflow UI checks
then passed, including the HITL approval/resume path. One manual-test case
timed out while the database recovered, but its immediate isolated retry passed
without code changes, confirming recovery latency rather than a UI or workflow
regression.

## Telemetry signal policy

The public project and both Container Apps export to the configured Application
Insights resource. FastAPI `/health`, `/api/health`, and chat SSE request spans
are intentionally excluded from request telemetry so Container Apps probes and
long-lived streams do not obscure workflow signal. Foundry `/readiness`,
invocation, model, workflow, checkpoint, and HITL spans remain observable.

Use a workflow dependency query rather than the portal's newest-first Search
list when investigating a conversation:

```kusto
AppDependencies
| where TimeGenerated > ago(6h)
| where Name startswith "workflow."
| extend thread_id = tostring(Properties["workflow.thread_id"])
| project TimeGenerated, Name, thread_id, OperationId
| order by TimeGenerated desc
```

Open an end-to-end transaction for a returned `OperationId` to inspect the
correlated Foundry, model, workflow, and HITL hierarchy.
