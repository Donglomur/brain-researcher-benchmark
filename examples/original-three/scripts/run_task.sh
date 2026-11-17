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
OUT="${OUT:-jobs}"
NILEARN_CACHE="${NILEARN_CACHE:-$HOME/nilearn_data}"
MOUNT_JSON=""
if [[ -d "$NILEARN_CACHE" ]]; then
  MOUNT_JSON="$(python3 -c 'import json, sys; print(json.dumps([{"type": "bind", "source": sys.argv[1], "target": "/nilearn_data", "read_only": True}]))' "$NILEARN_CACHE")"
fi

cmd_oracle=(harbor run -p "$TASK" -a oracle -k 1 -o "$OUT")
# GPT-5.5 via a ChatGPT login (~/.codex/auth.json) needs CODEX_FORCE_AUTH_JSON=1;
# with an OPENAI_API_KEY exported you can drop that --ae.
cmd_gpt=(harbor run -p "$TASK" -a codex -m gpt-5.5 --ak reasoning_effort=xhigh -k 3 -o "$OUT" --ae CODEX_FORCE_AUTH_JSON=1)
# claude-code reads CLAUDE_CODE_OAUTH_TOKEN from host env; if unset, run
# `python examples/original-three/scripts/patch_harbor_oauth.py` once to fall back to your ~/.claude login.
cmd_claude=(harbor run -p "$TASK" -a claude-code -m claude-opus-4-8 -k 3 -o "$OUT")

if [[ -n "$MOUNT_JSON" ]]; then
  cmd_oracle+=(--mounts "$MOUNT_JSON" --ae NILEARN_DATA=/nilearn_data)
  cmd_gpt+=(--mounts "$MOUNT_JSON" --ae NILEARN_DATA=/nilearn_data)
  cmd_claude+=(--mounts "$MOUNT_JSON" --ae NILEARN_DATA=/nilearn_data)
fi
cmd_oracle+=(-y)
cmd_gpt+=(-y)
cmd_claude+=(-y)

emit(){ # $1 label, remaining arguments are the literal command vector
  printf '# %s\n' "$1"
  shift
  printf '%q ' "$@"
  printf '\n\n'
  if [[ -n "$RUN" ]]; then "$@"; fi
}

case "$AGENT" in
  oracle)  emit "oracle (expect reward 1.0)"        "${cmd_oracle[@]}" ;;
  gpt-5.5) emit "GPT-5.5 xhigh (expect FAIL, k=3)"  "${cmd_gpt[@]}" ;;
  claude)  emit "Claude Opus 4.8 (expect FAIL, k=3)" "${cmd_claude[@]}" ;;
  all)
    emit "oracle (expect reward 1.0)"        "${cmd_oracle[@]}"
    emit "GPT-5.5 xhigh (expect FAIL, k=3)"  "${cmd_gpt[@]}"
    emit "Claude Opus 4.8 (expect FAIL, k=3)" "${cmd_claude[@]}" ;;
  *) echo "unknown agent: $AGENT (oracle|gpt-5.5|claude|all)"; exit 1 ;;
esac

if [[ -z "$RUN" ]]; then
  echo "# add --run to execute. Then hand re-score each run's findings.md (see examples/original-three/upstream-history/RESULTS.md)."
fi
