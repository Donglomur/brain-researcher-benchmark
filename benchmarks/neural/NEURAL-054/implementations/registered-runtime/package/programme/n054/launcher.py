"""Source-owned Docker launcher and explicitly inert local engineering route.
Docker scientific route is authored, never run during this construction phase.
"""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tarfile
import time
import threading
import uuid
from .common import need, pin, digest, tree, same_tree, load, put, read, relative, Refusal, stream_pin, copy_verified
from .journal import Journal
from .spec import INERT, DOMAIN
from .process_custody import OwnedProcess, ProcessCustodyError

LIMIT_KEYS = {'wall_s', 'cpu_s', 'memory_bytes', 'output_bytes', 'files', 'stream_bytes',
              'tool_calls', 'model_calls', 'tokens', 'collection_wall_s', 'request_bytes'}

class Launcher:
    def __init__(self, root, domain, environment, limits, fixture_programs=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.domain = domain; self.environment = environment; self.limits = limits
        need(set(limits) == LIMIT_KEYS and all(type(v) is int and v > 0 for v in limits.values()) and
             limits['request_bytes'] <= 8 << 30 and limits['output_bytes'] <= 8 << 30,
             'Positive complete process limits')
        self.fixture_programs = set(fixture_programs or [])
        self.records = Journal(self.root / 'receipt-index', 'original_processes', max(16 << 20, limits['output_bytes']), data_root=self.root)
        self.counter = 0; self.pending = {}; self.observation_counts = {}; self.active_job = None
        self.owned_children = {}; self.unresolved_holds = {}
        self.totals = {'cpu_s': 0., 'logical_request_bytes': 0, 'logical_output_bytes': 0,
                       'physical_read_bytes': 0, 'physical_write_bytes': 0,
                       'model_calls': 0, 'tokens': 0, 'unknown_model_counter_jobs': [], 'unknown_model_counter_count': 0,
                       'unknown_cpu_jobs': 0}
        if domain == DOMAIN:
            need(sys.platform == 'linux', 'Qualified Linux container executor required')
            need(set(environment) == {'image', 'python', 'qualification', 'aggregate_observer'}, 'Environment contract')
            need('@sha256:' in environment['image'], 'Content-addressed container image')
            need(environment['qualification']['status'] == 'INDEPENDENTLY_QUALIFIED', 'Environment unqualified')
            # This source does not turn an unchecked candidate declaration into authorization.
            need(environment['aggregate_observer']['kind'] == 'cgroup_v2_same_host', 'Concrete aggregate observer')
        else:
            need(domain == INERT, 'Explicit domain')

    def _observe(self, job, phase, values):
        """Persist original partial observations before any fallible downstream step."""
        ordinal = self.observation_counts.get(job.name, 0)
        record = {'phase': phase, 'ordinal': ordinal, 'values': values,
                  'prior': self.pending[job.name].get('observation_chain')}
        identity = put(job / 'observation' / ('o%06d.json' % ordinal), record, self.records.entry_cap)
        self.pending[job.name].update(values)
        self.pending[job.name].update({'observation_chain': identity['sha256'], 'observation_count': ordinal + 1})
        self.observation_counts[job.name] = ordinal + 1

    def _capture(self, job, phase, values):
        # Memory owns observed values before a possibly partial/failed file write.
        self.pending[job.name].update(values)
        ordinal = self.observation_counts.get(job.name, 0)
        try:
            return self._observe(job, phase, values)
        except BaseException as error:
            self.observation_counts[job.name] = max(ordinal + 1, self.observation_counts.get(job.name, 0))
            self.pending[job.name].setdefault('failed_observations', []).append(
                {'phase': phase, 'ordinal': ordinal, 'values': values,
                 'error': type(error).__name__ + ': ' + str(error)})
            raise

    def _retain(self, job, phase, values):
        try:
            self._capture(job, phase, values)
        except BaseException as error:
            return error
        return None

    def _child(self, job, command, wall_s, group=True):
        child = OwnedProcess(command, wall_s, self.limits['collection_wall_s'], group)
        self.owned_children.setdefault(job.name, []).append(child)
        return child

    def _raise_observed(self, primary, observation):
        error = Refusal('Original process failed: ' + type(primary).__name__ + ': ' + str(primary))
        error.original_observation = observation
        error.original_error = getattr(primary, 'original_error', primary)
        raise error from primary

    def _base(self, job, role, source, request, state, build):
        source_files = tree(source, 16 << 20, 512)
        source_id = digest(source_files)
        need(self.domain == DOMAIN or source_id in self.fixture_programs,
             'Local route accepts only explicitly pinned harmless fixtures')
        mounts = {'source': (Path(source), source_files)}
        for name, path in [('state', state), ('build', build)]:
            if path is not None:
                mounts[name] = (Path(path), tree(path, self.limits['output_bytes'], self.limits['files']))
        request_pin = put(job / 'request.json', request, self.limits['request_bytes'])
        self._capture(job, 'source_request_admitted', {'source': source_id, 'request': request_pin,
                      'mounts': {name: digest(files) for name, (_, files) in mounts.items()},
                      'mounted_input_bytes': sum(sum(f['bytes'] for f in files) for _, files in mounts.values())})
        return source_id, mounts, request_pin

    def _charge(self, record):
        t = self.totals
        known_cpu = [record[k] for k in ('cpu_s', 'cgroup_cpu_s') if record.get(k) is not None]
        if known_cpu: t['cpu_s'] += max(known_cpu)
        else: t['unknown_cpu_jobs'] += 1
        t['cpu_s'] += record.get('control_cpu_s', 0.)
        t['logical_request_bytes'] += (record.get('request') or {}).get('bytes', 0) + record.get('mounted_input_bytes', 0) + record.get('control_archive_read_bytes', 0)
        t['logical_output_bytes'] += sum(x['bytes'] for x in record['outputs']) + sum((record.get(k) or {}).get('bytes', 0) for k in ('stdout', 'stderr')) + record.get('control_stream_bytes', 0)
        for k in ('physical_read_bytes', 'physical_write_bytes'): t[k] += record.get(k) or 0
        if record.get('model_calls') is None or record.get('tokens') is None:
            t['unknown_model_counter_count'] += 1
            if len(t['unknown_model_counter_jobs']) < 32: t['unknown_model_counter_jobs'].append(record['job'])
        else:
            t['model_calls'] += record['model_calls']; t['tokens'] += record['tokens']

    def run(self, role, source, entry, request, state=None, build=None):
        need(not self.pending and not self.owned_children and not self.unresolved_holds,
             'Unresolved prior original process custody')
        self.counter += 1
        job = self.root / 'jobs' / ('%06d' % (self.counter // 1000)) / ('j%09d' % self.counter)
        job.mkdir(parents=True)
        for name in ('out', 'observation'): (job / name).mkdir()
        self.pending[job.name] = {'job': job.relative_to(self.root).as_posix(), 'role': role, 'domain': self.domain,
            'entry': entry, 'execution_started': False, 'cleanup_failures': [], 'failed_observations': [],
            'cpu_s': None, 'exit_code': None, 'model_calls': None, 'tokens': None}
        self.active_job = job
        before = time.monotonic(); primary = None; outputs = []; inventory_failure = None; result = None
        try:
            relative(entry); need((Path(source) / entry).is_file(), 'Source-owned entrypoint missing')
            self._capture(job, 'attempt', {'entry': entry, 'limits': self.limits})
            source_id, mounts, request_pin = self._base(job, role, source, request, state, build)
            observed = self._inert(job, mounts, entry) if self.domain == INERT else self._container(job, mounts, entry)
            self._capture(job, 'backend_return', observed)
            for _, (path, files) in mounts.items():
                same_tree(path, files, max(16 << 20, self.limits['output_bytes']), max(512, self.limits['files']))
            need(all(c.settled for c in self.owned_children.get(job.name, [])), 'Output inventory requires original group quiescence')
            outputs = tree(job / 'out', self.limits['output_bytes'], self.limits['files'])
            need(self.pending[job.name]['exit_code'] == 0 and not self.pending[job.name]['timeout'], 'Actor failed or timed out')
            result = load(job / 'out/result.json', self.limits['output_bytes'])
        except BaseException as error:
            primary = error
            self._retain(job, 'primary_failure', {'primary_failure': type(error).__name__ + ': ' + str(error)})
            # No inventory of a directory which an unresolved descendant may mutate.
            # The ownership sweep below precedes even a failure-path inventory.
        finally:
            # A last ownership sweep is independent of every event/final-record writer.
            children = self.owned_children.get(job.name, [])
            for child in children:
                if not child.settled:
                    try: child.wait(force=True)
                    except BaseException as error:
                        if primary is None: primary = error
            record = dict(self.pending[job.name])
            unsettled = any(not child.settled for child in children)
            container_hold = record.get('container_cleanup_unresolved', False)
            actor_hold = record.get('actor_possible', False) and record.get('exit_code') is None
            if unsettled or container_hold or actor_hold:
                outputs = []; inventory_failure = 'DEFERRED_UNRESOLVED_CUSTODY: no stable output inventory admitted'
            elif primary is not None:
                try: outputs = tree(job / 'out', self.limits['output_bytes'], self.limits['files'])
                except BaseException as inventory_error: inventory_failure = str(inventory_error)
            record.update({'children': [dict(c.observation) for c in children], 'outputs': outputs,
                'host_wall_s': time.monotonic() - before, 'failure': type(primary).__name__ + ': ' + str(primary) if primary else None,
                'partial_inventory_failure': inventory_failure, 'environment': digest(self.environment),
                'limits': self.limits, 'original_observer': True,
                'custody_status': 'UNRESOLVED_HOLD' if unsettled or container_hold or actor_hold else 'ORIGINALS_COMPLETE'})
            durable = False
            try:
                final = job / 'observation/FINAL.json'; put(final, record, self.records.entry_cap)
                self.records.append(record, path=final); self._charge(record); durable = True
            except BaseException as error:
                record['final_retention_error'] = type(error).__name__ + ': ' + str(error)
                if primary is None: primary = error
            if durable and record['custody_status'] == 'ORIGINALS_COMPLETE':
                self.pending.pop(job.name); self.observation_counts.pop(job.name, None)
                self.owned_children.pop(job.name, None); self.active_job = None
            else:
                record['custody_status'] = 'UNRESOLVED_HOLD'
                self.pending[job.name] = record; self.unresolved_holds[job.name] = record
                if primary is None: primary = ProcessCustodyError('Original custody unresolved', record)
        if primary is not None: self._raise_observed(primary, record)
        return {'result': result, 'output': job / 'out', 'receipt': digest(record), 'record': record}

    def _inert(self, job, mounts, entry):
        """Only reviewed harmless fixtures; ownership is real, isolation is not qualified."""
        env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
               'N054_REQUEST_BYTES': str(self.limits['request_bytes']), 'N054_STATE_BYTES': str(self.limits['output_bytes'])}
        args = [sys.executable, '-I', '-S', '-B', str((mounts['source'][0] / entry).resolve()),
                '--request', str((job / 'request.json').resolve()), '--output', str((job / 'out').resolve())]
        for name in ('state', 'build'):
            if name in mounts: args += ['--' + name, str(mounts[name][0].resolve())]
        def limit():
            os.setsid(); resource.setrlimit(resource.RLIMIT_CPU, (self.limits['cpu_s'], self.limits['cpu_s']))
            resource.setrlimit(resource.RLIMIT_FSIZE, (self.limits['stream_bytes'], self.limits['stream_bytes']))
        child = self._child(job, args, self.limits['wall_s']); primary = None
        try:
            with (job / 'observation/stdout').open('xb') as stdout, (job / 'observation/stderr').open('xb') as stderr:
                with child:
                    proc = child.start(cwd=job / 'out', env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, preexec_fn=limit)
                    self._capture(job, 'actor_started', {'argv': args, 'cwd': str((job / 'out').resolve()),
                                                       'pid': proc.pid, 'execution_started': True})
                    child.wait()
        except BaseException as error:
            primary = error
        finally:
            observed = {**child.observation, 'cwd': str((job / 'out').resolve()), 'model_calls': 0,
                        'tokens': 0, 'tool_calls': 0, 'isolation_qualified': False, 'scientific_operations': 0}
            child.observation.update(observed)
            error = self._retain(job, 'original_actor_wait', observed)
            if primary is None: primary = error
            for key in ('stdout', 'stderr'):
                try:
                    need(child.settled, 'Stream pin deferred: original group custody unresolved')
                    value = stream_pin(job / 'observation' / key, self.limits['stream_bytes'])
                    child.observation[key] = observed[key] = value
                    error = self._retain(job, 'original_actor_' + key, {key: value})
                    if primary is None: primary = error
                except BaseException as error:
                    observed[key + '_unavailable'] = type(error).__name__ + ': ' + str(error)
                    child.observation.update(observed)
                    if primary is None: primary = error
        if primary is not None: self._raise_observed(primary, observed)
        return observed

    def _docker(self, argv, timeout=None, output_cap=1 << 20, cleanup=False):
        """Host control process; cleanup still runs when event persistence fails."""
        job = self.active_job; need(job is not None, 'Observed control context required')
        state = self.pending[job.name]; ordinal = state.get('control_commands', 0)
        folder = job / 'control' / ('c%06d' % ordinal); folder.mkdir(parents=True)
        command = ['docker', *argv]; primary = None
        error = self._retain(job, 'control_launch', {'control_commands': ordinal + 1,
            'last_control_launch': {'argv': command, 'cwd': os.getcwd(), 'stdout': str(folder / 'stdout'), 'stderr': str(folder / 'stderr')}})
        if error is not None:
            if not cleanup: raise error
            primary = error
        def limit():
            os.setsid(); resource.setrlimit(resource.RLIMIT_FSIZE, (output_cap, output_cap))
        child = self._child(job, command, timeout or self.limits['wall_s'])
        try:
            with (folder / 'stdout').open('xb') as stdout, (folder / 'stderr').open('xb') as stderr:
                with child:
                    proc = child.start(stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, preexec_fn=limit)
                    error = self._retain(job, 'control_started', {'last_control_pid': proc.pid})
                    if error is not None:
                        if primary is None: primary = error
                        if not cleanup: raise error
                    child.wait()
        except BaseException as error:
            if primary is None: primary = error
        finally:
            observed = dict(child.observation)
            for key in ('stdout', 'stderr'):
                try:
                    need(child.settled, 'Control stream pin deferred: original group custody unresolved')
                    observed[key] = stream_pin(folder / key, output_cap)
                except BaseException as error:
                    observed[key + '_unavailable'] = type(error).__name__ + ': ' + str(error)
                    if primary is None: primary = error
            child.observation.update(observed)
            try: put(folder / 'ORIGINAL.json', observed, self.records.entry_cap)
            except BaseException as error:
                observed['original_file_retention_error'] = type(error).__name__ + ': ' + str(error)
                child.observation.update(observed)
                if primary is None: primary = error
            error = self._retain(job, 'control_wait', {'last_control_observation': observed,
                'control_cpu_s': state.get('control_cpu_s', 0.) + (observed['cpu_s'] or 0.),
                'control_stream_bytes': state.get('control_stream_bytes', 0) + sum((observed.get(k) or {}).get('bytes', 0) for k in ('stdout', 'stderr'))})
            if primary is None: primary = error
        if primary is not None: self._raise_observed(primary, observed)
        need(child.settled and observed['wait_completed'] and not observed['timeout'] and observed['exit_code'] == 0,
             'Original container control failed: ' + str(observed['exit_code']))
        need(observed['stdout']['bytes'] + observed['stderr']['bytes'] <= output_cap, 'Container control stream ceiling')
        return read(folder / 'stdout', output_cap)

    def _copy(self, name, source, destination):
        """Bounded original archive process, owned before its first observation."""
        command = ['docker', 'cp', name + ':' + source + '/.', '-']; job = self.active_job
        stderr_path = job / 'observation' / ('archive-stderr-%06d' % self.observation_counts[job.name])
        count = total = entries = 0; primary = None; bounded = None
        deadline = time.monotonic() + self.limits['collection_wall_s']
        class BoundedArchive:
            def __init__(self, stream, ceiling):
                import hashlib
                self.stream = stream; self.ceiling = ceiling; self.total = 0; self.hash = hashlib.sha256()
            def read(self, size=-1):
                need(size >= 0, 'Bounded archive read')
                if size == 0: return b''
                import select
                need(select.select([self.stream.fileno()], [], [], max(0., deadline - time.monotonic()))[0], 'Archive collection deadline')
                b = os.read(self.stream.fileno(), min(size, self.ceiling - self.total + 1)); self.total += len(b); self.hash.update(b)
                need(self.total <= self.ceiling, 'Archive transport quota'); return b
        def limit():
            os.setsid(); resource.setrlimit(resource.RLIMIT_FSIZE, (self.limits['stream_bytes'], self.limits['stream_bytes']))
        child = self._child(job, command, self.limits['collection_wall_s'])
        try:
            with stderr_path.open('xb') as stderr:
                with child:
                    proc = child.start(stdout=subprocess.PIPE, stderr=stderr, preexec_fn=limit)
                    try:
                        self._capture(job, 'archive_started', {'last_archive_launch': {'argv': command, 'pid': proc.pid, 'source': source}})
                        bounded = BoundedArchive(proc.stdout, self.limits['output_bytes'] + self.limits['files'] * 16384 + 65536)
                        with tarfile.open(fileobj=bounded, mode='r|') as archive:
                            for member in archive:
                                entries += 1; need(entries <= self.limits['files'] * 2 + 4, 'Archive member quota')
                                name = member.name.removeprefix('./').rstrip('/')
                                if not name: continue
                                relative(name)
                                need(member.isfile() or member.isdir(), 'No archive links or special files')
                                dest = destination / name
                                if member.isdir(): dest.mkdir(parents=True, exist_ok=True); continue
                                count += 1; total += member.size
                                need(count <= self.limits['files'] and total <= self.limits['output_bytes'], 'Archive quota')
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                with dest.open('xb') as f:
                                    stream = archive.extractfile(member)
                                    remaining = member.size
                                    while remaining:
                                        b = stream.read(min(65536, remaining)); need(b, 'Truncated archive')
                                        f.write(b); remaining -= len(b)
                    finally:
                        proc.stdout.close()
        except BaseException as error:
            primary = error
        finally:
            observed = {**child.observation, 'archive_transport_bytes': bounded.total if bounded else 0,
                'archive_observed_prefix_sha256': bounded.hash.hexdigest() if bounded else pin(b'')['sha256'],
                'admitted_files': count, 'admitted_bytes': total,
                'failure': type(primary).__name__ + ': ' + str(primary) if primary else None}
            try:
                need(child.settled, 'Archive stream pin deferred: original group custody unresolved')
                observed['stderr'] = stream_pin(stderr_path, self.limits['stream_bytes'])
            except BaseException as error:
                observed['stderr_unavailable'] = type(error).__name__ + ': ' + str(error)
                if primary is None: primary = error
            child.observation.update(observed)
            error = self._retain(job, 'archive_original_wait', {'last_archive_wait': observed,
                'control_cpu_s': self.pending[job.name].get('control_cpu_s', 0.) + (observed['cpu_s'] or 0.),
                'control_archive_read_bytes': self.pending[job.name].get('control_archive_read_bytes', 0) + observed['archive_transport_bytes'],
                'control_stream_bytes': self.pending[job.name].get('control_stream_bytes', 0) + (observed.get('stderr') or {}).get('bytes', 0)})
            if primary is None: primary = error
        if primary is not None: self._raise_observed(primary, observed)
        need(child.settled and observed['wait_completed'] and observed['exit_code'] == 0 and not observed['timeout'], 'Archive process failure or deadline')

    def _cleanup(self, job, action):
        try:
            action(); return None
        except BaseException as error:
            failures = [*self.pending[job.name]['cleanup_failures'], type(error).__name__ + ': ' + str(error)]
            self._retain(job, 'container_cleanup_failure', {'cleanup_failures': failures})
            return error

    def _container(self, job, mounts, entry):
        name = 'n054-' + uuid.uuid4().hex
        python = self.environment['python']; need(python.startswith('/'), 'Fixed image interpreter path')
        argv = [python, '-I', '-B', '/source/' + entry,
                '--request', '/input/request.json', '--output', '/work']
        for key in ('state', 'build'):
            if key in mounts: argv += ['--' + key, '/' + key]
        plan = {'argv': argv, 'env': {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work',
                                    'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1',
                                    'TRANSFORMERS_OFFLINE': '1', 'OMP_NUM_THREADS': '1',
                                    'N054_REQUEST_BYTES': str(self.limits['request_bytes']),
                                    'N054_STATE_BYTES': str(self.limits['output_bytes'])},
                **{k: self.limits[k] for k in ('cpu_s', 'wall_s', 'output_bytes', 'collection_wall_s')}}
        inp = job / 'container-input'; inp.mkdir()
        copy_verified(job / 'request.json', inp / 'request.json', self.limits['request_bytes'], self.pending[job.name]['request'])
        put(inp / 'launch.json', plan)
        cmd = ['create', '--name', name, '--read-only', '--network', 'none', '--pids-limit', '128',
               '--memory', str(self.limits['memory_bytes']), '--memory-swap', str(self.limits['memory_bytes']),
               '--cpus', '1', '--cap-drop', 'ALL', '--cap-add', 'SETUID', '--cap-add', 'SETGID',
               '--cap-add', 'KILL', '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
               '--tmpfs', '/work:rw,nosuid,nodev,size=' + str(self.limits['output_bytes']),
               '--tmpfs', '/observed:rw,nosuid,nodev,size=' + str(2 * self.limits['stream_bytes'] + 65536),
               '--mount', 'type=bind,src=' + str(inp.resolve()) + ',dst=/input,readonly',
               '--mount', 'type=bind,src=' + str(Path(__file__).with_name('sandbox_supervisor.py').resolve()) +
               ',dst=/supervisor.py,readonly',
               '--mount', 'type=bind,src=' + str(Path(__file__).with_name('process_custody.py').resolve()) + ',dst=/process_custody.py,readonly']
        for key, (path, _) in mounts.items():
            need(',' not in str(path.resolve()), 'Mount path delimiter')
            cmd += ['--mount', 'type=bind,src=' + str(path.resolve()) + ',dst=/' + key + ',readonly']
        cmd += [self.environment['image'], python, '-I', '-S', '-B', '/supervisor.py']
        primary = cleanup_error = None; cgroup = None
        self._capture(job, 'container_plan', {'container_argv': ['docker', *cmd],
                      'container_image': self.environment['image']})
        self.pending[job.name].update({'owned_container': name, 'container_cleanup_unresolved': True})
        try:
            self._docker(cmd)
            self.pending[job.name]['actor_possible'] = True
            self._docker(['start', name]); start = time.monotonic()
            self._capture(job, 'container_started', {'execution_started': True, 'container_name': name})
            info = json.loads(self._docker(['inspect', name]))[0]
            pid = info['State']['Pid']
            groups = Path(f'/proc/{pid}/cgroup').read_text().splitlines()
            unified = [x[3:] for x in groups if x.startswith('0::')]
            need(len(unified) == 1 and '..' not in Path(unified[0]).parts, 'Same-host cgroup v2 required')
            cgroup = Path('/sys/fs/cgroup') / unified[0].lstrip('/')
            while b'N054_OBSERVED_COMPLETION' not in self._docker(['logs', name]):
                need(time.monotonic() - start <= self.limits['wall_s'] + 5, 'Supervisor wall cap')
                state = json.loads(self._docker(['inspect', name]))[0]['State']
                need(state['Running'], 'Supervisor stopped without completion')
                time.sleep(.05)
            # A group wait does not contain descendants which changed groups.
            # Freeze the entire owned container before any stream/output copying;
            # observe both the control result and the exact same-host cgroup state.
            # This is separate containment evidence, never an original actor wait.
            self._docker(['pause', name])
            paused = json.loads(self._docker(['inspect', name]))[0]['State']
            need(paused.get('Paused') is True, 'Owned container pause unconfirmed')
            with (cgroup / 'cgroup.events').open('rb') as stream:
                frozen_raw = stream.read(4097)
            need(len(frozen_raw) <= 4096, 'Bounded cgroup freeze observation')
            frozen = dict(line.split() for line in frozen_raw.decode('ascii').splitlines())
            need(frozen.get('frozen') == '1', 'Owned container descendants not frozen')
            self._capture(job, 'container_output_containment', {
                'container_outputs_frozen': True, 'container_paused_state': paused,
                'cgroup_freeze_original': frozen_raw.decode('ascii'),
                'containment_scope': 'whole_owned_container_cgroup_until_removal',
                'not_an_original_actor_or_descendant_wait': True})
            aggregate = {x: (cgroup / x).read_text() for x in ('cpu.stat', 'memory.peak', 'io.stat', 'memory.events')}
            self._capture(job, 'original_cgroup_raw', {'cgroup_original_observations': aggregate})
            cpu = dict(line.split() for line in aggregate['cpu.stat'].splitlines())
            counters = [dict(item.split('=') for item in line.split()[1:]) for line in aggregate['io.stat'].splitlines()]
            self._capture(job, 'original_cgroup_counters', {
                'cgroup_cpu_s': int(cpu['usage_usec']) / 1e6,
                'cgroup_memory_peak_bytes': int(aggregate['memory.peak'].strip()),
                'physical_read_bytes': sum(int(x.get('rbytes', 0)) for x in counters),
                'physical_write_bytes': sum(int(x.get('wbytes', 0)) for x in counters)})
            # Trusted observations are durably copied and admitted BEFORE untrusted work output.
            self._copy(name, '/observed', job / 'observation')
            observed = load(job / 'observation/receipt.json')
            self._capture(job, 'original_actor_wait', observed)
            need(observed.get('failure') is None and observed.get('custody_status') == 'ORIGINAL_WAIT_AND_GROUP_COMPLETE',
                 'Supervisor reports original failure or unresolved custody')
            streams = {k: stream_pin(job / 'observation' / k, self.limits['stream_bytes']) for k in ('stdout', 'stderr')}
            self._capture(job, 'original_actor_streams', streams)
            self._copy(name, '/work', job / 'out')
            need(self.pending[job.name]['cgroup_memory_peak_bytes'] <= self.limits['memory_bytes'], 'Observed aggregate memory cap')
            source_id = digest(mounts['source'][1]); qualification = self.environment['qualification']
            meter = {'isolation_qualified': False, 'model_calls': None, 'tokens': None, 'tool_calls': 0,
                     'service_meter_scope': 'Only independently admitted exact source identities qualify model/non-model counters.'}
            if source_id in qualification.get('trusted_model_source_ids', []):
                usage = load(job / 'out/usage.json', 65536)
                need(usage['scope'] == 'TRUSTED_OFFLINE_MODEL_ADAPTER', 'Qualified adapter usage schema')
                need(all(type(usage[k]) is int and usage[k] >= 0 for k in ('model_calls', 'input_tokens', 'output_tokens')), 'Original integer usage')
                meter.update({'model_calls': usage['model_calls'], 'tokens': usage['input_tokens'] + usage['output_tokens'],
                              'model_usage': stream_pin(job / 'out/usage.json', 65536)})
            elif source_id in qualification.get('non_model_source_ids', []): meter.update({'model_calls': 0, 'tokens': 0})
            self._capture(job, 'original_service_meter', meter)
            if meter['model_calls'] is not None:
                need(meter['model_calls'] <= self.limits['model_calls'] and meter['tokens'] <= self.limits['tokens'], 'Original service ceiling')
        except BaseException as error:
            primary = error
            self._retain(job, 'container_primary_failure', {'container_primary_failure': type(error).__name__ + ': ' + str(error)})
        finally:
            if primary is not None:
                # Preserve available original counters and explicit observation gaps before destructive cleanup.
                if cgroup is not None:
                    try:
                        raw = {x: (cgroup / x).read_text() for x in ('cpu.stat', 'memory.peak', 'io.stat', 'memory.events')}
                        self._retain(job, 'failure_cgroup_snapshot', {'failure_cgroup_raw': raw, 'failure_counters_may_be_partial': True})
                    except BaseException as error:
                        self._retain(job, 'failure_cgroup_unavailable', {'failure_cgroup_unavailable': str(error)})
                if self.pending[job.name].get('exit_code') is None:
                    try:
                        kill_error = self._cleanup(job, lambda: self._docker(['kill', '--signal', 'KILL', name], cleanup=True))
                        waited = self._docker(['wait', name], cleanup=True)
                        self._retain(job, 'container_forced_wait', {'container_forced_wait_stdout': waited.decode(errors='replace'),
                                      'actor_exit_unavailable': 'Supervisor did not yield an admitted actor wait; container exit is not substituted.'})
                    except BaseException as error:
                        self._retain(job, 'forced_wait_failure', {'forced_wait_failure': str(error)})
            cleanup_error = self._cleanup(job, lambda: self._docker(['rm', '-f', name], cleanup=True))
            removal = getattr(cleanup_error, 'original_observation', {}) if cleanup_error else {}
            removed = cleanup_error is None or (removal.get('wait_completed') and removal.get('group_quiescent') is True and removal.get('exit_code') == 0)
            self.pending[job.name]['container_cleanup_unresolved'] = not removed
            retention_error = self._retain(job, 'container_removal_disposition', {'container_removed': removed})
            if cleanup_error is None: cleanup_error = retention_error
        if primary is not None: raise primary
        if cleanup_error is not None: raise cleanup_error
        return dict(self.pending[job.name])
