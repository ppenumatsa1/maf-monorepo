# Underwriting Foundry Public Runtime Profiles

## Purpose

Select a public Azure target without embedding its identity in current-state
documentation or application source.

The active profile must be an operator-owned, non-secret file outside the
repository. The checked-in
`profiles/foundry-public.env.example` is a sanitized template, not proof of a
current deployment.

## Profile contract

```dotenv
CONTRACT_VERSION=1
DEPLOYMENT_LANE=foundry-public
AZURE_ENV_NAME=<local-azd-environment-name>
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=<resource-group-name>
AZURE_LOCATION=<supported-region>
NAME_PREFIX=<portable-name-prefix>
```

Profiles must not contain:

- tenant or user identity;
- passwords, keys, tokens, or connection strings;
- endpoints or generated resource names;
- resource IDs;
- operator IP addresses;
- image tags or digests;
- Teams package/catalog state;
- release evidence.

Create and protect the external file:

```bash
install -d -m 700 "$HOME/.config/maf"
export FOUNDRY_DEPLOYMENT_PROFILE="$HOME/.config/maf/underwriting-foundry-public.env"
install -m 600 deployment/profiles/foundry-public.env.example \
  "$FOUNDRY_DEPLOYMENT_PROFILE"
```

Apply it:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
```

Applying a profile does not authenticate, preview, provision, deploy, publish,
or read a secret.

## Reuse/app-only path

Use for an existing environment:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap
make foundry-release-readiness
RELEASE_ID="<release-id>" make foundry-release
```

The retained AZD environment must already contain the required non-secret
resource outputs and local-only secrets. Routine release is hard app-only and
must not reconcile infrastructure.

## Clean bootstrap path

Use only after explicit authorization:

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE="$FOUNDRY_DEPLOYMENT_PROFILE"
make foundry-bootstrap-env
make foundry-iac-build
make foundry-provision-preview
```

After reviewed approval:

```bash
FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-provision
```

Bootstrap mode remains explicit until Bicep creates the target resources.
Only then does hydration switch the selected AZD environment to reuse mode.
The provision command also applies schema migration, converges the runtime
credential and `CustomKeys` connection, and verifies PostgreSQL readiness.
Then run the app-only release. Provisioning alone is not deployment acceptance.

## Protected workflow profiles

Protected GitHub workflows materialize the same validated non-secret profile
from the `FOUNDRY_DEPLOYMENT_PROFILE_B64` environment variable, authenticate
with OIDC, and verify subscription parity before applying it. Runtime and
administrator secrets stay in protected GitHub environment secrets.

The workflow profile is transient under `.artifacts/workflows/` and must not be
uploaded as evidence. Microsoft 365 Shared publication is excluded from GitHub
Actions because it requires delegated interactive user authentication.

## Runtime database contract

- Administrator tooling owns schema DDL.
- Backend and hosted runtime use a dedicated least-privilege credential.
- The project `CustomKeys` connection holds the runtime URL.
- Hosted metadata contains only the literal connection placeholder.
- Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Readiness must prove TLS, intended public firewall posture, schema parity,
  runtime access, and denial of DDL/role creation.

## Evidence

Release-local artifacts may be written under `.artifacts/releases/` by the
checked-in tooling. They remain operational state, not current-state
documentation.

Exact target identifiers, release IDs, hosted versions, counts, timings, and
live endpoints belong only in the deployment plan and dated delivery ledger.
See [deployment flow](../docs/design/deployment-flow.md).
