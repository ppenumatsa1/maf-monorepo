#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <profile-path>\n' "$0" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
repository_root="$(cd "$root_dir/../../.." && pwd -P)"
shared_applicator="$repository_root/agents/order-resolution/deployment/apply-azd-profile.sh"

[[ -f "$shared_applicator" ]] || {
  printf 'Underwriting deployment profile error: shared profile applicator is unavailable\n' >&2
  exit 1
}

AZD_PROJECT_DIR="$root_dir/infra/foundry-hosted" \
  bash "$shared_applicator" "$1"
