"""Explicit 512-MiB grading overlay; configured and scoring bytes stay intact."""
import ast
import hashlib
import json
from pathlib import Path
import time
import types

HERE = Path(__file__).resolve().parent
LOCAL = 'authoring/glial-context-v1/ordinary-completion-v1/'
PROFILE = {'schema': 'neural034-grade-memory-profile/v1',
           'id': 'neural034-viewer-grading-memory512-v1',
           'container_memory_bytes': 536870912, 'container_memory_swap_bytes': 536870912,
           'host_cooperative_ram_bytes': 2147483648, 'nano_cpus': 2000000000,
           'thread_environment': 2, 'cgroup_namespace': 'private',
           'qualified': False, 'measured_sufficiency': False}
PREFIX = 'NEURAL034_CGROUP_TELEMETRY_V1 '
EXTRA_CAPS = {'memory.json': 32768, 'worker_streams.json': 65536,
              'memory_exit_probe.json': 16384, 'memory_profile.json': 4096}
GRADER_CAP = 1813840 + sum(EXTRA_CAPS.values())
ALLOWED_USE = 'separately_admitted_closed_viewer_memory512_grading'

def need(value, message):
    if not value: raise ValueError(message)

def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def decode(body):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate memory metadata key'); value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite memory metadata'))

def replace(body, before, after, count=1):
    need(body.count(before) == count, 'Exact counted memory-profile source seam')
    return body.replace(before, after)

def derive_runtime(source):
    text = source.decode()
    need('os.fchmod(fd, 0o644)' in text, 'Accepted owned-fd publication repair preserved')
    text = replace(text, "name = '_neural034_ordinary_completion_frozen_grader'",
                   "name = '_neural034_memory512_frozen_grader'")
    text = replace(text, 'held_verify = held.verify', 'held_verify = derive_verify(held, source)')
    text = replace(text,
        'held.verify = lambda info, name, mounts, environment: verify(held_verify, info, name, mounts, environment)',
        'held.verify = lambda info, name, mounts, environment: verify(held_verify, info, name, mounts, environment)\n'
        '    held.memory_streams = memory_streams\n    held.TELEMETRY_SOURCE = TELEMETRY_SOURCE\n'
        '    held.MEMORY_PROFILE = MEMORY_PROFILE\n    held.TELEMETRY_PIN = TELEMETRY_PIN')
    text = replace(text,
        '     "        terminal(stopped_rows[0], created_id, name, outcome[\'returncode\'])\\n"\n'
        '     "        write(run/\'terminal_inspection.json\', stopped_rows[0])\\n"',
        '     "        write(run/\'terminal_inspection.json\', stopped_rows[0])\\n"\n'
        '     "        terminal(stopped_rows[0], created_id, name, outcome[\'returncode\'])\\n"')
    return text.encode()

def derive_verify(held, original_source):
    tree = ast.parse(original_source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify']
    need(len(nodes) == 1, 'One held resource verifier')
    text = ast.get_source_segment(original_source.decode(), nodes[0])
    text = replace(text, "c['Cmd'] == ['-I', '-B', '/source/grader.py']",
                   "c['Cmd'] == ['-I', '-B', '/source/telemetry.py']")
    text = replace(text, "h['Memory'] == h['MemorySwap'] == 4*1024**3",
                   "h['Memory'] == h['MemorySwap'] == 536870912 and h['CgroupnsMode'] == 'private'")
    scope = dict(held.__dict__)
    exec(compile(text, str(held.__file__) + '::memory512-verify', 'exec'), scope)
    return scope['verify']

def host_capture(held, original_source):
    """Reuse the original bounded pipe drain/reap code for two fixed host probes."""
    tree = ast.parse(original_source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'docker']
    need(len(nodes) == 1, 'One captured bounded original command function')
    text = ast.get_source_segment(original_source.decode(), nodes[0])
    text = replace(text, 'def docker(args, deadline, cap=300000):', 'def capture_host(args, deadline, cap=16384):')
    text = replace(text, "    env = dict(os.environ, DOCKER_CONFIG=str(ROOT / '.cache-build/docker-config'),\n               DOCKER_HOST=os.environ['NEURAL034_DOCKER_HOST'])",
                   "    need(args in (['/usr/bin/vm_stat'], ['/usr/sbin/sysctl', 'kern.memorystatus_vm_pressure_level']), 'Only fixed read-only host observations')\n    env = dict(os.environ)")
    text = replace(text, 'subprocess.Popen([DOCKER, *args]', 'subprocess.Popen(args')
    scope = dict(held.__dict__)
    exec(compile(text, str(held.__file__)+'::host-observation', 'exec'), scope)
    return scope['capture_host']

def substitutions():
    return [
      ("'candidate_code_executed': False}", "'candidate_code_executed': False, 'resource_profile': MEMORY_PROFILE}", 1),
      ("        initial = docker(['inspect', '--type', 'container', name], work)",
       "        need(lock(Path(TELEMETRY_SOURCE)) == TELEMETRY_PIN, 'Exact readonly telemetry source before dispatch')\n        initial = docker(['inspect', '--type', 'container', name], work)", 1),
      ("mounts = {'/source/grader.py': str(HERE/'grader.py'),",
       "mounts = {'/source/telemetry.py': TELEMETRY_SOURCE,\n                  '/source/grader.py': str(HERE/'grader.py'),", 1),
      ("'--read-only', '--user'", "'--read-only', '--cgroupns', 'private', '--user'", 1),
      ('str(4*1024**3)', 'str(536870912)', 2),
      ("args += [IMAGE, '-I', '-B', '/source/grader.py']",
       "args += [IMAGE, '-I', '-B', '/source/telemetry.py']", 1),
      ("        evidence['worker'] = outcome",
       "        outcome = memory_streams(run, created_id, name, outcome)\n        evidence['worker'] = outcome", 1),
    ]

def parse_streams(outcome):
    need(type(outcome) is dict and type(outcome.get('returncode')) is int
         and type(outcome.get('stdout')) is str and type(outcome.get('stderr')) is str,
         'Exact captured worker streams')
    frames = []; residual = []
    for line in outcome['stderr'].splitlines(keepends=True):
        if line.startswith(PREFIX):
            need(line.endswith('\n') and len(line.encode()) <= 8192, 'Bounded complete telemetry frame')
            value = decode(line[len(PREFIX):])
            need(type(value) is dict and value.get('schema') == 'neural034-cgroup-telemetry/v1'
                 and value.get('phase') in ('before', 'after'), 'Known telemetry frame schema')
            frames.append(value)
        else: residual.append(line)
    need(len(frames) <= 2 and [r['phase'] for r in frames] in ([], ['before'], ['before', 'after']),
         'Ordered unique telemetry frames')
    normalized = dict(outcome, stderr=''.join(residual))
    return {'frames': frames, 'coverage': 'both_ordered_frames' if len(frames) == 2 else 'incomplete',
            'raw_stdout_pin': pin(outcome['stdout'].encode()), 'raw_stderr_pin': pin(outcome['stderr'].encode()),
            'normalized_stderr_pin': pin(normalized['stderr'].encode()),
            'full_container_lifetime_peak_claim': False}, normalized

def install(api, root, review, source):
    """Select the explicit overlay for BOTH normal grade and post-owner recovery."""
    import run as shared
    root = Path(root)
    need(review.get('resource_profile') == PROFILE, 'Root selected exact proposed memory profile')
    qualification = shared.decode(shared.checked(review['portable_runtime']['qualification'], root=root))
    need(qualification.get('allowed_use') == ALLOWED_USE and qualification.get('resource_profile') == PROFILE,
         'New profile qualification; no old4GiB inheritance')
    freeze = shared.decode(shared.checked(shared.FREEZE, root=root))
    def body(name):
        return shared.checked({'path': name, **freeze['files'][name]}, root=root)
    runtime_path = LOCAL + 'grader/grader_runtime.py'; bridge_path = LOCAL + 'grader/grade_bridge.py'
    runtime_body = body(runtime_path); bridge_body = body(bridge_path)
    shared.checked({'path': 'telemetry.py', **source['members']['telemetry.py']}, root=HERE)
    derived = derive_runtime(runtime_body)
    r = shared.module('_neural034_memory512_grader_runtime', root/runtime_path, derived)
    r.derive_verify = derive_verify
    r.FILE_CAPS.update(EXTRA_CAPS); r.TOTAL_BYTES = sum(r.FILE_CAPS.values()); r.ENTRY_CAP = len(r.FILE_CAPS)+1
    need(r.TOTAL_BYTES == GRADER_CAP, 'Explicit extra telemetry journal allowance')
    r.TELEMETRY_SOURCE = str(HERE/'telemetry.py'); r.MEMORY_PROFILE = PROFILE
    r.TELEMETRY_PIN = source['members']['telemetry.py']
    r.RUN_CHILD_SUBSTITUTIONS.extend(substitutions())
    original_write = r.write
    profile_record = {'schema': 'neural034-executed-memory-overlay/v1', 'resource_profile': PROFILE,
       'configured_runtime': pin(runtime_body), 'derived_runtime': pin(derived), 'bridge_source': pin(bridge_body),
       'profile_source': source['members']['memory_profile.py'], 'telemetry_source': source['members']['telemetry.py'],
       'host_observation_source': source['members']['host_observation.py'],
       'original_worker': r.FROZEN_SOURCE_PINS['grader.py'], 'original_score': r.FROZEN_SCORE_PIN}
    def write(path, value):
        original_write(path, value)
        if Path(path).name == 'outer_intent.json':
            original_write(Path(path).with_name('memory_profile.json'), profile_record)
    r.write = write
    def memory_streams(run, created_id, name, outcome):
        raw = {'schema': 'neural034-memory-worker-capture/v1', 'immutable_id': created_id,
               'container': name, 'resource_profile': PROFILE, 'result': outcome}
        original_write(Path(run)/'worker_streams.json', raw)
        parsed, normalized = parse_streams(outcome)
        original_write(Path(run)/'memory.json', dict(parsed, immutable_id=created_id,
                       container=name, resource_profile=PROFILE))
        return normalized
    r.memory_streams = memory_streams
    original_cleanup = r.cleanup
    def cleanup(run, name, deadline):
        if not (Path(run)/'terminal_inspection.json').exists() and not (Path(run)/'memory_exit_probe.json').exists():
            observation = {'schema': 'neural034-memory-terminal-attempt/v1', 'container': name,
                           'state_observed': False, 'terminal_observed': False, 'error': None}
            try:
                created = r.ownership(Path(run), name); observation['immutable_id'] = created
                reply = r.scorer().docker(['inspect', '--type', 'container', created],
                                         min(deadline, time.monotonic()+.25))
                observation['reply'] = r.compact(reply)
                if reply['returncode'] == 0:
                    rows = decode(reply['stdout'])
                    need(type(rows) is list and len(rows) == 1 and rows[0]['Id'] == created,
                         'Exact current terminal probe ID')
                    original_write(Path(run)/'terminal_inspection.json', rows[0])
                    observation['state_observed'] = True
                    observation['terminal_observed'] = (rows[0]['State']['Status'] == 'exited'
                        and rows[0]['State']['Running'] is False and rows[0]['State']['Pid'] == 0)
            except Exception as error: observation['error'] = repr(error)[:2000]
            try: original_write(Path(run)/'memory_exit_probe.json', observation)
            except Exception: pass  # Cleanup continues; missing journal is never complete telemetry.
        return original_cleanup(run, name, deadline)
    r.cleanup = cleanup
    bridge = shared.module('_neural034_memory512_grade_bridge', root/bridge_path, bridge_body)
    need(bridge._RUNTIME is None and r._HELD is None, 'Fresh objects, no cached old runtime')
    bridge._RUNTIME = r
    original_grade = bridge.grade
    def grade(*args):
        return dict(original_grade(*args), resource_profile=PROFILE)
    bridge.grade = grade
    observer = shared.module('_neural034_host_observation', HERE/'host_observation.py',
        shared.checked({'path': 'host_observation.py', **source['members']['host_observation.py']}, root=HERE))
    def observe(deadline):
        held = r.scorer()
        score_body = r.read(r.PACKAGE/'score.py', r.FROZEN_SCORE_PIN['bytes'])
        need(pin(score_body) == r.FROZEN_SCORE_PIN, 'Exact original bounded command capture source')
        return observer.observe(host_capture(held, score_body), deadline)
    bridge.host_observe = observe
    bridge.memory_check = lambda operator, initial, terminal, child: check_memory(
        operator, initial, terminal, child, source, shared, r, profile_record)
    updated = types.SimpleNamespace(**vars(api)); updated.grader = bridge
    return updated

def check_memory(operator, initial, terminal, child, source, shared, r, expected_record):
    """Saved proof only; no Docker/API/private-label access."""
    operator = Path(operator)
    record = shared.decode(shared.capture(operator/'memory_profile.json', 4096))
    need(record == expected_record, 'Exact whole executed overlay/source derivation')
    owned = shared.decode(shared.capture(operator/'ownership.json', 65536))
    held = r.scorer()
    need(owned['mounts'].get('/source/telemetry.py') == str(HERE/'telemetry.py'),
         'Exact admitted telemetry mount source')
    environment = dict(row.split('=', 1) for row in initial['Config']['Env'])
    need(all(environment.get(key) == '2' for key in held.THREADS) and
         environment.get('PYTHONDONTWRITEBYTECODE') == '1', 'Original explicit two-thread environment')
    # Reuse every original isolation/mount/environment guard on the saved initial
    # inspection. The original verifier intentionally expects the created state.
    held.verify(initial, initial['Name'][1:], owned['mounts'], environment)
    for info in (initial, terminal):
        h = info['HostConfig']; c = info['Config']
        need(h['Memory'] == h['MemorySwap'] == 536870912 and h['NanoCpus'] == 2000000000
             and h['CgroupnsMode'] == 'private' and c['Cmd'] == ['-I', '-B', '/source/telemetry.py'],
             'Saved exact512MiB/private-cgroup worker profile')
    raw = shared.decode(shared.capture(operator/'worker_streams.json', 65536))
    observed = shared.decode(shared.capture(operator/'memory.json', 32768))
    parsed, normalized = parse_streams(raw['result'])
    need(raw['immutable_id'] == initial['Id'] == observed['immutable_id']
         and raw['container'] == initial['Name'][1:] == observed['container']
         and raw['resource_profile'] == observed['resource_profile'] == child['resource_profile'] == PROFILE,
         'Same new worker identity and resource profile')
    need(observed == dict(parsed, immutable_id=raw['immutable_id'], container=raw['container'], resource_profile=PROFILE)
         and normalized == child['worker'], 'Raw telemetry and normalized original worker streams join')
    need(parsed['coverage'] == 'both_ordered_frames', 'Both frames required for successful qualification control')
    before, after = parsed['frames']
    need(type(after.get('worker_returncode')) is int and after['worker_returncode'] == 0
         and after.get('before_frame_emitted') is True and after.get('same_cgroup_as_before') is True,
         'Completed original worker and stable measured cgroup')
    for frame in (before, after):
        measurement = frame['measurement']
        need(measurement.get('memory_limit_match') is True and
             measurement.get('swap_limit_match') is True and
             measurement.get('peak_status') == 'available' and
             type(measurement.get('peak_bytes')) is int and measurement['peak_bytes'] >= 0 and
             type(measurement.get('peak_observed_monotonic_ns')) is int and
             measurement.get('peak_kind') == 'kernel_cgroup_high_water' and
             measurement.get('entire_container_lifetime_measured') is False,
             'Supported kernel peak and exact limits required for complete memory evidence')
    return {'resource_profile': PROFILE, 'before': before, 'after': after,
            'observed_terminal_exit': terminal['State']['ExitCode'],
            'observed_terminal_oom_killed': terminal['State']['OOMKilled'],
            'full_container_lifetime_peak_claim': False, 'measured_sufficiency': False,
            'scope': 'Kernel high-water through recorded cutoff when supported; unknown stays unknown. No sampled peak substitution.'}
