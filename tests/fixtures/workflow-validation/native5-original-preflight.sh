set -euo pipefail
[[ "$GITHUB_REPOSITORY" == 'spicyChicken59/SpicyStock' ]]
[[ "$GITHUB_REPOSITORY_ID" == '1352997802' ]]
[[ "$GITHUB_REF" == 'refs/heads/main' && "$GITHUB_EVENT_NAME" == 'workflow_dispatch' ]]
[[ "$GITHUB_RUN_ATTEMPT" == '1' && "$READINESS_COMMENT_ID" =~ ^[1-9][0-9]*$ ]]
# These remain native run numbers. The guard independently verifies
# all three exact reviewed pre-job failures before admitting phase 1/2.
case "$MODE:$GITHUB_RUN_NUMBER" in rehearsal:4|real:5) ;; *) exit 1 ;; esac
[[ "$GITHUB_RUN_ID" =~ ^[1-9][0-9]*$ ]]
[[ "$RUNNER_TEMP" == /* && "$GITHUB_WORKSPACE" == /* ]]
[[ -d "$RUNNER_TEMP" && -d "$GITHUB_WORKSPACE" ]]
[[ "$RUNNER_TEMP" != *$'\n'* && "$RUNNER_TEMP" != *$'\r'* ]]
historical_temp_parent="$(realpath -e -- "$RUNNER_TEMP")"
historical_workspace="$(realpath -e -- "$GITHUB_WORKSPACE")"
[[ "$historical_temp_parent" != '/' && "$historical_temp_parent" != *$'\n'* && "$historical_temp_parent" != *$'\r'* ]]
[[ "$historical_temp_parent" != "$historical_workspace" && "$historical_temp_parent" != "$historical_workspace/"* ]]
historical_ancestor="$historical_temp_parent"
while true; do
  [[ ! -e "$historical_ancestor/.git" ]]
  [[ "$historical_ancestor" != '/' ]] || break
  historical_ancestor="$(dirname -- "$historical_ancestor")"
done
HISTORICAL_ROOT="$historical_temp_parent/historical-input-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
MPLCONFIGDIR="$HISTORICAL_ROOT/matplotlib"
export HISTORICAL_ROOT MPLCONFIGDIR
umask 077
mkdir -m 700 "$HISTORICAL_ROOT"
mkdir -m 700 "$MPLCONFIGDIR"
# GITHUB_ENV affects later steps only; the explicit exports above
# are required by this step's mkdir and any child process.
printf 'HISTORICAL_ROOT=%s\nMPLCONFIGDIR=%s\n' "$HISTORICAL_ROOT" "$MPLCONFIGDIR" >> "$GITHUB_ENV"
