"""Bounded local-Docker transport. No host execution fallback or image pulls.

The running namespace supplies bounded output bytes before an inspected pause,
removal and absence barrier. Capture is not an atomic paused-filesystem snapshot.
Actual runtime qualification is a separate step.
"""
import io
import hashlib
import base64
import binascii
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tarfile
import time

from common import decode, encoded, need, pin

MEMORY = 3221225472
NANO_CPUS = 1750000000
PIDS = 256
TMPFS = {'/output': 'rw,nosuid,nodev,noexec,size=1048576,mode=0700,uid=65534,gid=65534',
         '/tmp': 'rw,nosuid,nodev,size=3221225472,mode=0700,uid=65534,gid=65534'}
ENV = ['HOME=/tmp', 'PYTHONDONTWRITEBYTECODE=1', 'PYTHONNOUSERSITE=1',
       'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
       'VECLIB_MAXIMUM_THREADS=1', 'NUMEXPR_NUM_THREADS=1', 'BLIS_NUM_THREADS=1']
KEEPER = ['/usr/local/bin/python', '-I', '-B', '-c', 'import signal; signal.pause()']
CANDIDATE = ['/usr/local/bin/python', '-I', '-B', '/program/submission.py',
             '--input', '/input/data.npz', '--manifest', '/input/manifest.json',
             '--output', '/output/predictions.json']
CAPTURE_SOURCE = '''import os,stat,base64,hashlib,json,sys
def sig(s):
 return [s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def check(ok):
 if not ok: raise ValueError("Output changed or violates capture contract")
def capture(root='/output'):
 d=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  ds=sig(os.fstat(d));check(os.listdir(d)==['predictions.json'])
  f=os.open('predictions.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d)
  try:
   s=os.fstat(f);before=sig(s)
   check(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=131072)
   data=bytearray()
   while len(data)<131073:
    part=os.read(f,min(65536,131073-len(data)))
    if not part: break
    data.extend(part)
   after=sig(os.fstat(f))
   name=sig(os.stat('predictions.json',dir_fd=d,follow_symlinks=False))
   de=sig(os.fstat(d))
   check(len(data)==s.st_size and before==after==name and ds==de and os.listdir(d)==['predictions.json'])
   return {'schema':'neural031_running_output_capture_v1','capture_while_paused':False,
    'payload':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'base64':base64.b64encode(data).decode('ascii')},
    'file_before':before,'file_after':after,'name_after':name,'directory_before':ds,'directory_after':de}
  finally: os.close(f)
 finally: os.close(d)
if __name__=='__main__':
 print(json.dumps(capture(),sort_keys=True,separators=(',',':'),allow_nan=False))
'''
CAPTURE = ['/usr/local/bin/python', '-I', '-S', '-B', '-c', CAPTURE_SOURCE]
SELECTED_IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
SELECTED_IMAGE_ENV = {
    'PATH': '/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    'LANG': 'C.UTF-8', 'GPG_KEY': '7169605F62C751356D054A26A821E680E5FA6305',
    'PYTHON_VERSION': '3.12.8',
    'PYTHON_SHA256': 'c909157bb25ec114e5869124cc2a9c4a4d4c1e957ca4ff553f1edc692101154e',
    'OPENBLAS_NUM_THREADS': '2', 'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2'}
JOURNAL_CAP = 24 * 1024 * 1024
COMMAND_CAP = 448  # 441 complete normal calls; up to four failure-cleanup calls.
INTENT_CAP = RESULT_CAP = 4096


def prediction_from_frame(body):
    """Validate the exact running-capture frame; never claim paused atomicity."""
    need(type(body) is bytes and 0 < len(body) <= 262144, 'Bounded namespace capture frame')
    value = decode(body)
    need(type(value) is dict and set(value) == {'schema', 'capture_while_paused', 'payload',
         'file_before', 'file_after', 'name_after', 'directory_before', 'directory_after'}
         and value['schema'] == 'neural031_running_output_capture_v1'
         and value['capture_while_paused'] is False, 'Exact non-atomic running-capture schema')
    payload = value['payload']
    need(type(payload) is dict and set(payload) == {'bytes', 'sha256', 'base64'}
         and type(payload['bytes']) is int and 0 < payload['bytes'] <= 131072
         and type(payload['sha256']) is str and re.fullmatch('[0-9a-f]{64}', payload['sha256'])
         and type(payload['base64']) is str
         and len(payload['base64']) == 4 * ((payload['bytes'] + 2) // 3), 'Bounded exact payload descriptor')
    for key in ('file_before', 'file_after', 'name_after', 'directory_before', 'directory_after'):
        signature = value[key]
        need(type(signature) is list and len(signature) == 7
             and all(type(x) is int and 0 <= x < 2**64 for x in signature), 'Bounded metadata signature')
    before, directory = value['file_before'], value['directory_before']
    need(before == value['file_after'] == value['name_after']
         and stat.S_ISREG(before[2]) and before[3] == 1 and before[4] == payload['bytes']
         and directory == value['directory_after'] and stat.S_ISDIR(directory[2])
         and directory[3] >= 1, 'Stable ordinary file, directory and final name join')
    try:
        data = base64.b64decode(payload['base64'], validate=True)
    except (binascii.Error, ValueError, UnicodeError) as error:
        raise ValueError('Invalid capture base64') from error
    need(len(data) == payload['bytes'] and hashlib.sha256(data).hexdigest() == payload['sha256']
         and base64.b64encode(data).decode('ascii') == payload['base64'], 'Exact captured prediction bytes')
    return data


def group_absent(pgid):
    """Absence of this owned CLI group; permission errors remain unknown."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


class CommandJournal:
    """Exclusive private files; cumulative write grants include failed calls."""
    def __init__(self, root):
        self.root = Path(root)
        need(self.root.is_absolute() and self.root.parent.is_dir()
             and not self.root.exists() and not self.root.is_symlink(), 'Fresh absolute journal directory')
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.granted = self.written = self.calls = 0

    def begin(self, argv, cap, started, deadline):
        need(self.calls < COMMAND_CAP, 'Finite CLI command ceiling exhausted')
        grant = cap + 4096 + INTENT_CAP + RESULT_CAP
        need(self.granted + grant <= JOURNAL_CAP, 'Complete CLI evidence grant must fit before launch')
        self.granted += grant
        self.calls += 1
        label = f'command-{self.calls:03d}'
        value = {'schema': 'neural031_cli_intent_v1', 'sequence': self.calls,
                 'argv': argv, 'started_monotonic': started, 'deadline_monotonic': deadline,
                 'stdout_cap': cap, 'stderr_cap': 4096, 'journal_grant_bytes': grant}
        descriptor = self.put(label + '.intent.json', encoded(value), INTENT_CAP)
        return label, descriptor

    def put(self, name, body, cap):
        need(type(body) is bytes and len(body) <= cap and self.written + len(body) <= JOURNAL_CAP,
             'Bounded private command evidence')
        path = self.root / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        # Charge before a potentially partial write; never infer gross writes
        # from retained sizes or refund a failed/removed file.
        self.written += len(body)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body); stream.flush(); os.fchmod(stream.fileno(), 0o600); os.fsync(stream.fileno())
        return {'path': name, **pin(body)}

    def finish(self, label, intent, stdout, stderr, result):
        out = self.put(label + '.stdout', stdout, result['stdout_cap'])
        err = self.put(label + '.stderr', stderr, 4096)
        record = {**result, 'schema': 'neural031_cli_result_v1', 'intent': intent,
                  'stdout': out, 'stderr': err}
        receipt = self.put(label + '.result.json', encoded(record), RESULT_CAP)
        return {'event': 'command', 'sequence': self.calls,
                'intent': intent, 'result': receipt, 'stdout': out, 'stderr': err,
                'scope': result['scope'], 'simulated': result['scope'] != 'actual_owned_cli',
                'exit_code': result['returncode'],
                'error_type': result.get('error_type'),
                'process_group_absent': result['group_absent'],
                'direct_child_reaped': result['direct_child_reaped']}


class Deadline:
    def __init__(self, clock=time.monotonic, seconds=480):
        self.clock, self.start, self.seconds = clock, clock(), seconds
        self.end = self.start + seconds

    def left(self):
        left = self.end - self.clock()
        if left <= 0:
            raise TimeoutError('Original whole-batch480-second deadline exhausted')
        return left

    def elapsed(self):
        return self.clock() - self.start


def prediction_from_tar(body):
    need(type(body) is bytes and 0 < len(body) <= 262144, 'Bounded captured archive required')
    need(len(body) % 512 == 0, 'Whole tar blocks required')
    # Inspect the transport headers before tarfile can resolve GNU long names,
    # PAX path overrides or ignore trailing bytes. Only inert PAX timestamps
    # are supported, since normal Docker archives can retain subsecond times.
    offset = 0
    while offset < len(body):
        header = body[offset:offset + 512]
        if not any(header):
            need(len(body) - offset >= 1024 and not any(body[offset:]), 'Exact zero tar terminator; no trailing payload')
            break
        def octal(field):
            value = field.strip(b' \x00')
            need(value and all(c in b'01234567' for c in value), 'Plain bounded octal tar field')
            return int(value, 8)
        size = octal(header[124:136])
        checksum = octal(header[148:156])
        need(sum(header[:148]) + 8 * 32 + sum(header[156:]) == checksum, 'Tar header checksum')
        kind = header[156:157]
        need(kind in (b'0', b'\x00', b'5', b'x'), 'No GNU longname, links, special files or global PAX')
        start, end = offset + 512, offset + 512 + size
        padded = start + ((size + 511) // 512) * 512
        need(size <= 131072 and padded <= len(body) and not any(body[end:padded]), 'Bounded exact tar payload and padding')
        if kind == b'x':
            need(size <= 1024, 'Bounded PAX timestamp header')
            cursor, seen = start, set()
            while cursor < end:
                space = body.find(b' ', cursor, end)
                need(space > cursor and body[cursor:space].isdigit(), 'PAX length prefix')
                length = int(body[cursor:space])
                finish = cursor + length
                need(finish > space + 1 and finish <= end and body[finish-1:finish] == b'\n', 'PAX exact record extent')
                record = body[space+1:finish-1]
                key, separator, value = record.partition(b'=')
                need(separator and key in (b'mtime', b'atime', b'ctime') and key not in seen
                     and re.fullmatch(rb'-?[0-9]+(?:\.[0-9]+)?', value), 'Only inert unique PAX timestamp metadata')
                seen.add(key); cursor = finish
            need(cursor == end, 'Complete PAX record')
        offset = padded
    else:
        raise ValueError('Missing tar zero terminator')
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:') as archive:
        members = archive.getmembers()
        need(1 <= len(members) <= 2, 'Only output root and one prediction allowed')
        prediction = None
        seen = set()
        for member in members:
            need(member.name not in seen and set(member.pax_headers) <= {'mtime', 'atime', 'ctime'}
                 and not member.linkname, 'No duplicate, path-changing PAX or linked output members')
            seen.add(member.name)
            if member.name in ('.', './') and member.isdir():
                need(member.size == 0, 'Empty output root descriptor')
                continue
            need(member.name in ('predictions.json', './predictions.json') and member.isfile()
                 and not member.issparse() and 0 < member.size <= 131072 and prediction is None,
                 'Exactly one ordinary bounded prediction file; no other path/type')
            prediction = archive.extractfile(member).read(131073)
            need(len(prediction) == member.size, 'Captured prediction extent changed')
        need(prediction is not None, 'Complete prediction required')
    return prediction


class DockerBackend:
    def __init__(self, *, command=None, docker_binary=None,
                 socket='/var/run/docker.sock', journal_root=None, docker_config=None):
        if docker_binary is None:
            docker_binary = shutil.which('docker') if command is None else '/docker-not-executed'
        need(type(docker_binary) is str and Path(docker_binary).is_absolute() and Path(socket).is_absolute()
             and ',' not in socket, 'Explicit local Docker executable and Unix socket')
        need((journal_root is None) == (docker_config is None), 'Journal and empty Docker configuration selected together')
        need(command is not None or journal_root is not None, 'Production requires a private persistent command journal')
        self.journal = CommandJournal(journal_root) if journal_root is not None else None
        self.config = Path(docker_config) if docker_config is not None else None
        self.prefix = [docker_binary, '--host', 'unix://' + socket]
        if self.config is not None:
            need(self.config.is_absolute() and self.config.parent.is_dir()
                 and not self.config.exists() and not self.config.is_symlink(), 'Fresh owned Docker configuration')
            self.config.mkdir(mode=0o700); self.config.chmod(0o700)
            self.prefix += ['--config', str(self.config)]
        self.transport = command
        self.real_transport = command is None
        self.names, self.events = [], []
        self.image_environment = {}
        self.command_count = 0
        self._failure_recovery = None
        self._in_recovery = False
        self._journal_failed = False
        self._unknown_cli_closure = False

    def recovery_deadline(self, deadline):
        if self._failure_recovery is None:
            # One shared failure allowance, including CLI cleanup. It cannot
            # extend the original480-second deadline by more than10 seconds.
            self._failure_recovery = Deadline(clock=deadline.clock, seconds=10)
            self._failure_recovery.end = min(self._failure_recovery.end, deadline.end + 10)
        return self._failure_recovery

    def _process_command(self, argv, deadline, cap):
        started = deadline.clock()
        output = {'stdout': bytearray(), 'stderr': bytearray()}
        observed = {'stdout': 0, 'stderr': 0}
        proc = streams = None
        code = None
        error = None
        cleanup = []
        absent = False
        env = {'PATH': '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
        try:
            # Everything following Popen is inside this cleanup scope, including
            # selector construction and descriptor registration failures.
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env, start_new_session=True)
            streams = selectors.DefaultSelector()
            for stream, name in ((proc.stdout, 'stdout'), (proc.stderr, 'stderr')):
                os.set_blocking(stream.fileno(), False)
                streams.register(stream, selectors.EVENT_READ, name)
            while streams.get_map():
                for key, _ in streams.select(min(0.1, deadline.left())):
                    limit = cap if key.data == 'stdout' else 4096
                    chunk = os.read(key.fileobj.fileno(), min(65536, limit - len(output[key.data]) + 1))
                    if not chunk:
                        streams.unregister(key.fileobj); continue
                    observed[key.data] += len(chunk)
                    remaining = limit - len(output[key.data])
                    output[key.data].extend(chunk[:remaining])
                    need(len(chunk) <= remaining, 'Docker command output cap exceeded')
            code = proc.wait(timeout=deadline.left())
            need(code == 0, 'Docker command failed: ' + bytes(output['stderr']).decode('utf8', 'replace')[:512])
            absent = group_absent(proc.pid)
            need(absent, 'Owned CLI group survived its direct child')
        except BaseException as caught:
            error = caught
        finally:
            if proc is not None and (error is not None or not absent):
                recovery = self.recovery_deadline(deadline)
                cleanup_end = min(recovery.end, deadline.clock() + 1)
                try:
                    if not group_absent(proc.pid):
                        os.killpg(proc.pid, signal.SIGKILL)
                        cleanup.append('SIGKILL_owned_group')
                except ProcessLookupError:
                    pass
                except BaseException as caught:
                    cleanup.append('signal_error:' + type(caught).__name__)
                try:
                    if proc.poll() is None:
                        proc.wait(timeout=max(0.001, cleanup_end - deadline.clock()))
                    code = proc.returncode
                except BaseException as caught:
                    cleanup.append('reap_error:' + type(caught).__name__)
                try:
                    absent = group_absent(proc.pid)
                    while not absent and deadline.clock() < cleanup_end:
                        time.sleep(min(0.01, max(0, cleanup_end - deadline.clock())))
                        absent = group_absent(proc.pid)
                except BaseException as caught:
                    cleanup.append('absence_error:' + type(caught).__name__)
                    absent = False
            close_errors = []
            for resource in ([streams] if streams is not None else []) + ([proc.stdout, proc.stderr] if proc is not None else []):
                try:
                    resource.close()
                except BaseException as caught:
                    close_errors.append(type(caught).__name__)
            if close_errors and error is None:
                error = RuntimeError('Owned command stream closure failed')
        reaped = proc is not None and proc.poll() is not None
        if proc is not None and not (reaped and absent):
            self._unknown_cli_closure = True
            error = error or RuntimeError('Owned CLI closure is unknown')
        result = {'scope': 'actual_owned_cli', 'argv_sha256': hashlib.sha256(encoded(argv)).hexdigest(),
                  'started_monotonic': started, 'completed_monotonic': deadline.clock(),
                  'deadline_monotonic': deadline.end, 'pid': proc.pid if proc is not None else None,
                  'process_started': proc is not None, 'returncode': code, 'direct_child_reaped': reaped,
                  'group_absent': absent if proc is not None else None,
                  'cleanup': cleanup, 'stream_close_errors': close_errors,
                  'stdout_cap': cap, 'observed_bytes': observed,
                  'error_type': type(error).__name__ if error else None,
                  'error': str(error)[:512] if error else None,
                  'absence_scope': 'Owned start_new_session CLI group; not arbitrary processes outside that group'}
        return bytes(output['stdout']), bytes(output['stderr']), result, error

    def _command(self, args, deadline, cap=65536):
        need(self._in_recovery or (not self._unknown_cli_closure and not self._journal_failed),
             'Unknown CLI closure or incomplete evidence permits owned failure cleanup only')
        deadline.left()
        need(type(cap) is int and 0 < cap <= 262144, 'Bounded selected CLI capture')
        need(self.command_count < COMMAND_CAP, 'Finite CLI command count exhausted')
        self.command_count += 1
        argv = self.prefix + args
        if self.config is not None:
            need(self.config.is_dir() and not self.config.is_symlink() and not any(self.config.iterdir()),
                 'Selected Docker configuration remains empty')
        started = deadline.clock()
        label = intent = None
        journal_error = None
        if self.journal is not None:
            try:
                label, intent = self.journal.begin(argv, cap, started, deadline.end)
            except BaseException as caught:
                self._journal_failed = True
                journal_error = caught
                if not self._in_recovery:
                    raise
                # Evidence failure must not suppress a bounded owned-container
                # cleanup. It can never regain normal execution or grading.
                self.events.append({'event': 'recovery_intent_unpersisted', 'sequence': self.command_count,
                                    'error_type': type(caught).__name__})
        if self.transport is not None:
            body = self.transport(argv, deadline, cap)
            need(type(body) is bytes and len(body) <= cap, 'Bounded simulated command bytes')
            deadline.left()
            stderr = b''
            result = {'scope': 'generated_command_simulation', 'stdout_cap': cap,
                      'returncode': 0, 'group_absent': None, 'direct_child_reaped': None,
                      'started_monotonic': started, 'completed_monotonic': deadline.clock()}
            error = None
        else:
            body, stderr, result, error = self._process_command(argv, deadline, cap)
        if self.journal is not None and label is not None:
            try:
                self.events.append(self.journal.finish(label, intent, body, stderr, result))
            except BaseException as caught:
                self._journal_failed = True
                journal_error = caught
                self.events.append({'event': 'command_evidence_incomplete', 'sequence': self.command_count,
                                    'error_type': type(caught).__name__, 'group_absent': result['group_absent']})
        if error is not None:
            raise error
        if journal_error is not None and not self._in_recovery:
            raise journal_error
        return body

    @property
    def journal_records(self):
        return tuple(decode(encoded(row)) for row in self.events if row['event'] == 'command')

    def journal_summary(self):
        records = self.journal_records
        return {'schema': 'neural031_cli_journal_summary_v1',
                'root': str(self.journal.root) if self.journal else None,
                'command_count': self.command_count, 'record_count': len(records),
                'normal_complete_batch_commands': 441, 'command_ceiling': COMMAND_CAP,
                'cumulative_granted_bytes': self.journal.granted if self.journal else 0,
                'cumulative_write_charge_bytes': self.journal.written if self.journal else 0,
                'journal_cap_bytes': JOURNAL_CAP, 'evidence_complete': not self._journal_failed,
                'actual_cli_closure_complete': bool(records) and len(records) == self.command_count
                    and not self._unknown_cli_closure and not self._journal_failed
                    and all(not r['simulated'] and r['exit_code'] == 0
                            and r['error_type'] is None
                            and r['process_group_absent'] is True and r['direct_child_reaped'] is True
                            for r in records),
                'host_process_scope': 'Owned CLI process groups only; no universal hostile-host containment claim'}

    def verify_image(self, image, deadline):
        need(type(image) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'Immutable local image ID required')
        values = decode(self._command(['image', 'inspect', image], deadline))
        need(type(values) is list and len(values) == 1 and values[0]['Id'] == image
             and values[0]['Os'] == 'linux', 'Exact existing Linux image; no pull or tag lookup')
        config = values[0]['Config']
        need(not config.get('Volumes'), 'Image must not declare anonymous writable volumes')
        allowed = {'PATH', 'LANG', 'LC_ALL', 'PYTHON_VERSION', 'PYTHON_SHA256', 'GPG_KEY'}
        environment = config.get('Env') or []
        need(type(environment) is list and all(type(v) is str and '=' in v for v in environment),
             'Well-formed inherited image environment')
        values_by_key = dict(v.split('=', 1) for v in environment)
        need(len(values_by_key) == len(environment), 'Unique image environment keys')
        if image == SELECTED_IMAGE:
            need(values[0].get('Architecture') == 'arm64' and values_by_key == SELECTED_IMAGE_ENV,
                 'Exact reviewed385 image configuration; three original thread variables overridden to1')
        else:
            need(set(values_by_key) <= allowed, 'Unreviewed inherited image environment')
        self.image_environment[image] = values_by_key
        self.events.append({'event': 'image_inspected', 'image_id': image,
                            'inherited_environment': environment,
                            'image_content_inventory_independently_qualified': False})
        return values[0]

    def create_argv(self, spec):
        need(re.fullmatch(r'n031-[0-9a-f]{24}-[0-9]{2}-[bn]', spec['name']), 'Owned unique context name')
        need(len(spec['mounts']) == 3 and [m[1] for m in spec['mounts']] ==
             ['/input/data.npz', '/input/manifest.json', '/program/submission.py'], 'Exact three file mounts')
        argv = ['create', '--name', spec['name'], '--pull', 'never', '--network', 'none',
                '--ipc', 'none', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges:true', '--memory', str(MEMORY),
                '--memory-swap', str(MEMORY), '--cpus', '1.75', '--pids-limit', str(PIDS),
                '--restart', 'no', '--log-driver', 'none', '--workdir', '/tmp',
                '--label', 'neural031.batch=' + spec['batch']]
        for key, options in TMPFS.items(): argv += ['--tmpfs', key + ':' + options]
        for value in ENV: argv += ['--env', value]
        for source, destination in spec['mounts']:
            need(Path(source).is_absolute() and ',' not in source and '\n' not in source,
                 'Unambiguous absolute file bind path')
            argv += ['--mount', f'type=bind,src={source},dst={destination},readonly']
        return argv + ['--entrypoint', KEEPER[0], spec['image'], *KEEPER[1:]]

    def inspect_context(self, spec, deadline, *, paused):
        rows = decode(self._command(['container', 'inspect', spec['name']], deadline))
        need(type(rows) is list and len(rows) == 1, 'Exactly one context inspected')
        row, expected = rows[0], {dest: src for src, dest in spec['mounts']}
        host, config, state = row['HostConfig'], row['Config'], row['State']
        env = config.get('Env')
        need(type(env) is list and all(type(v) is str and '=' in v for v in env), 'Exact inspected environment')
        env_by_key = dict(v.split('=', 1) for v in env)
        need(len(env_by_key) == len(env) and spec['image'] in self.image_environment
             and env_by_key == {**self.image_environment[spec['image']], **dict(v.split('=', 1) for v in ENV)},
             'Inspected environment must equal verified image variables plus fixed overrides')
        need(row['Image'] == spec['image'] and row['Name'] == '/' + spec['name']
             and state['Running'] is True and state['Paused'] is paused,
             'Exact live context and pause state')
        need(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True
             and host['Memory'] == MEMORY and host['MemorySwap'] == MEMORY
             and host['NanoCpus'] == NANO_CPUS and host['PidsLimit'] == PIDS
             and host['IpcMode'] == 'none' and host['PidMode'] == ''
             and host['Privileged'] is False and not host.get('Devices')
             and not host.get('DeviceRequests') and not host.get('CapAdd')
             and host.get('CapDrop') == ['ALL'] and host.get('Tmpfs') == TMPFS
             and host['LogConfig']['Type'] == 'none'
             and host['RestartPolicy']['Name'] == 'no'
             and set(host.get('SecurityOpt') or []) == {'no-new-privileges:true'},
             'Actual isolation/resource settings differ from fixed policy')
        need(config['User'] == '65534:65534' and config['WorkingDir'] == '/tmp'
             and config['Entrypoint'] == [KEEPER[0]] and config['Cmd'] == KEEPER[1:]
             and (config.get('Labels') or {}).get('neural031.batch') == spec['batch']
             and not config.get('Volumes') and all(v in config.get('Env', []) for v in ENV),
             'Actual user, keeper, environment and writable-volume policy')
        bind = [m for m in row['Mounts'] if m['Type'] == 'bind']
        others = [m for m in row['Mounts'] if m['Type'] != 'bind']
        need(len(bind) == 3 and {m['Destination']: m['Source'] for m in bind} == expected
             and all(m['RW'] is False for m in bind)
             and all(m['Type'] == 'tmpfs' and m['Destination'] in TMPFS for m in others)
             and len({m['Destination'] for m in row['Mounts']}) == len(row['Mounts']),
             'Only exact context input/program read-only binds and bounded tmpfs mounts')
        self.events.append({'event': 'context_inspected', 'name': spec['name'], 'paused': paused})

    def absent(self, name, deadline):
        result = self._command(['ps', '--all', '--no-trunc', '--filter', 'name=^/' + name + '$',
                                '--format', '{{.ID}}'], deadline, 4096)
        need(not result.strip(), 'Owned producer still exists; cannot advance or score')
        self.events.append({'event': 'context_absence_observed', 'name': name})

    def run_context(self, spec, deadline):
        need(spec['name'] not in self.names, 'Never reuse a context identity')
        self.names.append(spec['name'])  # Register before create, including failed creates.
        creation_attempted = False
        try:
            self.absent(spec['name'], deadline)
            creation_attempted = True
            self._command(self.create_argv(spec), deadline, 4096)
            self._command(['start', spec['name']], deadline, 4096)
            self.inspect_context(spec, deadline, paused=False)
            self._command(['exec', '--user', '65534:65534', spec['name'], *CANDIDATE], deadline, 16384)
            # Docker cp cannot read tmpfs. Capture exact bytes in the running
            # namespace, then require inspected pause/removal/absence before
            # returning them. This is not an atomic paused-filesystem snapshot.
            body = prediction_from_frame(self._command(
                ['exec', '--user', '65534:65534', spec['name'], *CAPTURE], deadline, 262144))
            self.events.append({'event': 'output_captured_running', 'name': spec['name'],
                                'prediction': pin(body), 'atomic_paused_snapshot': False})
            self._command(['pause', spec['name']], deadline, 4096)
            self.inspect_context(spec, deadline, paused=True)
            self._command(['rm', '--force', spec['name']], deadline, 4096)
            self.absent(spec['name'], deadline)
            return body
        except BaseException:
            # Failure cleanup is never credited as an on-time successful batch.
            # If the original clock expires, bounded recovery is reported
            # separately; no next context or protected scoring follows.
            recovery = self.recovery_deadline(deadline)
            self._in_recovery = True
            try:
                need(creation_attempted, 'Initial name collision is not an owned resource')
                present = self._command(['ps', '--all', '--no-trunc', '--filter',
                    'name=^/' + spec['name'] + '$', '--format', '{{.ID}}'], recovery, 4096)
                if present.strip():
                    rows = decode(self._command(['container', 'inspect', spec['name']], recovery))
                    need(type(rows) is list and len(rows) == 1
                         and rows[0]['Name'] == '/' + spec['name']
                         and (rows[0]['Config'].get('Labels') or {}).get('neural031.batch') == spec['batch'],
                         'Never remove a resource without the exact owned batch label')
                    self._command(['rm', '--force', spec['name']], recovery, 4096)
                self.absent(spec['name'], recovery)
                closed = not self._unknown_cli_closure
            except BaseException:
                closed = False
            finally:
                self._in_recovery = False
            self.events.append({'event': 'failure_cleanup', 'name': spec['name'],
                                'absence_verified': closed, 'recovery_seconds': recovery.elapsed(),
                                'batch_deadline_elapsed_seconds': deadline.elapsed(),
                                'journal_complete': not self._journal_failed,
                                'host_CLI_closure_unknown': self._unknown_cli_closure})
            raise

    def absent_all(self, deadline):
        need(not self._unknown_cli_closure and not self._journal_failed,
             'Unknown CLI closure or incomplete evidence prevents final collection and grading')
        for name in self.names:
            self.absent(name, deadline)
