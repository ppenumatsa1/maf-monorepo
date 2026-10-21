#!/usr/bin/env bash

private_profile_resolve() {
  local root_dir="$1"
  local canonical="${root_dir}/../deployment/profiles/foundry-private.env"
  local profile_loader="${root_dir}/../deployment/profile.sh"
  local requested selection requested_dir requested_path canonical_dir canonical_path

  if [[ -n "${2:-}" ]]; then
    requested="$2"
    selection="explicit"
  elif [[ -n "${DEPLOYMENT_PROFILE_FILE:-}" ]]; then
    requested="$DEPLOYMENT_PROFILE_FILE"
    selection="explicit"
  else
    requested="$canonical"
    selection="canonical"
  fi

  if [[ ! -f "$requested" || -L "$requested" || ! -r "$requested" ]]; then
    if [[ "$selection" == "explicit" ]]; then
      echo "deployment profile selection error: explicit local profile must be a readable regular file; path and values were not displayed." >&2
    else
      echo "deployment profile selection error: canonical repository profile is unavailable." >&2
    fi
    return 1
  fi

  requested_dir="$(cd "$(dirname "$requested")" && pwd -P)" || return 1
  requested_path="${requested_dir}/$(basename "$requested")"
  canonical_dir="$(cd "$(dirname "$canonical")" && pwd -P)" || return 1
  canonical_path="${canonical_dir}/$(basename "$canonical")"

  if [[ "$requested_path" == "$canonical_path" ]]; then
    selection="canonical"
  fi

  if ! bash "$profile_loader" validate "$requested_path"; then
    if [[ "$selection" == "explicit" ]]; then
      echo "deployment profile selection error: explicit local profile failed validation; path and values were not displayed." >&2
    else
      echo "deployment profile selection error: canonical repository profile failed validation." >&2
    fi
    return 1
  fi

  if [[ "$selection" == "explicit" ]]; then
    echo "deployment profile selection: using supported explicit local profile; path and values are not displayed." >&2
  else
    echo "deployment profile selection: using canonical repository profile; values are not displayed." >&2
  fi
  printf '%s\n' "$requested_path"
}
