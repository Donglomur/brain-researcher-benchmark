"""One denied-by-default, fixed-custody two-bank Docker lifecycle.

Reuses the retained legacy verifier/absence grammar and RTT normalization;
does not invoke any original broad prepare/candidate/grade entrypoint.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from types import ModuleType

HERE = Path(__file__).resolve().parent
E = Path('/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2')
D = E / 'completion21-v1/parallel-task-wave'
DEST = D / 'native-neural024-two-bank-v1/attempt-001'
NAME = 'neural024-two-bank-authentic-001'
ENDPOINT = 'unix:///Users/nicholas/.docker/run/docker.sock'
DOCKER = '/usr/local/bin/docker'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
TASK_SOURCE = Path('/Users/nicholas/Documents/Codex/neuro-completion-20261117/integration/benchmarks/neural/NEURAL-024/implementations/causal-program-v2/source')
SCIENCE = TASK_SOURCE / 'authoring/rtt-neural-forecast-v1/causal-science-v1'
LEGACY = TASK_SOURCE / 'authoring/erp-neural-prediction-v1/reference-v1/runtime.py'
LEGACY_PIN = {'bytes': 12873, 'sha256': 'ca63d4f2f07f9a72471d8ae29c11b853f4b3f52f2b1c1ac48125de985daec0b1'}
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'NUMBA_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')
LIMITS = {'cpu': (25, 26), 'core': (0, 0), 'nofile': (1024, 1024), 'fsize': (7400000, 7400000)}
CONTROL_CAP = 196608
TOTAL_CAP = 17558528
WATCHDOG_RELATIVE = 'authoring/finite-sample-dimensionality/repeated-sampling-v2/ownership_long_v2'
WATCHDOG_PINS = {
    'process_owner.py': {'bytes': 7679, 'sha256': '9b97e25e973b5a4be5e6237d064546a6840ebdc5411a625b0bb61b3dc682192d'},
    'trusted_controller.py': {'bytes': 2094, 'sha256': '6ad9e2e74fdf9ee9dbbf8e4626cd8c8161ab0c3d64b7da2a3bcd45d1f0d4bdaa'},
    'group_bootstrap.py': {'bytes': 2351, 'sha256': '04b3654272b2c20efd5572713cb0a71e3408323dc805d8432a14e3c14c59c0ed'}}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path, cap, expected_size=None):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'canonical unlinked path')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= cap,
         'bounded single-link ordinary file')
    if expected_size is not None:
        need(info.st_size == expected_size, 'exact declared file size')
    return path


def read_metadata(path, cap, expected=None):
    path = ordinary(path, cap)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        need(len(body) == before.st_size and len(body) <= cap
             and stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'stable metadata bytes')
    finally:
        os.close(fd)
    if expected is not None:
        need(pin(body) == expected, 'exact selected metadata/source pin')
    return body


def strict(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate metadata key')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite metadata')))


def loaded(name, path, body):
    module = ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def mounts(contract):
    value = {}
    for role, descriptor in contract.DESCRIPTORS.items():
        value[descriptor['worker_path']] = (str(Path(contract.CUSTODY).parents[1] / descriptor['path']), True)
    for name in contract.SOURCE_PINS:
        value['/source/' + name] = (str(SCIENCE / name), True)
    for name in ('bank_contract.py', 'bank_operator.py'):
        value['/source/' + name] = (str(HERE / name), True)
    value['/provenance/RECEIPT.json'] = (str(Path(contract.CUSTODY) / 'receipt.json'), True)
    value['/provenance/MANIFEST.json'] = (str(Path(contract.CUSTODY) / 'attempt/packet/public/manifest.json'), True)
    for name in ('ADMISSION.json', 'ROOT_DECISION.json'):
        value['/provenance/' + name] = (str(DEST / 'control' / name), True)
    value['/out'] = (str(DEST / 'output'), False)
    return value


def worker_command(admission_sha):
    return ['-I', '-B', '/source/bank_operator.py', '--admission-sha256', admission_sha]


def create_args(mapping, admission_sha, owner, legacy):
    argv = ['create', '--pull', 'never', '--name', NAME, '--label', 'neural024.owner=' + owner,
            '--network', 'none', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--memory', '3221225472', '--memory-swap', '3221225472',
            '--cpus', '1.75', '--pids-limit', '32', '--shm-size', '1048576', '--restart', 'no',
            '--log-driver', 'none', '--workdir', '/tmp', '--entrypoint', 'python',
            '--tmpfs', '/tmp:' + legacy.TMPFS['/tmp']]
    for key, (lo, hi) in LIMITS.items():
        argv += ['--ulimit', f'{key}={lo}:{hi}']
    for key in THREADS:
        argv += ['--env', key + '=1']
    argv += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
    for destination, (source, ro) in sorted(mapping.items()):
        need(source.startswith('/') and not any(x in source for x in ',\r\n'), 'literal exact mount')
        argv += ['--mount', f'type=bind,src={source},dst={destination}' + (',readonly' if ro else '')]
    return argv + [IMAGE, *worker_command(admission_sha)]


def ownership(info, owner):
    identifier = info.get('Id')
    need(type(identifier) is str and re.fullmatch('[a-f0-9]{64}', identifier)
         and info.get('Name') == '/' + NAME and info.get('Image') == IMAGE
         and info.get('Config', {}).get('Labels', {}).get('neural024.owner') == owner,
         'exact owned container identity, never a foreign name collision')
    return identifier


def verify_profile(info, mapping, base_env, admission_sha, owner, legacy):
    identifier = ownership(info, owner)
    h, config = info['HostConfig'], info['Config']
    need(h['Memory'] == h['MemorySwap'] == 3221225472 and h['NanoCpus'] == 1750000000
         and 'OomKillDisable' in h and (h['OomKillDisable'] is None or h['OomKillDisable'] is False)
         and h.get('AutoRemove') is False,
         'exact narrow resource and owned removal policy')
    need(config['Cmd'] == worker_command(admission_sha) and config.get('StdinOnce') is False,
         'exact narrow worker command')
    need(len(h['Ulimits']) == len(LIMITS)
         and {r['Name']: (r['Soft'], r['Hard']) for r in h['Ulimits']} == LIMITS, 'exact narrow ulimits')
    environment = dict(base_env)
    environment.update({key: '1' for key in THREADS}, PYTHONDONTWRITEBYTECODE='1')
    # Same normalization technique as retained rtt_profile.verify_exact. Only
    # the already verified resource/command delta is normalized; all mount,
    # environment, no-network, nonroot and sandbox checks remain legacy.verify.
    normalized = copy.deepcopy(info)
    normalized['HostConfig']['Memory'] = normalized['HostConfig']['MemorySwap'] = 4294967296
    normalized['HostConfig']['NanoCpus'] = 2000000000
    normalized['HostConfig']['Ulimits'] = [{'Name': k, 'Soft': v[0], 'Hard': v[1]} for k, v in legacy.ULIMITS.items()]
    normalized['Config']['Cmd'] = ['-I', '-B', '/program/bank_operator.py']
    legacy.verify(normalized, NAME, mapping, environment, '65534:65534', 'bank_operator.py', False)
    return identifier


class Journal:
    """All control writes are exclusive, bounded and fsynced; never retry."""
    def __init__(self, root):
        self.root = Path(root)
        self.written = 0

    def extent(self):
        total = 0
        for path in self.root.iterdir():
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and not path.is_symlink() and info.st_nlink == 1,
                 'only ordinary control records')
            total += info.st_size
        need(total <= CONTROL_CAP, 'cumulative retained control extent')
        return total

    def write(self, name, value, cap=65536, reserved=False):
        need(re.fullmatch('[a-zA-Z0-9_.-]+', name), 'fixed control leaf name')
        body = canonical(value)
        limit = CONTROL_CAP if reserved else CONTROL_CAP - 32768
        need(len(body) <= cap and self.extent() + len(body) <= limit, 'failure-inclusive control cap with cleanup reserve')
        with (self.root / name).open('xb') as stream:
            self.written += len(body)  # Conservative requested bytes, including failed writes.
            need(stream.write(body) == len(body), 'complete control write')
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class Docker:
    def __init__(self, journal, stop_group):
        self.journal, self.stop_group = journal, stop_group
        self.sequence = 0
        self.quiescent = True

    def call(self, argv, end, cap=32768, cleanup=False):
        need(time.monotonic() + .8 < end, 'CLI cleanup reserve within deadline')
        self.sequence += 1
        need(not cleanup or argv[:2] == ['rm', '--force'] or argv[:3] == ['inspect', '--type', 'container'],
             'cleanup diagnostic bypass cannot launch work')
        journal_errors = []
        def record(name, value, limit):
            try:
                self.journal.write(name, value, limit, reserved=cleanup)
            except Exception as exc:
                if not cleanup:
                    raise
                # Disk/receipt exhaustion must never prevent owned removal.
                # No record is silently claimed; the returned cleanup result
                # retains the publication failure when any receipt is possible.
                journal_errors.append(type(exc).__name__)
        record(f'cli-{self.sequence:02d}-intent.json', {'argv': [DOCKER, '--host', ENDPOINT, *argv]}, 16384)
        # Preserve only identity/configuration environment needed by the CLI;
        # inherited Docker host/context/TLS/config overrides cannot redirect it.
        env = {k: os.environ[k] for k in ('HOME', 'TMPDIR') if k in os.environ}
        env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin', LANG='C', LC_ALL='C')
        process = None
        buffers = {'stdout': bytearray(), 'stderr': bytearray()}
        selector = selectors.DefaultSelector()
        result = {'argv': argv, 'returncode': None, 'stdout': '', 'stderr': '', 'cleanup': None}
        error = None
        try:
            process = subprocess.Popen([DOCKER, '--host', ENDPOINT, *argv], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env=env, start_new_session=False)
            for name, stream in (('stdout', process.stdout), ('stderr', process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                left = end - .8 - time.monotonic()
                if left <= 0:
                    raise TimeoutError('bounded CLI transport deadline')
                for key, _ in selector.select(min(.02, left)):
                    body = os.read(key.fileobj.fileno(), 1024)
                    if not body:
                        selector.unregister(key.fileobj)
                    else:
                        room = cap - sum(map(len, buffers.values()))
                        buffers[key.data].extend(body[:room])
                        need(len(body) <= room, 'enforced combined CLI stream cap')
            process.wait(timeout=max(.001, end - .8 - time.monotonic()))
        except BaseException as exc:
            error = exc
        finally:
            selector.close()
            if process is not None:
                try:
                    result['cleanup'] = self.stop_group(process)
                except BaseException as exc:
                    result['cleanup'] = {'leader_reaped': False, 'whole_group_cleanup_delegated_to_watchdog': True}
                    error = error or exc
                result['returncode'] = process.returncode
                process.stdout.close()
                process.stderr.close()
                if not all(result['cleanup'].values()) and error is None:
                    error = RuntimeError('owned CLI leader reaping unconfirmed')
                if not all(result['cleanup'].values()):
                    self.quiescent = False
            result.update({k: bytes(v).decode('utf-8', errors='replace') for k, v in buffers.items()})
            result['error_type'] = type(error).__name__ if error else None
            record(f'cli-{self.sequence:02d}-result.json', result, 65536)
            result['diagnostic_publication_errors'] = journal_errors
        if error is not None:
            raise error
        return result


def stop_cli_leader(process):
    """Reap only this Popen leader; all descendants stay in the watchdog group.

    This does not assert whole-group absence. The retained independent owner
    must stop and verify its entire group before committing native success.
    """
    for action, seconds in ((process.terminate, .2), (process.kill, .6)):
        if process.poll() is not None:
            break
        try:
            action()
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            pass
    return {'leader_reaped': process.poll() is not None,
            'whole_group_cleanup_delegated_to_watchdog': True}


def require_watchdog(source_pin, launch_sha):
    """Require the retained independently owned bootstrap before any CLI."""
    for name, expected in WATCHDOG_PINS.items():
        read_metadata(DEST / 'source' / WATCHDOG_RELATIVE / name, expected['bytes'], expected)
    folder = DEST / 'watchdog'
    owner = strict(read_metadata(folder / 'process_owner.json', 16384))
    intent = strict(read_metadata(folder / 'process_intent.json', 16384))
    gate = strict(read_metadata(folder / 'process_gate.json', 16384))
    controller = {'path': 'authoring/neural024-bank-operator/bank_launcher.py', **source_pin}
    argv = [sys.executable, str(HERE / 'bank_launcher.py'), '--launch-admission-sha256', launch_sha]
    need(owner.get('controller') == intent.get('controller') == controller
         and owner.get('child_argv') == argv and owner.get('seconds') == 30.0
         and owner.get('pid_recorded_before_activation') is True,
         'exact source-frozen parent watchdog activation')
    pid, token = owner.get('pid'), owner.get('token')
    need(type(pid) is int and pid > 1 and owner.get('pgid') == pid
         and os.getppid() == os.getpgrp() == pid
         and type(token) is str and re.fullmatch('[a-f0-9]{32}', token)
         and intent.get('token') == token and gate == {'token': token, 'activate': True}
         and owner.get('bootstrap_argv') == intent.get('bootstrap_argv'),
         'same durable inherited parent process group, not an unowned launcher')


def row(result):
    need(result['returncode'] == 0 and not result['stderr'], 'successful bounded Docker inspection')
    rows = strict(result['stdout'])
    need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, 'one exact inspect object')
    return rows[0]


class Lifecycle:
    """Injected Docker/journal/clock seam; generated tests need no runtime."""
    def __init__(self, docker, journal, legacy, clock=time.monotonic):
        self.docker, self.journal, self.legacy, self.clock = docker, journal, legacy, clock

    def run(self, mapping, admission_sha, owner, end, validate_outputs):
        active_end = end - 4.0
        created = False
        create_return_confirmed = False
        owned_id = None
        cleanup = {'attempted': False, 'absence_verified': False}
        status, error_type, output = 'failed', None, None
        try:
            self.journal.write('attempt-claim.json', {'owner': owner, 'container_name': NAME,
                'max_attempts': 1, 'mounts': mapping, 'admission_sha256': admission_sha,
                'input_read_upper_on_any_partial_failure': 8942144,
                'source_copy_bytes': 0, 'output_cap_bytes': 8616384, 'total_storage_cap_bytes': TOTAL_CAP}, 16384)
            need(self.clock() < active_end, 'remaining work before cleanup reserve')
            image = row(self.docker.call(['image', 'inspect', IMAGE], active_end, 16384))
            need(image.get('Id') == IMAGE, 'exact current selected image')
            base_list = image.get('Config', {}).get('Env')
            need(type(base_list) is list and all(type(v) is str and '=' in v for v in base_list), 'image environment')
            base_env = dict(v.split('=', 1) for v in base_list)
            need(len(base_env) == len(base_list), 'unique image environment')
            initial = self.docker.call(['inspect', '--type', 'container', NAME], active_end, 2048)
            need(self.legacy.absent(initial, NAME), 'fresh container name before any create')
            argv = create_args(mapping, admission_sha, owner, self.legacy)
            self.journal.write('create-intent.json', {'owner': owner, 'argv': argv}, 16384)
            created = True  # Intent is durable before a possibly ambiguous create.
            made = self.docker.call(argv, active_end, 1024)
            need(made['returncode'] == 0 and not made['stderr']
                 and re.fullmatch('[a-f0-9]{64}\n', made['stdout']), 'one immutable created ID')
            create_return_confirmed = True
            info = row(self.docker.call(['inspect', '--type', 'container', NAME], active_end))
            owned_id = ownership(info, owner)
            need(made['stdout'].strip() == owned_id, 'returned and inspected ID agree')
            verify_profile(info, mapping, base_env, admission_sha, owner, self.legacy)
            self.journal.write('prestart-verified.json', {'id': owned_id, 'owner': owner, 'exact_profile_verified': True}, 2048)
            reply = self.docker.call(['start', '--attach', owned_id], active_end, 8192)
            need(reply['returncode'] == 0 and not reply['stderr'], 'successful bounded worker exit transport')
            summary = strict(reply['stdout'])
            need(summary.get('status') == 'two_bank_projection_qualified_only'
                 and summary.get('benchmark_ready') is False
                 and summary.get('complete_benchmark_preparation') is False, 'worker source-only success summary')
            ended = row(self.docker.call(['inspect', '--type', 'container', owned_id], active_end))
            need(ownership(ended, owner) == owned_id, 'same ended worker identity')
            state = ended['State']
            need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
                 and state['ExitCode'] == 0 and not state.get('OOMKilled') and not state.get('Error'), 'clean final state')
            output = summary
            status = 'worker_completed_cleanup_pending'
        except BaseException as exc:
            error_type = type(exc).__name__
        finally:
            if created:
                cleanup['attempted'] = True
                try:
                    need(self.clock() < end, 'cleanup within absolute total deadline')
                    if owned_id is None:
                        inspected = self.docker.call(['inspect', '--type', 'container', NAME], end, 32768, cleanup=True)
                        if self.legacy.absent(inspected, NAME):
                            cleanup['absence_verified'] = True
                        else:
                            owned_id = ownership(row(inspected), owner)
                    if owned_id is not None:
                        removed = self.docker.call(['rm', '--force', owned_id], end, 2048, cleanup=True)
                        absent = self.docker.call(['inspect', '--type', 'container', owned_id], end, 2048, cleanup=True)
                        cleanup['absence_verified'] = self.legacy.absent(absent, owned_id)
                        cleanup['remove_returncode'] = removed['returncode']
                    cleanup['id'] = owned_id
                    cleanup['create_operation_extent_unknown'] = not create_return_confirmed
                    cleanup['point_in_time_absence_observed'] = cleanup['absence_verified']
                    if not create_return_confirmed or not getattr(self.docker, 'quiescent', True):
                        cleanup['absence_verified'] = False
                    cleanup['cli_leaders_reaped'] = getattr(self.docker, 'quiescent', True)
                except BaseException as exc:
                    cleanup['error_type'] = type(exc).__name__
        if status == 'worker_completed_cleanup_pending' and cleanup['absence_verified']:
            try:
                need(self.clock() < end, 'post-cleanup output validation within absolute deadline')
                output = validate_outputs(output, end)
                status = 'two_bank_projection_qualified_only'
            except BaseException as exc:
                status, error_type = 'output_validation_failed', type(exc).__name__
        elif created and not cleanup['absence_verified']:
            status = 'cleanup_unconfirmed'
        else:
            status = 'failed'
        return {'status': status, 'error_type': error_type, 'cleanup': cleanup, 'output': output,
                'input_read_extent_unknown_on_failure': status != 'two_bank_projection_qualified_only',
                'input_read_upper_bytes_on_failure': 8942144,
                'final_native_commit_requires_independent_watchdog_group_absence': True,
                'benchmark_ready': False, 'complete_benchmark_preparation': False}


def opaque_output(path, expected, end):
    path = ordinary(path, expected['bytes'], expected['bytes'])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    try:
        before = os.fstat(fd)
        total, sha = 0, hashlib.sha256()
        while total < before.st_size:
            need(time.monotonic() < end, 'opaque validation within absolute deadline')
            body = os.read(fd, min(65536, before.st_size - total))
            need(bool(body), 'complete bounded opaque output')
            total += len(body)
            sha.update(body)
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'stable opaque output')
    finally:
        os.close(fd)
    actual = {'bytes': total, 'sha256': sha.hexdigest()}
    need(actual == expected, 'output byte identity agrees with trusted worker')
    return actual


def validate_output(summary, end, contract, inner_sha, decision_pin, operator_pins):
    folder = DEST / 'output'
    need({p.name for p in folder.iterdir()} == set(contract.CAPS), 'exact complete three-file output; no partials')
    receipt_pin = summary.get('receipt')
    need(contract.valid_pin(receipt_pin, 16384), 'bounded exact qualification receipt')
    raw = read_metadata(folder / 'sourcebank_qualification.json', 16384, receipt_pin)
    result = strict(raw)
    need(result.get('schema') == 'neural024-two-bank-result/v1' and result.get('task_id') == 'NEURAL-024'
         and result.get('operation_id') == contract.OPERATION
         and result.get('status') == 'two_bank_projection_qualified_only'
         and result.get('admission_sha256') == inner_sha and result.get('root_decision_pin') == decision_pin
         and result.get('operator_sources') == operator_pins
         and result.get('source_origin') == 'NEURAL-023' and result.get('qualification_inherited') is False
         and result.get('input_identity_pins') == {role: {key: desc[key] for key in ('bytes', 'sha256')}
                                                  for role, desc in contract.DESCRIPTORS.items()}
         and result.get('error_type') is None
         and result.get('incomplete_extent') is False and result.get('native_clock_edges_modified') is False
         and result.get('benchmark_ready') is False and result.get('complete_benchmark_preparation') is False,
         'exact receipt/admission/source/lineage join')
    pins = result.get('files_before_receipt')
    need(type(pins) is dict and set(pins) == {r + '.npz' for r in contract.ROLES}, 'both full published banks')
    guard = contract.ProjectionGuard()
    guard.state, guard.position, guard.pins = 'complete', 2, pins
    guard.completed(result.get('counters', {}))
    need(result.get('writer_attempted_before_receipt') == result.get('writer_completed_before_receipt') == 2,
         'exact completed data publications')
    for name, expected in pins.items():
        need(contract.valid_pin(expected, contract.CAPS[name]), 'bounded projected output pin')
        opaque_output(folder / name, expected, end)
    return {'files': {**pins, 'sourcebank_qualification.json': receipt_pin}, 'opaque_host_validation_only': True,
            'host_array_decoding': False, 'source_origin': 'NEURAL-023', 'qualification_inherited': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch-admission-sha256', required=True)
    args = parser.parse_args()
    started, end = time.monotonic(), time.monotonic() + 30
    def interrupted(signum, frame):
        raise TimeoutError('absolute native allocation or external interruption')
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    signal.setitimer(signal.ITIMER_REAL, 30)
    launch_path = DEST / 'control/LAUNCH_ADMISSION.json'
    raw = read_metadata(launch_path, 32768)
    need(pin(raw)['sha256'] == args.launch_admission_sha256, 'exact final root launch packet')
    launch = strict(raw)
    need(launch.get('execution_authorized') is True, 'authentic execution is denied')
    need(set(launch) == {'schema', 'execution_authorized', 'task_id', 'operation_id', 'launcher_sources',
         'worker_admission_pin', 'root_decision_pin', 'destination', 'resource_owner', 'max_attempts',
         'total_wall_seconds', 'cleanup_reserve_seconds', 'total_storage_bytes', 'control_storage_bytes',
         'host_opaque_output_hashing_authorized', 'original_input_host_hashing_authorized'}, 'exact launch schema')
    need(launch['schema'] == 'neural024-bank-launch-admission/v1' and launch['task_id'] == 'NEURAL-024'
         and launch['operation_id'] == 'qualify_exact_converted_public_banks_v1'
         and launch['destination'] == str(DEST) and launch['resource_owner'] == '/root'
         and type(launch['max_attempts']) is int and launch['max_attempts'] == 1
         and launch['total_wall_seconds'] == 30 and launch['cleanup_reserve_seconds'] == 4
         and launch['total_storage_bytes'] == TOTAL_CAP and launch['control_storage_bytes'] == CONTROL_CAP
         and launch['host_opaque_output_hashing_authorized'] is True
         and launch['original_input_host_hashing_authorized'] is False, 'fixed root resource selection')
    source_pins = launch['launcher_sources']
    need(type(source_pins) is dict and set(source_pins) == {'bank_launcher.py', 'bank_contract.py', 'bank_operator.py'},
         'exact launcher and worker source roster')
    bodies = {name: read_metadata(HERE / name, 65536, expected) for name, expected in source_pins.items()}
    contract = loaded('bank_contract', HERE / 'bank_contract.py', bodies['bank_contract.py'])
    legacy = loaded('bank_retained_legacy', LEGACY, read_metadata(LEGACY, LEGACY_PIN['bytes'], LEGACY_PIN))
    require_watchdog(source_pins['bank_launcher.py'], args.launch_admission_sha256)
    inner_raw = read_metadata(DEST / 'control/ADMISSION.json', 32768, launch['worker_admission_pin'])
    inner = strict(inner_raw)
    operator_pins = {n: source_pins[n] for n in ('bank_contract.py', 'bank_operator.py')}
    contract.admission(inner, operator_pins)
    need(inner['root_decision_pin'] == launch['root_decision_pin'], 'same explicit root decision')
    decision = strict(read_metadata(DEST / 'control/ROOT_DECISION.json', 16384, launch['root_decision_pin']))
    contract.root_decision(decision, operator_pins)
    mapping = mounts(contract)
    for role, desc in contract.DESCRIPTORS.items():
        # Original inputs: filename/stat metadata only on host, never read/hash.
        ordinary(mapping[desc['worker_path']][0], desc['bytes'], desc['bytes'])
    for name, expected in contract.SOURCE_PINS.items():
        read_metadata(SCIENCE / name, expected['bytes'], expected)
    for name, expected in (('RECEIPT.json', contract.RECEIPT_PIN), ('MANIFEST.json', contract.MANIFEST_PIN)):
        read_metadata(mapping['/provenance/' + name][0], expected['bytes'], expected)
    need(DEST.is_dir() and all(not p.is_symlink() for p in (DEST, *DEST.parents)), 'exact owned native destination')
    need({p.name for p in DEST.iterdir()} == {'control', 'source', 'watchdog'} and (DEST / 'control').is_dir(),
         'fresh destination except final root packets and watchdog source staging')
    need(HERE == DEST / 'source/authoring/neural024-bank-operator', 'fixed staged authoring controller for retained watchdog')
    need({p.name for p in (DEST / 'control').iterdir()} == {'LAUNCH_ADMISSION.json', 'ADMISSION.json', 'ROOT_DECISION.json'},
         'one attempt; existing claim or partials forbid replay')
    for destination, (host, ro) in mapping.items():
        if ro:
            need(Path(host).stat().st_mode & 4, 'worker-readable readonly mount source')
    (DEST / 'output').mkdir(mode=0o777)
    (DEST / 'output').chmod(0o777)
    journal = Journal(DEST / 'control')
    docker = Docker(journal, stop_cli_leader)
    lifecycle = Lifecycle(docker, journal, legacy)
    outcome = lifecycle.run(mapping, pin(inner_raw)['sha256'], args.launch_admission_sha256, end,
                            lambda summary, deadline: validate_output(summary, deadline, contract,
                                pin(inner_raw)['sha256'], launch['root_decision_pin'], operator_pins))
    # The independent watchdog is necessarily still alive while this child
    # writes. Only its root owner can commit after stopping/verifying that group.
    need(time.monotonic() < end, 'no receipt extension beyond absolute allocation')
    outcome['elapsed_seconds'] = time.monotonic() - started
    if outcome['status'] == 'two_bank_projection_qualified_only':
        journal.write('RESULT_PENDING_WATCHDOG_STOP.json', outcome, 16384, reserved=True)
    else:
        journal.write('FAILED.json', outcome, 16384, reserved=True)
    signal.setitimer(signal.ITIMER_REAL, 0)
    return 0 if outcome['status'] == 'two_bank_projection_qualified_only' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # No unbounded traceback, stdout or claim of successful cleanup. The
        # durable attempt/CLI records remain the recovery source of truth.
        raise SystemExit(2)
