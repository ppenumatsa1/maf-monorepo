#!/usr/bin/env bash

private_profile_resolve() {
  local root_dir="$1"
  local canonical="${root_dir}/../deployment/profiles/foundry-private.env"
  local requested="${2:-${DEPLOYMENT_PROFILE_FILE:-$canonical}}"

  if [[ "$requested" != "$canonical" ]]; then
    echo "WARNING: non-canonical private profile path is legacy_pending_cutover; prefer ${canonical}" >&2
  fi
  printf '%s\n' "$requested"
}
