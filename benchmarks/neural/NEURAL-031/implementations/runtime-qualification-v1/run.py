"""Run one complete, source-bound NEURAL-031 ratio-one engineering control.

The forty-context programme still owns its original 480-second deadline. The
separate protected score is reached only after all outputs, runtime reports and
owned transport closure are accepted. No target is opened during preflight.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
TARGET = {'bytes': 114872,
          'sha256': 'c050bafec41ab3ad88c29241a8af3dd595c28ed4ad737b0e925f32d7a8065130'}
PRODUCTION = {'common.py', 'docker_backend.py', 'executor.py', 'control.py',
              'proof.py', 'run.py', 'configure.py', 'CONTROL_METHOD.md', 'IMAGE_PROFILE.json'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON constant'))


def read(path, cap, expected=None, *, allow_empty=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and (0 if allow_empty else 1) <= before.st_size <= cap,
             'Bounded ordinary singly linked metadata file required')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        need(len(body) == before.st_size
             and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
             'Metadata changed during capture')
    need(expected is None or digest(body) == expected, 'Frozen metadata identity changed')
    return body


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def write(path, value):
    body = encoded(value)
    need(len(body) <= 1048576, 'Bounded one-MiB result metadata')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fchmod(stream.fileno(), 0o600); os.fsync(stream.fileno())
    return digest(body)


def require_remaining(began, seconds, *, clock=time.monotonic):
    """Admit a phase only with its complete minimum window still available.

    These are remaining-time gates under one 600-second deadline, not new
    per-phase clocks. Unused time stays in the same original outer allowance.
    """
    remaining = began + 600 - clock()
    need(type(seconds) in (int, float) and 0 < seconds <= 600 and remaining >= seconds,
         'Full minimum phase window must fit the unchanged outer deadline')
    return remaining


def load_sources(source_sha256):
    body = read(HERE / 'SOURCE.json', 65536)
    need(digest(body)['sha256'] == source_sha256, 'Exact selected source closure')
    source = decode(body)
    need(set(source) == {'schema', 'candidate_id', 'files', 'predecessors', 'qualification'}
         and source['schema'] == 'neural031_runtime_qualification_source_v1'
         and source['candidate_id'] == 'NEURAL-031'
         and set(source['files']) == PRODUCTION, 'Complete fixed source roster')
    bodies = {}
    for name, pin in source['files'].items():
        need(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'Exact source descriptor')
        bodies[name] = read(HERE / name, 262144, pin)
    modules = {}
    # Execute only authenticated captured source, never the participant body.
    for name in ('common', 'docker_backend', 'executor', 'proof'):
        module = types.ModuleType(name)
        module.__file__ = str(HERE / (name + '.py'))
        sys.modules[name] = module
        exec(compile(bodies[name + '.py'], module.__file__, 'exec'), module.__dict__)
        modules[name] = module
    return source, bodies, modules


def validate_plan(plan, source_sha256):
    need(type(plan) is dict and set(plan) == {'schema', 'candidate_id', 'kind',
         'source_sha256', 'image_id', 'docker_binary', 'socket', 'output_root',
         'store_root', 'targets', 'image_inventory_review', 'method_review'},
         'Exact finite control plan fields')
    need(plan['schema'] == 'neural031_full40_fixed_control_plan_v1'
         and plan['candidate_id'] == 'NEURAL-031' and plan['kind'] == 'fixed_ratio_one'
         and plan['source_sha256'] == source_sha256 and plan['image_id'] == IMAGE,
         'Selected complete fixed control, source and immutable image')
    for key in ('docker_binary', 'socket', 'output_root', 'store_root'):
        value = plan[key]
        need(type(value) is str and os.path.isabs(value)
             and '\n' not in value and '\x00' not in value and ',' not in value,
             'Unambiguous absolute operator path')
    target = plan['targets']
    need(type(target) is dict and set(target) == {'path', 'bytes', 'sha256'}
         and type(target['path']) is str and os.path.isabs(target['path'])
         and {k: target[k] for k in ('bytes', 'sha256')} == TARGET,
         'Reuse the accepted exact private target without early stat or open')
    for key in ('image_inventory_review', 'method_review'):
        item = plan[key]
        need(type(item) is dict and set(item) == {'bytes', 'sha256'}
             and type(item['bytes']) is int and 0 < item['bytes'] <= 262144
             and type(item['sha256']) is str and len(item['sha256']) == 64
             and all(c in '0123456789abcdef' for c in item['sha256']),
             'Exact source-local reviewed metadata descriptor, with no caller path')
    return plan


def verify_runtime_reports(records, prefix, journal_root, proof, expected_commands,
                           capture_argv, decode_capture, prediction_pins):
    """Join forty runtime reports and captured outputs before private access.

    Captures occur in the running container's namespace. The exact captured
    bytes, not a claim of an atomic paused-filesystem snapshot, are committed
    only after the subsequent pause, inspection, removal and absence checks.
    """
    need(type(records) in (list, tuple) and len(records) == len(expected_commands) == 441,
         'All 441 normal transport commands required')
    need(type(prediction_pins) is list and len(prediction_pins) == 40,
         'Forty completed context prediction identities')
    def captured(descriptor, cap, *, empty=False):
        need(type(descriptor) is dict and set(descriptor) == {'path', 'bytes', 'sha256'},
             'Exact private journal descriptor')
        relative = descriptor['path']
        need(type(relative) is str and len(Path(relative).parts) == 1
             and Path(relative).name == relative and relative not in ('.', '..'),
             'Owned flat journal path')
        return read(Path(journal_root) / relative, cap,
                    {key: descriptor[key] for key in ('bytes', 'sha256')}, allow_empty=empty)
    reports = []
    for index, record in enumerate(records, 1):
        need(record['sequence'] == index and record['exit_code'] == 0 and record['error_type'] is None
             and record['direct_child_reaped'] is True and record['process_group_absent'] is True
             and record['simulated'] is False and record['scope'] == 'actual_owned_cli',
             'Every successful real command must close its owned process group')
        intent = decode(captured(record['intent'], 4096))
        result = decode(captured(record['result'], 4096))
        argv = intent['argv']
        need(intent['schema'] == 'neural031_cli_intent_v1' and intent['sequence'] == index
             and argv == prefix + expected_commands[index - 1],
             'Exact image/context/capture/removal/final-absence command order')
        need(result['schema'] == 'neural031_cli_result_v1' and result['intent'] == record['intent']
             and result['stdout'] == record['stdout'] and result['stderr'] == record['stderr']
             and result['argv_sha256'] == digest(encoded(argv))['sha256']
             and result['returncode'] == 0 and result['error_type'] is None
             and result['direct_child_reaped'] is True and result['group_absent'] is True
             and result['stream_close_errors'] == [] and result['scope'] == 'actual_owned_cli',
             'Exact saved intent, streams and successful real CLI closure')
        raw = captured(record['stdout'], intent['stdout_cap'], empty=True)
        captured(record['stderr'], 4096, empty=True)
        args = argv[len(prefix):]
        if args[:2] == ['ps', '--all']:
            need(not raw.strip(), 'Every saved absence response must be empty')
        if args[:3] == ['exec', '--user', '65534:65534']:
            if args[4:] == ['/usr/local/bin/python', '-I', '-B', '/program/submission.py',
                 '--input', '/input/data.npz', '--manifest', '/input/manifest.json',
                 '--output', '/output/predictions.json']:
                need(not reports or 'captured_prediction' in reports[-1],
                     'Finish each captured-output join before the next participant')
                need(0 < len(raw) <= 4096, 'Bounded fixed runtime report')
                report = proof.validate_probe(decode(raw))
                reports.append({'name': args[3], 'stdout': record['stdout'], 'report': report})
            else:
                need(args[4:] == capture_argv and reports and reports[-1]['name'] == args[3]
                     and 'captured_prediction' not in reports[-1],
                     'Exactly one trusted namespace capture after its participant')
                captured_pin = digest(decode_capture(raw))
                need(captured_pin == prediction_pins[len(reports) - 1],
                     'Saved namespace capture must equal committed context prediction')
                reports[-1].update({'capture_stdout': record['stdout'],
                                    'captured_prediction': captured_pin,
                                    'capture_scope': 'bytes_observed_before_pause_committed_after_absence'})
    need(len(reports) == 40 and len({r['name'] for r in reports}) == 40
         and all('captured_prediction' in report for report in reports),
         'Forty distinct successful participant reports and matching namespace captures')
    return reports


def expected_commands(batch, root, backend, module):
    def absent(name):
        return ['ps', '--all', '--no-trunc', '--filter', 'name=^/' + name + '$',
                '--format', '{{.ID}}']
    commands = [['image', 'inspect', IMAGE]]
    for index, row in enumerate(batch['contexts']):
        fold, view = index // 2, ('baseline', 'neural')[index % 2]
        need(row['fold'] == fold and row['view'] == view, 'Complete ordered paired contexts')
        name = row['container_name']
        context = root / 'batch/contexts' / f'fold{fold:02d}-{view}'
        spec = {'name': name, 'image': IMAGE, 'batch': name.split('-')[1],
                'mounts': [(str(context / 'data.npz'), '/input/data.npz'),
                           (str(context / 'manifest.json'), '/input/manifest.json'),
                           (str(root / 'batch/submission.py'), '/program/submission.py')]}
        commands.extend([absent(name), backend.create_argv(spec), ['start', name],
                         ['container', 'inspect', name],
                         ['exec', '--user', '65534:65534', name, *module.CANDIDATE],
                         ['exec', '--user', '65534:65534', name, *module.CAPTURE],
                         ['pause', name], ['container', 'inspect', name],
                         ['rm', '--force', name], absent(name)])
    commands.extend(absent(row['container_name']) for row in batch['contexts'])
    return commands


def perform(plan, source_sha256, source, bodies, modules, began):
    root = Path(plan['output_root'])
    need(not root.exists() and not root.is_symlink() and root.parent.is_dir(),
         'Fresh operator result root with existing parent')
    root.mkdir(mode=0o700); root.chmod(0o700)
    write(root / 'INTENT.json', {'schema': 'neural031_full40_fixed_control_intent_v1',
          'plan': plan, 'source_sha256': source_sha256,
          'outer_wall_allowance_seconds': 600, 'original_batch_seconds': 480,
          'failure_only_cleanup_seconds': 10, 'automatic_retry': False,
          'historical_costs_reset': False, 'private_target_body_reads': 0})
    backend = None
    try:
        for key, name in (('image_inventory_review', 'IMAGE_PROFILE.json'),
                          ('method_review', 'CONTROL_METHOD.md')):
            need(plan[key] == source['files'][name] == digest(bodies[name]),
                 'Use only already captured source-local review documents')
        backend = modules['docker_backend'].DockerBackend(
            journal_root=root / 'transport', docker_config=root / 'docker-config',
            docker_binary=plan['docker_binary'], socket=plan['socket'])
        method = {'schema': 'neural031_frozen_program_method_v1',
                  'program': source['files']['control.py'],
                  'method': 'Fixed ratio one for every requested row, with no fitting, selection or use of feature values.',
                  'same_method_across_views': True, 'training_only_selection': True,
                  'image_inventory_review_sha256': plan['image_inventory_review']['sha256'],
                  'method_review_sha256': plan['method_review']['sha256']}
        write(root / 'METHOD.json', method)
        require_remaining(began, 570)
        batch = modules['executor'].execute(plan['store_root'], HERE / 'control.py',
                    root / 'batch', IMAGE, method, backend=backend)
        need(batch['status'] == 'complete' and len(batch['contexts']) == 40
             and batch['producer_absence_observed_for_all_contexts'] is True,
             'Complete closed original programme batch')
        require_remaining(began, 90)
        journal = backend.journal_summary()
        need(journal['actual_cli_closure_complete'] is True and journal['evidence_complete'] is True
             and journal['command_count'] == journal['record_count'] == 441,
             'Complete source-bound real transport journal before scoring')
        commands = expected_commands(batch, root, backend, modules['docker_backend'])
        reports = verify_runtime_reports(backend.journal_records, backend.prefix,
                                         root / 'transport', modules['proof'], commands,
                                         modules['docker_backend'].CAPTURE,
                                         modules['docker_backend'].prediction_from_frame,
                                         [row['prediction'] for row in batch['contexts']])
        need([r['name'] for r in reports] == [r['container_name'] for r in batch['contexts']],
             'Actual runtime reports join every ordered batch context')
        common = modules['common']
        _, endpoint, scorer = common.dependencies()
        support = decode(read(root / 'batch/collection/support.json', 131072))
        bundle = decode(read(root / 'batch/collection/submission.json', 6291456))
        coverage = modules['proof'].validate_constant_predictions(endpoint, bundle, support)
        public_pin = write(root / 'PUBLIC_BARRIER.json', {
            'schema': 'neural031_fixed_control_public_barrier_v1', 'coverage': coverage,
            'all_40_probe_reports': reports, 'real_closed_transport_commands': 441,
            'journal': journal,
            'all_producers_absent': True, 'private_target_body_reads': 0,
            'batch_receipt': digest(read(root / 'batch/BATCH.json', 1048576))})
        # First target body read is inside this unchanged protected scorer,
        # after complete public validation and actual participant closure.
        require_remaining(began, 60)
        score = scorer.run(root / 'batch/collection/support.json',
                           root / 'batch/collection/submission.json',
                           plan['targets']['path'], plan['targets']['sha256'])
        score_pin = write(root / 'SCORE.json', score)
        result = modules['proof'].validate_constant_score(score)
        need(time.monotonic() - began < 600, 'Complete outer operation inside its admitted allowance')
        write(root / 'COMPLETE.json', {'schema': 'neural031_full40_fixed_control_complete_v1',
              'status': 'engineering_control_complete_pending_independent_review',
              'result': result, 'coverage': coverage, 'public_barrier': public_pin,
              'score': score_pin, 'source_sha256': source_sha256,
              'outer_wall_seconds': time.monotonic() - began,
              'native_runtime_qualification_by_this_driver': False,
              'scientific_or_AI_qualification': False})
    except BaseException as error:
        write(root / 'FAILED.json', {'schema': 'neural031_full40_fixed_control_failure_v1',
              'status': 'failed_preserved', 'error_type': type(error).__name__,
              'error': str(error)[:2048], 'automatic_retry': False,
              'outer_wall_seconds': time.monotonic() - began,
              'absence_not_inferred_from_host_exit': True})
        raise


def main():
    began = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args()
    # A hard stop has unknown closure; an intent without COMPLETE is never success.
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, max(.001, began + 600 - time.monotonic()))
    try:
        raw = read(args.plan, 65536)
        need(digest(raw)['sha256'] == args.plan_sha256, 'Exact selected operator plan')
        plan = validate_plan(decode(raw), args.source_sha256)
        source, bodies, modules = load_sources(args.source_sha256)
        perform(plan, args.source_sha256, source, bodies, modules, began)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
