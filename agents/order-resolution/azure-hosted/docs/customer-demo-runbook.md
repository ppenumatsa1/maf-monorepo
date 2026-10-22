# Azure-Hosted Customer Demo and Operator Runbook

## Purpose

Prepare, demonstrate, validate, and recover the FastAPI-hosted Order Resolution
application without recording environment-specific values in tracked files.

## 1. Prepare an ignored target profile

Create a secret-free profile outside tracked documentation and deployment
examples. Use `.azure/azure-hosted.env` or set `AZURE_HOSTED_PROFILE` to another
ignored regular file. The minimum target identity is:

```dotenv
CONTRACT_VERSION=1
DEPLOYMENT_LANE=azure-hosted
AZURE_ENV_NAME=<azd-environment>
AZURE_TENANT_ID=<tenant-guid>
AZURE_SUBSCRIPTION_ID=<subscription-guid>
AZURE_RESOURCE_GROUP=<resource-group>
AZURE_LOCATION=<azure-region>
NAME_PREFIX=<name-prefix>
POSTGRES_DATABASE_NAME=<database-name>
```

The tracked bootstrap example documents additional approved model, database,
and capacity selectors. Keep user IDs, credentials, connection strings,
operator IPs, generated resource IDs, endpoints, and image references outside
the profile.

## 2. Verify operator context

1. Authenticate Azure CLI and AZD interactively.
2. Validate the profile as data; never source an unvalidated profile.
3. Confirm the active subscription matches the profile.
4. Confirm the selected AZD environment resolves the same target.
5. Stop on any mismatch.

## 3. Choose the lifecycle action

| Situation | Action |
| --- | --- |
| No platform exists | Fresh bootstrap |
| Platform exists and only the app changes | App-only release |
| Shared infrastructure intentionally changes | Steady-state preview, then explicit reconciliation |
| Only validation is needed | Release validation against the exact deployed source and release context |

Do not infer infrastructure execution from changed files.

## 4. Fresh bootstrap

1. Supply required untracked operator inputs through the shell or secret store.
2. Prepare the local AZD environment.
3. Run and review a fresh subscription-scope preview.
4. Stop on unexpected replacement, public exposure, identity expansion,
   PostgreSQL mismatch, or capacity failure.
5. Apply only through the authorized bootstrap path.
6. Verify the PostgreSQL server, database, schema, and backend managed identity.
7. Remove temporary bootstrap access and transition to steady state.

## 5. Routine app-only release

```bash
make release-app
```

The release must:

1. validate source and target selection;
2. deploy immutable backend and frontend images;
3. keep the backend internal and frontend external;
4. retain PostgreSQL and managed-identity access;
5. run smoke, browser E2E, and the three domain scenarios;
6. verify exact Application Insights correlation;
7. run report-only Foundry evaluation over captured HTTP results; and
8. aggregate secret-free final evidence.

## 6. Demonstrate the workflow

1. Open the external frontend endpoint from the selected AZD environment.
2. Run `ORD-1001` and confirm completion without HITL.
3. Run `ORD-1009`, confirm a durable approval request, approve it, and confirm
   one terminal result.
4. Run a damaged-item scenario and demonstrate approve or reject.
5. Reopen history and show the durable event timeline.
6. Show that AG-UI and CopilotKit can select the existing thread but cannot
   create or mutate workflow state.

## 7. Retain only sanitized evidence

Keep generated release evidence under
`.artifacts/releases/<release-id>/`. Do not copy live endpoint values,
subscription/resource identifiers, credentials, or customer data into tracked
documentation. Record only the profile-independent result and point operators
to the release bundle.

## 8. Rollback

1. Preserve the failed release bundle.
2. Restore the last known-good application source or image inputs.
3. Run a new app-only release and full evidence window.
4. Verify PostgreSQL history and pending approvals remain intact.
5. Do not use infrastructure reconciliation or database recreation as an
   application rollback shortcut.

## 9. Troubleshooting

- **Target mismatch:** stop and correct the ignored profile or AZD selection.
- **Backend is public:** stop the release and restore internal ingress.
- **Database login fails:** verify the retained server and backend managed
  identity; do not add a password fallback.
- **Evaluation fails:** inspect individual evaluator rows; do not accept a
  run-level pass with errors.
- **Telemetry is incomplete:** rerun the domain scenarios in a new release
  window; do not broaden the query to historical traffic.
- **Generated evidence contains sensitive values:** stop distribution, remove
  the artifact, rotate exposed credentials when applicable, and fix the
  producer before rerunning.
