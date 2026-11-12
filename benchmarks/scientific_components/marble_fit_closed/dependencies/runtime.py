"""Bounded MARBLE Docker phase backend, source-only and unqualified on real Docker.

Caller authenticates the binary/socket/runtime and immutable inputs, owns a
durable journal and quarantined collector sink, and supplies an outer observer.
Inspect proves the selected process boundary, not clean-image contents, genuine
scientific fitting, or absence of query-time parameter fitting in memory.
"""
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
HOLD = 'import time; time.sleep(2147483647)'
CLEANUP_COMMAND_RESERVE = 14
ARGV_METADATA_BYTES = 65536


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique_json(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate inspect JSON field')
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def keys(value, expected):
    need(type(value) is dict and set(value) == set(expected), 'Exact selected fields required')


def absolute(path):
    need(type(path) is str and path.startswith('/') and '\x00' not in path
         and not any(x in path for x in (',', '\n', '\r')),
         'Canonical literal absolute path required')
    p = Path(path)
    need('..' not in p.parts and str(p) == path
         and not any(q.is_symlink() for q in (p, *p.parents)), 'No path aliases or symlinks')
    return path


def selected(s, mounts, collector_path, collector_args):
    keys(s, ('schema', 'execution_selected', 'task_id', 'phase', 'name_prefix',
             'docker_binary', 'docker_host', 'image', 'candidate_argv', 'collector_python',
             'producer_limits', 'keeper_limits', 'output_limits', 'clocks', 'streams', 'max_commands'))
    need(s['schema'] == 'marble_phase_runtime_v1' and s['execution_selected'] is True
         and s['task_id'] == 'PAPER-paper-method-034' and s['phase'] in ('fit', 'query'),
         'Explicit future MARBLE phase selection required')
    need(type(s['name_prefix']) is str and re.fullmatch(r'nb-marble-[a-z0-9]{16,40}', s['name_prefix']),
         'Fresh exact MARBLE resource prefix required')
    absolute(s['docker_binary'])
    need(type(s['docker_host']) is str and s['docker_host'].startswith('unix:///'),
         'Explicit local Docker socket required')
    absolute(s['docker_host'][7:])
    need(type(s['image']) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', s['image']),
         'Immutable existing image required; no pulls')
    argv = s['candidate_argv']
    need(type(argv) is list and 1 <= len(argv) <= 128
         and all(type(x) is str and x and '\x00' not in x for x in argv), 'Literal selected argv required')
    need(argv[0].startswith('/') and '\n' not in argv[0], 'Absolute image entrypoint required')
    need(type(s['collector_python']) is str and s['collector_python'].startswith('/')
         and not any(x in s['collector_python'] for x in ('\x00', '\n')), 'Explicit trusted interpreter required')
    need(type(s['max_commands']) is int and 32 <= s['max_commands'] < 2**31,
         'Explicit command inventory including fourteen cleanup slots required')
    for role in ('producer', 'keeper'):
        lim = s[role + '_limits']
        keys(lim, ('nano_cpus', 'memory_bytes', 'swap_bytes', 'pids', 'cpu_seconds',
                   'cpu_hard_seconds', 'nofile', 'file_bytes', 'scratch_bytes', 'log_bytes', 'threads'))
        for name, value in lim.items():
            need(type(value) is int and 0 <= value < 2**63
                 and (name in ('scratch_bytes', 'swap_bytes') or value > 0), 'Explicit integer resource bounds')
        need(lim['cpu_hard_seconds'] >= lim['cpu_seconds'], 'CPU hard limit must cover soft limit')
    need(s['keeper_limits']['scratch_bytes'] == 0, 'Keeper has no scratch mount')
    keys(s['output_limits'], ('bytes', 'inodes'))
    need(all(type(x) is int and 0 < x < 2**63 for x in s['output_limits'].values()), 'Explicit output tmpfs bounds')
    keys(s['clocks'], ('whole_seconds', 'producer_seconds', 'collector_seconds', 'client_seconds', 'cleanup_seconds', 'poll_seconds'))
    need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in s['clocks'].values()),
         'Explicit finite clocks required')
    need(s['clocks']['whole_seconds'] > s['clocks']['cleanup_seconds'], 'Whole clock includes cleanup reserve')
    keys(s['streams'], ('stdout_bytes', 'stderr_bytes', 'inspect_bytes', 'collector_stdout_bytes', 'collector_stderr_bytes', 'journal_bytes'))
    need(all(type(x) is int and 0 < x < 2**63 for x in s['streams'].values()), 'Explicit stream ceilings')
    need(type(mounts) is dict and set(mounts) == ({'/program', '/input', '/state'}
         if s['phase'] == 'query' else {'/program', '/input'}), 'Exact phase input mount set')
    for path in mounts.values():
        absolute(path)
    absolute(collector_path)
    need(type(collector_args) is list and len(collector_args) <= 32
         and all(type(x) is str and '\x00' not in x for x in collector_args), 'Literal trusted collector argv')
    need(s['streams']['journal_bytes'] >= journal_envelope(s, mounts, collector_path, collector_args),
         'Selected journal must preserve the worst-case command and cleanup envelope')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def journal_envelope(s, mounts, collector_path, collector_args):
    """Preselected bound, not a grant or an inferred runtime selection."""
    volume = s['name_prefix'] + '-output'
    examples = [['image', 'inspect', s['image']], ['volume', 'inspect', volume],
                ['inspect', '--type', 'container', 'a' * 64], ['rm', '--force', 'a' * 64],
                ['start', 'a' * 64], ['volume', 'rm', volume],
                ['exec', '--user', '65534:65534', 'a' * 64, s['collector_python'],
                 '-I', '-S', '-B', '/trusted/collector.py', *collector_args]]
    create_volume = ['volume', 'create', '--driver', 'local']
    for key, value in {'type': 'tmpfs', 'device': 'tmpfs', 'o': volume_options(s)}.items():
        create_volume += ['--opt', key + '=' + value]
    examples.append([*create_volume, volume])
    for role in ('producer', 'keeper'):
        mapping, argv = role_spec(s, role, mounts, volume, collector_path)
        examples.append(create_args(s, s['name_prefix'] + '-' + role, role, mapping, argv))
    longest = max(len(encoded(x)) for x in examples)
    need(longest <= ARGV_METADATA_BYTES, 'Bounded literal command metadata envelope')
    # A command record has at most 512 additional bytes; identities and four
    # cleanup observations have a separate conservative envelope. Returned
    # inspection bodies and collector bytes are never copied into this journal.
    context = {k: s[k] for k in ('docker_binary', 'docker_host', 'image')}
    return s['max_commands'] * (longest + 512) + 32768 + len(encoded(context))


def absence(result, kind, name):
    if result['returncode'] != 1 or result['stdout'].strip() not in (b'', b'[]'):
        return False
    try:
        stderr = result['stderr'].decode('utf8').strip()
    except UnicodeError:
        return False
    wanted = ({f'Error response from daemon: get {name}: no such volume',
               f'Error: No such volume: {name}', f'error: no such volume: {name}'}
              if kind == 'volume' else
              {f'Error: No such object: {name}', f'Error response from daemon: No such container: {name}',
               f'error: no such object: {name}', f'error response from daemon: no such container: {name}'})
    return stderr in wanted


def bounded_cli(binary, docker_host, whole_end, args, deadline, stdout_cap, stderr_cap,
                stdout_sink=None, clock=time.monotonic):
    """Future real CLI path. Controls never invoke this function."""
    need(clock() < deadline <= whole_end, 'Original command deadline required')
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'DOCKER_HOST': docker_host,
           'DOCKER_CONFIG': '/nonexistent', 'LANG': 'C.UTF-8'}
    p = subprocess.Popen([binary, *args], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True, bufsize=0)
    selector = None
    natural = False
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    counts = {'stdout': 0, 'stderr': 0}
    def group_exists():
        try:
            os.killpg(p.pid, 0)
            return True
        except ProcessLookupError:
            return False
    try:
        selector = selectors.DefaultSelector()
        for name, pipe in (('stdout', p.stdout), ('stderr', p.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map():
            need(clock() < deadline, 'CLI deadline exceeded')
            for key, _ in selector.select(min(.05, max(0, deadline - clock()))):
                name = key.data
                cap = stdout_cap if name == 'stdout' else stderr_cap
                try:
                    part = os.read(key.fileobj.fileno(), min(65536, cap - counts[name] + 1))
                except BlockingIOError:
                    continue
                if not part:
                    selector.unregister(key.fileobj)
                    continue
                counts[name] += len(part)
                need(counts[name] <= cap, 'CLI stream cap exceeded')
                if name == 'stdout' and stdout_sink is not None:
                    stdout_sink(part)
                    need(clock() < deadline, 'Collector callback used remaining command time')
                else:
                    buffers[name].extend(part)
        code = p.wait(timeout=max(.001, deadline - clock()))
        need(clock() <= deadline and not group_exists(), 'Natural CLI exit and process-group absence required')
        natural = True
        return {'returncode': code, 'stdout': bytes(buffers['stdout']), 'stderr': bytes(buffers['stderr']),
                'stdout_bytes': counts['stdout'], 'stderr_bytes': counts['stderr'],
                'natural_exit': True, 'client_reaped': True, 'client_group_absent': True}
    finally:
        if p.poll() is None or group_exists():
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                p.wait(timeout=max(.001, min(1, whole_end - clock())))
            except subprocess.TimeoutExpired:
                pass
        if selector is not None:
            selector.close()
        p.stdout.close()
        p.stderr.close()
        need(p.poll() is not None and not group_exists(), 'Unresolved Docker client process group')


def source_match(actual, wanted, kind):
    return actual == wanted or kind == 'bind' and wanted.startswith('/Users/') and actual == '/host_mnt' + wanted


def volume_options(s):
    return ('size=' + str(s['output_limits']['bytes']) + ',nr_inodes=' + str(s['output_limits']['inodes'])
            + ',uid=65534,gid=65534,mode=0700,noexec,nosuid,nodev')


def role_spec(s, role, mounts, volume, collector_path):
    if role == 'producer':
        mapping = {target: {'type': 'bind', 'source': source, 'rw': False} for target, source in mounts.items()}
        mapping['/output'] = {'type': 'volume', 'source': volume, 'rw': True}
        argv = s['candidate_argv']
    else:
        mapping = {'/trusted/collector.py': {'type': 'bind', 'source': collector_path, 'rw': False},
                   '/output': {'type': 'volume', 'source': volume, 'rw': False}}
        argv = [s['collector_python'], '-I', '-S', '-B', '-c', HOLD]
    return mapping, argv


def create_args(s, name, role, mapping, argv):
    lim = s[role + '_limits']
    args = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--restart', 'no', '--cpus', format(lim['nano_cpus'] / 1e9, '.9f'),
            '--memory', str(lim['memory_bytes']), '--memory-swap', str(lim['memory_bytes'] + lim['swap_bytes']),
            '--pids-limit', str(lim['pids']), '--log-driver', 'local', '--log-opt', 'max-size=' + str(lim['log_bytes']),
            '--log-opt', 'max-file=1', '--log-opt', 'compress=false', '--workdir', '/output' if role == 'producer' else '/',
            '--label', 'neurobench.task_id=PAPER-paper-method-034', '--label', 'neurobench.phase_id=' + s['name_prefix']]
    for key, value in {'cpu': (lim['cpu_seconds'], lim['cpu_hard_seconds']),
                       'nofile': (lim['nofile'], lim['nofile']), 'core': (0, 0),
                       'fsize': (lim['file_bytes'], lim['file_bytes'])}.items():
        args += ['--ulimit', f'{key}={value[0]}:{value[1]}']
    if lim['scratch_bytes']:
        args += ['--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=' + str(lim['scratch_bytes']) + ',mode=1777']
    for key in THREADS:
        args += ['--env', key + '=' + str(lim['threads'])]
    args += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
    for target, row in sorted(mapping.items()):
        value = f'type={row["type"]},src={row["source"]},dst={target}'
        if not row['rw']:
            value += ',readonly'
        if row['type'] == 'volume':
            value += ',volume-nocopy'
        args += ['--mount', value]
    return args + ['--entrypoint', argv[0], s['image'], *argv[1:]]


def verify_container(info, name, identity, s, role, mapping, argv, image_env):
    h, c, state = info['HostConfig'], info['Config'], info['State']
    lim = s[role + '_limits']
    need(info['Id'] == identity and info['Name'] == '/' + name
         and info['Image'] == c['Image'] == s['image']
         and c['Entrypoint'] == [argv[0]] and c['Cmd'] == argv[1:]
         and c['WorkingDir'] == ('/output' if role == 'producer' else '/'), 'Exact container identity and command')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False
         and c['User'] == '65534:65534' and h.get('CapDrop') == ['ALL'] and not h.get('CapAdd')
         and 'no-new-privileges:true' in h.get('SecurityOpt', []), 'Offline nonroot readonly security profile')
    need(not any(h.get(k) for k in ('Devices', 'DeviceRequests', 'PortBindings', 'Links', 'VolumesFrom', 'Binds'))
         and h.get('PidMode') != 'host' and h.get('IpcMode') != 'host'
         and set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'}
         and h['AutoRemove'] is False and h['RestartPolicy']['Name'] in ('', 'no'), 'No hidden mounts/devices/host namespaces')
    need(h['Memory'] == lim['memory_bytes'] and h['MemorySwap'] == lim['memory_bytes'] + lim['swap_bytes']
         and h['NanoCpus'] == lim['nano_cpus'] and h['PidsLimit'] == lim['pids'], 'Exact selected resource bounds')
    tmpfs = {'/tmp': 'rw,noexec,nosuid,nodev,size=' + str(lim['scratch_bytes']) + ',mode=1777'} if lim['scratch_bytes'] else {}
    need((h.get('Tmpfs') or {}) == tmpfs, 'Exact scratch mount')
    expected_limits = {'cpu': (lim['cpu_seconds'], lim['cpu_hard_seconds']), 'nofile': (lim['nofile'], lim['nofile']),
                       'core': (0, 0), 'fsize': (lim['file_bytes'], lim['file_bytes'])}
    need(len(h['Ulimits']) == 4 and {x['Name']: (x['Soft'], x['Hard']) for x in h['Ulimits']} == expected_limits,
         'Exact process ulimits')
    need(h['LogConfig'] == {'Type': 'local', 'Config': {'max-size': str(lim['log_bytes']), 'max-file': '1', 'compress': 'false'}},
         'Exact bounded daemon logs')
    env = c['Env']
    need(type(env) is list and all(type(x) is str and '=' in x for x in env), 'Typed image environment')
    actual_env = dict(x.split('=', 1) for x in env)
    expected_env = dict(image_env)
    expected_env.update({x: str(lim['threads']) for x in THREADS}, PYTHONDONTWRITEBYTECODE='1')
    need(len(actual_env) == len(env) and actual_env == expected_env, 'Only exact image environment and fixed controls')
    need(c.get('Labels', {}).get('neurobench.task_id') == 'PAPER-paper-method-034'
         and c.get('Labels', {}).get('neurobench.phase_id') == s['name_prefix'], 'Selected ownership labels')
    for label, rows, targetkey in (('requested', h.get('Mounts', []), 'Target'),
                                   ('effective', [x for x in info['Mounts'] if x['Type'] != 'tmpfs'], 'Destination')):
        need(len(rows) == len(mapping) and {x[targetkey] for x in rows} == set(mapping), 'Exact mount inventory')
        for row in rows:
            want = mapping[row[targetkey]]
            actual = row.get('Name') if label == 'effective' and want['type'] == 'volume' else row['Source']
            need(row['Type'] == want['type'] and source_match(actual, want['source'], want['type']), 'Exact mount source')
            if label == 'requested':
                need(row.get('ReadOnly', False) is (not want['rw']), 'Exact readonly mount request')
                if want['type'] == 'volume':
                    need(row.get('VolumeOptions', {}).get('NoCopy') is True, 'No volume copy-up')
            else:
                need(row['RW'] is want['rw'], 'Exact effective mount mode')
    need(len({x['Destination'] for x in info['Mounts']}) == len(info['Mounts'])
         and all(x['Destination'] in tmpfs and x['RW'] is True for x in info['Mounts'] if x['Type'] == 'tmpfs'),
         'No additional effective mount')
    need(state.get('OOMKilled') is False and state.get('Dead') is False and not state.get('Error'), 'No OOM/dead/runtime error')


def run_phase(selection, mounts, collector_path, collector_args, receive, journal,
              *, cli=None, clock=time.monotonic, started=None, sleeper=time.sleep):
    """Run one future selected phase; publish only after returned success.

receive(chunk) writes quarantine, never final artifacts. journal(snapshot) must
durably save before returning. An outer observer must verify natural host exit;
forced termination leaves its already durable known-resource obligations.
producer_seconds covers start dispatch through observed natural exit, otherwise
proved removal or this function's return. elapsed_seconds also includes all
preflight, journals, collection and cleanup. A failed client call without
reaped/group-absence evidence leaves all_clients_closed false.
"""
    origin = clock() if started is None else started
    selected(selection, mounts, collector_path, collector_args)
    s = selection
    need(type(origin) in (int, float) and math.isfinite(origin) and origin <= clock(), 'Original phase origin required')
    end = origin + s['clocks']['whole_seconds']
    normal_end = end - s['clocks']['cleanup_seconds']
    need(callable(receive) and callable(journal), 'Trusted collector and durable journal required')
    if cli is None:
        cli = lambda args, deadline, outcap, errcap, stdout_sink=None: bounded_cli(
            s['docker_binary'], s['docker_host'], end, args, deadline, outcap, errcap, stdout_sink, clock)
    owned, commands, cleanup = [], [], []
    result = {'schema': 'marble_phase_runtime_result_v1', 'phase': s['phase'], 'success': False,
              'candidate_status': 'not_started', 'collector_complete': False, 'owned': owned,
              'commands': commands, 'cleanup': cleanup, 'scientific_scoring_performed': False,
              'requires_independent_natural_host_exit': True, 'producer_exit_code': None,
              'producer_natural_exit': False, 'producer_removed': False, 'producer_oom_killed': None,
              'producer_timed_out': False, 'all_clients_closed': True, 'producer_seconds': 0.0}
    producer_started = producer_finished = producer_end = None
    def guard(deadline=end):
        need(clock() < deadline, 'Original whole/phase deadline exhausted')
    def persist():
        guard()
        snapshot = {'schema': 'marble_phase_ownership_journal_v1', 'phase_id': s['name_prefix'],
                 'runtime_context': {k: s[k] for k in ('docker_binary', 'docker_host', 'image')},
                 'owned': [dict(x) for x in owned], 'commands': list(commands), 'cleanup': list(cleanup),
                 'elapsed_seconds': clock() - origin}
        body = encoded(snapshot)
        need(len(body) <= s['streams']['journal_bytes'], 'Bounded durable journal required')
        journal(json.loads(body))
        guard()
    def call(args, deadline=normal_end, inspect=False, sink=None, cleaning=False):
        guard(deadline)
        normal_count = sum(not row['cleanup'] for row in commands)
        need(len(commands) < s['max_commands'] and
             (cleaning or normal_count < s['max_commands'] - CLEANUP_COMMAND_RESERVE),
             'Selected command inventory preserves cleanup reserve')
        need(len(encoded(args)) <= ARGV_METADATA_BYTES, 'Bounded command metadata required')
        cap = s['streams']['inspect_bytes'] if inspect else s['streams']['stdout_bytes']
        if sink is not None:
            cap = s['streams']['collector_stdout_bytes']
        errcap = s['streams']['collector_stderr_bytes'] if sink is not None else s['streams']['stderr_bytes']
        command_end = min(deadline, clock() + (s['clocks']['collector_seconds'] if sink is not None else s['clocks']['client_seconds']))
        row = {'argv': list(args), 'status': 'dispatch_pending', 'started_seconds': clock() - origin,
               'deadline_seconds': command_end - origin, 'cleanup': cleaning,
               'client_reaped': None, 'client_group_absent': None}
        commands.append(row)
        try:
            persist()
            guard(command_end)
        except BaseException:
            row['status'] = 'not_dispatched'
            raise
        row['status'] = 'dispatched'
        try:
            returned = cli(args, command_end, cap, errcap, stdout_sink=sink)
            if type(returned) is dict:
                for field in ('client_reaped', 'client_group_absent'):
                    row[field] = returned.get(field) is True
            need(type(returned) is dict and all(returned.get(k) is True for k in ('natural_exit', 'client_reaped', 'client_group_absent')),
                 'Natural reaped CLI and absent client group required')
            need(type(returned.get('returncode')) is int and -(2**31) <= returned['returncode'] < 2**31
                 and type(returned.get('stdout')) is bytes and type(returned.get('stderr')) is bytes
                 and len(returned['stdout']) <= cap and len(returned['stderr']) <= errcap, 'Bounded typed CLI result')
            for field, maximum in (('stdout_bytes', cap), ('stderr_bytes', errcap)):
                need(type(returned.get(field)) is int and 0 <= returned[field] <= maximum,
                     'Exact bounded CLI byte counts required')
            need(returned['stderr_bytes'] == len(returned['stderr'])
                 and (sink is not None or returned['stdout_bytes'] == len(returned['stdout'])),
                 'Complete retained CLI streams required')
            row.update(status='completed', returncode=returned['returncode'],
                       stdout_bytes=returned['stdout_bytes'], stderr_bytes=returned['stderr_bytes'])
            persist()
            guard(command_end)
            return returned
        except BaseException as error:
            row.update(status='failed', error_type=type(error).__name__[:64])
            try:
                persist()
            except BaseException:
                pass  # Prior dispatch_pending journal remains a live obligation.
            raise
    def inspect(kind, target, deadline=normal_end, cleaning=False):
        return call(['volume', 'inspect', target] if kind == 'volume' else ['inspect', '--type', 'container', target],
                    deadline, True, cleaning=cleaning)
    def one(r):
        need(r['returncode'] == 0, 'Successful exact inspect required')
        values = unique_json(r['stdout'])
        need(type(values) is list and len(values) == 1 and type(values[0]) is dict, 'One inspect object required')
        return values[0]
    def volume_identity(v):
        value = {k: v[k] for k in ('Name', 'CreatedAt', 'Mountpoint', 'Driver', 'Options')}
        need(len(encoded(value)) <= 8192, 'Bounded volume identity metadata')
        return value
    def register(kind, name):
        need(absence(inspect(kind, name), kind, name), 'Exact absence before ownership dispatch')
        row = {'kind': kind, 'name': name, 'identity': None, 'attempted_before_dispatch': True}
        owned.append(row)
        persist()
        return row
    def retire(row):
        report = {'kind': row['kind'], 'name': row['name'], 'absence_verified': False}
        try:
            need(row['identity'] is not None, 'Unknown creation identity remains unresolved')
            kind, name = row['kind'], row['name']
            identity = row['identity']
            target = identity if kind == 'container' else name
            observed = inspect(kind, target, end, cleaning=True)
            if not absence(observed, kind, target):
                current = one(observed)
                need((current['Id'] == identity and current['Name'] == '/' + name) if kind == 'container'
                     else volume_identity(current) == identity, 'Stable owned identity before removal')
                removed = call(['rm', '--force', identity] if kind == 'container' else ['volume', 'rm', name], end, cleaning=True)
                need(removed['returncode'] == 0, 'Owned removal command succeeded')
            targets = [name, identity] if kind == 'container' else [name]
            checks = {x: absence(inspect(kind, x, end, cleaning=True), kind, x) for x in targets}
            report.update(required_absence_targets=targets, absence_observations=checks,
                          absence_verified=all(checks.values()))
        except BaseException as error:
            report['error_type'] = type(error).__name__
        cleanup.append(report)
        return report
    try:
        guard(normal_end)
        image = one(call(['image', 'inspect', s['image']], inspect=True))
        need(image['Id'] == s['image'] and not image['Config'].get('Volumes'), 'Exact existing image without implicit volumes')
        image_env_rows = image['Config'].get('Env') or []
        need(all(type(x) is str and '=' in x for x in image_env_rows), 'Typed selected image environment')
        image_env = dict(x.split('=', 1) for x in image_env_rows)
        need(len(image_env) == len(image_env_rows), 'Unique image environment keys')
        volume = register('volume', s['name_prefix'] + '-output')
        opts = {'type': 'tmpfs', 'device': 'tmpfs', 'o': volume_options(s)}
        args = ['volume', 'create', '--driver', 'local']
        for k, v in opts.items():
            args += ['--opt', k + '=' + v]
        created = call([*args, volume['name']])
        need(created['returncode'] == 0 and created['stdout'].decode().strip() == volume['name'], 'Exact output volume creation')
        v = one(inspect('volume', volume['name']))
        need(v['Name'] == volume['name'] and v['Driver'] == 'local' and v['Options'] == opts
             and type(v['CreatedAt']) is str and v['CreatedAt'] and type(v['Mountpoint']) is str,
             'Exact tmpfs output volume identity')
        volume['identity'] = volume_identity(v)
        persist()
        resources = {}
        for role in ('keeper', 'producer'):
            mapping, argv = role_spec(s, role, mounts, volume['name'], collector_path)
            row = register('container', s['name_prefix'] + '-' + role)
            created = call(create_args(s, row['name'], role, mapping, argv))
            identity = created['stdout'].decode().strip()
            need(created['returncode'] == 0 and re.fullmatch('[a-f0-9]{64}', identity), 'Exact created container ID')
            v = one(inspect('container', identity))
            need(v['Id'] == identity and v['Name'] == '/' + row['name'], 'Created identity/name join')
            row['identity'] = identity
            persist()
            verify_container(v, row['name'], identity, s, role, mapping, argv, image_env)
            need(v['State']['Status'] == 'created' and v['State']['Running'] is False and v['State']['Pid'] == 0,
                 'Verified before start')
            resources[role] = (row, mapping, argv)
            if role == 'keeper':
                need(call(['start', identity])['returncode'] == 0, 'Keeper start')
                running = one(inspect('container', identity))
                verify_container(running, row['name'], identity, s, role, mapping, argv, image_env)
                need(running['State']['Running'] is True and running['State']['Status'] == 'running'
                     and type(running['State']['Pid']) is int and running['State']['Pid'] > 0, 'Keeper running')
        producer, mapping, argv = resources['producer']
        producer_started = clock()
        producer_end = min(normal_end, producer_started + s['clocks']['producer_seconds'])
        result['candidate_status'] = 'started'
        need(call(['start', producer['identity']], producer_end)['returncode'] == 0, 'Producer start')
        while True:
            state = one(inspect('container', producer['identity'], producer_end))
            if type(state['State'].get('OOMKilled')) is bool:
                result['producer_oom_killed'] = state['State']['OOMKilled']
            verify_container(state, producer['name'], producer['identity'], s, 'producer', mapping, argv, image_env)
            if state['State']['Running'] is False:
                need(state['State']['Status'] == 'exited' and type(state['State']['ExitCode']) is int
                     and state['State']['Pid'] == 0,
                     'Natural exited container state required')
                producer_finished = clock()
                result['producer_natural_exit'] = True
                result['producer_exit_code'] = state['State']['ExitCode']
                need(state['State']['ExitCode'] == 0, 'Candidate phase returned nonzero')
                break
            guard(producer_end)
            sleeper(min(s['clocks']['poll_seconds'], max(0, producer_end - clock())))
        need(retire(producer)['absence_verified'], 'Producer absent before opaque collection')
        result['candidate_status'] = 'exited_zero_and_removed'
        persist()
        keeper, mapping, argv = resources['keeper']
        state = one(inspect('container', keeper['identity']))
        verify_container(state, keeper['name'], keeper['identity'], s, 'keeper', mapping, argv, image_env)
        need(state['State']['Running'] is True and state['State']['Status'] == 'running'
             and type(state['State']['Pid']) is int and state['State']['Pid'] > 0,
             'Verified readonly keeper before collection')
        count = 0
        def sink(chunk):
            nonlocal count
            need(type(chunk) is bytes and len(chunk) <= 65536, 'Bounded collector stream chunk')
            count += len(chunk)
            need(count <= s['streams']['collector_stdout_bytes'], 'Cumulative collector stream cap')
            guard(normal_end)
            receive(chunk)
            guard(normal_end)
        captured = call(['exec', '--user', '65534:65534', keeper['identity'], s['collector_python'],
                         '-I', '-S', '-B', '/trusted/collector.py', *collector_args],
                        min(normal_end, clock() + s['clocks']['collector_seconds']), sink=sink)
        need(captured['returncode'] == 0 and captured['stdout_bytes'] == count,
             'Trusted collector exited naturally zero with complete stream')
        result.update(collector_complete=True, collector_bytes=count)
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error)[:300])
        result['producer_timed_out'] = bool(producer_end is not None and producer_finished is None and clock() >= producer_end)
    finally:
        for row in reversed(owned):
            retire(row)
            if row['kind'] == 'container' and row['name'].endswith('-producer') and cleanup[-1]['absence_verified']:
                result['producer_removed'] = True
                if producer_started is not None and producer_finished is None:
                    producer_finished = clock()
        result['all_owned_absent'] = bool(owned) and len(owned) == 3 and all(
            any(x['kind'] == row['kind'] and x['name'] == row['name'] and x['absence_verified']
                for x in cleanup[-len(owned):]) for row in owned)
        result['elapsed_seconds'] = clock() - origin
        result['all_clients_closed'] = all(row['status'] == 'not_dispatched' or
            row['client_reaped'] is True and row['client_group_absent'] is True for row in commands)
        result['success'] = bool(result['collector_complete'] and result['all_owned_absent']
                                 and result['all_clients_closed'] and result['elapsed_seconds'] <= s['clocks']['whole_seconds'])
        try:
            persist()
        except BaseException as error:
            result.update(success=False, final_journal_error=type(error).__name__)
        result['elapsed_seconds'] = clock() - origin
        if producer_started is not None:
            result['producer_seconds'] = (producer_finished if producer_finished is not None else clock()) - producer_started
        result['success'] = bool(result['success'] and result['elapsed_seconds'] <= s['clocks']['whole_seconds'])
    return result
