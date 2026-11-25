"""Whole-cohort candidate execution; operator-private capture and late grading.

Run requires an externally admitted Docker daemon/image, complete authentic
packet and operator environment. Source hashes do not issue that authority.
No candidate programme executes on the host. Generated tests use a fake daemon.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

import io_utils as safe
from absence import absence
import runtime_contract as contract

HERE = Path(__file__).resolve().parent
METHOD = {
    'grade.py': (2251, '0615bdabd0aa402e588c4f1a075dbb0af987965c0a9e9b54a6b17e69313e5774'),
    'core.py': (9137, 'cfa13c3d1e43e7705221c74c6fe5ba1000934e3a743a014f4682b8445b3f3ed1'),
    'io_utils.py': (2996, '2f0ac23b3456432933c96e6579708b949b1e093659f99ebc6bfce5ae3f222f7e'),
    'source_identity_join.py': (15773, '9abd80cfea2e92a48e59d24af2672e6988faaf45b2397a18c74c57923ab328b3')}
SHA = re.compile('[0-9a-f]{64}')


def lexical_path(value):
    """Validate spelling only: no stat, link query, resolution or file read."""
    safe.need(type(value) is str and value and not any(c in value for c in '\x00\n\r'),
              'Explicit ordinary path')
    path = Path(value)
    safe.need(path.is_absolute() and path.anchor == '/' and str(path) == value and '..' not in path.parts,
              'Canonical lexical path')
    return path


def plain_path(value):
    path = lexical_path(value)
    safe.need(all(not p.is_symlink() for p in (path, *path.parents)), 'Canonical no-link path')
    return path


def admit_private_separation(r, request_path=None):
    """Refuse protected-path aliases before checking any executor path metadata.

    Source/bootstrap and the operator request are already admitted authority
    inputs. A declaration cannot retroactively make those bytes private. Once
    parsed, the request cannot alias them or any pre-closure operand to its
    private binding or prepared private subtree.
    """
    paths = {k: lexical_path(r[k]) for k in ('program', 'prepared_root', 'binding',
             'method_root', 'grader_python', 'docker', 'docker_config', 'output')}
    socket = lexical_path(r['docker_host'][7:])
    protected = (paths['binding'], paths['prepared_root'] / 'private')
    early = (paths['program'], paths['prepared_root'] / 'public', paths['method_root'],
             HERE, paths['docker'], paths['docker_config'], socket, paths['output'],
             paths['grader_python'])
    if request_path is not None:
        early += (lexical_path(request_path),)
    def overlap(a, b):
        return a == b or a in b.parents or b in a.parents
    safe.need(all(not overlap(private, public) for private in protected for public in early),
              'Private binding/tree lexically disjoint from all pre-closure operands')
    return paths


def pin(value, cap):
    safe.need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
              type(value['bytes']) is int and 0 < value['bytes'] <= cap and
              type(value['sha256']) is str and SHA.fullmatch(value['sha256']), 'Exact bounded pin')
    return value


def read_pinned(path, value, cap):
    raw = safe.read(path, cap)
    safe.need(len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256'],
              'Exact pinned content')
    return raw


def write_bytes(path, raw, mode=0o444):
    path = plain_path(str(path)); fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, mode)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def validate_request(r, request_path=None):
    fields = {'schema', 'program', 'program_pin', 'prepared_root', 'public_manifest_pin',
              'binding', 'method_root', 'grader_python', 'docker', 'docker_pin',
              'docker_host', 'docker_config', 'image', 'output', 'candidate_wall_seconds',
              'grade_wall_seconds', 'cleanup_wall_seconds', 'whole_wall_seconds',
              'candidate_cpu_seconds', 'candidate_memory_bytes', 'candidate_nano_cpus',
              'host_memory_budget_bytes', 'retention_budget_bytes'}
    safe.need(type(r) is dict and set(r) == fields and r['schema'] == 'neural029-program-request-v1',
              'Closed explicit operator request')
    safe.need(type(r['docker_host']) is str and r['docker_host'].startswith('unix:///') and
              not any(c in r['docker_host'] for c in '\x00\n\r'), 'Explicit local Unix Docker daemon')
    admit_private_separation(r, request_path)
    # The private binding receives only lexical admission until all producer
    # resources are absent. Even a symlink/metadata query is deferred.
    for k in ('program', 'prepared_root', 'method_root', 'docker', 'docker_config', 'output'):
        plain_path(r[k])
    # An independently qualified venv interpreter commonly has a symlink entry.
    # This is a trusted post-closure programme, never a candidate-selected path.
    py = r['grader_python']
    safe.need(type(py) is str and Path(py).is_absolute() and str(Path(py)) == py and
              '..' not in Path(py).parts and not any(c in py for c in '\x00\n\r'),
              'Explicit trusted operator interpreter')
    pin(r['program_pin'], 1048576); pin(r['public_manifest_pin'], 2000000)
    pin(r['docker_pin'], 134217728)
    safe.need(type(r['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}', r['image']),
              'Immutable image identifier')
    safe.need(type(r['docker_host']) is str and r['docker_host'].startswith('unix:///') and
              not any(c in r['docker_host'] for c in '\x00\n\r'), 'Explicit local Unix Docker daemon')
    plain_path(r['docker_host'][7:])
    for k in ('candidate_wall_seconds', 'grade_wall_seconds', 'cleanup_wall_seconds',
              'whole_wall_seconds', 'candidate_cpu_seconds', 'candidate_memory_bytes',
              'candidate_nano_cpus', 'host_memory_budget_bytes', 'retention_budget_bytes'):
        safe.need(type(r[k]) is int and r[k] > 0, 'Exact positive integral budget: ' + k)
    safe.need(r['whole_wall_seconds'] >= r['candidate_wall_seconds'] + r['grade_wall_seconds'] +
              2*r['cleanup_wall_seconds'] + 60, 'Preparation and separate cleanup allowances')
    safe.need(r['cleanup_wall_seconds'] >= 30 and r['whole_wall_seconds'] <= 86400 and
              r['candidate_cpu_seconds'] <= r['whole_wall_seconds'], 'Bounded complete operation')
    safe.need(r['candidate_memory_bytes'] >= 536870912 and r['candidate_nano_cpus'] <= 8000000000,
              'Explicit candidate memory and at most8CPU request')
    safe.need(r['host_memory_budget_bytes'] >= 536870912 and r['retention_budget_bytes'] >= 536870912,
              'Full100MB capture/JSON and70MB public packet allowances; not measured capacity')
    out = Path(r['output']); roots = [Path(r[k]) for k in ('prepared_root', 'method_root', 'docker_config')]
    safe.need(all(out != p and out not in p.parents and p not in out.parents for p in roots),
              'Output disjoint from input, method and daemon configuration')
    safe.need(all(Path(r[k]) != out and out not in Path(r[k]).parents
                  for k in ('program', 'binding', 'grader_python', 'docker')), 'No output/input alias')
    return r


def bounded_command(argv, env, end, seconds, cap=131072):
    remaining = min(seconds, end - time.monotonic())
    safe.need(remaining > 0, 'Command deadline')
    proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, close_fds=True)
    parts = [bytearray(), bytearray()]; selector = selectors.DefaultSelector()
    for i, stream in enumerate((proc.stdout, proc.stderr)):
        os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, i)
    deadline = time.monotonic() + remaining
    try:
        while selector.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('Owned command wall deadline')
            for key, _ in selector.select(min(left, .1)):
                block = os.read(key.fd, min(65536, cap + 1 - len(parts[key.data])))
                if not block:
                    selector.unregister(key.fileobj); continue
                parts[key.data].extend(block)
                if len(parts[key.data]) > cap:
                    raise ValueError('Owned command output cap; prefix retained on error')
        code = proc.wait(timeout=max(.001, deadline-time.monotonic()))
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError('Owned CLI descendants still live')
        return {'returncode': code, 'stdout': bytes(parts[0]).decode('utf8', 'replace'),
                'stderr': bytes(parts[1]).decode('utf8', 'replace')}
    except BaseException as error:
        secondary = []
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except BaseException as cleanup_error:
            secondary.append(repr(cleanup_error))
        try:
            proc.wait(timeout=5)
        except BaseException as cleanup_error:
            secondary.append(repr(cleanup_error))
        error.command_observation = {'argv': argv, 'stdout_prefix': bytes(parts[0]).decode('utf8', 'replace'),
            'stderr_prefix': bytes(parts[1]).decode('utf8', 'replace'), 'secondary': secondary}
        raise
    finally:
        selector.close(); proc.stdout.close(); proc.stderr.close()


class Docker:
    def __init__(self, r, output, end):
        self.r, self.output, self.end = r, output, end
        self.owned = []; self.calls = []; self.cleanup_rows = []
        self.env = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR') if k in os.environ}
        self.env.update(DOCKER_HOST=r['docker_host'], DOCKER_CONFIG=r['docker_config'])

    def call(self, argv, seconds=10):
        safe.need(len(self.calls) < 48, 'Complete operation Docker command allowance including cleanup')
        row = {'argv': argv}
        try:
            result = bounded_command([self.r['docker'], *argv], self.env, self.end, seconds)
            row.update(result); return result
        except BaseException as error:
            row.update(error=repr(error), original=getattr(error, 'command_observation', None)); raise
        finally:
            self.calls.append(row)
            safe.write_new(self.output / f'command-{len(self.calls):04d}.json', row, 2200000)

    def missing(self, kind, name):
        result = self.call(['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name])
        return absence(result['returncode'], result['stdout'], result['stderr'], kind, name)

    def own(self, kind, name):
        safe.need(self.missing(kind, name), 'Exact resource absent before ownership')
        self.owned.append((kind, name))
        safe.write_new(self.output / f'ownership-{len(self.owned):02d}.json',
                       {'kind': kind, 'name': name, 'attempt_recorded_before_create': True}, 4096)

    def inspect(self, kind, name):
        row = self.call(['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name])
        safe.need(row['returncode'] == 0, 'Successful resource inspect')
        rows = safe.strict(row['stdout'])
        safe.need(type(rows) is list and len(rows) == 1 and rows[0]['Name'] ==
                  (name if kind == 'volume' else '/' + name), 'Exact single resource identity')
        return rows[0]

    def volume(self, name):
        self.own('volume', name)
        result = self.call(['volume', 'create', '--driver', 'local', '--opt', 'type=tmpfs',
            '--opt', 'device=tmpfs', '--opt', 'o=' + contract.VOLUME_OPTIONS, name])
        safe.need(result['returncode'] == 0, 'Output volume creation')
        row = self.inspect('volume', name)
        safe.need(row['Driver'] == 'local' and row['Options'] == {'type': 'tmpfs',
            'device': 'tmpfs', 'o': contract.VOLUME_OPTIONS}, 'Complete bounded memory-backed output')

    def create(self, name, role, mounts):
        argv = contract.create_argv(name, role, mounts, self.r)
        self.own('container', name); result = self.call(argv)
        safe.need(result['returncode'] == 0, 'Container creation')
        return contract.verify(self.inspect('container', name), name, role, mounts, self.r)

    def remove(self, kind, name):
        result = self.call(['volume', 'rm', name] if kind == 'volume' else ['rm', '--force', name])
        closed = self.missing(kind, name)
        row = {'kind': kind, 'name': name, 'removal': result, 'absence_verified': closed}
        self.cleanup_rows.append(row)
        safe.need(closed, 'Owned resource absence before capture/grade')

    def close(self):
        errors = []
        for kind, name in reversed(self.owned):
            if any(x['kind'] == kind and x['name'] == name and x['absence_verified'] for x in self.cleanup_rows):
                continue
            try:
                self.remove(kind, name)
            except BaseException as error:
                errors.append({'kind': kind, 'name': name, 'error': repr(error)})
        return errors


def stage_public(r, work):
    prepared = plain_path(r['prepared_root'])
    raw = read_pinned(prepared / 'public/MANIFEST.json', r['public_manifest_pin'], 2000000)
    manifest = safe.strict(raw)
    safe.need(type(manifest) is dict and set(manifest) == {'schema', 'time_seconds', 'pairs'} and
              manifest['schema'] == 'neural029-public-v1' and
              manifest['time_seconds'] == [i / 20 for i in range(61)] and
              type(manifest['pairs']) is list and manifest['pairs'], 'Complete public manifest')
    public = work / 'public'; public.mkdir(mode=0o755); public.chmod(0o755)
    expected = {'MANIFEST.json'}; total = len(raw); ids = set()
    for row in manifest['pairs']:
        safe.need(type(row) is dict and set(row) == {'pair_id', 'cell_ids', 'query_ids',
                  'source_delay_seconds', 'target_delay_seconds', 'reward_type',
                  'calibration_trials', 'validation_trials', 'file'}, 'Exact public pair fields')
        key = row['pair_id']
        safe.need(type(key) is str and SHA.fullmatch(key) and key not in ids, 'Unique opaque pair')
        ids.add(key)
        for field in ('cell_ids', 'query_ids'):
            values = row[field]
            safe.need(type(values) is list and values and all(type(x) is str and SHA.fullmatch(x) for x in values)
                      and len(set(values)) == len(values), 'Complete unique opaque public axes')
        safe.need(type(row['source_delay_seconds']) is int and row['source_delay_seconds'] == 1 and
                  type(row['target_delay_seconds']) is int and row['target_delay_seconds'] == 2 and
                  row['reward_type'] in ('DAT', 'MFB') and
                  all(type(row[k]) is int and row[k] > 0 for k in ('calibration_trials', 'validation_trials')),
                  'Unchanged planned condition and training support')
        descriptor = row['file']; name = key + '.npz'
        safe.need(type(descriptor) is dict and set(descriptor) == {'path', 'bytes', 'sha256'} and
                  descriptor['path'] == 'public/' + name, 'Only source-condition file path')
        pin({k: descriptor[k] for k in ('bytes', 'sha256')}, 70000000)
        total += descriptor['bytes']; safe.need(total <= 72000000, 'Whole public packet allowance')
        body = safe.captured(prepared, descriptor, 70000000)
        write_bytes(public / name, body); expected.add(name)
    actual = {p.name for p in (prepared / 'public').iterdir()}
    safe.need(actual == expected, 'Complete exact input public directory; no private/extra members')
    write_bytes(public / 'MANIFEST.json', raw)
    return {'pairs': len(ids), 'public_bytes': total, 'manifest': r['public_manifest_pin']}


def stage_method(r, work):
    method = work / 'method'; method.mkdir(mode=0o700)
    for name, (size, sha) in METHOD.items():
        raw = read_pinned(Path(r['method_root']) / name, {'bytes': size, 'sha256': sha}, 1048576)
        write_bytes(method / name, raw)
    return method


def execute(r, *, request_path=None):
    validate_request(r, request_path); work = plain_path(r['output'])
    safe.need(not work.exists(), 'Fresh exclusive operator output directory')
    start = time.monotonic(); whole_end = start + r['whole_wall_seconds']
    work.mkdir(mode=0o700)
    event_rows = []; engine = None; failure = None; result = {'status': 'started', 'scientific_qualification': False}
    def event(name, **values):
        safe.need(len(event_rows) < 24, 'Complete phase-event metadata allowance')
        row = {'event': name, 'elapsed_seconds': time.monotonic()-start, **values}
        event_rows.append(row); safe.write_new(work / f'event-{len(event_rows):02d}.json', row, 16384)
    old_handlers = {}
    def cancelled(signum, frame):
        raise InterruptedError('Operator received signal ' + str(signum))
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, cancelled)
        program = read_pinned(r['program'], r['program_pin'], 1048576)
        program.decode('utf8')
        write_bytes(work / 'candidate.py', program); event('programme_frozen', pin=r['program_pin'])
        method = stage_method(r, work)
        public = stage_public(r, work); event('whole_public_packet_staged', **public)
        read_pinned(r['docker'], r['docker_pin'], 134217728)
        capture = work / 'capture'; capture.mkdir(mode=0o777); capture.chmod(0o777)
        command_dir = work / 'commands'; command_dir.mkdir(mode=0o700)
        engine = Docker(r, command_dir, whole_end-r['cleanup_wall_seconds']-r['grade_wall_seconds'])
        suffix = uuid.uuid4().hex; volume = 'neural029-output-' + suffix
        holder = 'neural029-holder-' + suffix; candidate = 'neural029-candidate-' + suffix
        engine.volume(volume)
        hm = {'/trusted/holder.py': {'type': 'bind', 'source': str(HERE/'holder.py'), 'rw': False},
              '/capture': {'type': 'volume', 'source': volume, 'rw': False},
              '/export': {'type': 'bind', 'source': str(capture), 'rw': True}}
        engine.create(holder, 'holder', hm)
        safe.need(engine.call(['start', holder])['returncode'] == 0, 'Holder started')
        safe.need(engine.inspect('container', holder)['State']['Running'] is True, 'Live output holder')
        cm = {'/program/candidate.py': {'type': 'bind', 'source': str(work/'candidate.py'), 'rw': False},
              '/input/public': {'type': 'bind', 'source': str(work/'public'), 'rw': False},
              '/output': {'type': 'volume', 'source': volume, 'rw': True}}
        engine.create(candidate, 'candidate', cm); event('candidate_boundary_checked')
        launched = time.monotonic()
        safe.need(engine.call(['start', candidate])['returncode'] == 0, 'Candidate start')
        remaining = r['candidate_wall_seconds'] - (time.monotonic()-launched)
        safe.need(remaining > 0, 'Candidate allowance starts before start request')
        waited = engine.call(['wait', candidate], remaining)
        state = engine.inspect('container', candidate)['State']
        safe.need(waited['returncode'] == 0 and waited['stdout'].strip() == '0' and
                  state['Running'] is False and state['Pid'] == 0 and state['OOMKilled'] is False and
                  state['ExitCode'] == 0 and time.monotonic()-launched <= r['candidate_wall_seconds'],
                  'Successful candidate stopped within complete wall allowance')
        engine.remove('container', candidate); event('candidate_removed_and_absent')
        copied = engine.call(['exec', holder, 'python', '-I', '-B', '/trusted/holder.py', 'capture'], 30)
        safe.need(copied['returncode'] == 0 and not copied['stderr'], 'Trusted streaming output capture')
        descriptor = safe.strict(copied['stdout'])
        safe.need(type(descriptor) is dict and set(descriptor) == {'status', 'bytes', 'sha256'} and
                  descriptor['status'] == 'captured', 'Exact trusted capture result')
        output_pin = pin({k: descriptor[k] for k in ('bytes', 'sha256')}, contract.OUTPUT_BYTES)
        engine.end = min(whole_end-r['grade_wall_seconds'], time.monotonic()+r['cleanup_wall_seconds'])
        safe.need(not engine.close(), 'All producer, holder and volume resources absent')
        event('all_candidate_resources_absent')
        raw = read_pinned(capture/'submission.json', output_pin, contract.OUTPUT_BYTES)
        safe.need({p.name for p in capture.iterdir()} == {'submission.json'}, 'Exact trusted captured directory')
        committed = write_bytes(work/'submission.json', raw); event('submission_committed', pin=committed)
        # The binding/private source is not opened, hashed or mounted before this point.
        event('private_grading_start')
        binding_raw = safe.read(plain_path(r['binding']), 2000000)
        binding = safe.strict(binding_raw)
        safe.need(type(binding) is dict and set(binding) == {'schema', 'public', 'private', 'identity'}
                  and binding['schema'] == 'neural029-binding-v2' and binding['public'] ==
                  {'path': 'public/MANIFEST.json', **r['public_manifest_pin']},
                  'Grade binding names the exact candidate-visible public manifest')
        write_bytes(work/'binding.json', binding_raw)
        grade_env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR') if k in os.environ}
        grade_env.update({k: '1' for k in contract.THREADS}); grade_env['PYTHONDONTWRITEBYTECODE'] = '1'
        grade = bounded_command([r['grader_python'], '-I', '-B', str(method/'grade.py'),
            '--root', r['prepared_root'], '--binding', str(work/'binding.json'), '--submission', str(work/'submission.json'),
            '--output', str(work/'grade.json')], grade_env, whole_end, r['grade_wall_seconds'])
        safe.write_new(work/'grade-process.json', grade, 2200000)
        safe.need(grade['returncode'] == 0 and time.monotonic() <= whole_end, 'Complete unchanged grader process')
        grade_raw = safe.read(work/'grade.json', 2000000)
        grade_value = safe.strict(grade_raw)
        safe.need(grade_value['schema'] == 'neural029-grade-v2' and grade_value['all_pairs_retained'] is True
                  and len(grade_value['pairs']) == public['pairs'], 'Full unchanged grade result')
        event('grade_completed')
        result.update(status='programme_captured_and_graded', public=public, programme=r['program_pin'],
                      submission=committed, grade={'bytes': len(grade_raw), 'sha256': hashlib.sha256(grade_raw).hexdigest()})
        return result
    except BaseException as error:
        failure = error
        result.update(status='failed_preserved', error=repr(error),
                      original_command=getattr(error, 'command_observation', None))
        raise
    finally:
        cleanup_errors = []
        if engine is not None:
            engine.end = min(whole_end, time.monotonic()+r['cleanup_wall_seconds'])
            cleanup_errors = engine.close()
        result.update(events=event_rows, cleanup_errors=cleanup_errors,
                      native_qualification=False, elapsed_seconds=time.monotonic()-start,
                      whole_process_observer_required=True, operating_system_SIGKILL_recovery_automatic=False)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        try:
            safe.write_new(work/'RESULT.json', result, 2500000)
        except BaseException as error:
            if failure is not None:
                failure.add_note('Result preservation also failed: ' + repr(error))
            else:
                raise
        if cleanup_errors and failure is None:
            raise RuntimeError('Owned cleanup incomplete; no successful execution claim')
