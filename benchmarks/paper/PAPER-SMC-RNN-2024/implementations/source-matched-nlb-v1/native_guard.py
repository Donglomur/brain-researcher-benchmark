#!/usr/bin/env python3
"""Watch one owned, leased full inference process for RAM and wall deadlines."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time


POLL_SECONDS = 0.5
TERM_GRACE_SECONDS = 5.0
MAX_WALL_SECONDS = 7180


def process_snapshot(pid):
    """Read identity as well as RSS; a recycled or reparented PID is not ours."""
    proc = subprocess.run(
        ['ps', '-p', str(pid), '-o', 'ppid=,pgid=,stat=,rss=,time=,lstart=,command='],
        capture_output=True, text=True, timeout=2, check=False)
    if not proc.stdout.strip():
        return None
    fields = proc.stdout.strip().split(None, 10)
    if len(fields) != 11:
        raise RuntimeError('Cannot establish process identity from ps')
    if fields[2].startswith('Z'):
        return None
    return dict(pid=pid, ppid=int(fields[0]), pgid=int(fields[1]),
                rss_bytes=int(fields[3]) * 1024, cpu=fields[4],
                started=' '.join(fields[5:10]), command=fields[10])


def process_identity(snapshot):
    return tuple(snapshot[key] for key in ('pid', 'ppid', 'pgid', 'started', 'command'))


def lease_row(ledger, run_id):
    rows = [row for row in json.loads(ledger.read_text())['native_runs']
            if row['id'] == run_id]
    if len(rows) > 1:
        raise RuntimeError('Duplicate native lease identity')
    return rows[0] if rows else None


def require_owned(row, snapshot):
    if (row['owner'] != 'smc' or snapshot['pid'] != row['child_pid']
            or snapshot['ppid'] != row['coordinator_pid']
            or snapshot['pgid'] != snapshot['pid']
            or 'author_predict.py' not in snapshot['command']):
        raise RuntimeError('Process identity does not match the owned native lease; no signal sent')


def signal_owned(ledger, row, identity, sig):
    """Reauthenticate immediately before each signal, including escalation."""
    current = lease_row(ledger, row['id'])
    if current is None or current['status'] != 'running':
        return False
    for key in ('owner', 'child_pid', 'coordinator_pid', 'started_utc', 'command', 'declared_max_working_ram_bytes'):
        if current[key] != row[key]:
            raise RuntimeError('Native lease identity changed; no signal sent')
    snapshot = process_snapshot(row['child_pid'])
    if snapshot is None:
        return False
    require_owned(row, snapshot)
    if process_identity(snapshot) != identity:
        raise RuntimeError('PID identity changed; no signal sent')
    try:
        os.kill(row['child_pid'], sig)
    except ProcessLookupError:
        return False
    return True


def guard(ledger, run_id, output, wall_limit=MAX_WALL_SECONDS):
    ledger, output = Path(ledger), Path(output)
    if not run_id.startswith('smc-full-') or output.exists() or not 0 < wall_limit <= MAX_WALL_SECONDS:
        raise ValueError('Require a fresh owned full-run guard and deadline at most 7180 seconds')
    row = None
    for _ in range(600):
        row = lease_row(ledger, run_id)
        if row and 'child_pid' in row:
            break
        time.sleep(0.1)
    if (not row or row.get('owner') != 'smc'
            or not any(Path(part).name == 'author_predict.py' for part in row['command'])
            or row.get('child_pid', 0) <= 1 or row.get('coordinator_pid', 0) <= 1):
        raise ValueError('No matching owned author inference lease')
    started = datetime.fromisoformat(row['started_utc'])
    age = (datetime.now(timezone.utc) - started).total_seconds()
    if age < -1:
        raise ValueError('Native lease start time is in the future')
    deadline = time.monotonic() + wall_limit - max(0, age)
    peak, reason, last_cpu, identity, error, escalated = 0, None, None, None, None, False
    exit_reason = 'not_started'
    try:
        while True:
            current = lease_row(ledger, run_id)
            if current is None:
                raise RuntimeError('Native lease disappeared')
            for key in ('owner', 'child_pid', 'coordinator_pid', 'started_utc', 'command', 'declared_max_working_ram_bytes'):
                if current[key] != row[key]:
                    raise RuntimeError('Native lease identity changed; no signal sent')
            if current['status'] != 'running':
                exit_reason = 'lease_completed'
                break
            snapshot = process_snapshot(row['child_pid'])
            if snapshot is None:
                exit_reason = 'process_exited'
                break
            require_owned(row, snapshot)
            observed = process_identity(snapshot)
            if identity is None:
                identity = observed
            elif observed != identity:
                raise RuntimeError('PID identity changed; no signal sent')
            peak, last_cpu = max(peak, snapshot['rss_bytes']), snapshot['cpu']
            if snapshot['rss_bytes'] > row['declared_max_working_ram_bytes']:
                reason = 'rss_limit'
            elif time.monotonic() >= deadline:
                reason = 'wall_deadline'
            if reason:
                sent = signal_owned(ledger, row, identity, signal.SIGTERM)
                if sent:
                    grace_end = time.monotonic() + TERM_GRACE_SECONDS
                    while time.monotonic() < grace_end:
                        current_snapshot = process_snapshot(row['child_pid'])
                        if current_snapshot is None:
                            break
                        if process_identity(current_snapshot) != identity:
                            raise RuntimeError('PID identity changed during termination; no further signal sent')
                        time.sleep(min(0.1, max(0, grace_end - time.monotonic())))
                    else:
                        escalated = signal_owned(ledger, row, identity, signal.SIGKILL)
                exit_reason = 'termination_requested'
                break
            time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        exit_reason = 'guard_error'
    usage = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    self_cpu, children_cpu = usage.ru_utime + usage.ru_stime, children.ru_utime + children.ru_stime
    result = dict(schema='smc_full_native_guard_v1', run_id=run_id, pid=row['child_pid'],
        peak_observed_rss_bytes=peak, ram_limit_bytes=row['declared_max_working_ram_bytes'],
        wall_deadline_seconds=wall_limit, sigterm_grace_seconds=TERM_GRACE_SECONDS,
        termination_reason=reason, sigkill_sent=escalated, last_observed_cpu=last_cpu,
        sampling_seconds=POLL_SECONDS, guard_self_cpu_seconds=self_cpu,
        guard_child_cpu_seconds=children_cpu, guard_cpu_seconds=self_cpu + children_cpu,
        exit_reason=exit_reason, error=error,
        enforcement='Cooperative owned-process watchdog plus child RLIMIT_CPU; not an OS sandbox. Coordinator must monitor guard exit and stop/review its owned run if guard exits nonzero.')
    with output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result), flush=True)
    if error:
        raise RuntimeError(error)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--wall-seconds', type=int, default=MAX_WALL_SECONDS)
    a = p.parse_args()
    guard(a.ledger, a.run_id, a.output, a.wall_seconds)
