#!/bin/bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
script="$ROOT_DIR/scripts/release/reconcile-infrastructure.sh"
safe_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
safe_home="${HOME:-}"

[[ "$safe_home" == /* && -d "$safe_home" ]] || {
  echo "Protected reconciliation requires a usable absolute HOME directory." >&2
  exit 1
}
safe_home="$(cd "$safe_home" && pwd -P)"
home_owner="$(/usr/bin/stat -c '%u' "$safe_home")"
home_mode="$(/usr/bin/stat -c '%a' "$safe_home")"
if [[ "$home_owner" != "$UID" && "$home_owner" != "0" ]] ||
  [[ $((8#$home_mode & 8#022)) -ne 0 ]]; then
  echo "Protected reconciliation refuses an unsafe HOME configuration directory." >&2
  exit 1
fi

environment=(
  /usr/bin/env -i
  "HOME=$safe_home"
  "PATH=$safe_path"
  "LANG=${LANG:-C.UTF-8}"
  "LC_ALL=${LC_ALL:-C.UTF-8}"
)

for variable in \
  AZURE_ENV_NAME RELEASE_RUN_ID RELEASE_DRY_RUN AZURE_SUBSCRIPTION_ID
do
  if [[ -v "$variable" ]]; then
    environment+=("$variable=${!variable}")
  fi
done

exec "${environment[@]}" /bin/bash "$script" "$@"
