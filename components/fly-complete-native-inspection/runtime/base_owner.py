"""One selected complete Fly PID preparation; no retries or other workloads."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import sys
import time


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def blob(row):
    path = Path(row['path'])
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == row['bytes'], 'ordinary exact source')
    b = path.read_bytes()
    require(hashlib.sha256(b).hexdigest() == row['sha256'], 'source hash')
    return b


def write(path, value):
    b = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    require(len(b) <= 262144, 'metadata cap')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(b)
        f.flush()
        os.fsync(f.fileno())


def module(name, row):
    blob(row)
    spec = importlib.util.spec_from_file_location(name, row['path'])
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def memory_potential(text):
    page = re.search(r'page size of ([0-9]+) bytes', text)
    require(page is not None, 'vm_stat page size')
    values = {}
    for name in ('Pages free', 'File-backed pages'):
        match = re.search(r'^' + re.escape(name) + r':\s*([0-9]+)\.?\s*$', text, re.M)
        require(match is not None, 'vm_stat required field')
        values[name] = int(match.group(1))
    return sum(values.values()) * int(page.group(1))


def capacity(memory, disk, req):
    host_floor = req['outside_host_bytes'] + 268435456 + 1073741824
    disk_floor = req['outside_disk_bytes'] + 33554432 + 1073741824
    return {'memory_potential_bytes': memory, 'disk_available_bytes': disk,
            'host_floor_bytes': host_floor, 'disk_floor_bytes': disk_floor,
            'passed': memory >= host_floor and disk >= disk_floor,
            'interpretation': 'Free plus file-backed pages is a capacity heuristic, not guaranteed reclaimable RAM.',
            'outside_source_cpu_nonzero': True, 'own_serial_cpu_reservation': 1,
            'other_selected_serial_actual_cpu_reservations': 1}


def audit_products(output):
    output = Path(output)
    s = output.lstat()
    require(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o700, 'private output directory')
    expected = {'OUTCOME.json'} | {f'trace-{i:02d}{suffix}' for i in range(0, 14, 2)
                                  for suffix in ('.jsonl', '-diagnostic.json')}
    require({p.name for p in output.iterdir()} == expected, 'complete exact product namespace')
    rows, bodies, total = [], {}, 0
    for name in sorted(expected):
        p = output / name
        st = p.lstat()
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o600,
                'private ordinary product')
        require(total + st.st_size <= 16777216, 'complete output cap')
        b = p.read_bytes()
        total += len(b)
        rows.append({'file': name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()})
        if name == 'OUTCOME.json':
            bodies[name] = b
    result = json.loads(bodies['OUTCOME.json'])
    require(result['status'] == 'complete_preparation' and result['trace_count'] == 7 and result['rows'] == 44984,
            'complete population')
    require(result['scientific_admission'] is False and result['physical_offset_calibration'] is False and
            result['animal_count_inferred'] is False and result['imaging_body_reads'] == 0, 'scope holds')
    require(sorted(result['products'], key=lambda x: x['file']) == [r for r in rows if r['file'] != 'OUTCOME.json'],
            'all product identity joins')
    return {'files': rows, 'total_bytes': total, 'trace_count': 7, 'rows': 44984,
            'scientific_admission': False, 'physical_offset_calibration': False}


def main():
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (10, 45))
    source = Path(__file__).absolute().parent
    body = (source / 'REQUEST.json').read_bytes()
    req = json.loads(body)
    root = Path(req['owner_output'])
    require(not root.exists() and not root.is_symlink(), 'owner namespace already exists')
    require(not Path(req['output']).exists() and not Path(req['output']).is_symlink(), 'producer namespace already exists')
    root.mkdir(mode=0o700)
    result = {'status': 'failed_partial_preserved', 'owner_pid': os.getpid(), 'owner_pgid': os.getpgrp(),
              'request_sha256': hashlib.sha256(body).hexdigest(), 'stages': [], 'error': None,
              'scientific_admission': False, 'hard_aggregate_rss_enforced': False}
    signals = []

    def interrupted(signum, frame):
        signals.append(signum)
        signal.alarm(0)
        raise TimeoutError('owner interruption')

    for sig in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM, signal.SIGXCPU):
        signal.signal(sig, interrupted)
    signal.alarm(105)
    try:
        for row in req['preparer_sources'] + [req['worker']]:
            blob(row)
        owner = module('fly_process_owner', req['process_owner'])
        closer = module('fly_process_closer', req['process_closer'])
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'}

        def birth(label):
            return lambda child: write(root / (label + '_BIRTH.json'),
                                       {'pid': child.pid, 'pgid': child.pid, 'parent_pid': os.getpid(),
                                        'registered_before_work_gate': label == 'PREPARER'})

        vm = owner.run_owned(['/usr/bin/vm_stat'], root, env, min(started + 10, time.monotonic() + 9),
                             root / 'vm.stdout', root / 'vm.stderr', closer,
                             work_until=min(started + 5, time.monotonic() + 4), stream_cap=16384,
                             on_spawn=birth('VM'), signals=signals)
        result['stages'].append(vm)
        require(vm['complete'], 'fresh capacity observation failed')
        v = os.statvfs(root)
        gate = capacity(memory_potential((root / 'vm.stdout').read_text()), v.f_bavail * v.f_frsize, req)
        gate['observed_at_unix_ns'] = time.time_ns()
        result['capacity'] = gate
        write(root / 'CAPACITY.json', gate)
        if not gate['passed']:
            result['status'] = 'capacity_refused_no_preparation'
            return 2
        until = started + 100
        argv = [req['python'], '-I', '-S', '-B', req['worker']['path']]
        gate_body = (json.dumps({'owner_pid': os.getpid(), 'request_sha256': result['request_sha256']}) + '\n').encode()
        run = owner.run_owned(argv, root, env, until, root / 'preparer.stdout', root / 'preparer.stderr', closer,
                              work_until=started + 92, stream_cap=16384, on_spawn=birth('PREPARER'),
                              start_gate=gate_body, signals=signals)
        result['stages'].append(run)
        require(run['complete'], 'preparation process did not close naturally and completely')
        worker = json.loads((root / 'WORKER_RESULT.json').read_bytes())
        require(worker['status'] == 'complete' and worker['pid'] == run['pid'], 'worker completion identity')
        require(worker['observed_maxrss_bytes_macos'] <= 201326592, 'observed worker RSS allowance exceeded')
        result['worker'] = worker
        result['products'] = audit_products(req['output'])
        require(time.monotonic() < until, 'complete owner horizon')
        result['status'] = 'complete_preparation_owned_closed'
        return 0
    except BaseException as exc:
        result['error'] = {'type': type(exc).__name__, 'reason': str(exc)[:512]}
        return 1
    finally:
        signal.alarm(0)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(elapsed_seconds=time.monotonic() - started, owner_cpu_seconds=usage.ru_utime + usage.ru_stime,
                      observed_owner_maxrss_bytes_macos=usage.ru_maxrss,
                      all_reaped_child_cpu_seconds=child_usage.ru_utime + child_usage.ru_stime,
                      signals=signals)
        write(root / 'OWNER_RESULT.json', result)
        print(json.dumps({'status': result['status'], 'owner_pid': os.getpid(), 'result': str(root / 'OWNER_RESULT.json')}))


if __name__ == '__main__':
    sys.exit(main())
