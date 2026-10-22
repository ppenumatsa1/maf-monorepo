#!/usr/bin/env bash
set -euo pipefail

_profile_script_dir="$(cd "${BASH_SOURCE[0]%/*}" && pwd -P)"
_shared_profile_script="$(cd "$_profile_script_dir/../../deployment" && pwd -P)/profile.sh"
source "$_shared_profile_script"

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  [[ $# -eq 2 && ( "$1" == "validate" || "$1" == "validate-example" ) ]] || {
    printf 'Usage: %s <validate|validate-example> <profile-path>\n' "$0" >&2
    exit 2
  }
  deployment_profile_load "$2"
  if [[ "$1" == "validate-example" ]]; then
    deployment_profile_validate true
  else
    deployment_profile_validate
  fi
fi
