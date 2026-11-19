"""Portable two-episode fixed-canary boundary; no model study or scoring.

The caller supplies a separately selected configuration and resource admission.
Only run() opens a packet or starts children; pure helpers support source controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
import time
import types

HERE = Path(__file__).resolve().parent
RELATIVE = 'benchmarks/neural/NEURAL-077/implementations/full32-paired-runtime-v1'
H = 'benchmarks/neural/NEURAL-077/implementations/full32-paired-benchmark-v1'
EXPECTED_PATHS = {
    'evaluator': H + '/evaluator.py', 'consumer': H + '/consumer.py',
    'bundle': H + '/bundle.py', 'evaluator_bindings': H + '/SOURCE_BINDINGS.json',
    'wire': 'benchmarks/neural/NEURAL-077/implementations/waveform-transport-v1/transport.py',
    'owned': 'benchmarks/shared/viewer-process-ownership-v1/owned_exit.py',
    'profile': RELATIVE + '/profile_successor.py',
    'episode': RELATIVE + '/diagnostic_episode.py', 'canary': RELATIVE + '/canary.py',
}
CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
LIMITS = {'whole_seconds': 300, 'work_seconds': 210, 'episode_seconds': 30, 'cleanup_seconds': 5}
RUNTIME_ROOTS = ('/System', '/usr', '/Library/Frameworks')
READ_CAP = 32 * 1024**2
WRITE_CAP = 16 * 1024**2
SESSION_RESERVE = 8 * 1024**2
EPISODE_RESERVE = 512 * 1024
PIPE_RESERVE = 65536 + 4096 + 4 + 1
FINAL_RESERVE = 256 * 1024


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON field')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(value, cap=1048576):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded byte/hash descriptor required')


def absolute(value):
    need(type(value) is str and Path(value).is_absolute() and '..' not in Path(value).parts,
         'Absolute normalized operator path required')
    return Path(value)


def in_runtime(path):
    return any(path.is_relative_to(root) for root in RUNTIME_ROOTS)


def validate_config(value, here=HERE):
    need(type(value) is dict and set(value) == {
        'schema', 'selected', 'repository_root', 'public_root', 'public_manifest',
        'output_root', 'interpreter', 'sandbox', 'operator_source', 'source_bindings',
        'positions', 'limits'}, 'Exact portable runtime configuration')
    need(value['schema'] == 'erp-full32-two-episode-runtime-v1' and value['selected'] is True,
         'Separate explicit two-episode selection required')
    root, packet, output = [absolute(value[key]) for key in ('repository_root', 'public_root', 'output_root')]
    need(root / RELATIVE == Path(here), 'Exact portable sibling location')
    need(not in_runtime(packet) and not in_runtime(output), 'Packet/output outside runtime data scopes')
    need(not output.is_relative_to(packet) and not packet.is_relative_to(output) and
         not output.is_relative_to(Path(here)) and not Path(here).is_relative_to(output),
         'Output must not alias packet or runtime source')
    for key in ('public_manifest', 'operator_source', 'source_bindings'):
        descriptor(value[key])
    for key in ('interpreter', 'sandbox'):
        row = value[key]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact executable descriptor')
        path = absolute(row['path'])
        descriptor({k: row[k] for k in ('bytes', 'sha256')})
        need(in_runtime(path), 'Selected executable inside existing runtime scope')
    need(value['sandbox']['path'] == '/usr/bin/sandbox-exec', 'Exact maintained sandbox executable')
    need(value['positions'] == [0, 1] and all(type(v) is int for v in value['positions']),
         'Only deterministic sorted-roster positions zero and one')
    need(value['limits'] == LIMITS and all(type(v) is int for v in value['limits'].values()),
         'Exact finite two-episode deadlines')
    return value


def validate_bindings(value):
    need(type(value) is dict and set(value) == {'schema', 'members'} and
         value['schema'] == 'erp-full32-portable-runtime-sources-v1' and
         type(value['members']) is dict and set(value['members']) == set(EXPECTED_PATHS),
         'Exact portable dependency closure')
    for name, row in value['members'].items():
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
             row['path'] == EXPECTED_PATHS[name], 'Exact repository-relative source locator')
        descriptor({key: row[key] for key in ('bytes', 'sha256')}, 65536)
    return value


class Budget:
    def __init__(self):
        self.read = self.written = 0

    def input(self, count):
        need(type(count) is int and count >= 0 and self.read + count <= READ_CAP, 'Runtime read ceiling')
        self.read += count

    def output(self, count):
        need(type(count) is int and count >= 0 and self.written + count <= WRITE_CAP, 'Runtime artifact ceiling')
        self.written += count


def capture(path, maximum, budget, expected=None):
    path = Path(path)
    need(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'Direct source/input paths')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
             'Bounded ordinary single-link input')
        budget.input(before.st_size)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(before.st_size)
        fields = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        need(len(body) == before.st_size and fields(before) == fields(os.fstat(fd)) == fields(path.lstat()),
             'Input changed during capture')
    finally:
        os.close(fd)
    need(expected is None or pin(body) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Source/input pin mismatch')
    return body


def write_new(path, body, budget, reserved=False):
    if not reserved:
        budget.output(len(body))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return pin(body)


def loaded(name, path, body):
    value = types.ModuleType(name); value.__file__ = str(path); sys.modules[name] = value
    exec(compile(body, str(path), 'exec'), value.__dict__)
    return value


def matched_commitment(direct, program, no_tools, program_tools):
    need(set(direct) == set(program) == {'trial_id', 'condition', 'prompt', 'context_sha256'}, 'Exact context projection')
    need(direct['trial_id'] == program['trial_id'] and direct['condition'] == CONDITIONS[0] and
         program['condition'] == CONDITIONS[1], 'Same opaque query, separate permission policies')
    a, b = direct['prompt'], program['prompt']
    need(a.count(no_tools) == b.count(program_tools) == 1 and b.replace(program_tools, no_tools, 1) == a,
         'Only the specified tool-permission sentence may differ')
    need(all(pin(x['prompt'].encode())['sha256'] == x['context_sha256'] for x in (direct, program)),
         'Complete context hashes required')
    return {'trial_id': direct['trial_id'], 'direct_context': pin(a.encode()), 'program_context': pin(b.encode()),
            'permission_normalized_context': pin(a.encode()), 'direct_model_called': False}


def end_closed(end):
    if (type(end) is not dict or end.get('schema') != 'erp-full6400-owned-episode-v1' or
            end.get('generated_protocol_only') is not False or
            end.get('diagnostic_mode') != 'concurrent_bounded_stderr_v1' or
            not {'pid', 'owned_cleanup', 'stderr_capture', 'stdout_EOF_observed'} <= set(end)):
        return False
    if end['pid'] is None:
        return end['owned_cleanup'] is None and end['stderr_capture'] is None and end['stdout_EOF_observed'] is False
    cleanup, stderr = end.get('owned_cleanup') or {}, end.get('stderr_capture') or {}
    fields = {'eof_observed', 'reader_joined', 'closed', 'overflow', 'error', 'observed_bytes', 'retained_bytes'}
    if (type(stderr) is not dict or not fields <= set(stderr) or
            any(type(stderr[k]) is not bool for k in ('eof_observed', 'reader_joined', 'closed', 'overflow')) or
            type(stderr['observed_bytes']) is not int or type(stderr['retained_bytes']) is not int or
            not 0 <= stderr['retained_bytes'] <= min(16384, stderr['observed_bytes']) or
            stderr['observed_bytes'] > 65536):
        return False
    clean = stderr['eof_observed'] and not stderr['overflow'] and stderr['error'] is None
    drained = stderr['eof_observed'] and stderr['overflow'] and stderr['error'] == 'stderr_byte_limit'
    capped = (not stderr['eof_observed'] and stderr['overflow'] and stderr['error'] == 'stderr_read_limit' and
              stderr['observed_bytes'] == 65536 and stderr['retained_bytes'] == 16384)
    return (type(end.get('pid')) is int and end['pid'] > 1 and type(cleanup.get('pid')) is int and cleanup['pid'] == end['pid'] and
            cleanup.get('cleanup_complete') is True and cleanup.get('reaped') is True and
            cleanup.get('group_absence_observed') is True and end.get('stdout_EOF_observed') is True and
            stderr.get('reader_joined') is True and stderr.get('closed') is True and (clean or drained or capped))


def accept_episode(envelope, end, identifier, context_sha256):
    need(envelope.get('status') == 'ok' and envelope.get('error') is None and
         envelope.get('trial_id') == identifier and envelope.get('condition') == CONDITIONS[1] and
         envelope.get('context_sha256') == context_sha256, 'Canary response failed')
    response = decode(envelope['response'])
    need(set(response) == {'trial_id', 'target_probability'} and response['trial_id'] == identifier and
         type(response['target_probability']) in (int, float) and response['target_probability'] == 0.5,
         'Only the fixed unscored canary response is admitted')
    need(end_closed(end) and end.get('schema') == 'erp-full6400-owned-episode-v1' and
         end.get('status') == 'ok' and end.get('generated_protocol_only') is False and
         type(end.get('returncode')) is int and end['returncode'] == 0 and
         end.get('normal_exit_observed') is True and end.get('trial_id') == identifier and
         end.get('condition') == CONDITIONS[1] and end.get('context_sha256') == context_sha256,
         'Real sandbox episode and complete resource closure required')
    stderr = end.get('stderr_capture') or {}
    need(stderr.get('eof_observed') is True and stderr.get('overflow') is False and stderr.get('error') is None,
         'Clean complete bounded stderr required for success')


def drive_two(identifiers, context_for, episode_call, projection_sink, no_tools, program_tools):
    """Small target-blind join; callbacks permit pure generated orchestration controls."""
    need(len(identifiers) == 2 and len(set(identifiers)) == 2 and
         all(re.fullmatch('q-[0-9a-f]{32}', x) for x in identifiers), 'Two distinct selected opaque identities')
    rows = [{'position': i, 'trial_id': identifier, 'status': 'not_attempted',
             'pid': None, 'end': None, 'closure_complete': True} for i, identifier in enumerate(identifiers)]
    value = {'episodes': rows, 'error': None, 'direct_projection_count': 0,
             'program_episode_count': 0, 'complete': False}
    try:
        for i, identifier in enumerate(identifiers):
            direct, program = [context_for(identifier, condition) for condition in CONDITIONS]
            commitment = matched_commitment(direct, program, no_tools, program_tools)
            projection_sink(i, direct, commitment)
            value['direct_projection_count'] += 1
            rows[i].update(status='dispatch_started', closure_complete=False, matched=commitment)
            envelope, end = episode_call(i, program)
            rows[i].update(status='closed_failure' if end.get('pid') is not None else 'not_launched',
                           pid=end.get('pid'), end=end, closure_complete=end_closed(end))
            value['program_episode_count'] += int(end.get('pid') is not None)
            accept_episode(envelope, end, identifier, program['context_sha256'])
            rows[i]['status'] = 'passed'
            if i:
                need(rows[0]['pid'] != rows[1]['pid'], 'Fresh processes for consecutive episodes')
        value['complete'] = True
    except BaseException as error:
        value['error'] = {'type': type(error).__name__, 'message': str(error)[:2048]}
    return value


def _run(config):
    """Internal work and finalization, entirely inside run()'s admitted timer."""
    started = time.monotonic()
    validate_config(config)
    budget = Budget()
    source_root = Path(config['repository_root'])
    operator = capture(HERE / 'runtime.py', 65536, budget, config['operator_source'])
    bindings = validate_bindings(decode(capture(HERE / 'SOURCE_BINDINGS.json', 16384, budget, config['source_bindings'])))
    bodies = {name: capture(source_root / row['path'], 65536, budget, row)
              for name, row in bindings['members'].items()}
    public_bindings = decode(bodies['evaluator_bindings'])
    need(public_bindings['schema'] == 'erp-full32-portable-evaluator-sources-v1' and
         public_bindings['members'] == {name: {'path': name + '.py', **pin(bodies[name])}
                                      for name in ('bundle', 'consumer')}, 'Evaluator dependency join changed')
    for name in ('interpreter', 'sandbox'):
        capture(config[name]['path'], 1048576, budget, config[name])
        need(os.access(config[name]['path'], os.X_OK), 'Selected executable permission required')
    need(sys.platform == 'darwin', 'Maintained sandbox-exec substrate required; no host fallback')
    output = absolute(config['output_root'])
    need(all(not p.is_symlink() for p in (output, *output.parents)) and not output.exists(), 'Fresh direct output root')
    output.mkdir(mode=0o700)
    budget.output(FINAL_RESERVE)
    result = {'schema': 'erp-full32-portable-two-episode-result-v1', 'status': 'failed', 'operation_complete': False,
              'positions': [0, 1], 'model_calls': 0, 'direct_model_calls': 0, 'scores_computed': False,
              'private_inputs_opened': False, 'full_condition_queries': 6400,
              'full6400_execution_qualified': False, 'provider_policy_qualified': False,
              'operator_source': pin(operator), 'source_bindings': config['source_bindings'],
              'public_manifest': config['public_manifest'], 'canonical_configuration': pin(encode(config)),
              'episodes': [{'position': i, 'status': 'not_attempted', 'pid': None,
                            'end': None, 'closure_complete': True} for i in (0, 1)]}
    session = None
    try:
        modules = {name: loaded('erp_runtime_' + name, source_root / bindings['members'][name]['path'], bodies[name])
                   for name in ('evaluator', 'bundle', 'consumer', 'wire', 'owned', 'profile', 'episode')}
        evaluator = modules['evaluator']
        modules['wire'] = modules['profile'].wrap_wire(modules['wire'])
        witness_root = output / 'witnesses'; witness_root.mkdir(mode=0o700)
        paths = {'prior_episode': 'prior-episode.bin', 'answer': 'answer.bin',
                 'person': 'person.bin', 'manifest': 'manifest.bin'}
        for name, filename in paths.items():
            write_new(witness_root / filename, ('GENERATED NON-NEURAL ' + name + '\n').encode(), budget)
        candidate_config = {'witnesses': {name: str(witness_root / filename) for name, filename in paths.items()},
                            'witnesses_are_generated_non_neural': True, 'actual_private_paths_provided': False}
        staging = output / 'bundle-input'; staging.mkdir(mode=0o700)
        write_new(staging / 'canary.py', bodies['canary'], budget)
        config_body = encode(candidate_config)
        write_new(staging / 'config.json', config_body, budget)
        declaration = {'schema': 'neural077_python_bundle_v1', 'entry_module': 'canary',
                       'modules': ['canary.py'], 'config': 'config.json'}
        budget.input(len(bodies['canary']) + len(config_body))
        frozen = modules['bundle'].capture(staging, declaration)
        client_body = modules['bundle'].verify(frozen)
        client_root = output / 'client'; client_root.mkdir(mode=0o700)
        frozen_pin = write_new(client_root / 'FROZEN.json', encode(frozen), budget)
        client = client_root / 'CLIENT.py'
        client_pin = write_new(client, client_body, budget)
        result.update(frozen=frozen_pin, client=client_pin, bundle_identity=frozen['bundle_identity'])
        result['effective_profile'] = write_new(output / 'SELECTED_PROFILE.sb', modules['wire'].sandbox_profile(client).encode(), budget)
        budget.input(SESSION_RESERVE)
        session = modules['consumer'].PacketSession(config['public_root'], config['public_manifest'])
        need(len(session.trial_ids) == 6400, 'Full public condition remains intact')
        episodes = output / 'episodes'; episodes.mkdir(mode=0o700)

        def continuity():
            capture(HERE / 'runtime.py', 65536, budget, config['operator_source'])
            capture(HERE / 'SOURCE_BINDINGS.json', 16384, budget, config['source_bindings'])
            for name, row in bindings['members'].items():
                capture(source_root / row['path'], 65536, budget, row)
            for name in ('interpreter', 'sandbox'):
                capture(config[name]['path'], 1048576, budget, config[name])
            capture(client, 1048576, budget, client_pin)

        def project(i, direct, commitment):
            write_new(output / ('DIRECT_REQUEST_%04d.json' % i), encode(direct), budget)
            write_new(output / ('MATCHED_%04d.json' % i), encode(commitment), budget)

        def invoke(i, program):
            need(time.monotonic() < started + LIMITS['work_seconds'] - 35, 'Enough bounded work window for next episode')
            continuity()
            budget.output(EPISODE_RESERVE); budget.input(PIPE_RESERVE)
            episode_budget = {'written': 0}
            value = modules['episode'].episode(
                evaluator, program, CONDITIONS[1], episodes / ('%04d' % i), client,
                config['interpreter']['path'], {'episode_work_seconds': 30, 'episode_cleanup_seconds': 5},
                started + LIMITS['work_seconds'], modules, episode_budget, generated_protocol_only=False)
            need(episode_budget['written'] <= EPISODE_RESERVE, 'Episode evidence envelope')
            return value

        joined = drive_two([session.trial_ids[i] for i in config['positions']], session.context, invoke, project,
                           modules['consumer'].NO_TOOLS, modules['consumer'].PROGRAMME_TOOLS)
        result.update(joined)
        continuity()
        capture(client_root / 'FROZEN.json', 1048576, budget, frozen_pin)
        if joined['complete']:
            result.update(status='two_episode_scoped_delivery_passed', operation_complete=True,
                          qualification_scope='Fixed canaries only; clocks, shared OS side channels and escaped descendants unqualified')
    except BaseException as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:2048]}
    finally:
        if session is not None:
            try:
                session.close()
            except BaseException as error:
                result.update(status='failed', operation_complete=False, session_close_error=type(error).__name__)
        result['all_episode_children_closed'] = all(row['closure_complete'] for row in result['episodes'])
        result['read_bytes_conservatively_charged'] = budget.read
        result['artifact_bytes_conservatively_reserved'] = budget.written
        result['accounting'] = 'Includes 8 MiB PacketSession and per-dispatch 69,637-byte pipe precharges; not measured I/O'
        body = encode(result); need(len(body) <= FINAL_RESERVE, 'Reserved result receipt')
        write_new(output / 'RESULT.json', body, budget, reserved=True)
    return result


def run(config):
    """Standalone main-thread execution after external resource admission.

    Existing interval timers are refused before any input/packet/native work.
    This module is not an in-process replacement for a caller's watchdog.
    """
    validate_config(config)
    need(threading.current_thread() is threading.main_thread(), 'Standalone main-thread timer ownership required')
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'Existing caller timer must not be replaced')
    handlers = {}
    def interrupted(signum, frame):
        raise TimeoutError('Finite runtime operation') if signum == signal.SIGALRM else InterruptedError('Runtime interrupted')
    try:
        for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            handlers[sig] = signal.signal(sig, interrupted)
        signal.setitimer(signal.ITIMER_REAL, LIMITS['whole_seconds'])
        return _run(config)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args(argv)
    config_path = args.config.absolute()
    need(not in_runtime(config_path), 'Operator config outside participant runtime data scopes')
    body = capture(config_path, 65536, Budget())
    need(pin(body)['sha256'] == args.config_sha256, 'Selected configuration digest')
    result = run(decode(body))
    print(json.dumps({key: result[key] for key in ('status', 'operation_complete', 'all_episode_children_closed')}))
    return 0 if result['operation_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
