#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"

for script in \
  "$root_dir/scripts/foundry/capture_release_rollback_baseline.sh" \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_dev.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh" \
  "$root_dir/scripts/foundry/hosted_e2e.sh" \
  "$root_dir/scripts/foundry/run_foundry_trace_eval.sh" \
  "$root_dir/scripts/foundry/verify_foundry_release.sh" \
  "$root_dir/scripts/foundry/verify_release_rollback.sh" \
  "$root_dir/scripts/foundry/verify_telemetry.sh"; do
  bash -n "$script"
done

"$root_dir/.venv/bin/python" -m py_compile \
  "$root_dir/scripts/foundry/hosted_review_e2e.py"

grep -A2 '^foundry-release:' "$root_dir/Makefile" |
  grep -Fq 'foundry-python-wheelhouse'
grep -A2 '^foundry-release-package:' "$root_dir/Makefile" |
  grep -Fq 'foundry-python-wheelhouse'
grep -A2 '^foundry-release-build:' "$root_dir/Makefile" |
  grep -Fq 'foundry-python-wheelhouse'
grep -A8 '^foundry-release-deploy:' "$root_dir/Makefile" |
  grep -Fq 'foundry-release-hosted-activate'
grep -A8 '^foundry-release-deploy:' "$root_dir/Makefile" |
  grep -Fq 'foundry-release-app-deploy'

for script in \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh"; do
  grep -Fq '@sha256:[0-9a-f]{64}' "$script"
done

grep -Fq 'hosted_repository="$(required_env HOSTED_AGENT_IMAGE_REPOSITORY)"' \
  "$root_dir/scripts/foundry/build_release_images.sh"
grep -Fq 'image_repository="$(required_env HOSTED_AGENT_IMAGE_REPOSITORY)"' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'AGENT_UNDERWRITING_HOSTED_IMAGE_REPOSITORY' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'protocol=AgentEndpointProtocol.ACTIVITY' \
  "$root_dir/scripts/foundry/deploy_hosted_container.py"
grep -Fq '.protocol == "activity" and .version == "2.0.0"' \
  "$root_dir/scripts/foundry/verify_foundry_release.sh"
grep -A2 '^foundry-teams-native-acceptance:' "$root_dir/Makefile" |
  grep -Fq 'hosted_review_e2e.py'
! grep -Fq 'hosted_review_e2e.py' \
  "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'run_timed_stage native_teams_acceptance make foundry-teams-native-acceptance' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'This script does not synthesize Bot or Activity traffic.' \
  "$root_dir/scripts/foundry/hosted_review_e2e.py"

grep -Fq 'make foundry-release-rollback-baseline' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq -- '--target-port "$backend_target_port"' \
  "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq 'BACKEND_READINESS_ATTEMPTS:-120' \
  "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq 'latestReadyRevisionName' \
  "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq "jq -r '.properties.latestReadyRevisionName // empty'" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh"
grep -Fq 'run_timed_stage rollback_verification make foundry-rollback-verify' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
[[ "$(grep -c -- '--all' "$root_dir/scripts/foundry/verify_release_rollback.sh")" -eq 2 ]]
grep -Fq 'name: "web_referral_pending"' "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'name: "web_review_spoofed_identity_rejected"' \
  "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq "X-MS-CLIENT-PRINCIPAL-ID: spoofed-release-reviewer" \
  "$root_dir/scripts/foundry/hosted_e2e.sh"
! grep -Fq 'api_post_review_json' "$root_dir/scripts/foundry/hosted_e2e.sh"
grep -Fq 'FOUNDRY_ROLLBACK_EVIDENCE_FILE' \
  "$root_dir/scripts/foundry/release_paths.sh"

! grep -Fq -- '--input-file' \
  "$root_dir/infra/foundry-hosted/runtime/smoke-test.sh"
grep -Fq -- '--data-binary "@$request_file"' \
  "$root_dir/infra/foundry-hosted/runtime/smoke-test.sh"
grep -Fq -- '--oauth2-bearer "$token"' \
  "$root_dir/infra/foundry-hosted/runtime/smoke-test.sh"
grep -Fq 'workflow_runs' \
  "$root_dir/infra/foundry-hosted/runtime/smoke-test.sh"
grep -Fq 'underwriting_results' \
  "$root_dir/infra/foundry-hosted/runtime/smoke-test.sh"
