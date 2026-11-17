"""Bounded local-Docker transport. No host execution fallback or image pulls.

The kept-alive container is paused before tmpfs capture, then removed and proved
absent before another context. Actual runtime qualification is a separate step.
"""
import io
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tarfile
import time

from common import decode, need

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
                 socket='/var/run/docker.sock'):
        if docker_binary is None:
            docker_binary = shutil.which('docker') if command is None else '/docker-not-executed'
        need(type(docker_binary) is str and Path(docker_binary).is_absolute() and Path(socket).is_absolute()
             and ',' not in socket, 'Explicit local Docker executable and Unix socket')
        self.prefix = [docker_binary, '--host', 'unix://' + socket]
        self.transport = command
        self.real_transport = command is None
        self.names, self.events = [], []
        self.image_environment = {}

    def _command(self, args, deadline, cap=65536):
        deadline.left()
        argv = self.prefix + args
        if self.transport is not None:
            result = self.transport(argv, deadline, cap)
            need(type(result) is bytes and len(result) <= cap, 'Bounded simulated command bytes')
            deadline.left()
            return result
        env = {'PATH': '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin',
               'LANG': 'C', 'LC_ALL': 'C', 'DOCKER_CONFIG': '/dev/null'}
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, start_new_session=True)
        streams, output = selectors.DefaultSelector(), {'stdout': bytearray(), 'stderr': bytearray()}
        for stream, name in ((proc.stdout, 'stdout'), (proc.stderr, 'stderr')):
            os.set_blocking(stream.fileno(), False); streams.register(stream, selectors.EVENT_READ, name)
        try:
            while streams.get_map():
                for key, _ in streams.select(min(0.1, deadline.left())):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        streams.unregister(key.fileobj); continue
                    limit = cap if key.data == 'stdout' else 4096
                    need(len(output[key.data]) + len(chunk) <= limit, 'Docker command output cap exceeded')
                    output[key.data].extend(chunk)
            code = proc.wait(timeout=deadline.left())
            need(code == 0, 'Docker command failed: ' + bytes(output['stderr']).decode('utf8', 'replace')[:1024])
            return bytes(output['stdout'])
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                try: proc.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
            streams.close(); proc.stdout.close(); proc.stderr.close()

    def verify_image(self, image, deadline):
        need(type(image) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'Immutable local image ID required')
        values = decode(self._command(['image', 'inspect', image], deadline))
        need(type(values) is list and len(values) == 1 and values[0]['Id'] == image
             and values[0]['Os'] == 'linux', 'Exact existing Linux image; no pull or tag lookup')
        config = values[0]['Config']
        need(not config.get('Volumes'), 'Image must not declare anonymous writable volumes')
        allowed = {'PATH', 'LANG', 'LC_ALL', 'PYTHON_VERSION', 'PYTHON_SHA256', 'GPG_KEY'}
        environment = config.get('Env') or []
        need(type(environment) is list and all(type(v) is str and '=' in v
             and v.split('=', 1)[0] in allowed for v in environment), 'Unreviewed inherited image environment')
        values_by_key = dict(v.split('=', 1) for v in environment)
        need(len(values_by_key) == len(environment), 'Unique image environment keys')
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
            self._command(['pause', spec['name']], deadline, 4096)
            self.inspect_context(spec, deadline, paused=True)
            body = prediction_from_tar(self._command(['cp', spec['name'] + ':/output/.', '-'], deadline, 262144))
            self._command(['rm', '--force', spec['name']], deadline, 4096)
            self.absent(spec['name'], deadline)
            return body
        except BaseException:
            # Failure cleanup is never credited as an on-time successful batch.
            # If the original clock expires, bounded recovery is reported
            # separately; no next context or protected scoring follows.
            recovery = Deadline(clock=deadline.clock, seconds=10)
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
                closed = True
            except BaseException:
                closed = False
            self.events.append({'event': 'failure_cleanup', 'name': spec['name'],
                                'absence_verified': closed, 'recovery_seconds': recovery.elapsed(),
                                'batch_deadline_elapsed_seconds': deadline.elapsed()})
            raise

    def absent_all(self, deadline):
        for name in self.names:
            self.absent(name, deadline)
