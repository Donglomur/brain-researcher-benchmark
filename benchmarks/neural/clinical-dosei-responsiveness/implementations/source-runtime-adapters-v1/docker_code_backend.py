"""Fresh-container code assistance; source implementation, not qualification.

Only trusted host code constructs this object. No path, daemon, runtime choice,
mount or evidence sink comes from participant frames. Each Python tool call
has fresh scratch space and sees the same single immutable observation.
"""
import hashlib
import os
import re
import shutil
import stat
import tempfile
import time

TOOL = {'name': 'python', 'input_format': 'utf8_text',
        'description': 'Run Python 3.12.8 with NumPy 2.2.6 in a fresh network-disabled container. Read the exact case JSON at /input/observation.json. Print results. Each call has new /tmp and /work; files do not persist between calls.'}


class CodeBackendFailure(RuntimeError):
    def __init__(self, category):
        self.category = category
        super().__init__(category)


def require(ok, category):
    if not ok: raise CodeBackendFailure(category)


def file_identity(path):
    value = os.lstat(path)
    require(stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and value.st_uid == os.getuid(),
            'case_file_identity')
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode)


class DockerCodeBackend:
    """Owned one-case backend for the accepted ParticipantInterface.

    The caller authenticates source/profile and provides a bounded durable
    recorder and trusted renderer. The selected Docker runtime must receive a
    separate native qualification before authentic use. No install/pull occurs.
    Daemon and host administrator are trusted; this is not a universal sandbox
    proof. A cleanup/custody/inspection error permanently poisons this context.
    """
    def __init__(self, *, profile_bytes, public_binding, observation_bytes, viewer,
                 context_id, staging_parent, docker_executable, docker_socket,
                 recorder, policy_api, command_api, process_api,
                 call_wall_seconds=30, max_calls=64, command_runner=None):
        self._closed = self._poisoned = False; self._count = 0; self._calls = []; self._setup_failures = []
        self._owned = {}; self._uncertain_names = set(); self._stage = None; self._close_binding = None
        self._close_complete = False
        self._policy, self._command, self._process = policy_api, command_api, process_api
        self._recorder = recorder; self._viewer = viewer
        self._profile = policy_api.profile(profile_bytes)
        self._context = policy_api.context(context_id)
        require(type(public_binding) is dict and set(public_binding) == {'case_id', 'observation_sha256'}
                and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in public_binding.values()),
                'trusted_public_binding')
        require(type(observation_bytes) is bytes and 0 < len(observation_bytes) <= policy_api.MAX_OBSERVATION
                and hashlib.sha256(observation_bytes).hexdigest() == public_binding['observation_sha256'],
                'exact_case_observation')
        # The unchanged participant interface validates full packet semantics.
        # This backend checks exact bytes and cannot authenticate a hash by itself.
        require(callable(recorder) and callable(viewer), 'trusted_local_callbacks')
        require(type(call_wall_seconds) in (int, float) and 0 < call_wall_seconds <= 60
                and type(max_calls) is int and 1 <= max_calls <= 128, 'declared_tool_limits')
        self._wall, self._maximum = float(call_wall_seconds), max_calls
        self._binding = dict(public_binding); self._observation = bytes(observation_bytes)
        self._runner = command_runner or command_api.run
        require(callable(self._runner), 'trusted_command_runner')
        for value in (staging_parent, docker_executable, docker_socket): policy_api.exact_path(value)
        require(os.path.basename(docker_executable) == 'docker', 'explicit_docker_cli')
        parent = os.lstat(staging_parent)
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
                and not parent.st_mode & 0o077, 'private_owned_staging_parent')
        self._cli = [docker_executable]
        self._socket = docker_socket
        try:
            self._stage = tempfile.mkdtemp(prefix='dosei-code-', dir=staging_parent)
            os.chmod(self._stage, 0o700)
            config = os.path.join(self._stage, 'docker-config')
            os.mkdir(config, 0o700)
            self._cli += ['--config', config, '--host', 'unix://'+docker_socket]
            self._observation_path = os.path.join(self._stage, 'observation.json')
            self._write(self._observation_path, observation_bytes)
            self._observation_identity = file_identity(self._observation_path)
            image = self._execute(['image', 'inspect', policy_api.IMAGE], timeout=15, cap=131072)
            require(image['returncode'] == 0, 'selected_image_unavailable')
            policy_api.admit_image(self._profile, policy_api.decode(image['output']))
            self._setup = self._retain('code_setup', policy_api.canonical({
                'schema': 'dosei_docker_code_setup_v1', 'context_id': context_id,
                'case': self._binding, 'profile_sha256': policy_api.PROFILE_SHA256,
                'image_receipt': image['receipt']['retained_receipt'], 'tool': TOOL,
                'call_wall_seconds': self._wall, 'max_calls': max_calls,
                'fresh_container_per_call': True, 'candidate_host_execution': False,
                'actual_docker_qualification_inherited': False}))
        except BaseException as original:
            self._poisoned = True
            try: self.close()
            except BaseException as cleanup:
                if isinstance(original, Exception) and not isinstance(cleanup, Exception): raise
            raise original

    def _retain(self, kind, raw):
        return self._command.retain(self._recorder, kind, raw)

    def _write(self, path, raw):
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o400)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                require(written > 0, 'staging_write_failure')
                view = view[written:]
            os.fchmod(fd, 0o444)  # exact files readable by container uid 65534
            os.fsync(fd)
        finally: os.close(fd)

    def _execute(self, args, *, timeout=15, cap=131072):
        return self._runner(self._cli+args, cwd=self._stage, recorder=self._recorder,
                            process_api=self._process, timeout_seconds=timeout, output_limit=cap)

    def _usable(self):
        require(not self._closed and not self._poisoned, 'code_context_unavailable')
        require(file_identity(self._observation_path) == self._observation_identity,
                'observation_file_changed')

    def code_observation(self):
        self._usable()
        return bytes(self._observation)

    def viewer_action(self, command):
        self._usable()
        return self._viewer(command)

    def _inspect(self, spec, identity, *, running=None):
        result = self._execute(['container', 'inspect', identity])
        require(result['returncode'] == 0, 'owned_container_inspection_failed')
        state = self._policy.admit_container(self._profile, spec,
            self._policy.decode(result['output']), required_id=identity, running=running)
        return state, result['receipt']['retained_receipt']

    def _remove(self, spec, identity):
        """Remove only our admitted ID, then demand exact global ID absence.

        Name collision is never authority to remove someone else's container.
        A create-command ambiguity is resolved by exact name/owner/profile
        inspection before cleanup; if that fails, report unknown and stop.
        """
        inspection = self._execute(['container', 'inspect', identity])
        require(inspection['returncode'] == 0, 'cleanup_ownership_inspection_failed')
        self._policy.admit_ownership(spec, self._policy.decode(inspection['output']), required_id=identity)
        removal = self._execute(['container', 'rm', '--force', identity])
        require(removal['returncode'] == 0 and removal['output'].strip() == identity.encode('ascii'),
                'container_removal_unconfirmed')
        listing = self._execute(['container', 'ls', '--all', '--no-trunc', '--quiet',
                                 '--filter', 'id='+identity])
        require(listing['returncode'] == 0 and listing['output'].strip() == b'',
                'container_absence_unconfirmed')
        self._owned.pop(identity, None)
        self._uncertain_names.discard(spec['name'])
        return {'remove': removal['receipt']['retained_receipt'],
                'absence': listing['receipt']['retained_receipt']}

    def run_tool(self, name, program):
        self._usable()
        require(name == 'python' and type(program) is str, 'declared_python_tool_only')
        raw = program.encode('utf-8')
        require(len(raw) <= self._policy.MAX_PROGRAM, 'bounded_python_source')
        require(self._count < self._maximum, 'declared_call_count_exhausted')
        self._count += 1; ordinal = self._count
        path = os.path.join(self._stage, f'program-{ordinal:03d}.py')
        try:
            self._write(path, raw); program_identity = file_identity(path)
            spec = self._policy.specification(self._profile, self._context, ordinal,
                                              self._observation_path, path)
            call = {'schema': 'dosei_docker_code_call_v1', 'context_id': self._context,
                    'ordinal': ordinal, 'program': self._retain('python_source', raw),
                    'case': self._binding, 'specification': spec}
        except BaseException as error:
            self._poisoned = True
            self._setup_failures.append({'ordinal': ordinal, 'phase': 'program_preparation',
                'type': type(error).__name__, 'conservative_staging_write_grant_bytes': len(raw),
                'successful_source_custody_confirmed': False, 'container_create_attempted': False})
            raise
        identity = None; closure = None; command_result = None; state = None
        failure = None; interruption = None; create_attempted = False
        try:
            create_attempted = True
            self._uncertain_names.add(spec['name'])
            created = self._execute(self._policy.create_arguments(self._profile, spec))
            require(created['returncode'] == 0 and re.fullmatch(b'[0-9a-f]{64}\n?', created['output']),
                    'container_creation_unconfirmed')
            identity = created['output'].strip().decode('ascii')
            self._owned[identity] = spec
            _, call['initial_inspection'] = self._inspect(spec, identity, running=False)
            command_result = self._execute(['container', 'start', '--attach', identity],
                                            timeout=self._wall, cap=2097152)
            state, call['final_inspection'] = self._inspect(spec, identity, running=False)
            require(type(state.get('ExitCode')) is int and type(state.get('OOMKilled')) is bool
                    and state.get('Error', '') == '', 'candidate_exit_state_unknown')
            require(file_identity(path) == program_identity and
                    file_identity(self._observation_path) == self._observation_identity,
                    'case_input_changed')
            # Exit status is daemon-observed, never parsed from candidate output.
            require(command_result['returncode'] == state['ExitCode'], 'attach_exit_disagrees')
            call['command'] = command_result['receipt']['retained_receipt']
            call['state'] = {key: state[key] for key in ('ExitCode', 'OOMKilled', 'Running', 'Paused')}
        except BaseException as error:
            failure = {'type': type(error).__name__, 'category': getattr(error, 'category', 'code_backend_failure')}
            if not isinstance(error, Exception): interruption = error
        finally:
            try:
                if identity is None and create_attempted:
                    # Even a failed CLI may have created a daemon object. Inspect
                    # exact name, then authenticate all ownership fields first.
                    recovery = self._execute(['container', 'inspect', spec['name']])
                    require(recovery['returncode'] == 0, 'create_outcome_unknown')
                    value = self._policy.decode(recovery['output'])
                    recovered = value[0]['Id']
                    self._policy.admit_ownership(spec, value, required_id=recovered)
                    identity = recovered; self._owned[identity] = spec
                if identity is not None: closure = self._remove(spec, identity)
            except BaseException as error:
                self._poisoned = True
                call['cleanup_failure'] = {'type': type(error).__name__,
                    'category': getattr(error, 'category', 'cleanup_failure')}
                failure = failure or call['cleanup_failure']
                if not isinstance(error, Exception) and interruption is None: interruption = error
        call['closure'] = closure; call['failure'] = failure
        try:
            self._calls.append(self._retain('code_call', self._policy.canonical(call)))
        except BaseException as error:
            self._poisoned = True
            failure = failure or {'category': 'call_custody_failure'}
            if not isinstance(error, Exception) and interruption is None: interruption = error
        if failure:
            self._poisoned = True
            if interruption is not None: raise interruption
            raise CodeBackendFailure(failure['category'])
        # Error text is candidate output, not a trusted failure declaration.
        # Capacity/time/transport faults above invalidate, never become abstention.
        text = command_result['output'].decode('utf-8', errors='replace')
        return {'status': 'ok' if state['ExitCode'] == 0 and not state['OOMKilled'] else 'participant_error',
                'text': text}

    def close(self):
        if self._closed:
            require(self._close_complete and self._close_binding is not None, 'code_closure_unconfirmed')
            return dict(self._close_binding)
        self._closed = True; errors = []; interruption = None
        for identity, spec in list(self._owned.items()):
            try: self._remove(spec, identity)
            except BaseException as error:
                errors.append({'phase': 'owned_container', 'type': type(error).__name__})
                if not isinstance(error, Exception) and interruption is None: interruption = error
        if self._stage is not None and not self._owned and not self._uncertain_names:
            try: shutil.rmtree(self._stage)
            except BaseException as error:
                errors.append({'phase': 'staging_cleanup', 'type': type(error).__name__})
                if not isinstance(error, Exception) and interruption is None: interruption = error
        receipt = {'schema': 'dosei_docker_code_close_v1', 'context_id': self._context,
                   'calls': self._calls, 'owned_container_ids_unresolved': sorted(self._owned),
                   'pre_container_setup_failures': self._setup_failures,
                   'container_names_with_unresolved_create': sorted(self._uncertain_names),
                   'poisoned': self._poisoned, 'errors': errors,
                   'complete': not self._owned and not self._uncertain_names and not errors}
        try: self._close_binding = self._retain('code_close', self._policy.canonical(receipt))
        except BaseException as error:
            errors.append({'phase': 'closure_custody', 'type': type(error).__name__})
            if not isinstance(error, Exception) and interruption is None: interruption = error
        if interruption is not None: raise interruption
        require(not errors and receipt['complete'] and self._close_binding is not None,
                'code_closure_unconfirmed')
        self._close_complete = True
        return dict(self._close_binding)
