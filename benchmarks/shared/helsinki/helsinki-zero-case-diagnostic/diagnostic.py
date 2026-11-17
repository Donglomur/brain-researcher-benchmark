"""Authenticated, synthetic-only operator CLI. No benchmark admission API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import sys
import time
import types

SCHEMA = 'helsinki-zero-case-request/v1'
MODULES = ('common', 'durable_evidence', 'participant_policy',
           'participant_container', 'parent_observer')
READ_LIMIT = 128 * 1024 * 1024
WRITE_LIMIT = 16 * 1024 * 1024
WALL = 240
EXPECTED = (b'{"child_natural_zero":true,"schema":'
            b'"helsinki-cgroup-lifecycle-fixture/v1","touched_bytes":8388608}\n')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def strict(body):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'nonfinite JSON'))


def ordinary(path, cap):
    """Bootstrap read, no import of an unauthenticated helper."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute ordinary path')
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), 'no path symlinks')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size <= cap, 'bounded single-link regular file')
        body = bytearray()
        while len(body) <= cap:
            chunk = os.read(fd, min(65536, cap + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        require(len(body) == before.st_size and identity(os.fstat(fd)) ==
                identity(before) == identity(path.lstat()),
                'stable complete file')
        return bytes(body)
    finally:
        os.close(fd)


def authenticate(root, expected):
    root = Path(root)
    manifest = ordinary(root / 'SOURCE.json', 65536)
    require(re.fullmatch('[0-9a-f]{64}', expected or '') and
            digest(manifest) == expected, 'source manifest identity')
    obj = strict(manifest)
    require(set(obj) == {'schema', 'files'} and
            obj['schema'] == 'helsinki-zero-case-source/v1', 'source manifest schema')
    files = obj['files']
    require(type(files) is list and 8 <= len(files) <= 24, 'finite source members')
    names = [x['path'] for x in files]
    require(len(set(names)) == len(names) and all(
        type(n) is str and re.fullmatch('[A-Za-z0-9_.-]+', n) and
        n not in ('.', '..', 'SOURCE.json') for n in names), 'flat source members')
    entries = list(root.iterdir())
    require(len(entries) <= 25 and {x.name for x in entries} == set(names) | {'SOURCE.json'},
            'exact source namespace before imports')
    bodies = {}
    for row in files:
        require(set(row) == {'path', 'bytes', 'sha256'} and
                type(row['bytes']) is int and 0 <= row['bytes'] <= 262144,
                'source member descriptor')
        body = ordinary(root / row['path'], 262144)
        require(len(body) == row['bytes'] and digest(body) == row['sha256'],
                'source member identity: ' + row['path'])
        bodies[row['path']] = body
    require('diagnostic.py' in bodies and all(x + '.py' in bodies for x in MODULES),
            'complete executable graph')
    return manifest, bodies


def load_modules(root, bodies):
    """Execute only already authenticated bytes, in a fresh operator process."""
    loaded = {}
    for name in MODULES:
        require(name not in sys.modules, 'fresh helper module namespace')
        module = types.ModuleType(name)
        module.__file__ = str(root / (name + '.py'))
        sys.modules[name] = module
        exec(compile(bodies[name + '.py'], module.__file__, 'exec'), module.__dict__)
        loaded[name] = module
    return loaded


def validate_request(req, mode, output, image):
    require(type(req) is dict and set(req) == {'schema', 'selection', 'target',
            'provision', 'provisioning_authority_sha256'}, 'request fields')
    require(req['schema'] == SCHEMA and mode in ('check', 'run'), 'request schema/mode')
    selection = req['selection']
    require(type(selection) is dict and set(selection) == {'operation_id', 'mode',
            'authority_sha256', 'output', 'parent_device', 'parent_inode'},
            'explicit operation selection required')
    require(selection['mode'] == mode and selection['output'] == str(output) and
            re.fullmatch('[a-z0-9][a-z0-9-]{0,79}', selection['operation_id'] or ''),
            'selected operation/mode/output')
    for value in (selection['authority_sha256'], req['provisioning_authority_sha256']):
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value),
                'external reviewed authority identity')
    require(type(selection['parent_device']) is int and selection['parent_device'] >= 0
            and type(selection['parent_inode']) is int and selection['parent_inode'] > 0,
            'exact output parent identity')
    target = req['target']
    require(type(target) is dict and set(target) == {'python', 'docker', 'socket',
            'socket_guard', 'image_id', 'architecture'}, 'target fields')
    require(target['image_id'] == image['image_id'] and target['architecture'] == 'amd64',
            'fixed synthetic image and architecture')
    require(type(target['socket']) is str and Path(target['socket']).is_absolute(),
            'selected local socket')
    guard = target['socket_guard']
    require(type(guard) is dict and set(guard) == {'dev', 'inode', 'mode', 'uid', 'gid', 'nlink'}
            and all(type(x) is int and x >= 0 for x in guard.values()), 'exact socket metadata')
    for role in ('python', 'docker'):
        item = target[role]
        require(type(item) is dict and set(item) == {'path', 'bytes', 'sha256'} and
                type(item['path']) is str and Path(item['path']).is_absolute() and
                type(item['bytes']) is int and 0 < item['bytes'] <= 64 * 1024 * 1024 and
                re.fullmatch('[0-9a-f]{64}', item['sha256'] or ''), 'selected executable')
    require(sum(target[x]['bytes'] for x in ('python', 'docker')) <= READ_LIMIT - 16777216,
            'executable hashes leave metadata read capacity')
    return req


def authenticate_executable(row, common, budget):
    path = common.plain(row['path'])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == row['bytes'] and before.st_mode & 0o111 and
                not before.st_mode & 0o022, 'selected executable regular/extent/mode')
        h = hashlib.sha256()
        total = 0
        while total <= row['bytes']:
            budget.check()
            body = os.read(fd, min(1048576, row['bytes'] + 1 - total))
            budget.charge_read(len(body))
            if not body:
                break
            total += len(body)
            h.update(body)
        require(total == row['bytes'] and h.hexdigest() == row['sha256'] and
                identity(os.fstat(fd)) == identity(before) == identity(path.lstat()),
                'current executable identity')
    finally:
        os.close(fd)


def validate_daemon(info, provision):
    expected = {'ID': provision['daemon_id'], 'ServerVersion': provision['daemon_version'],
                'KernelVersion': provision['kernel_release'], 'OSType': 'linux',
                'Architecture': 'x86_64', 'CgroupDriver': 'cgroupfs', 'CgroupVersion': '2'}
    require(type(info) is dict and all(info.get(k) == v for k, v in expected.items()),
            'daemon identity/architecture/cgroupfs-v2 mismatch')


def validate_image(rows, image):
    require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict,
            'one local synthetic image')
    item = rows[0]
    require(item.get('Id') == image['image_id'] and item.get('Os') == 'linux' and
            item.get('Architecture') == 'amd64', 'local synthetic image mismatch')
    require(type(item.get('Config')) is dict and not item['Config'].get('OnBuild') and
            not item['Config'].get('Volumes'), 'no synthetic image mount/build hooks')


def check_delegation(observer_module, observer, budget):
    host = observer._host()
    p = observer.provision
    fd = observer_module.open_directory(p['delegation_path'])
    try:
        s = os.fstat(fd)
        require(observer_module.filesystem_magic(fd) == observer_module.MAGIC and
                observer_module.identity(fd) == (p['delegation_device'], p['delegation_inode'])
                and s.st_uid == os.getuid() and not s.st_mode & 0o022,
                'owner-controlled cgroup2 delegation identity')
        values = {name: observer_module.read_at(fd, name, budget) for name in
                  ('cgroup.procs', 'cgroup.type', 'cgroup.subtree_control')}
        require(not values['cgroup.procs'].strip() and values['cgroup.type'] == 'domain\n'
                and observer_module.CONTROLLERS <= set(values['cgroup.subtree_control'].split())
                and not observer_module.children(fd), 'empty pre-enabled exclusive delegation')
        return {'host': host, 'values': values, 'identity': [s.st_dev, s.st_ino],
                'exclusive_ownership_is_external_operating_condition': True}
    finally:
        os.close(fd)


def preflight(req, modules, root, policy, image, budget, deadline):
    c = modules['participant_container']
    common = modules['common']
    observer_module = modules['parent_observer']
    require(sys.platform == 'linux' and platform.machine() == 'x86_64',
            'Linux amd64 owner required')
    require(str(Path(sys.executable).resolve()) == req['target']['python']['path'],
            'selected running interpreter')
    for role in ('python', 'docker'):
        authenticate_executable(req['target'][role], common, budget)
    c.DOCKER = req['target']['docker']['path']
    c.DAEMON_SOCKET = Path(req['target']['socket'])
    c.DAEMON_GUARD = dict(req['target']['socket_guard'])
    c.daemon_guard()
    observer_root = root / 'observer'
    observer_root.mkdir(mode=0o700)
    observer = observer_module.ParentObserver(provision=req['provision'], policy=policy,
                 budget=budget, evidence_root=observer_root)
    # Read-only checks precede all Docker commands and all cgroup writes.
    delegation = check_delegation(observer_module, observer, budget)
    cli = c.configure_cli(root / 'cli', budget)
    logs = root / 'preflight-logs'
    logs.mkdir(mode=0o700)
    journal = modules['durable_evidence'].Evidence(root / 'PREFLIGHT_JOURNAL.bin', budget)
    calls = []
    try:
        for args in (['info', '--format', '{{json .}}'],
                     ['image', 'inspect', image['image_id']]):
            n = len(calls) + 1
            require(journal.emit('intent', {'number': n, 'argv': c.cli_argv(args)}),
                    'preflight intent durable')
            def observed(phase, record):
                return journal.emit(phase, {'number': n, 'record': record})
            record, out, err = c.command(c.cli_argv(args), directory=logs, number=n,
                budget=budget, until=min(deadline, time.monotonic() + 10),
                observed=observed, cap=65536)
            calls.append(record)
            require(record['complete'] and record['exit_code'] == 0 and not err,
                    'complete successful read-only Docker metadata')
            obj = common.decode(out, 65536)
            if n == 1:
                validate_daemon(obj, req['provision'])
            else:
                validate_image(obj, image)
    finally:
        journal.close()
    require(journal.closed and not journal.errors and not c.registered_clients(),
            'preflight journal and clients closed')
    result = {'schema': 'helsinki-zero-case-preflight/v1', 'calls': calls,
              'delegation': delegation, 'cli': cli, 'journal': journal.receipt(),
              'conditional_prerequisites_observed': True, 'runtime_qualified': False}
    common.write(root / 'PREFLIGHT.json', common.encode(result), budget)
    return observer


def inspect_closed(closed, container, common, root, budget):
    closed = container.require_closed(closed)
    require(closed.submission['path'] == str(root / 'SUBMISSION.private.bin') and
            closed.lifecycle['path'] == str(root / 'LIFECYCLE.private.json'),
            'exact owned artifact locations')
    body = common.read(Path(closed.submission['path']),
        {k: closed.submission[k] for k in ('bytes', 'sha256')}, budget)
    require(body == EXPECTED, 'exact synthetic fixture output')
    life = common.decode(common.read(Path(closed.lifecycle['path']),
        {k: closed.lifecycle[k] for k in ('bytes', 'sha256')}, budget), 1048576)
    counters = life['kernel_accounting']
    require(life['candidate_closed'] is True and life['remaining_owned_cid'] is None
            and counters['CPU_seconds'] >= 0.1 and
            counters['peak_memory_bytes'] >= 8388608, 'closed fixture and descendant counters')
    return {'submission': closed.submission, 'lifecycle': closed.lifecycle,
            'CPU_seconds': counters['CPU_seconds'],
            'peak_memory_bytes': counters['peak_memory_bytes']}


def _operate(req, mode, output, modules, bodies, source_sha256, started, bootstrap_bytes=0):
    common = modules['common']
    c = modules['participant_container']
    budget = common.Budget(started + WALL, READ_LIMIT, WRITE_LIMIT)
    budget.charge_read(sum(map(len, bodies.values())) + bootstrap_bytes)
    image = strict(bodies['SYNTHETIC_IMAGE.json'])
    validate_request(req, mode, output, image)
    output = common.plain(output)
    s = output.parent.stat()
    require((s.st_dev, s.st_ino) == (req['selection']['parent_device'],
            req['selection']['parent_inode']) and s.st_uid == os.getuid() and
            not s.st_mode & 0o022, 'selected owner output parent')
    output.mkdir(mode=0o700)
    policy = {'profile': modules['participant_policy'].PROFILE, 'image': image['image_id'],
              'runtime_manifest_sha256': digest(bodies['SYNTHETIC_IMAGE.json']),
              'observer_source_sha256': digest(bodies['parent_observer.py']),
              'source_closure_sha256': source_sha256, 'wall_seconds': 15,
              'cpu_seconds': 120, 'memory_bytes': 1073741824}
    result = {'schema': 'helsinki-zero-case-report/v1', 'mode': mode,
              'source_sha256': source_sha256, 'request_canonical_sha256': digest(common.encode(req)),
              'synthetic_only': True, 'runtime_qualified': False,
              'scientific_qualified': False, 'production_gate_changed': False,
              'status': 'refused', 'result': None, 'failure': None}
    try:
        common.write(output / 'REQUEST.json', common.encode(req), budget)
        observer = preflight(req, modules, output, policy, image, budget, started + 60)
        if mode == 'check':
            result['status'] = 'conditional_prerequisites_observed'
        else:
            input_dir = output / 'input'
            bundle_dir = output / 'candidate'
            for path in (input_dir, bundle_dir):
                path.mkdir(mode=0o755)
            common.write(input_dir / 'EMPTY_INPUT.json', bodies['EMPTY_INPUT.json'], budget, mode=0o444)
            common.write(bundle_dir / 'solution.py', bodies['fixture_solution.py'], budget, mode=0o444)
            for path in (input_dir, bundle_dir):
                os.chmod(path, 0o555)
            closed = c.run_candidate(root=output / 'run', input_dir=input_dir,
                bundle_dir=bundle_dir, policy=policy, accounting=observer,
                budget=budget, active_deadline=started + 180)
            result['result'] = inspect_closed(closed, c, common, output / 'run', budget)
            result['status'] = 'synthetic_lifecycle_observed'
    except BaseException as error:
        result['failure'] = {'class': type(error).__name__, 'message': str(error)}
    finally:
        # The outer task-local guard restores both handlers independently.
        # New cancellation cannot skip already-owned client closeout.
        for signum in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(signum, signal.SIG_IGN)
            except BaseException as error:
                result['status'] = 'refused'
                result.setdefault('signal_masking_errors', []).append({
                    'signal': signum, 'class': type(error).__name__})
                if result['failure'] is None:
                    result['failure'] = {'class': type(error).__name__,
                                         'message': 'cleanup signal masking failed'}
        if c.registered_clients():
            result['status'] = 'refused'
            try:
                result['fallback_client_cleanup'] = c.cleanup_registered_clients(budget.deadline)
            except BaseException as error:
                result['fallback_cleanup_error'] = {'class': type(error).__name__}
            if result['failure'] is None:
                result['failure'] = {'class': 'ClosureRefusal',
                                     'message': 'registered client remained after operation'}
    result['managed_reads'] = budget.reads
    result['reserved_writes_before_report'] = budget.reserved
    result['remaining_client_records'] = list(c.registered_clients())
    common.write(output / 'REPORT.json', common.encode(result), budget)
    return result



def operate(req, mode, output, modules, bodies, source_sha256, started, bootstrap_bytes=0):
    """Task-local owner guard; no alarm, quota or general executor is added."""
    previous = {}
    failure = None
    result = None
    def cancelled(signum, frame):
        raise ValueError('selected owner cancelled by signal ' + str(signum))
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, cancelled)
        result = _operate(req, mode, output, modules, bodies, source_sha256,
                          started, bootstrap_bytes)
    except BaseException as error:
        failure = error
    finally:
        # An installation/restoration failure cannot skip the other attempt.
        for signum, old in previous.items():
            try:
                signal.signal(signum, old)
            except BaseException as error:
                if failure is None:
                    failure = error
                else:
                    failure.add_note('handler restoration: ' + type(error).__name__)
    if failure is not None:
        raise failure
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'run'))
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    root = Path(__file__).resolve().parent
    try:
        manifest, bodies = authenticate(root, args.source_sha256)
        raw = ordinary(args.request, 65536)
        require(digest(raw) == args.request_sha256, 'request byte identity')
        req = strict(raw)
        validate_request(req, args.mode, args.output, strict(bodies['SYNTHETIC_IMAGE.json']))
        modules = load_modules(root, bodies)
        result = operate(req, args.mode, args.output, modules, bodies,
                         digest(manifest), started, len(manifest) + len(raw))
        print(json.dumps({'status': result['status'], 'report': str(args.output / 'REPORT.json'),
                          'runtime_qualified': False}, sort_keys=True))
        return 0 if result['failure'] is None else 2
    except BaseException as error:
        # Static refusals occur before any selected native operation/output root.
        print(json.dumps({'status': 'refused', 'class': type(error).__name__,
                          'message': str(error), 'runtime_qualified': False}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
