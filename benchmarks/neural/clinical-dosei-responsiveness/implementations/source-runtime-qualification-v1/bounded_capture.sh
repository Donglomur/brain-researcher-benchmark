#!/bin/bash
# Library only: importing this file never launches a qualification or command.
# Caller supplies an admitted private parent and an encompassing hard deadline.

qualification_close_extra_fds() {
  local item descriptor
  # This executes only in the owned producer subshell, immediately before exec.
  # Numeric descriptors are never evaluated as participant-provided shell text.
  [ -d /dev/fd ] || return 74
  for item in /dev/fd/[0-9]*; do
    descriptor=${item##*/}
    case "$descriptor" in ''|*[!0-9]*) return 74 ;; esac
    if [ "$descriptor" -gt 2 ]; then
      eval "exec ${descriptor}>&-" || return 74
    fi
  done
  return 0
}

qualification_bounded_receive() {
  local -a prefix_status probe_status drain_status
  local status
  exec 9>&- 10>&-
  { /bin/dd bs=1 count=32768 >&3; } 2>&1 | /usr/bin/head -c 4096 >&5
  prefix_status=("${PIPESTATUS[@]}")
  { /bin/dd bs=1 count=1 >&4; } 2>&1 | /usr/bin/head -c 4096 >&6
  probe_status=("${PIPESTATUS[@]}")
  { /bin/cat >/dev/null; } 2>&1 | /usr/bin/head -c 4096 >&7
  drain_status=("${PIPESTATUS[@]}")
  printf 'prefix_dd=%s\nprefix_diagnostic_cap=%s\nprobe_dd=%s\nprobe_diagnostic_cap=%s\ndrain=%s\ndrain_diagnostic_cap=%s\n' \
    "${prefix_status[0]}" "${prefix_status[1]}" "${probe_status[0]}" "${probe_status[1]}" \
    "${drain_status[0]}" "${drain_status[1]}" >&8 || return 74
  for status in "${prefix_status[@]}" "${probe_status[@]}" "${drain_status[@]}"; do
    if [ "$status" -ne 0 ]; then return 74; fi
  done
  return 0
}

qualification_capture_bytes() {
  local size
  size=$(/usr/bin/wc -c <"$1") || return 74
  size=${size//[[:space:]]/}
  case "$size" in ''|*[!0-9]*) return 74 ;; esac
  printf '%s' "$size"
}

bounded_capture() (
  # Exact retained ceilings: 32768+1+3*4096+1024+2048+1024=49153 bytes.
  # Beyond-cap console is drained, not retained or claimed fully observed.
  set +e
  set -o pipefail
  set -o noclobber
  umask 077
  local destination="$1"
  shift
  [ "$#" -gt 0 ] || exit 64
  case "$destination" in /*) ;; *) exit 64 ;; esac
  case "$destination" in *$'\n'*|*$'\r'*|*\\*) exit 64 ;; esac
  [ "${#destination}" -le 2048 ] || exit 64
  /bin/mkdir -m 700 "$destination" || exit 73
  exec 3>"$destination/console.txt" || exit 73
  exec 4>"$destination/overflow.probe" || exit 73
  exec 5>"$destination/prefix-dd.stderr" || exit 73
  exec 6>"$destination/probe-dd.stderr" || exit 73
  exec 7>"$destination/drain.stderr" || exit 73
  exec 8>"$destination/receiver.status" || exit 73
  exec 9>"$destination/launch.status" || exit 73
  exec 10>"$destination/launch.start" || exit 73
  printf 'schema=dosei_bounded_qualification_capture_v1\nstatus=started\nconsole_cap=32768\nprobe_cap=1\nall_capture_cap=49153\nretention_scope=reserved_generated_runtime_qualification_artifact\n' >&10 || exit 74
  exec 10>&-
  ( qualification_close_extra_fds || exit 74; exec "$@" </dev/null ) 2>&1 | qualification_bounded_receive
  local -a pipeline_status=("${PIPESTATUS[@]}")
  exec 3>&- 4>&- 5>&- 6>&- 7>&- 8>&-
  local console_bytes=-1 probe_bytes=-1 console_sha='' result complete=false
  local accounted=true name size cap
  console_bytes=$(qualification_capture_bytes "$destination/console.txt") || accounted=false
  probe_bytes=$(qualification_capture_bytes "$destination/overflow.probe") || accounted=false
  console_sha=$(/usr/bin/shasum -a 256 "$destination/console.txt") || accounted=false
  console_sha=${console_sha%% *}
  case "$console_sha" in *[!0-9a-f]*) accounted=false ;; esac
  [ "${#console_sha}" -eq 64 ] || accounted=false
  for name in prefix-dd.stderr probe-dd.stderr drain.stderr receiver.status launch.start; do
    size=$(qualification_capture_bytes "$destination/$name") || { accounted=false; continue; }
    cap=1024
    case "$name" in *.stderr) cap=4096 ;; esac
    # At exactly the diagnostic cap there is no retained proof of completeness.
    [ "$size" -lt "$cap" ] || accounted=false
    case "$name" in receiver.status|launch.start) [ "$size" -gt 0 ] || accounted=false ;; esac
  done
  result=${pipeline_status[0]}
  if [ "${pipeline_status[1]}" -ne 0 ] || [ "$accounted" != true ]; then
    [ "$result" -ne 0 ] || result=74
  elif [ "$console_bytes" -gt 32768 ] || [ "$probe_bytes" -gt 1 ]; then
    [ "$result" -ne 0 ] || result=74
  elif [ "$probe_bytes" -ne 0 ]; then
    [ "$result" -ne 0 ] || result=65
  else
    complete=true
  fi
  printf 'producer_exit=%s\nreceiver_exit=%s\nreturned_exit=%s\nconsole_bytes=%s\noverflow_probe_bytes=%s\nconsole_sha256=%s\ncomplete_console_capture=%s\naccounting_complete=%s\noverflow_never_returns_success=true\ndiscarded_console_bytes=unknown_when_probe_present\n' \
    "${pipeline_status[0]}" "${pipeline_status[1]}" "$result" "$console_bytes" "$probe_bytes" \
    "$console_sha" "$complete" "$accounted" >&9 || exit 74
  exec 9>&-
  size=$(qualification_capture_bytes "$destination/launch.status") || exit 74
  [ "$size" -gt 0 ] && [ "$size" -lt 2048 ] || exit 74
  printf 'bounded_launch_exit=%s complete_console_capture=%s retained_console_bytes=%s\n' "$result" "$complete" "$console_bytes"
  exit "$result"
)
