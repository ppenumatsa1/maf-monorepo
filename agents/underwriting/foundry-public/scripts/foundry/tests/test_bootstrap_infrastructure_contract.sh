#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
prepare_script="$root_dir/scripts/foundry/prepare_bootstrap_env.sh"
template="$root_dir/infra/foundry-hosted/iac/main.bicep"
mock_bin="$root_dir/scripts/foundry/tests/mock-bin"
provision_workflow="$root_dir/../../../.github/workflows/underwriting-public-provision.yml"

output="$(
  PATH="$mock_bin:$PATH" bash "$prepare_script" 2>&1
)"

for expected in \
  'set INFRASTRUCTURE_MODE=bootstrap' \
  'set NAME_PREFIX=mafunderwriting' \
  'set RESOURCE_NAME_SUFFIX=2a5b830c' \
  'set POSTGRES_SERVER_NAME=mafunderwrit2a5b830cpg' \
  'set CONTAINER_REGISTRY_NAME=mafunderwrit2a5b830cacr' \
  'set BACKEND_IMAGE_REPOSITORY=underwriting-public-backend' \
  'set FRONTEND_IMAGE_REPOSITORY=underwriting-public-frontend' \
  'set FOUNDRY_RUNTIME_CONNECTION_NAME=underwritingruntimesecrets' \
  'set HOSTED_AGENT_NAME=underwriting-hosted'; do
  grep -Fxq "$expected" <<<"$output"
done

grep -Fq 'set_default FOUNDRY_ACCOUNT_NAME "${resource_name_base}ai"' "$prepare_script"
grep -Fq "param infrastructureMode string = 'bootstrap'" "$template"
grep -Fq "resource foundryModelDeployment" "$template"
grep -A18 "resource foundryAccountBootstrap" "$template" | grep -Fq 'allowProjectManagement: true'
grep -A18 "resource foundryAccountBootstrap" "$template" | grep -Fq 'disableLocalAuth: true'
grep -A4 -Fq "resource foundryProjectBootstrap" "$template"
grep -A4 "resource foundryProjectBootstrap" "$template" | grep -Fq 'location: location'
grep -A16 "resource foundryProjectBootstrap" "$template" | grep -Fq 'foundryModelDeployment'
grep -A16 "resource publicBackendFoundryUser" "$template" | grep -Fq 'foundryProjectBootstrap'
grep -Fq "resource backendContainerApp" "$template"
grep -Fq "resource frontendContainerApp" "$template"
grep -A30 "resource backendContainerApp" "$template" | grep -Fq 'external: false'
grep -A30 "resource frontendContainerApp" "$template" | grep -Fq 'external: true'
grep -Fq "name: 'NGINX_API_UPSTREAM'" "$template"
grep -Fq "name: 'DB_SCHEMA_MANAGED_EXTERNALLY'" "$template"
grep -Fq "output FOUNDRY_RUNTIME_CONNECTION_NAME" "$template"
grep -Fq "output FOUNDRY_MODEL_DEPLOYMENT_NAME" "$template"
grep -Fq "reference(foundryAccountId, '2025-06-01').endpoint" "$template"
! grep -Fq "reference(foundryAccountId, '2025-06-01').properties.endpoint" "$template"
! grep -Eq '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' \
  "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
grep -Fq 'required_env_value POSTGRES_SERVER_NAME' "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
grep -Fq 'INFRASTRUCTURE_MODE="$(required_env_value INFRASTRUCTURE_MODE)"' "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
grep -Fq "requires a bootstrap-mode environment" "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
grep -Fq 'actual_server_location=' "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
grep -Fq 'does not match the existing server location' "$root_dir/scripts/foundry/rebuild_postgres_server.sh"
! grep -Fq -- '--rule-name' "$root_dir/scripts/foundry/provision_postgres_runtime_credentials.sh"
! grep -Fq -- '--database-name' "$root_dir/scripts/foundry/provision_postgres_runtime_credentials.sh"
grep -Fq -- '--server-name "$server_name"' "$root_dir/scripts/foundry/provision_postgres_runtime_credentials.sh"
grep -Fq 'Backend ingress must already be internal' "$root_dir/scripts/foundry/deploy_public_backend.sh"
! grep -Fq 'az containerapp ingress update' "$root_dir/scripts/foundry/deploy_public_backend.sh"
! grep -A20 'az containerapp update' "$root_dir/scripts/foundry/deploy_public_backend.sh" | grep -Fq -- '--target-port'
grep -Fq 'required_env AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT' "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq '"AZURE_CLIENT_ID=${backend_identity_client_id}"' "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq '"FOUNDRY_HOSTED_AGENT_VERSION=${hosted_agent_version}"' "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq '"DB_SCHEMA_MANAGED_EXTERNALLY=true"' "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq '"NGINX_API_UPSTREAM=https://${backend_fqdn}"' "$root_dir/scripts/foundry/deploy_public_frontend.sh"
grep -Fq 'Frontend ingress must already be external' "$root_dir/scripts/foundry/deploy_public_frontend.sh"
! grep -Fq 'az containerapp ingress update' "$root_dir/scripts/foundry/deploy_public_frontend.sh"
! grep -Fq 'VITE_API_BASE_URL=https://' "$root_dir/scripts/foundry/deploy_public_frontend.sh"
grep -Fq 'location /api/' "$root_dir/frontend/nginx.conf.template"
grep -Fq 'location = /backend-health' "$root_dir/frontend/nginx.conf.template"
grep -Fq 'api_base_url="$frontend_url"' "$root_dir/scripts/foundry/hosted_e2e.sh"
! grep -Fq '$backend_url/api/' "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'index("idempotency_skip") != null' "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'index("retry_backoff") != null' "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'backend:' "$root_dir/infra/foundry-hosted/azure.yaml"
grep -Fq 'frontend:' "$root_dir/infra/foundry-hosted/azure.yaml"
grep -Fq 'underwriting-hosted:' "$root_dir/infra/foundry-hosted/azure.yaml"
grep -Fq 'task_adherence' "$root_dir/backend/eval.yaml"
grep -Fq 'intent_resolution' "$root_dir/backend/eval.yaml"
grep -Fq 'relevance' "$root_dir/backend/eval.yaml"
! grep -Fq 'task_completion' "$root_dir/backend/eval.yaml"
grep -Fq 'foundry-release-readiness:' "$root_dir/Makefile"
grep -A5 'foundry-release-readiness:' "$root_dir/Makefile" | grep -Fq 'foundry-runtime-connection'
grep -Fq 'foundry-provision: foundry-provision-infrastructure foundry-provision-converge' "$root_dir/Makefile"
grep -A12 'foundry-provision-infrastructure:' "$root_dir/Makefile" | grep -Fq 'bootstrap) ./scripts/foundry/prepare_bootstrap_env.sh'
grep -A12 'foundry-provision-infrastructure:' "$root_dir/Makefile" | grep -Fq 'reuse) ./scripts/foundry/bootstrap_azd_env.sh; ./scripts/foundry/ensure_foundry_azd_defaults.sh'
grep -A4 'foundry-provision-converge:' "$root_dir/Makefile" | grep -Fq 'foundry-postgres-credentials'
grep -A4 'foundry-provision-converge:' "$root_dir/Makefile" | grep -Fq 'foundry-postgres-readiness'
grep -Fq 'foundry-postgres-credentials: foundry-postgres-schema' "$root_dir/Makefile"
! grep -Fq 'bootstrap_postgres_schema.sh' "$root_dir/scripts/foundry/provision_postgres_runtime_credentials.sh"
grep -Fq 'run: FOUNDRY_FULL_INFRA_AUTHORIZED=true make foundry-provision-infrastructure' "$provision_workflow"
grep -Fq 'run: make foundry-provision-converge' "$provision_workflow"
grep -Fq 'name: Prepare schema migration tooling' "$provision_workflow"
grep -Fq 'foundry-package:' "$root_dir/Makefile"
grep -Fq 'foundry-verify:' "$root_dir/Makefile"
grep -Fq 'foundry-evidence:' "$root_dir/Makefile"
! grep -Eq '7df95e88|rg-maf-underwriting|Refusing migration outside the canonical' \
  "$root_dir/scripts/foundry/internalize_backend_ingress.sh"
grep -Fq 'Backend ingress must already be internal. Use the one-time foundry-backend-internalize command for migration.' \
  "$root_dir/scripts/foundry/deploy_public_backend.sh"
! grep -R -Fq 'agents/order-resolution' \
  --exclude='test_bootstrap_infrastructure_contract.sh' \
  "$root_dir/deployment" "$root_dir/scripts" "$root_dir/infra" "$root_dir/frontend" "$root_dir/backend"
grep -Fq 'set_value INFRASTRUCTURE_MODE reuse' "$root_dir/scripts/foundry/bootstrap_azd_env.sh"
grep -Fq 'set_if_missing NAME_PREFIX underwriting' "$root_dir/scripts/foundry/bootstrap_azd_env.sh"

az bicep build --file "$template" --stdout | python3 -c '
import json
import sys

template = json.load(sys.stdin)
assignments = [
    resource
    for resource in template["resources"]
    if resource["type"] == "Microsoft.Authorization/roleAssignments"
]
assert len(assignments) == 10
assert all("scope" in assignment for assignment in assignments)
assert sum("resource-scope-v2" in assignment["name"] for assignment in assignments) == 9
assert all(
    "subscriptionResourceId" in assignment["properties"]["roleDefinitionId"]
    for assignment in assignments
)
'
az bicep build \
  --file "$root_dir/infra/foundry-hosted/iac/runtime-secret-connection.bicep" \
  --stdout >/dev/null
