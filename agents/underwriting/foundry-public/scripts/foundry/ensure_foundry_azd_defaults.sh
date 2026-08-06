#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

"$ROOT_DIR/scripts/foundry/bootstrap_azd_env.sh"

cd "$FOUNDRY_DIR"

get_env_value() {
  local key="$1"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$key" --no-prompt 2>/dev/null || true
}

set_if_missing() {
  local key="$1"
  local value="$2"
  local existing
  existing="$(get_env_value "$key")"
  if [[ -z "$existing" && -n "$value" ]]; then
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set "$key" "$value" --no-prompt >/dev/null
    echo "defaulted $key"
  fi
}

project_endpoint="$(get_env_value AZURE_AI_PROJECT_ENDPOINT)"
hosted_agent_name="$(get_env_value HOSTED_AGENT_NAME)"
project_name="$(get_env_value FOUNDRY_PROJECT_NAME)"

set_if_missing FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint"
set_if_missing FOUNDRY_PROJECT_ENDPOINT "$project_endpoint"
set_if_missing FOUNDRY_HOSTED_AGENT_NAME "$hosted_agent_name"
set_if_missing APPINSIGHTS_CONNECTION_STRING "$(get_env_value APPLICATIONINSIGHTS_CONNECTION_STRING)"

responses_endpoint="$(get_env_value AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT)"
agent_name_recorded="$(get_env_value AGENT_UNDERWRITING_HOSTED_NAME)"
expected_responses_endpoint="${project_endpoint}/agents/${hosted_agent_name}/endpoint/protocols/openai/responses?api-version=v1"

if [[ -n "$responses_endpoint" && "$responses_endpoint" != "$expected_responses_endpoint" ]]; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_NAME "" --no-prompt >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_VERSION "" --no-prompt >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT "" --no-prompt >/dev/null
  echo "cleared stale hosted-agent deployment metadata for project ${project_name}"
fi

if [[ -n "$agent_name_recorded" && "$agent_name_recorded" != "$hosted_agent_name" ]]; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_NAME "" --no-prompt >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_VERSION "" --no-prompt >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT "" --no-prompt >/dev/null
  echo "cleared hosted-agent metadata because HOSTED_AGENT_NAME changed to ${hosted_agent_name}"
fi
