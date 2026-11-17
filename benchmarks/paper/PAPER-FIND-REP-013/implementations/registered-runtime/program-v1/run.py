#!/usr/bin/env python3
"""One operator-selected portable Purkinje PROGRAM attempt, never a model campaign."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import signal
import stat
import sys
import time

HERE = Path(__file__).absolute().parent
MODULES = ('common', 'durable_evidence', 'schema', 'bundle', 'numeric_score', 'docker_owner', 'boundary')
SOURCE_NAMES = {'run.py', *(n + '.py' for n in MODULES), 'bridge.py', 'TASK.md',
                'SCHEMA.json', 'INPUT_PINS.json', 'REFERENCE_PINS.json', 'verify_source.py'}
EXECUTABLE_PIN = (52640, '4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def ordinary(path, cap):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 <= a.st_size <= cap, 'ordinary_file')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            raw = f.read(cap + 1)
        stamp = lambda s: tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
        need(stamp(a) == stamp(os.fstat(fd)) == stamp(path.lstat()) and len(raw) == a.st_size, 'stable_file')
        return raw
    finally:
        os.close(fd)


def capture_source(expected):
    need(type(expected) is str and len(expected) == 64, 'source_lock_hash')
    raw = ordinary(HERE / 'SOURCE_LOCK.json', 65536)
    need(hashlib.sha256(raw).hexdigest() == expected, 'selected_source_lock')
    lock = json.loads(raw)
    need(set(lock) == {'schema', 'members'} and lock['schema'] == 'purkinje-portable-program-source/v1' and
         set(lock['members']) == SOURCE_NAMES, 'complete_closed_source')
    bodies = {}; count = len(raw)
    for name, pin in lock['members'].items():
        need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
             type(pin['bytes']) is int and 0 <= pin['bytes'] <= 1048576, 'source_pin')
        body = ordinary(HERE / name, pin['bytes']); count += len(body)
        need(count <= 2 * 1024 ** 2 and hashlib.sha256(body).hexdigest() == pin['sha256'], 'source_identity')
        bodies[name] = body
    return bodies, count


def main():
    need(len(sys.argv) == 5, 'usage: run.py SOURCE_SHA REQUEST_ABSOLUTE_PATH REQUEST_BYTES REQUEST_SHA')
    source_sha, request_path, request_size, request_sha = sys.argv[1:]
    started = time.monotonic(); deadline = started + 150; active = started + 120
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and
         platform.system() == 'Darwin' and sys.version_info[:3] == (3, 11, 6), 'qualified_host_profile')
    executable = ordinary(Path(os.path.realpath(sys.executable)), EXECUTABLE_PIN[0])
    need((len(executable), hashlib.sha256(executable).hexdigest()) == EXECUTABLE_PIN, 'qualified_host_interpreter')
    loaded = {}; root = None; budget = None; result = None; failure = None
    def fatal(*unused):
        owner = loaded.get('docker_owner')
        if owner is not None:
            owner.kill_registered_clients()
        os._exit(124)
    def soft(*unused):
        signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGALRM, fatal)
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
        raise TimeoutError('original_work_deadline_or_cancellation')
    old = {s: signal.signal(s, soft) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL, max(.001, active - time.monotonic()))
    try:
        bodies, count = capture_source(source_sha)
        need(not any(n in sys.modules for n in MODULES), 'fresh_component_namespace')
        for name in MODULES:
            spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
            mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; loaded[name] = mod
            exec(compile(bodies[name + '.py'], str(HERE / (name + '.py')), 'exec'), mod.__dict__)
        c = loaded['common']; boundary = loaded['boundary']; owner = loaded['docker_owner']
        budget = c.Budget(deadline, 256 * 1024 ** 2, 128 * 1024 ** 2)
        budget.charge_read(count + len(executable))
        entry = {'bytes': int(request_size), 'sha256': request_sha}
        request_raw = c.read(request_path, entry, budget, cap=65536, mode=0o400)
        request = c.decode(request_raw, 65536)
        pins = {'public_inputs': c.decode(bodies['INPUT_PINS.json']), 'references': c.decode(bodies['REFERENCE_PINS.json'])}
        capacity, history = boundary.admit(request, pins, source_sha, budget)
        root = c.plain(request['output_root']); root.mkdir(mode=0o700)
        c.write(root / 'REQUEST.json', request_raw, budget)
        c.write(root / 'STARTED.json', c.encode({'attempt_id': request['attempt_id'], 'source_lock_sha256': source_sha,
                'known_prior_seconds': history['known_charged_seconds'], 'reserved_seconds': 150,
                'new_model_calls': 0, 'native_qualification_inherited': False}), budget)
        need(time.monotonic() + 95 < active, 'complete_candidate_and_cleanup_horizon')
        result = boundary.execute(request, bodies, owner, budget, root, active)
        need(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss <= 512 * 1024 ** 2, 'owner_report_point_RSS')
        c.write(root / 'OUTCOME.json', c.encode({'status': 'complete_pending_independent_review',
                'task_id': boundary.ID, 'candidate_result_status': result['status'],
                'elapsed_seconds': time.monotonic() - started, 'reserved_seconds': 150,
                'known_charged_seconds': history['known_charged_seconds'] + max(150, time.monotonic() - started),
                'managed_read_bytes': budget.reads, 'reserved_write_bytes': budget.reserved,
                'science_qualification': False, 'new_benchmark_ids': 0}), budget)
    except BaseException as error:
        failure = {'class': type(error).__name__, 'message': str(error)[:2048],
                   'elapsed_seconds': time.monotonic() - started, 'automatic_retry': False}
        owner = loaded.get('docker_owner')
        if owner is not None:
            try: failure['owned_client_cleanup'] = owner.cleanup_registered_clients(deadline)
            except BaseException as secondary: failure['cleanup_failure'] = type(secondary).__name__
        if root is not None and root.exists() and budget is not None:
            try: loaded['common'].write(root / 'FAILURE.json', loaded['common'].encode(failure), budget)
            except BaseException as secondary: failure['preservation_failure'] = type(secondary).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for s, handler in old.items(): signal.signal(s, handler)
    print(json.dumps({'status': 'failed_preserved_or_partial' if failure else 'complete_pending_independent_review',
                      'failure': failure, 'new_benchmark_ids': 0}))
    return 1 if failure else 0


if __name__ == '__main__':
    os.umask(0o077)
    raise SystemExit(main())
