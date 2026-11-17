#!/usr/bin/env bash
# Generate (and optionally run) the Harbor commands for a tb-science task, with
# all the auth / cache gotchas baked in. Prints the commands by default; pass
# --run to execute them.
#
#   ./examples/original-three/scripts/run_task.sh DEVCONN-001                 # print oracle+gpt-5.5+claude cmds
#   ./examples/original-three/scripts/run_task.sh DEVCONN-001 oracle          # just the oracle command
#   ./examples/original-three/scripts/run_task.sh DEVCONN-001 gpt-5.5 --run   # run GPT-5.5 (k=3)
#   ./examples/original-three/scripts/run_task.sh DEVCONN-001 all --run       # run all three
#
# agent: oracle | gpt-5.5 | claude | all (default: all)
# Reads a warm ~/nilearn_data cache if present (skips the ~30-min ds000228 fetch).
set -euo pipefail

TASK="${1:?usage: run_task.sh <TASK_ID_OR_DIR> [oracle|gpt-5.5|claude|all] [--run]}"
case "$TASK" in
  GRADIENT-001|SOCIALBRAIN-001|DEVCONN-001)
    EXAMPLES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    TASK="$EXAMPLES_DIR/$TASK"
    ;;
esac
AGENT="${2:-all}"; [[ "${2:-}" == --run ]] && AGENT="all"
RUN=""; for a in "$@"; do [[ "$a" == --run ]] && RUN=1; done
[[ -d "$TASK" ]] || { echo "no such task dir: $TASK (use a task ID or an existing directory)"; exit 1; }
printf -v TASK_ARG '%q' "$TASK"

OUT="${OUT:-jobs}"
MNT=""
[[ -d "$HOME/nilearn_data" ]] && \
  MNT="--mounts '[{\"type\":\"bind\",\"source\":\"$HOME/nilearn_data\",\"target\":\"/nilearn_data\",\"read_only\":true}]' --ae NILEARN_DATA=/nilearn_data"

cmd_oracle="harbor run -p $TASK_ARG -a oracle -k 1 -o $OUT $MNT -y"
# GPT-5.5 via a ChatGPT login (~/.codex/auth.json) needs CODEX_FORCE_AUTH_JSON=1;
# with an OPENAI_API_KEY exported you can drop that --ae.
cmd_gpt="harbor run -p $TASK_ARG -a codex -m gpt-5.5 --ak reasoning_effort=xhigh -k 3 -o $OUT $MNT --ae CODEX_FORCE_AUTH_JSON=1 -y"
# claude-code reads CLAUDE_CODE_OAUTH_TOKEN from host env; if unset, run
# `python examples/original-three/scripts/patch_harbor_oauth.py` once to fall back to your ~/.claude login.
cmd_claude="harbor run -p $TASK_ARG -a claude-code -m claude-opus-4-8 -k 3 -o $OUT $MNT -y"

emit(){ # $1 label  $2 command
  echo "# $1"; echo "$2"; echo
  if [[ -n "$RUN" ]]; then eval "$2"; fi
}

case "$AGENT" in
  oracle)  emit "oracle (expect reward 1.0)"        "$cmd_oracle" ;;
  gpt-5.5) emit "GPT-5.5 xhigh (expect FAIL, k=3)"  "$cmd_gpt" ;;
  claude)  emit "Claude Opus 4.8 (expect FAIL, k=3)" "$cmd_claude" ;;
  all)
    emit "oracle (expect reward 1.0)"        "$cmd_oracle"
    emit "GPT-5.5 xhigh (expect FAIL, k=3)"  "$cmd_gpt"
    emit "Claude Opus 4.8 (expect FAIL, k=3)" "$cmd_claude" ;;
  *) echo "unknown agent: $AGENT (oracle|gpt-5.5|claude|all)"; exit 1 ;;
esac

[[ -z "$RUN" ]] && echo "# add --run to execute. Then hand re-score each run's findings.md (see examples/original-three/upstream-history/RESULTS.md)."
