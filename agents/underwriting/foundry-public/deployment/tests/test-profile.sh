#!/usr/bin/env bash
set -euo pipefail

unset DEPLOYMENT_PROFILE_ALLOW_ENV_OVERRIDES

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
scratch_dir="$project_dir/backend/.tmp/profile-contract-$$"
mkdir -p "$scratch_dir/bin"
trap 'rm -rf "$scratch_dir"' EXIT

profile="$scratch_dir/foundry-public.env"
cat >"$profile" <<'EOF'
CONTRACT_VERSION=1
DEPLOYMENT_LANE=foundry-public
AZURE_ENV_NAME=portable-underwriting
AZURE_SUBSCRIPTION_ID=11111111-1111-4111-8111-111111111111
AZURE_RESOURCE_GROUP=rg-portable-underwriting
AZURE_LOCATION=eastus2
NAME_PREFIX=portableuw
INFRASTRUCTURE_MODE=reuse
FOUNDRY_LOCATION=eastus2
FOUNDRY_ACCOUNT_NAME=portable-foundry
FOUNDRY_PROJECT_NAME=portable-underwriting
FOUNDRY_CUSTOM_SUBDOMAIN_NAME=portable-foundry
HOSTED_AGENT_NAME=underwriting-hosted
FOUNDRY_RUNTIME_CONNECTION_NAME=underwriting-runtime
FOUNDRY_MODEL_DEPLOYMENT_NAME=portable-model
FOUNDRY_MODEL_FORMAT=OpenAI
FOUNDRY_MODEL_NAME=model-name
FOUNDRY_MODEL_VERSION=1
FOUNDRY_MODEL_SKU_NAME=GlobalStandard
FOUNDRY_MODEL_CAPACITY=25
FOUNDRY_RAI_POLICY_NAME=Default.Policy
POSTGRES_SERVER_NAME=portable-postgres
POSTGRES_SERVER_LOCATION=eastus2
POSTGRES_SKU_NAME=Standard_D2s_v5
POSTGRES_SKU_TIER=GeneralPurpose
POSTGRES_VERSION=17
POSTGRES_DATABASE=underwriting
POSTGRES_ADMIN_USERNAME=pgadmin
POSTGRES_RUNTIME_USERNAME=underwriting_runtime
CONTAINER_REGISTRY_NAME=portableuwacr
CONTAINER_REGISTRY_SKU_NAME=Basic
CONTAINER_APPS_ENVIRONMENT_NAME=portable-cae
BACKEND_CONTAINER_APP_NAME=portable-backend
FRONTEND_CONTAINER_APP_NAME=portable-frontend
PUBLIC_BACKEND_MANAGED_IDENTITY_NAME=portable-backend-mi
PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME=portable-frontend-mi
APPLICATION_INSIGHTS_NAME=portable-ai
LOG_ANALYTICS_WORKSPACE_NAME=portable-log
BACKEND_IMAGE_REPOSITORY=portable-backend
FRONTEND_IMAGE_REPOSITORY=portable-frontend
HOSTED_AGENT_IMAGE_REPOSITORY=portable-hosted
EVALUATION_STORAGE_ACCOUNT_NAME=portableuweval
BOT_SERVICE_NAME=portable-underwriting-bot
BOT_SERVICE_SKU_NAME=F0
EOF

bash "$script_dir/profile.sh" validate "$profile"
for forbidden_key in \
  AZURE_TENANT_ID RUNTIME_DATABASE_URL DATABASE_URL \
  APPLICATIONINSIGHTS_CONNECTION_STRING POSTGRES_ADMIN_PASSWORD \
  POSTGRES_HOSTED_PASSWORD; do
  ! grep -q "^${forbidden_key}=" "$profile"
done

if bash "$script_dir/profile.sh" validate \
  "$script_dir/profiles/foundry-public.env.example" \
  >"$scratch_dir/template.out" 2>&1; then
  echo "The generic profile template must fail until placeholders are replaced." >&2
  exit 1
fi

wrong_region="$scratch_dir/wrong-region.env"
sed 's/^POSTGRES_SERVER_LOCATION=.*/POSTGRES_SERVER_LOCATION=westus2/' \
  "$profile" >"$wrong_region"
if bash "$script_dir/profile.sh" validate "$wrong_region" \
  >"$scratch_dir/region.out" 2>&1; then
  echo "The public profile must require a complete single-region target." >&2
  exit 1
fi
grep -Fq 'public deployment requires one region' "$scratch_dir/region.out"

override_profile="$scratch_dir/override.env"
sed 's/^AZURE_LOCATION=.*/AZURE_LOCATION=placeholder/' "$profile" >"$override_profile"
DEPLOYMENT_PROFILE_ALLOW_ENV_OVERRIDES=true \
AZURE_LOCATION=eastus2 \
FOUNDRY_LOCATION=eastus2 \
POSTGRES_SERVER_LOCATION=eastus2 \
  bash "$script_dir/profile.sh" validate "$override_profile"

cat >"$scratch_dir/bin/azd" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$scratch_dir/bin/azd"

AZD_COMMAND="$scratch_dir/bin/azd" AZD_LOG="$scratch_dir/azd.log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 11111111-1111-4111-8111-111111111111' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-portable-underwriting' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$scratch_dir/azd.log"
grep -Fq 'env set FOUNDRY_MODEL_CAPACITY 25' "$scratch_dir/azd.log"
grep -Fq 'env set HOSTED_AGENT_IMAGE_REPOSITORY portable-hosted' "$scratch_dir/azd.log"
grep -Fq 'env set BOT_SERVICE_NAME portable-underwriting-bot' "$scratch_dir/azd.log"

bootstrap_profile="$scratch_dir/foundry-public-bootstrap.env"
sed 's/^INFRASTRUCTURE_MODE=reuse$/INFRASTRUCTURE_MODE=bootstrap/' \
  "$profile" >"$bootstrap_profile"
bash "$script_dir/profile.sh" validate "$bootstrap_profile"
: >"$scratch_dir/azd.log"
AZD_COMMAND="$scratch_dir/bin/azd" AZD_LOG="$scratch_dir/azd.log" \
  bash "$script_dir/apply-azd-profile.sh" "$bootstrap_profile"
grep -Fq 'env set INFRASTRUCTURE_MODE bootstrap' "$scratch_dir/azd.log"
! grep -Fq 'env set INFRASTRUCTURE_MODE reuse' "$scratch_dir/azd.log"

git -C "$project_dir" check-ignore --no-index -q deployment/profiles/foundry-public.env
! git -C "$project_dir" check-ignore -q deployment/profiles/foundry-public.env.example

if grep -REn \
  'AZURE_SUBSCRIPTION_ID=[0-9a-fA-F-]{36}|AZURE_RESOURCE_GROUP=rg-[A-Za-z0-9-]+|AZURE_LOCATION=(eastus2|westus2)' \
  "$script_dir/profiles"/*.example; then
  echo "Tracked profile templates must not contain a real target." >&2
  exit 1
fi
