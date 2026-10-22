#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
scratch_dir="$project_dir/backend/.tmp/profile-contract-$$"
mkdir -p "$scratch_dir/bin"
trap 'rm -rf "$scratch_dir"' EXIT

profile="$scratch_dir/foundry-public.env"
cat >"$profile" <<'EOF'
CONTRACT_VERSION=1
DEPLOYMENT_LANE=foundry-public
AZURE_ENV_NAME=portable-public
AZURE_SUBSCRIPTION_ID=11111111-1111-4111-8111-111111111111
AZURE_RESOURCE_GROUP=rg-portable-public
AZURE_LOCATION=regionone
INFRASTRUCTURE_MODE=reuse
FOUNDRY_LOCATION=regionone
FOUNDRY_ACCOUNT_NAME=portable-foundry
FOUNDRY_PROJECT_NAME=portable-project
FOUNDRY_CUSTOM_SUBDOMAIN_NAME=portable-foundry
HOSTED_AGENT_NAME=portable-agent
FOUNDRY_RUNTIME_CONNECTION_NAME=portable-runtime
FOUNDRY_MODEL_DEPLOYMENT_NAME=portable-chat
FOUNDRY_MODEL_FORMAT=OpenAI
FOUNDRY_MODEL_NAME=chat-model
FOUNDRY_MODEL_VERSION=1
FOUNDRY_MODEL_SKU_NAME=GlobalStandard
FOUNDRY_MODEL_CAPACITY=25
FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME=portable-embeddings
FOUNDRY_EMBEDDINGS_MODEL_FORMAT=OpenAI
FOUNDRY_EMBEDDINGS_MODEL_NAME=embedding-model
FOUNDRY_EMBEDDINGS_MODEL_VERSION=1
FOUNDRY_EMBEDDINGS_MODEL_SKU_NAME=GlobalStandard
FOUNDRY_EMBEDDINGS_MODEL_CAPACITY=2
FOUNDRY_EVAL_MODEL=portable-evaluator
FOUNDRY_EVALUATION_MODEL_FORMAT=OpenAI
FOUNDRY_EVALUATION_MODEL_NAME=evaluator-model
FOUNDRY_EVALUATION_MODEL_VERSION=1
FOUNDRY_EVALUATION_MODEL_SKU_NAME=GlobalStandard
FOUNDRY_EVALUATION_MODEL_CAPACITY=3
FOUNDRY_RAI_POLICY_NAME=Default.Policy
AI_SEARCH_SERVICE_NAME=portable-search
AI_SEARCH_LOCATION=regionone
AI_SEARCH_SKU_NAME=basic
POSTGRES_SERVER_NAME=portable-postgres
POSTGRES_SERVER_LOCATION=regionone
POSTGRES_SKU_NAME=Standard_D2s_v5
POSTGRES_SKU_TIER=GeneralPurpose
POSTGRES_VERSION=17
POSTGRES_DATABASE=appdb
POSTGRES_ADMIN_USERNAME=pgadmin
POSTGRES_RUNTIME_USERNAME=app_runtime
CONTAINER_REGISTRY_NAME=portableacr
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
EVALUATION_STORAGE_ACCOUNT_NAME=portableeval
BOT_SERVICE_NAME=portable-bot
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

missing_profile="$scratch_dir/missing.env"
grep -v '^FOUNDRY_MODEL_CAPACITY=' "$profile" >"$missing_profile"
if bash "$script_dir/profile.sh" validate "$missing_profile" \
  >"$scratch_dir/missing.out" 2>&1; then
  echo "Profiles missing desired capacity must fail closed." >&2
  exit 1
fi
grep -Fq 'required key is missing: FOUNDRY_MODEL_CAPACITY' "$scratch_dir/missing.out"

cat >"$scratch_dir/bin/azd" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$scratch_dir/bin/azd"

AZD_COMMAND="$scratch_dir/bin/azd" AZD_LOG="$scratch_dir/azd.log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 11111111-1111-4111-8111-111111111111' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-portable-public' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_LOCATION regionone' "$scratch_dir/azd.log"
grep -Fq 'env set FOUNDRY_MODEL_SKU_NAME GlobalStandard' "$scratch_dir/azd.log"
grep -Fq 'env set FOUNDRY_MODEL_CAPACITY 25' "$scratch_dir/azd.log"
grep -Fq 'env set BOT_SERVICE_NAME portable-bot' "$scratch_dir/azd.log"

git -C "$project_dir" check-ignore --no-index -q deployment/profiles/foundry-public.env
! git -C "$project_dir" check-ignore -q deployment/profiles/foundry-public.env.example

router_output="$("$project_dir/scripts/skills/deployment-mode-router.sh" HEAD)"
grep -Fxq 'deploy_mode=app_only' <<<"$router_output"
