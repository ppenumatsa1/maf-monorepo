# Underwriting Foundry-public deployment profiles

This lane uses the shared Order Resolution non-secret deployment profile
contract to select an existing Azure target. A profile identifies only the
subscription, resource group, location, AZD environment, name prefix, and
`foundry-public` lane.

Copy `profiles/foundry-public.env` outside source control, replace its
placeholders, then apply it:

```bash
./deployment/apply-azd-profile.sh /secure/path/underwriting-foundry-public.env
```

The target AZD environment must already contain the non-secret identities for
the existing Foundry account/project, ACR, PostgreSQL server/database,
Container Apps, managed identity, Application Insights, and Log Analytics
workspace. It must also retain its existing lane-local secrets, including the
runtime database URL and PostgreSQL credentials.

Profiles never contain secrets, endpoints, resource names, image tags, or
resource IDs. Applying a profile does not authenticate, provision, deploy, or
read a secret. Routine `make foundry-release` is app-only. Provisioning,
database rebuild/schema operations, RBAC, networking, and Foundry connections
remain explicit separate operations.
