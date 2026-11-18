"""SMC's durable controller launch barrier with an unrenewable absolute clock.

Derived from ownership-v4/process_owner.py. This owns one trusted process group;
independent Provider CLI groups require the enclosing parent's separate custody.
No candidate code, Docker operation or model runs in this module.
"""
from pathlib import Path
import json
import math
import os
import re
import signal
import stat
import subprocess
import sys
import time
import uuid

from trusted_controller import validate_controller

HERE = Path(__file__).resolve().parent
PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560}
RECOVERY_SECONDS = 60
META_CAP = 16384
MODE = 'smc_owned_controller_v1'
FIXTURE_MODE = 'smc_fixed_trusted_fixture_v1'


def clock_identity():
    """A retained monotonic deadline is usable only within this same boot."""
    if sys.platform.startswith('linux'):
        raw = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if not re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', raw):
            raise ValueError('Bounded Linux boot identity')
        return 'linux:' + raw
    if sys.platform == 'darwin':
        p = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.boottime'], capture_output=True,
                           text=True, timeout=1, check=True)
        if len(p.stdout) > 256 or p.stderr:
            raise ValueError('Bounded macOS boot identity')
        match = re.match(r'^\{ sec = ([0-9]+), usec = ([0-9]+) \}', p.stdout)
        if match is None:
            raise ValueError('Exact macOS boot identity')
        return 'darwin:' + ':'.join(match.groups())
    raise ValueError('Unsupported process-owner clock identity')


def read(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unlinked process journal')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= META_CAP:
            raise ValueError('Bounded regular process journal')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
        named = path.stat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if len(raw) != before.st_size or any(getattr(before, k) != getattr(after, k)
                                       or getattr(before, k) != getattr(named, k) for k in fields):
        raise ValueError('Stable complete process journal')
    def unique(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate journal key')
            value[key] = item
        return value
    def finite(_):
        raise ValueError('Nonfinite journal value')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=finite)


def atomic(path, value):
    """Publish a new durable record; never replace an earlier invocation record."""
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unlinked process journal')
    tmp = path.with_suffix('.next')
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    if len(raw) > META_CAP:
        raise ValueError('Process metadata cap')
    with tmp.open('xb') as stream:
        os.chmod(tmp, 0o400)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(tmp, path, follow_symlinks=False)  # O_EXCL publication, unlike replace.
    tmp.unlink()
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_grant(grant, *, fixture=False, require_remaining=True):
    keys = {'outcome', 'origin', 'controller_deadline', 'deadline', 'clock_identity', 'invocation_pin'}
    if (type(grant) is not dict or set(grant) != keys or type(grant['outcome']) is not str
            or grant['outcome'] not in PAIR_SECONDS):
        raise ValueError('Exact SMC retained-clock grant')
    for key in ('origin', 'controller_deadline', 'deadline'):
        if type(grant[key]) not in (int, float) or not math.isfinite(grant[key]) or grant[key] <= 0:
            raise ValueError('Finite positive original monotonic clock')
    if fixture:
        # This route can invoke only the tiny checked trusted_fixture.py.
        if grant['deadline'] != grant['origin'] + 8 or grant['controller_deadline'] != grant['deadline'] - 2:
            raise ValueError('Fixed eight-second software fixture only')
    elif (grant['deadline'] != grant['origin'] + PAIR_SECONDS[grant['outcome']]
          or grant['controller_deadline'] != grant['deadline'] - RECOVERY_SECONDS):
        raise ValueError('Unchanged whole-pair ceiling and in-budget recovery reserve')
    pin = grant['invocation_pin']
    if (type(pin) is not dict or set(pin) != {'bytes', 'sha256'}
            or type(pin['bytes']) is not int or not 0 < pin['bytes'] <= META_CAP
            or type(pin['sha256']) is not str or re.fullmatch('[a-f0-9]{64}', pin['sha256']) is None):
        raise ValueError('Exact bounded immutable invocation pin')
    if type(grant['clock_identity']) is not str or grant['clock_identity'] != clock_identity():
        raise ValueError('Retained deadline belongs to this same boot')
    if require_remaining and not grant['origin'] <= time.monotonic() < grant['controller_deadline']:
        raise TimeoutError('Original controller interval remains; no renewed clock')
    return grant


def _argv(folder, token, channel_fd):
    return [sys.executable, '-I', '-B', str(HERE / 'group_bootstrap.py'),
            '--owner', str(folder / 'process_owner.json'), '--token', token,
            '--channel-fd', str(channel_fd)]


def _channel(argv, channel_fd):
    if type(channel_fd) is not int or channel_fd < 3 or argv.count('--channel-fd') != 1:
        raise ValueError('One explicit inherited journal channel')
    at = argv.index('--channel-fd')
    if at + 1 >= len(argv) or argv[at + 1] != str(channel_fd):
        raise ValueError('Controller argv binds exact inherited channel')
    if not stat.S_ISSOCK(os.fstat(channel_fd).st_mode):
        raise ValueError('Existing socket journal channel only')


def launch(argv, folder, grant, controller, channel_fd):
    return _launch(argv, folder, grant, controller, channel_fd, fixture=False)


def _launch_fixture(argv, folder, grant, controller, channel_fd):
    return _launch(argv, folder, grant, controller, channel_fd, fixture=True)


def _launch(argv, folder, grant, controller, channel_fd, *, fixture):
    folder = Path(folder).absolute()
    if (not folder.is_dir() or any(p.is_symlink() for p in (folder, *folder.parents))
            or stat.S_IMODE(folder.stat().st_mode) & 0o077 or any(folder.iterdir())):
        raise ValueError('Fresh private bounded process ownership directory')
    validate_grant(grant, fixture=fixture)
    validate_controller(controller, argv, fixture=fixture)
    _channel(argv, channel_fd)
    token = uuid.uuid4().hex
    args = _argv(folder, token, channel_fd)
    mode = FIXTURE_MODE if fixture else MODE
    intent = {'mode': mode, 'bootstrap_argv': args, 'token': token,
              'activation_requires_fsynced_owner': True, 'controller': controller,
              'child_argv': argv, 'grant': grant, 'channel_fd': channel_fd}
    atomic(folder / 'process_intent.json', intent)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, close_fds=True, pass_fds=(channel_fd,))
    try:
        ready_path = folder / 'process_ready.json'
        ready_end = min(grant['controller_deadline'], time.monotonic() + 1.5)
        while not ready_path.exists():
            # Keep the exact Popen leader unreaped until the failure cleanup.
            # Poll could reap it and release its numeric PID before killpg.
            if time.monotonic() >= ready_end:
                raise TimeoutError('Bounded initialized-bootstrap readiness')
            time.sleep(.01)
        ready = read(ready_path)
        if ready != {'token': token, 'pid': proc.pid, 'pgid': proc.pid,
                     'python_initialized_before_identity_snapshot': True}:
            raise ValueError('Exact initialized-bootstrap readiness')
        observed = inspect_leader(proc.pid, min(grant['controller_deadline'], time.monotonic() + 1))
        if observed is None or observed['pgid'] != proc.pid or not observed['command'].endswith(' ' + ' '.join(args[1:])):
            raise ValueError('Observed exact bootstrap arguments')
        validate_grant(grant, fixture=fixture)
        validate_controller(controller, argv, fixture=fixture)
        atomic(folder / 'process_owner.json', {**intent, 'observed_leader': observed,
               'pid': proc.pid, 'pgid': proc.pid, 'pid_recorded_before_activation': True})
        atomic(folder / 'process_gate.json', {'token': token, 'activate': True})
        return proc
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        raise


def expected(folder, *, require_remaining=False):
    folder = Path(folder).absolute()
    owner, intent = read(folder / 'process_owner.json'), read(folder / 'process_intent.json')
    if owner.get('mode') not in (MODE, FIXTURE_MODE):
        raise ValueError('Known task ownership mode')
    fixture = owner['mode'] == FIXTURE_MODE
    validate_grant(owner['grant'], fixture=fixture, require_remaining=require_remaining)
    pid, token = owner['pid'], owner['token']
    if (type(pid) is not int or pid <= 1 or owner['pgid'] != pid
            or owner.get('pid_recorded_before_activation') is not True
            or type(token) is not str or re.fullmatch('[a-f0-9]{32}', token) is None):
        raise ValueError('Exact durable process identity')
    args = _argv(folder, token, owner['channel_fd'])
    if owner['bootstrap_argv'] != args:
        raise ValueError('Exact bootstrap command identity')
    keys = {'mode', 'bootstrap_argv', 'token', 'activation_requires_fsynced_owner',
            'controller', 'child_argv', 'grant', 'channel_fd'}
    if set(intent) != keys or any(owner.get(key) != intent[key] for key in keys) or intent['activation_requires_fsynced_owner'] is not True:
        raise ValueError('Immutable invocation across intent and ownership')
    validate_controller(owner['controller'], owner['child_argv'], check_bytes=False, fixture=fixture)
    # Recovery does not require that the inherited channel is still open.
    at = owner['child_argv'].index('--channel-fd')
    if owner['child_argv'].count('--channel-fd') != 1 or owner['child_argv'][at + 1] != str(owner['channel_fd']):
        raise ValueError('Retained exact channel identity')
    return owner, args


def inspect_leader(pid, end):
    if time.monotonic() >= end:
        raise TimeoutError('Original process inspection deadline')
    p = subprocess.run(['/bin/ps', '-ww', '-p', str(pid), '-o', 'pid=', '-o', 'pgid=',
                        '-o', 'lstart=', '-o', 'stat=', '-o', 'command='], capture_output=True,
                       text=True, timeout=min(1, max(.001, end - time.monotonic())))
    if len(p.stdout) > 8192 or len(p.stderr) > 1024:
        raise ValueError('Untruncated process identity required')
    fields = p.stdout.strip().split(None, 8)
    if p.returncode != 0 or len(fields) != 9:
        return None
    return {'pid': int(fields[0]), 'pgid': int(fields[1]), 'started': ' '.join(fields[2:7]),
            'state': fields[7], 'command': fields[8]}


def group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop(folder, end, proc=None, *, reap_owned_children=None):
    """Stop exact owned group; separate CLI custody is the parent's obligation.

    A Linux subreaper may supply a deadline-taking callback which reaps only its
    already identity-bound adopted controller children. It runs after bootstrap
    reaping and during the absence wait. Its independently stored evidence is
    owned by that caller; a callback exception never yields a closure success.
    """
    folder = Path(folder)
    if not (folder / 'process_owner.json').exists():
        if (folder / 'process_gate.json').exists():
            raise ValueError('Activation without ownership')
        if (folder / 'process_intent.json').exists():
            # A caller lost between Popen and durable ownership cannot certify
            # host absence merely because the activation gate is still absent.
            return {'status': 'unactivated_ownership_incomplete', 'absence_verified': False,
                    'no_group_identity_claim': True, 'activation_observed': False}
        return {'status': 'never_activated', 'absence_verified': True, 'no_group_identity_claim': True}
    owner, _ = expected(folder)
    if type(end) not in (int, float) or not math.isfinite(end):
        raise ValueError('Finite cleanup cutoff')
    if reap_owned_children is not None and not callable(reap_owned_children):
        raise ValueError('Explicit callable scoped child reaper')
    end = min(end, owner['grant']['deadline'])
    pid = owner['pid']
    if proc is not None and proc.pid != pid:
        raise ValueError('Only the actual owned Popen handle')
    row = {'pid': pid, 'pgid': pid, 'status': 'checking', 'absence_verified': False,
           'original_deadline': owner['grant']['deadline'], 'cleanup_cutoff': end,
           'independent_provider_CLI_custody_established': False, 'scoped_child_reap_calls': 0}
    if group_exists(pid):
        if time.monotonic() >= end:
            raise TimeoutError('Original process cleanup deadline')
        actual = inspect_leader(pid, end)
        row['leader_inspection'] = actual
        initial = owner['observed_leader']
        own_unreaped_zombie = (actual is not None and actual['state'].startswith('Z')
                              and proc is not None and proc.returncode is None)
        exact = (actual is not None and actual['pid'] == pid and actual['pgid'] == pid
                 and actual['started'] == initial['started']
                 and (actual['command'] == initial['command'] or own_unreaped_zombie))
        if exact:
            try:
                os.killpg(pid, signal.SIGKILL)
                row['kill_sent'] = True
            except ProcessLookupError:
                pass
        elif group_exists(pid):
            raise ValueError('Refuse nonmatching process-group leader')
    if proc is not None:
        stdout, stderr = proc.communicate(timeout=min(1, max(.001, end - time.monotonic())))
        if len(stdout) > 65536 or len(stderr) > 65536:
            raise ValueError('Bounded trusted controller logs')
        row.update(stdout=stdout.decode(errors='replace'), stderr=stderr.decode(errors='replace'),
                   bootstrap_returncode=proc.returncode)
    if reap_owned_children is not None:
        reap_owned_children(end)
        row['scoped_child_reap_calls'] += 1
    while group_exists(pid) and time.monotonic() < end:
        if reap_owned_children is not None:
            reap_owned_children(end)
            row['scoped_child_reap_calls'] += 1
        time.sleep(.01)
    row['absence_verified'] = not group_exists(pid)
    row['cleanup_before_original_deadline'] = time.monotonic() <= owner['grant']['deadline']
    row['status'] = 'owned_group_absent' if row['absence_verified'] else 'owned_group_absence_unverified'
    return row
