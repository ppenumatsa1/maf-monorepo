#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scripts_dir="$root_dir/scripts/foundry"

for script in \
  "$root_dir/deployment/profile.sh" \
  "$root_dir/deployment/apply-azd-profile.sh" \
  "$scripts_dir/preflight_foundry_model.sh" \
  "$scripts_dir/preview_public_infrastructure.sh"; do
  bash -n "$script"
done

bash "$root_dir/deployment/tests/test-profile.sh"
! git -C "$root_dir" ls-files --error-unmatch \
  infra/foundry-hosted/.azure/config.json >/dev/null 2>&1
! git -C "$root_dir" ls-files --error-unmatch \
  infra/foundry-hosted/.azure/.state-change >/dev/null 2>&1

grep -A3 -F 'protocol: responses' "$root_dir/infra/foundry-hosted/azure.yaml" |
  grep -Fq 'version: 2.0.0'
grep -A3 -F 'protocol: activity' "$root_dir/infra/foundry-hosted/azure.yaml" |
  grep -Fq 'version: 2.0.0'

main_bicep="$root_dir/infra/foundry-hosted/iac/main.bicep"
grep -Fq "publicNetworkAccess: 'Enabled'" "$main_bicep"
grep -A30 -F 'resource backendContainerApp' "$main_bicep" |
  grep -Fq 'external: false'
grep -A30 -F 'resource frontendContainerApp' "$main_bicep" |
  grep -Fq 'external: true'
if grep -Eiq \
  'privateEndpoint|virtualNetworks|subnets|bastion|vnet[[:alnum:]_-]*runner' \
  "$root_dir/infra/foundry-hosted/iac/"*.bicep \
  "$root_dir/infra/foundry-hosted/iac/teams/"*.bicep; then
  echo "Public IaC must not contain private-network or VNet-runner resources." >&2
  exit 1
fi

if grep -REn \
  'AZURE_SUBSCRIPTION_ID=[0-9a-fA-F-]{36}|AZURE_RESOURCE_GROUP=rg-[A-Za-z0-9-]+|AZURE_LOCATION=(eastus2|westus2)' \
  "$root_dir/deployment/profiles"/*.example \
  "$root_dir/deployment/profile.sh" \
  "$scripts_dir/aggregate_release_evidence.py" \
  "$scripts_dir/capacity_preflight.py" \
  "$scripts_dir/internalize_backend_ingress.sh" \
  "$scripts_dir/preview_public_infrastructure.sh"; then
  echo "Portable public tooling contains a tracked target value." >&2
  exit 1
fi
if grep -En '7df95e88|rg-maf-underwriting' \
  "$scripts_dir/aggregate_release_evidence.py" \
  "$scripts_dir/internalize_backend_ingress.sh" \
  "$scripts_dir/verify_foundry_release.sh"; then
  echo "Historical Underwriting target enforcement remains in public tooling." >&2
  exit 1
fi
if grep -En \
  'hosted_repository="underwriting-hosted"|image_repository="underwriting-hosted"|/underwriting-hosted(@|:)' \
  "$scripts_dir/build_release_images.sh" \
  "$scripts_dir/deploy_hosted_container.sh" \
  "$scripts_dir/verify_foundry_release.sh"; then
  echo "Hosted image tooling must use HOSTED_AGENT_IMAGE_REPOSITORY." >&2
  exit 1
fi

git -C "$root_dir" check-ignore --no-index -q deployment/profiles/foundry-public.env
git -C "$root_dir" check-ignore --no-index -q .artifacts/teams-publication/packages/appPackage-1.0.0.zip
git -C "$root_dir" check-ignore --no-index -q .artifacts/teams-publication/sensitive-state.json
git -C "$root_dir" check-ignore --no-index -q .artifacts/teams-publication/catalog-state.json
git -C "$root_dir" check-ignore --no-index -q .artifacts/teams-publication/publication-token.json
git -C "$root_dir" check-ignore --no-index -q .artifacts/teams-publication/user-state.json

if grep -REn 'mktemp|/tmp/' \
  "$scripts_dir/preview_public_infrastructure.sh" \
  "$scripts_dir/preflight_foundry_model.sh" \
  "$scripts_dir/publish_teams_agent.py"; then
  echo "Public release tooling must keep scratch state inside the ignored project tree." >&2
  exit 1
fi

echo "Underwriting public IaC portability contract passed."
