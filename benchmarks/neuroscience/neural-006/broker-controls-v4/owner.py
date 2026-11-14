"""Public Linux N006 single-attempt Docker owner. No execution on import."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import stat
import struct
import sys
import time

IMAGE = 'sha256:de8d79606beff46114d4abd5c392116c62142cbe582f8ede92cf4a64e1a10ff5'
IMAGE_REFERENCE = 'python@sha256:6d10e720318bd84cc3d88af92bb5a47189222e17620a2fd214da6445e4afb679'
FIXED_PIN = {'bytes': 6584, 'sha256': '325dbe77866b1f58e028cfad1a24ec267aec6f7cc1b5b726c355713e70405457'}
SOURCE_CAP = 2 * 1048576
BINARY_CAP = 128 * 1048576
STREAM_CAP = 262144
WORK_STREAM_CAP = 196607
CLEANUP_STREAM_CAP = 65535
RETAIN_CAP = 1048576


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def json_one(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            need(key not in obj, 'duplicate JSON key')
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


class Owner:
    def __init__(self, start):
        self.start = start
        self.end = start + 60
        self.actor_end = start + 50
        self.read_bytes = 0
        self.binary_bytes = 0
        self.stream_bytes = 0
        self.phase_stream_bytes = {False: 0, True: 0}
        self.identity_verified = False
        self.start_requested = False
        self.retained = 0
        self.events = []
        self.errors = []
        self.directory = None
        self.cid = None
        self.nonce = secrets.token_hex(16)
        self.created_requested = False
        self.stopped = False
        self.removed = False
        self.absent = False
        self.forced_container_kill = False
        self.result = None
        self.docker = None
        self.name = None
        self.bootstrap = None

    def deadline(self, cleanup=False):
        deadline = self.end if cleanup else self.actor_end
        need(time.monotonic() < deadline, 'original whole-attempt deadline exhausted')
        return deadline

    def error(self, stage, exc):
        # Inputs are the fixed public source/control graph; never serialize environment/headers.
        self.errors.append({'stage': stage, 'type': type(exc).__name__, 'message': str(exc)[:4096]})

    def capture(self, path, row, binary=False):
        self.deadline()
        path = Path(path)
        limit = 64 * 1048576 if binary else 1048576
        need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
             'ordinary selected source/binary ancestry')
        need(type(row['bytes']) is int and 0 < row['bytes'] <= limit and
             re.fullmatch('[0-9a-f]{64}', row['sha256']), 'bounded exact identity')
        if binary:
            need(self.binary_bytes + row['bytes'] <= BINARY_CAP, 'separate binary admission cap')
            self.binary_bytes += row['bytes']
        else:
            need(self.read_bytes + row['bytes'] <= SOURCE_CAP, 'ordinary source admission cap')
            self.read_bytes += row['bytes']
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        body = []
        hasher = hashlib.sha256()
        left = row['bytes']
        total = 0
        try:
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                 before.st_size == row['bytes'], 'single-link exact selected extent')
            while left:
                self.deadline()
                chunk = os.read(fd, min(left, 65536))
                need(chunk, 'short selected body')
                total += len(chunk); left -= len(chunk); hasher.update(chunk)
                if not binary:
                    body.append(chunk)
            need(os.read(fd, 1) == b'', 'selected EOF')
            after = os.fstat(fd)
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            need(all(getattr(before, k) == getattr(after, k) for k in fields), 'stable selected descriptor')
            need(total == row['bytes'] and hasher.hexdigest() == row['sha256'], 'selected body hash')
        finally:
            os.close(fd)
        self.deadline()
        return b''.join(body)

    def write(self, name, body):
        self.deadline(cleanup=True)
        need(self.directory is not None and '/' not in name and len(body) <= 1048576,
             'bounded private evidence name/body')
        need(self.retained + len(body) <= RETAIN_CAP, 'whole retained-output cap')
        self.retained += len(body)
        fd = os.open(self.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            offset = 0
            while offset < len(body):
                self.deadline(cleanup=True)
                count = os.write(fd, memoryview(body)[offset:])
                need(0 < count <= len(body) - offset, 'complete evidence write')
                offset += count
            os.fsync(fd)
        finally:
            os.close(fd)
        self.deadline(cleanup=True)
        return dict(path=name, **pin(body))

    def command(self, argv, *, data=b'', cleanup=False, seconds=5, cap=65536):
        horizon = self.deadline(cleanup)
        deadline = min(horizon, time.monotonic() + seconds)
        phase_cap = CLEANUP_STREAM_CAP if cleanup else WORK_STREAM_CAP
        need(len(self.events) < 16 and len(data) <= 524288 and cap <= STREAM_CAP, 'finite CLI invocation')
        event = {'argv': argv, 'input': pin(data), 'returncode': None, 'forced_client_kill': False,
                 'cleanup_phase': cleanup, 'phase_stream_cap': phase_cap,
                 'eof': {'stdout': False, 'stderr': False}, 'errors': [], 'stream_files': {}}
        self.events.append(event); index = len(self.events)
        child = self.ChildOwner(self.guard)
        selector = None; fds = {}; chunks = {'stdout': [], 'stderr': []}; total = 0; offset = 0
        original = None; mask = None

        def failure(exc):
            nonlocal original
            if original is None: original = exc
            event['errors'].append({'type': type(exc).__name__, 'message': str(exc)[:2048]})

        def close(key):
            fd = fds.pop(key, None)  # Ambiguous closes are never retried.
            if fd is not None:
                try: os.close(fd)
                except BaseException as exc: failure(exc)

        try:
            self.guard()
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])
            signal.pthread_sigmask(signal.SIG_BLOCK, signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP})
            for standard in (0, 1, 2): os.fstat(standard)
            fds['input_read'], fds['input_write'] = os.pipe()
            fds['stdout_read'], fds['stdout_write'] = os.pipe()
            fds['stderr_read'], fds['stderr_write'] = os.pipe()
            self.deadline(cleanup); self.guard()
            pid = os.fork()
            if pid == 0:
                try:
                    os.setsid()
                    os.dup2(fds['input_read'], 0); os.dup2(fds['stdout_write'], 1); os.dup2(fds['stderr_write'], 2)
                    for fd in fds.values(): os.close(fd)
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    os.execve(self.docker[0], self.docker + argv, {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                except BaseException:
                    os._exit(127)
            child.adopt(pid)  # Signal-blocked adoption before any pending Python handler.
            event['client_pid'] = pid
            signal.pthread_sigmask(signal.SIG_SETMASK, mask); mask = None
            for key in ('input_read', 'stdout_write', 'stderr_write'): close(key)
            need(original is None, 'spawn descriptor closure')
            selector = selectors.DefaultSelector()
            for role in ('stdout', 'stderr'):
                fd = fds[role + '_read']; os.set_blocking(fd, False)
                selector.register(fd, selectors.EVENT_READ, role)
            os.set_blocking(fds['input_write'], False)
            if data: selector.register(fds['input_write'], selectors.EVENT_WRITE, 'stdin')
            else: close('input_write')
            while selector.get_map():
                need(time.monotonic() < deadline, 'owned CLI deadline')
                for key, _ in selector.select(min(.02, max(0, deadline - time.monotonic()))):
                    need(time.monotonic() < deadline, 'owned CLI deadline')
                    if key.data == 'stdin':
                        written = os.write(key.fd, data[offset:offset + 65536])
                        need(written > 0, 'CLI complete input transfer'); offset += written
                        if offset == len(data): selector.unregister(key.fd); close('input_write')
                    else:
                        available = min(cap - total, phase_cap - self.phase_stream_bytes[cleanup])
                        need(available >= 0, 'global stream charge')
                        part = os.read(key.fd, min(8192, available + 1))
                        if not part:
                            selector.unregister(key.fd); event['eof'][key.data] = True
                            continue
                        total += len(part); self.stream_bytes += len(part)
                        self.phase_stream_bytes[cleanup] += len(part); chunks[key.data].append(part)
                        need(total <= cap and self.phase_stream_bytes[cleanup] <= phase_cap and
                             self.stream_bytes <= STREAM_CAP, 'owned CLI stream cap crossed')
            while child.state == 'owned_unreaped':
                need(time.monotonic() < deadline, 'owned CLI wait deadline')
                if child.wait_once(): break
                time.sleep(min(.005, max(0, deadline - time.monotonic())))
            need(time.monotonic() < deadline and offset == len(data) and child.state == 'reaped',
                 'CLI original wait/input deadline')
        except BaseException as exc:
            failure(exc)
        finally:
            if child.pid is not None:
                try:
                    self.deadline(True)
                    child.stop_unreaped()  # Exact donor retires kill authority before any ambiguous/terminal wait.
                    while child.state == 'owned_unreaped':
                        self.deadline(True)
                        if child.wait_once(): break
                        time.sleep(.005)
                    need(child.state == 'reaped' and child.observe_absence(), 'original CLI reaped and group absent')
                except BaseException as exc: failure(exc)
                event['client_owner'] = child.evidence()
                event['forced_client_kill'] = child.stop_attempted
                event['returncode'] = child.returncode
            if selector is not None:
                try: selector.close()
                except BaseException as exc: failure(exc)
            for key in tuple(fds): close(key)
            if mask is not None:
                try: signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                except BaseException as exc: failure(exc)
            for role in ('stdout', 'stderr'):
                try: event['stream_files'][role] = self.write('CLI-%02d.%s' % (index, role), b''.join(chunks[role]))
                except BaseException as exc: failure(exc)
            event['seconds_from_original_start'] = time.monotonic() - self.start
        if original is not None: raise original
        return event['returncode'], b''.join(chunks['stdout']), b''.join(chunks['stderr'])

    def checked(self, argv, **kwargs):
        code, stdout, stderr = self.command(argv, **kwargs)
        need(code == 0 and not stderr, 'selected Docker command failed or emitted diagnostics')
        return stdout

    def inspect_identity(self, identifier, cleanup=False):
        raw = self.checked(['container', 'inspect', identifier], cleanup=cleanup, seconds=2 if cleanup else 5)
        rows = json_one(raw); need(type(rows) is list and len(rows) == 1, 'one exact container observation')
        obj = rows[0]; cfg = obj['Config']; host = obj['HostConfig']; state = obj['State']
        need(re.fullmatch('[0-9a-f]{64}', obj['Id']) and obj['Name'] == '/' + self.name and
             cfg['Labels'].get('org.neurobench.owner') == self.nonce and obj['Image'] == IMAGE,
             'owned immutable container identity')
        if self.cid is not None:
            need(obj['Id'] == self.cid, 'unchanged owned container ID')
        self.cid = obj['Id']
        self.identity_verified = True
        return obj

    def inspect_owned(self, identifier, cleanup=False):
        obj = self.inspect_identity(identifier, cleanup)
        cfg = obj['Config']; host = obj['HostConfig']
        need(host['NetworkMode'] == 'none' and host['PidMode'] == '' and
             host['CgroupnsMode'] == 'private' and host['IpcMode'] == 'none' and
             not host['Privileged'] and host['ReadonlyRootfs'] and not host.get('Binds') and
             not host.get('Devices') and not host.get('DeviceRequests') and
             all(m.get('Type') == 'tmpfs' and m.get('Destination') in ('/n006', '/tmp') and
                 not m.get('Source') for m in obj.get('Mounts', [])),
             'no host mounts/devices, network or shared PID/cgroup/IPC namespace')
        need(host['RestartPolicy']['Name'] == 'no' and host['AutoRemove'] is False and
             host.get('Init') is False and host['CapDrop'] == ['ALL'] and
             not host.get('CapAdd') and 'no-new-privileges:true' in host['SecurityOpt'],
             'unprivileged directly owned PID 1 without restart')
        need(host['LogConfig']['Type'] == 'none' and not host['LogConfig']['Config'],
             'no container log-driver persistence; attach streams retained by owner')
        need(host['Memory'] == 536870912 and host['MemorySwap'] == 536870912 and
             host['NanoCpus'] == 2000000000 and host['PidsLimit'] == 12 and
             host['Tmpfs'] == {'/n006': 'rw,nosuid,nodev,noexec,size=16m,mode=0700,uid=65534,gid=65534',
             '/tmp': 'rw,nosuid,nodev,noexec,size=8m,mode=1777'}, 'fixed finite resource/private-storage limits')
        need(cfg['User'] == '65534:65534' and cfg['WorkingDir'] == '/' and cfg['Entrypoint'] == ['/usr/local/bin/python3'] and
             cfg['Cmd'] == ['-I', '-S', '-B', '-c', self.bootstrap.decode()] and cfg['Tty'] is False and
             cfg['OpenStdin'] is True, 'fixed non-TTY PID 1 command')
        return obj

    def cleanup(self):
        if not self.created_requested:
            return
        if not self.identity_verified:
            try:
                # Cleanup identity is independent of a failing pre-start policy admission.
                self.inspect_identity(self.cid or self.name, cleanup=True)
            except BaseException as exc:
                self.error('cleanup_identity_unestablished', exc)
                return

        def kill_once():
            if self.forced_container_kill:
                return
            self.forced_container_kill = True
            try:
                self.checked(['container', 'kill', '--signal', 'KILL', self.cid], cleanup=True, seconds=2)
            except BaseException as exc:
                # An already-stopped race or CLI failure cannot suppress the following observation.
                self.error('owned_container_kill', exc)

        # Exact full ID+nonce+image were already authenticated. A failed read cannot
        # take away this kill authority; do not reacquire it from a name alone.
        if self.errors and self.start_requested:
            kill_once()
        try:
            obj = self.inspect_identity(self.cid, cleanup=True)
        except BaseException as exc:
            self.error('owned_container_exit_observation', exc)
            if not self.start_requested:
                return  # No running harness; unknown state remains incomplete.
            kill_once()
            try:
                # A distinct observation after the owned kill, never a new attempt.
                obj = self.inspect_identity(self.cid, cleanup=True)
            except BaseException as postkill:
                self.error('owned_container_postkill_after_observation_failure', postkill)
                return  # No unobserved-exit removal or success claim.
        if obj['State']['Running']:
            kill_once()
            try:
                obj = self.inspect_identity(self.cid, cleanup=True)
            except BaseException as exc:
                self.error('owned_container_postkill_observation', exc)
                return
        try:
            state = obj['State']
            need(state['Running'] is False and state['Pid'] == 0 and state['Status'] in ('exited', 'created', 'dead'),
                 'owned container namespace exit observed')
            self.stopped = True
            removed = self.checked(['container', 'rm', self.cid], cleanup=True, seconds=2)
            need(removed.strip().decode() == self.cid, 'exact owned container removal')
            self.removed = True
            left = self.checked(['container', 'ls', '--all', '--no-trunc', '--filter', 'id=' + self.cid,
                                 '--format', '{{.ID}}'], cleanup=True, seconds=2)
            need(left == b'', 'owned container absence observed')
            self.absent = True
        except BaseException as exc:
            self.error('owned_container_closure', exc)

    def run(self, config, config_pin):
        need(set(config) == {'schema', 'docker', 'host_python', 'endpoint', 'output_directory', 'container_name', 'owner_selection'},
             'closed concrete operator configuration')
        need(config['schema'] == 'n006_public57_operator_v1', 'exact operator schema')
        self.name = config['container_name']
        need(type(self.name) is str and re.fullmatch('n006-57-[a-z0-9-]{8,48}', self.name), 'fresh scoped container name')
        out = Path(config['output_directory'])
        need(out.is_absolute() and not out.exists() and not any(p.is_symlink() for p in out.parents), 'fresh private output directory')
        out.mkdir(mode=0o700); self.directory = out
        selected = config['owner_selection']
        selection_raw = self.capture(selected['path'], selected)
        selection = json_one(selection_raw)
        need(selection['schema'] == 'n006_public57_owner_sources_v1' and len(selection['files']) == 4,
             'fixed complete owner source selection')
        files = {}
        for row in selection['files']:
            body = self.capture(row['path'], row)
            name = Path(row['path']).name
            need(name not in files, 'unique owner source filename')
            files[name] = body
        need(set(files) == {'owner.py', 'bootstrap.py', 'FIXED_SOURCES.json', 'cli_ownership.py'} and
             files['owner.py'] == self.capture(str(Path(__file__).absolute()),
                 next(r for r in selection['files'] if Path(r['path']).name == 'owner.py')),
             'exact executing owner selection')
        need(pin(files['FIXED_SOURCES.json']) == FIXED_PIN, 'fixed original control/source identities')
        fixed = json_one(files['FIXED_SOURCES.json']); self.bootstrap = files['bootstrap.py']
        self.fixed = fixed
        body_files = []
        source_root=Path(__file__).absolute().parent
        for row in fixed['files']:
            relative=Path(row['path'])
            need(not relative.is_absolute() and '..' not in relative.parts and relative.as_posix()==row['path'],
                 'exact canonical public source path')
            body_files.append({'path': row['path'], 'body_base64': base64.b64encode(self.capture(source_root/relative,row)).decode()})
        bundle = encoded({'fixed_source_base64': base64.b64encode(files['FIXED_SOURCES.json']).decode(), 'files': body_files})
        need(len(bundle) <= 524284, 'bounded exact stdin bundle')
        bundle = struct.pack('!I', len(bundle)) + bundle
        need(Path(sys.executable).resolve() == Path(config['host_python']['path']), 'actual selected Linux owner interpreter')
        self.capture(config['host_python']['path'], config['host_python'], binary=True)
        namespace = {'__name__': 'authenticated_n006_cli_ownership'}
        exec(compile(files['cli_ownership.py'], '<authenticated_cli_ownership>', 'exec', dont_inherit=True), namespace)
        self.ChildOwner = namespace['ChildOwner']
        self.guard, self.handlers = namespace['exclusive_admission']()
        need(signal.getsignal(signal.SIGINT) is signal.default_int_handler,
             'selected caught SIGINT cancellation route; inherited ignored/default SIGINT refused')
        self.capture(config['docker']['path'], config['docker'], binary=True)
        endpoint = config['endpoint']
        need(endpoint == 'unix:///var/run/docker.sock', 'fixed local Linux Docker endpoint only')
        docker_config = out / 'empty-docker-config'; docker_config.mkdir(mode=0o700)
        self.docker = [config['docker']['path'], '--host', endpoint, '--config', str(docker_config)]
        self.write('ATTEMPT.json', encoded({'schema': 'n006_enclosed57_attempt_v1', 'config': config_pin,
            'source_selection': selected, 'image': IMAGE, 'image_reference': IMAGE_REFERENCE, 'name': self.name, 'owner_nonce': self.nonce,
            'original_start': self.start, 'actor_end': self.actor_end, 'whole_end': self.end,
            'original_seconds': 60, 'maximum_inert_python_children': 11, 'maximum_attempts': 1,
            'source_bytes_cap': SOURCE_CAP, 'binary_bytes_cap': BINARY_CAP,
            'stream_bytes_cap': STREAM_CAP, 'work_stream_bytes_cap': WORK_STREAM_CAP,
            'cleanup_stream_bytes_cap': CLEANUP_STREAM_CAP, 'one_overflow_sentinel_per_phase': True,
            'retained_bytes_cap': RETAIN_CAP,
            'provider_network_model_scientific_calls_permitted': False, 'host_mounts_permitted': False,
            'docker_allowed_only_in_enclosing_owner': True, 'bundle': pin(bundle)}))
        image = json_one(self.checked(['image', 'inspect', IMAGE_REFERENCE]))
        need(type(image) is list and len(image) == 1 and image[0]['Id'] == IMAGE and
             image[0]['Os'] == 'linux' and image[0]['Architecture'] == 'amd64' and
             not image[0]['Config'].get('Volumes'), 'existing exact Linux amd64 image without volumes; no pull')
        self.created_requested = True
        raw = self.checked(['container', 'create', '--pull', 'never', '--name', self.name,
            '--label', 'org.neurobench.owner=' + self.nonce, '--network', 'none', '--cgroupns', 'private',
            '--ipc', 'none', '--init=false', '--log-driver', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--read-only', '--user', '65534:65534', '--cpus', '2', '--memory', '512m',
            '--memory-swap', '512m', '--pids-limit', '12', '--restart', 'no', '--stop-timeout', '1',
            '--tmpfs', '/n006:rw,nosuid,nodev,noexec,size=16m,mode=0700,uid=65534,gid=65534',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777',
            '--workdir', '/', '--entrypoint', '/usr/local/bin/python3', '--interactive', IMAGE_REFERENCE,
            '-I', '-S', '-B', '-c', self.bootstrap.decode()])
        cid = raw.strip().decode(); need(re.fullmatch('[0-9a-f]{64}', cid), 'complete created container ID')
        self.cid = cid
        self.inspect_owned(cid)
        self.start_requested = True
        code, stdout, stderr = self.command(['container', 'start', '--attach', '--interactive', cid],
             data=bundle, seconds=max(.001, self.actor_end - time.monotonic()), cap=196608)
        need(code == 0, 'harness attached client natural exit zero')
        result = json_one(stdout)
        need(set(result) == {'schema', 'tests_run', 'failures', 'errors', 'all_passed', 'model_calls',
             'provider_network_calls', 'scientific_runs', 'actual_model_qualification'}, 'one exact control result')
        need(result['schema'] == 'n006-inert-engineering-controls-v1' and
             type(result['tests_run']) is int and result['tests_run'] == 57 and result['all_passed'] is True and
             result['actual_model_qualification'] is False and all(type(result[k]) is int and result[k] == 0
             for k in ('failures', 'errors', 'model_calls', 'provider_network_calls', 'scientific_runs')),
             'all exact 57 inert controls passed')
        lines = stderr.decode('utf-8').splitlines()
        runtime_lines=[line[len('N006_RUNTIME '):] for line in lines if line.startswith('N006_RUNTIME ')]
        need(len(runtime_lines)==1,'one actual immutable-image runtime observation')
        runtime=json_one(runtime_lines[0])
        need(runtime['schema']=='n006-public-linux-runtime-v1' and runtime['platform']=='linux'
             and runtime['machine']=='x86_64' and runtime['python_version']==[3,11,18]
             and runtime['pid']==1 and runtime['uid']==runtime['gid']==65534
             and 0<runtime['interpreter']['bytes']<=1048576
             and re.fullmatch('[0-9a-f]{64}',runtime['interpreter']['sha256']),
             'actual selected Linux image runtime; no reused arm64 binary identity')
        self.runtime=runtime
        for name in fixed['test_names']:
            need(sum(line.startswith(name + ' (') and line.endswith(' ... ok') for line in lines) == 1,
                 'complete named unittest outcomes')
        obj = self.inspect_owned(cid)
        state = obj['State']
        need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0 and
             state['ExitCode'] == 0 and state['OOMKilled'] is False and not state['Error'],
             'authentic container natural exit zero without OOM')
        self.result = result

    def finish(self):
        self.cleanup()
        success = (not self.errors and self.result is not None and self.stopped and self.removed and
                   self.absent and not self.forced_container_kill and all(not e['forced_client_kill'] for e in self.events))
        receipt = {'schema': 'n006_enclosed57_outer_result_v1', 'success_before_final_transport': success,
            'original_start': self.start, 'original_end': self.end, 'elapsed_before_publication': time.monotonic() - self.start,
            'maximum_attempts': 1, 'automatic_retry': False, 'container_id': self.cid,
            'container_stopped_observed': self.stopped, 'container_removed_observed': self.removed,
            'container_absent_observed': self.absent, 'forced_container_kill': self.forced_container_kill,
            'events': self.events, 'errors': self.errors, 'control_result': self.result,
            'container_runtime':getattr(self,'runtime',None), 'image_reference':IMAGE_REFERENCE, 'image_config':IMAGE,
            'source_read_bytes': self.read_bytes, 'binary_read_bytes': self.binary_bytes,
            'observed_stream_bytes': self.stream_bytes,
            'work_stream_bytes': self.phase_stream_bytes[False],
            'cleanup_stream_bytes': self.phase_stream_bytes[True], 'retained_bytes_before_result': self.retained,
            'native_or_scientific_or_actual_model_qualification': False,
            'child_count_status': 'eleven allowed by exact source; no independent cumulative process-start count claimed',
            'cleanup_basis': 'private container PID namespace init exit plus exact-ID stopped/removal/absence observations',
            'physical_IO_and_full_RSS_measured': False,
            'cancellation': 'SIGINT is caught; abrupt SIGTERM/SIGKILL owner loss cannot promise automatic closure',
            'requires_final_owner_natural_exit_zero_after_final_deadline_check': True}
        row = self.write('RESULT.json', encoded(receipt))
        self.deadline(True)
        print(json.dumps({'success': success, 'result': row, 'elapsed_seconds': time.monotonic() - self.start}), flush=True)
        self.deadline(True)
        return 0 if success else 1


def main():
    owner = Owner(time.monotonic())
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize, 'isolated -I -S -B owner')
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True); parser.add_argument('--config-bytes', required=True, type=int)
    parser.add_argument('--config-sha256', required=True); args = parser.parse_args()
    try:
        row = {'path': args.config, 'bytes': args.config_bytes, 'sha256': args.config_sha256}
        raw = owner.capture(args.config, row)
        owner.run(json_one(raw), row)
    except BaseException as exc:
        owner.error('original_attempt', exc)
    try:
        return owner.finish()
    except BaseException as exc:
        owner.error('final_retention_or_deadline', exc)
        # Complete evidence/closure is unavailable. Never print a successful fallback.
        print(json.dumps({'success': False, 'evidence_incomplete': True, 'container_id': owner.cid,
                          'errors': owner.errors[-4:]}), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
