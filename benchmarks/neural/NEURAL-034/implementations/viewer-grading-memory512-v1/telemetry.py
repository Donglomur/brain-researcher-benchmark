"""Cgroup high-water observations around the unchanged NEURAL-034 grader.

The host must separately verify the fresh container, private cgroup namespace,
final exit and OOMKilled state. Kernel peaks cover only their observation cutoff,
not the rest of the container lifetime. Missing or unsupported readings are not
zero and are never replaced by process RSS or sampled Docker statistics.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
PREFIX = 'NEURAL034_CGROUP_TELEMETRY_V1 '
SCHEMA = 'neural034-cgroup-telemetry/v1'
FRAME_CAP = 8192
MEMORY_LIMIT = 512 * 1024**2
WORKER_PIN = {'bytes': 6091, 'sha256': 'e48954a3b0e6ab44fbe4ad393b2716a31151bd8c2362e472bc0fef99bee2b5e6'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def read_kernel(path, cap):
    """Bounded pseudo-file reads; st_size is deliberately not a content length."""
    need(path in ('/proc/self/cgroup', '/proc/self/mountinfo') or
         path.startswith('/sys/fs/cgroup/'), 'Fixed kernel telemetry paths')
    need('..' not in Path(path).parts and type(cap) is int and 0 < cap <= 65536, 'Bounded kernel read')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'Ordinary kernel pseudo-file')
        parts = []; total = 0
        while True:
            block = os.read(fd, min(4096, cap + 1 - total))
            if not block:
                break
            parts.append(block); total += len(block)
            need(total <= cap, 'Kernel telemetry extent exceeded')
        return b''.join(parts)
    finally:
        os.close(fd)


def text(body):
    need(type(body) is bytes and len(body) <= 65536, 'Bounded kernel bytes')
    return body.decode('ascii', errors='strict')


def integer(body):
    value = text(body).strip()
    need(re.fullmatch('[0-9]{1,20}', value) is not None, 'Unsigned kernel counter')
    return int(value)


def counters(body):
    result = {}
    for line in text(body).splitlines():
        fields = line.split()
        need(len(fields) == 2 and re.fullmatch('[a-z_]+', fields[0]) is not None and fields[0] not in result,
             'Unique kernel counter fields')
        result[fields[0]] = integer(fields[1].encode())
    need(result, 'Nonempty kernel counters')
    return result


def discover(reader):
    membership = []
    for line in text(reader('/proc/self/cgroup', 16384)).splitlines():
        fields = line.split(':', 2)
        need(len(fields) == 3 and fields[0].isdigit(), 'Cgroup membership fields')
        if fields[0] == '0' and fields[1] == '':
            membership.append(('cgroup_v2', fields[2]))
        elif 'memory' in fields[1].split(','):
            membership.append(('cgroup_v1_memory_files', fields[2]))
    need(len(membership) == 1 and membership[0][1] == '/', 'Unambiguous namespace-root memory cgroup required')
    provider = membership[0][0]
    wanted = 'cgroup2' if provider == 'cgroup_v2' else 'cgroup'
    root = '/sys/fs/cgroup' if provider == 'cgroup_v2' else '/sys/fs/cgroup/memory'
    matches = []
    for line in text(reader('/proc/self/mountinfo', 65536)).splitlines():
        parts = line.split(' - ')
        need(len(parts) == 2, 'Mountinfo separator')
        before, after = parts[0].split(), parts[1].split()
        need(len(before) >= 6 and len(after) == 3, 'Mountinfo fields')
        if after[0] != wanted:
            continue
        if provider == 'cgroup_v1_memory_files' and 'memory' not in after[2].split(','):
            continue
        matches.append((before[3], before[4]))
    need(matches == [('/', root)], 'One exact namespace-root memory mount required')
    return {'provider': provider, 'membership': '/', 'mount_root': '/', 'mountpoint': root}


def reason(error):
    return type(error).__name__ + ': ' + str(error)[:240]


def snapshot(reader=read_kernel, clock=time.monotonic_ns):
    result = {'provider': None, 'cgroup_identity': None, 'expected_memory_limit_bytes': MEMORY_LIMIT,
        'memory_limit_bytes': None, 'memory_limit_match': None,
        'swap_limit_status': 'unsupported', 'swap_limit_bytes': None, 'swap_limit_match': None,
        'peak_kind': 'kernel_cgroup_high_water', 'peak_status': 'unsupported', 'peak_bytes': None,
        'peak_observed_monotonic_ns': None, 'oom_status': 'unsupported', 'oom_counters': None,
        'oom_observed_monotonic_ns': None, 'limit_events': None, 'allocation_failure_count': None,
        'scope': 'namespace-root cgroup and descendants through each recorded read; host container binding required',
        'entire_container_lifetime_measured': False, 'reason': None}
    try:
        identity = discover(reader); root = identity['mountpoint']; provider = identity['provider']
        result.update(provider=provider, cgroup_identity=identity)
        limit_path = root + ('/memory.max' if provider == 'cgroup_v2' else '/memory.limit_in_bytes')
        limit = integer(reader(limit_path, 128))
        result.update(memory_limit_bytes=limit, memory_limit_match=limit == MEMORY_LIMIT)
        need(limit == MEMORY_LIMIT, 'Observed cgroup memory limit differs from512MiB candidate')
    except Exception as error:
        result['reason'] = reason(error)
        return result
    try:
        swap = integer(reader(root + ('/memory.swap.max' if provider == 'cgroup_v2' else '/memory.memsw.limit_in_bytes'), 128))
        result.update(swap_limit_status='available', swap_limit_bytes=swap,
                      swap_limit_match=swap == (0 if provider == 'cgroup_v2' else MEMORY_LIMIT))
    except Exception as error:
        result['swap_limit_reason'] = reason(error)
    try:
        events = counters(reader(root + ('/memory.events' if provider == 'cgroup_v2' else '/memory.oom_control'), 4096))
        result['oom_observed_monotonic_ns'] = clock()
        result['limit_events'] = events
        required = ('oom', 'oom_kill') if provider == 'cgroup_v2' else ('oom_kill',)
        need(all(name in events for name in required), 'Kernel OOM counters unavailable; flags are not counters')
        selected = [name for name in ('oom', 'oom_kill', 'oom_group_kill') if name in events]
        result.update(oom_status='available', oom_counters={name: events[name] for name in selected})
    except Exception as error:
        result['oom_reason'] = reason(error)
    if provider == 'cgroup_v1_memory_files':
        try:
            # failcnt counts allocation-limit events, not OOM kills.
            result['allocation_failure_count'] = integer(reader(root + '/memory.failcnt', 128))
        except Exception as error:
            result['allocation_failure_reason'] = reason(error)
    try:
        peak_path = root + ('/memory.peak' if provider == 'cgroup_v2' else '/memory.max_usage_in_bytes')
        peak = integer(reader(peak_path, 128)); observed = clock()
        result.update(peak_status='available', peak_bytes=peak, peak_observed_monotonic_ns=observed,
                      peak_source_file=peak_path)
    except Exception as error:
        result['reason'] = reason(error)
    return result


def frame_bytes(record):
    body = (PREFIX + json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    need(len(body) <= FRAME_CAP, 'Bounded single telemetry frame')
    return body


def emit_frame(record):
    sys.stderr.buffer.write(frame_bytes(record)); sys.stderr.buffer.flush()


def safe_emit(emit, record):
    try:
        frame_bytes(record)  # Enforce the same frame bound for injected emitters.
        emit(record)
        return True
    except Exception:
        return False


def measured(reader, clock):
    try:
        return snapshot(reader, clock)
    except Exception as error:
        return {'peak_status': 'unsupported', 'peak_bytes': None, 'cgroup_identity': None,
                'oom_status': 'unsupported', 'oom_counters': None,
                'entire_container_lifetime_measured': False, 'reason': reason(error)}


def run_worker(worker, *, reader=read_kernel, emit=emit_frame, clock=time.monotonic_ns):
    before = measured(reader, clock)
    emitted = safe_emit(emit, {'schema': SCHEMA, 'phase': 'before', 'measurement': before,
                               'worker_started': False, 'coverage': 'pre_worker_observation_only'})
    code = worker()  # The exact original main controls stdout, validation and scoring.
    after = measured(reader, clock)
    same = before.get('cgroup_identity') is not None and before.get('cgroup_identity') == after.get('cgroup_identity')
    delta = None
    if same and before.get('oom_status') == after.get('oom_status') == 'available':
        a, b = before['oom_counters'], after['oom_counters']
        if set(a) == set(b) and all(b[key] >= a[key] for key in a):
            delta = {key: b[key] - a[key] for key in a}
    safe_emit(emit, {'schema': SCHEMA, 'phase': 'after', 'measurement': after,
        'worker_returncode': code, 'before_frame_emitted': emitted,
        'same_cgroup_as_before': same, 'oom_counter_delta': delta,
        'coverage': 'through_post_worker_kernel_read_only; later_container_lifetime_unobserved',
        'host_exit_and_oom_state_required': True})
    return code  # Telemetry support/publication failure never replaces a completed worker status.


def worker_from_bytes(body, filename='/source/grader.py'):
    need(type(body) is bytes and {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == WORKER_PIN,
         'Exact unchanged original grader bytes')
    namespace = {'__name__': '_unchanged_neural034_grader', '__file__': filename}
    exec(compile(body, filename, 'exec'), namespace)
    return namespace['main']


def load_worker():
    path = '/source/grader.py'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == WORKER_PIN['bytes'],
             'Original ordinary bounded worker source')
        body = os.read(fd, WORKER_PIN['bytes'] + 1); after = os.fstat(fd)
        need(all(getattr(before, k) == getattr(after, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')), 'Stable worker source')
        return worker_from_bytes(body, path)
    finally:
        os.close(fd)


if __name__ == '__main__':
    raise SystemExit(run_worker(load_worker()))
