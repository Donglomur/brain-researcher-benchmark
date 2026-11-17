"""Independent generated controls; no Docker, real payloads or host probes.

The 441-command fixture uses the real journal serializer with an in-memory
storage sink. Its successful process fields are invented test values, never
runtime observations. Full-panel arithmetic uses the original endpoint.
"""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load('qualification_run', HERE / 'run.py')
proof = load('qualification_proof', HERE / 'proof.py')
backend = load('qualification_backend', HERE / 'docker_backend.py')
endpoint = load('qualification_original_endpoint', HERE.parent / 'ratio-scoring-v1/endpoint.py')


def probe():
    return {'schema': 'neural031_fixed_control_runtime_probe_v1',
            'python': '3.12.8', 'numpy': '2.2.6', 'uid': 65534, 'gid': 65534,
            'fresh_tmp_marker_before_creation': True, 'empty_output_before_prediction': True,
            'write_denial_errnos': {'root': 30, 'data': 30, 'manifest': 30, 'program': 30},
            'network_denial_errno': 101, 'network_probe_timeout_seconds': 0.25,
            'scope': 'observed_fixed_probes_not_universal_isolation_proof'}


def capture_frame(body):
    file_signature = [1, 2, 0o100600, 1, len(body), 3, 4]
    directory_signature = [1, 3, 0o40700, 2, 128, 3, 4]
    return run.encoded({'schema': 'neural031_running_output_capture_v1',
        'capture_while_paused': False,
        'payload': {**run.digest(body), 'base64': base64.b64encode(body).decode('ascii')},
        'file_before': file_signature, 'file_after': file_signature,
        'name_after': file_signature, 'directory_before': directory_signature,
        'directory_after': directory_signature})


def full_panel():
    support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
               'folds': [], 'request_rows': 774, 'query_targets_included': False}
    bundle = {'schema': 'neural031_ordinary_submission_bundle_v1',
              'candidate_id': 'NEURAL-031', 'outputs': []}
    for fold in range(20):
        ids = list(range(fold, 774, 20))
        item = {'fold': fold, 'rowids': ids, 'views': {}}
        for view in ('baseline', 'neural'):
            desc = run.digest(f'generated-{fold}-{view}'.encode())
            item['views'][view] = {'data': desc, 'manifest': desc}
            bundle['outputs'].append({'schema': 'neural031_ordinary_prediction_v1',
                'candidate_id': 'NEURAL-031', 'fold': fold, 'view': view,
                'input_manifest': desc, 'rows': [{'row_id': row, 'prediction': 1.0} for row in ids]})
        support['folds'].append(item)
    targets = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031',
               'mice': list(endpoint.MICE), 'rows': []}
    for row in range(1143):
        targets['rows'].append({'rowid': row, 'mouse': row % 20,
            'y': (0.0 if row % 2 else 2.0) if row < 731 else None,
            'request': int(row < 774), 'observed': int(row < 731),
            'baseline_new': row % 2, 'compartment': row % 2})
    return support, bundle, targets


def journal_fixture(root, prediction_bodies=None):
    transport = backend.DockerBackend(command=lambda *_: b'', docker_binary='/generated/docker',
                                      socket='/generated/socket')
    batch = {'status': 'complete', 'producer_absence_observed_for_all_contexts': True,
             'contexts': [{'fold': fold, 'view': view,
                           'container_name': 'n031-' + 'a' * 24 + f'-{fold:02d}-' + suffix}
                          for fold in range(20) for view, suffix in (('baseline', 'b'), ('neural', 'n'))]}
    predictions = {}
    for row in batch['contexts']:
        body = (prediction_bodies[(row['fold'], row['view'])] if prediction_bodies is not None
                else run.encoded({'generated_fold': row['fold'], 'generated_view': row['view']}))
        row['prediction'] = run.digest(body)
        predictions[row['container_name']] = body
    commands = run.expected_commands(batch, root, transport, backend)
    # Exercise real Journal.begin/finish serialization with a bounded memory
    # sink. No subprocess or filesystem publication is performed by this seam.
    journal = backend.CommandJournal.__new__(backend.CommandJournal)
    journal.root = root / 'transport'
    journal.calls = journal.granted = journal.written = 0
    files = {}
    def put(name, body, cap):
        assert len(body) <= cap and name not in files
        journal.written += len(body)
        assert journal.written <= 2 * 1024 * 1024
        files[name] = body
        return {'path': name, **run.digest(body)}
    journal.put = put
    records = []
    for args in commands:
        is_capture = args[:3] == ['exec', '--user', '65534:65534'] and args[4:] == backend.CAPTURE
        cap = 65536 if args[0] == 'image' or args[:2] == ['container', 'inspect'] else (
              262144 if is_capture else 16384 if args[0] == 'exec' else 4096)
        argv = transport.prefix + args
        label, intent = journal.begin(argv, cap, 1.0, 480.0)
        stdout = (capture_frame(predictions[args[3]]) if is_capture else run.encoded(probe())
                  if args[0] == 'exec' else b'' if args[0] == 'ps' else b'{}')
        result = {'scope': 'actual_owned_cli', 'argv_sha256': run.digest(run.encoded(argv))['sha256'],
                  'started_monotonic': 1.0, 'completed_monotonic': 2.0, 'deadline_monotonic': 480.0,
                  'pid': 10000 + journal.calls, 'process_started': True, 'returncode': 0,
                  'direct_child_reaped': True, 'group_absent': True, 'cleanup': [],
                  'stream_close_errors': [], 'stdout_cap': cap,
                  'observed_bytes': {'stdout': len(stdout), 'stderr': 0},
                  'error_type': None, 'error': None, 'absence_scope': 'generated test values only'}
        records.append(journal.finish(label, intent, stdout, b'', result))
    return transport, batch, commands, records, files, journal


def reader(root, files, extra=None, opened=None):
    extra = extra or {}
    def read(path, cap, expected=None, *, allow_empty=False):
        path = Path(path)
        if opened is not None:
            opened.append(str(path))
        if str(path) in extra:
            body = extra[str(path)]
        else:
            assert path.parent == root / 'transport', ('unexpected body read', str(path))
            body = files[path.name]
        if not (0 if allow_empty else 1) <= len(body) <= cap:
            raise ValueError('fixture bounded read')
        if expected is not None and run.digest(body) != expected:
            raise ValueError('fixture pin mismatch')
        return body
    return read


def replace_result(record, files, field, value):
    original = record['result']['path']
    result = run.decode(files[original])
    result[field] = value
    files[original] = run.encoded(result)
    record['result'] = {'path': original, **run.digest(files[original])}


def perform_fixture(root, *, wrong_prediction=False, wrong_review=False, wrong_capture=False):
    support, bundle, targets = full_panel()
    if wrong_prediction:
        bundle['outputs'][-1]['rows'][-1]['prediction'] = 1.5
    # The integration fixture carries the same generated prediction bytes
    # through capture, BATCH identity and the collected scoring bundle.
    prediction_bodies = {(row['fold'], row['view']): run.encoded(row) for row in bundle['outputs']}
    transport, batch, commands, records, files, _ = journal_fixture(root, prediction_bodies)
    if wrong_capture:
        index = max(i for i, args in enumerate(commands)
                    if args[:3] == ['exec', '--user', '65534:65534'] and args[4:] == backend.CAPTURE)
        record = records[index]
        body = capture_frame(b'{"different_generated_prediction":true}\n')
        files[record['stdout']['path']] = body
        record['stdout'] = {'path': record['stdout']['path'], **run.digest(body)}
        replace_result(record, files, 'stdout', record['stdout'])
    bodies = {'IMAGE_PROFILE.json': b'generated image profile',
              'CONTROL_METHOD.md': b'generated method review', 'control.py': b'generated fixed control'}
    source = {'files': {name: run.digest(body) for name, body in bodies.items()}}
    plan = {'schema': 'neural031_full40_fixed_control_plan_v1', 'candidate_id': 'NEURAL-031',
            'kind': 'fixed_ratio_one', 'source_sha256': '0' * 64, 'image_id': run.IMAGE,
            'docker_binary': '/generated/docker', 'socket': '/generated/socket',
            'output_root': str(root), 'store_root': '/generated/public',
            'targets': {'path': '/generated/private/targets.json', **run.TARGET},
            'image_inventory_review': dict(source['files']['IMAGE_PROFILE.json']),
            'method_review': dict(source['files']['CONTROL_METHOD.md'])}
    if wrong_review:
        plan['method_review']['sha256'] = 'f' * 64
    order, scored, constructed = [], [], []
    transport._fixture_records = tuple(records)
    # Do not instantiate a production Docker backend. This explicit generated
    # object supplies only the already exercised real argv construction method.
    selected = types.SimpleNamespace(prefix=transport.prefix, journal_records=tuple(records),
        create_argv=transport.create_argv,
        journal_summary=lambda: {'actual_cli_closure_complete': True, 'evidence_complete': True,
                                'command_count': 441, 'record_count': 441})
    def factory(**kwargs):
        constructed.append(kwargs)
        return selected
    def execute(*args, **kwargs):
        assert kwargs['backend'] is selected
        order.append('producer_closed')
        return batch
    def score(*args):
        assert 'PUBLIC_BARRIER.json' in order and 'producer_closed' in order
        assert args[2:] == (plan['targets']['path'], plan['targets']['sha256'])
        scored.append(args)
        order.append('private_score')
        return endpoint.score(support, bundle, targets)
    modules = {'docker_backend': types.SimpleNamespace(DockerBackend=factory, CANDIDATE=backend.CANDIDATE,
                    CAPTURE=backend.CAPTURE, prediction_from_frame=backend.prediction_from_frame),
               'executor': types.SimpleNamespace(execute=execute), 'proof': proof,
               'common': types.SimpleNamespace(dependencies=lambda: (None, endpoint, types.SimpleNamespace(run=score)))}
    extra = {str(root / 'batch/collection/support.json'): run.encoded(support),
             str(root / 'batch/collection/submission.json'): run.encoded(bundle),
             str(root / 'batch/BATCH.json'): run.encoded(batch)}
    def write(path, value):
        order.append(Path(path).name)
        return run.digest(run.encoded(value))
    return plan, source, bodies, modules, reader(root, files, extra), write, order, scored, constructed


class QualificationTests(unittest.TestCase):
    def test_complete_real_journal_abi_and_441_command_join(self):
        root = Path('/generated/attempt')
        transport, batch, commands, records, files, journal = journal_fixture(root)
        with mock.patch.object(run, 'read', reader(root, files)):
            reports = run.verify_runtime_reports(tuple(records), transport.prefix,
                root / 'transport', proof, commands, backend.CAPTURE, backend.prediction_from_frame,
                [row['prediction'] for row in batch['contexts']])
        self.assertEqual(len(reports), 40)
        self.assertEqual([r['name'] for r in reports], [r['container_name'] for r in batch['contexts']])
        self.assertEqual(journal.calls, 441)
        self.assertLess(journal.granted, backend.JOURNAL_CAP)
        self.assertTrue(all('captured_prediction' in report for report in reports))
        self.assertEqual(sum(args[0] == 'exec' for args in commands), 80)
        self.assertFalse(any(args[0] == 'cp' for args in commands))

    def test_missing_final_absence_and_reordered_commands_refused(self):
        root = Path('/generated/attempt')
        transport, batch, commands, records, files, _ = journal_fixture(root)
        captures = (backend.CAPTURE, backend.prediction_from_frame,
                    [row['prediction'] for row in batch['contexts']])
        with mock.patch.object(run, 'read', reader(root, files)):
            with self.assertRaises(ValueError):
                run.verify_runtime_reports(records[:-1], transport.prefix, root / 'transport', proof, commands, *captures)
            wrong = list(commands); wrong[1], wrong[11] = wrong[11], wrong[1]
            with self.assertRaises(ValueError):
                run.verify_runtime_reports(records, transport.prefix, root / 'transport', proof, wrong, *captures)

    def test_zero_exit_after_cli_error_or_unknown_absence_refused(self):
        root = Path('/generated/attempt')
        transport, batch, commands, records, files, _ = journal_fixture(root)
        captures = (backend.CAPTURE, backend.prediction_from_frame,
                    [row['prediction'] for row in batch['contexts']])
        for field, value in [('error_type', 'TimeoutError'), ('group_absent', False),
                             ('direct_child_reaped', False), ('stream_close_errors', ['OSError'])]:
            altered = copy.deepcopy(records); payload = dict(files)
            replace_result(altered[-1], payload, field, value)
            with self.subTest(field=field), mock.patch.object(run, 'read', reader(root, payload)):
                with self.assertRaises(ValueError):
                    run.verify_runtime_reports(altered, transport.prefix, root / 'transport', proof, commands, *captures)

    def test_private_journal_path_escape_rejected_before_read(self):
        root = Path('/generated/attempt')
        transport, batch, commands, records, files, _ = journal_fixture(root)
        records[0]['intent']['path'] = '../private-targets.json'
        opened = []
        with mock.patch.object(run, 'read', reader(root, files, opened=opened)):
            with self.assertRaises(ValueError):
                run.verify_runtime_reports(records, transport.prefix, root / 'transport', proof, commands,
                    backend.CAPTURE, backend.prediction_from_frame, [row['prediction'] for row in batch['contexts']])
        self.assertEqual(opened, [])

    def test_linux_probe_errno_and_profile_not_host_aliases(self):
        self.assertEqual(proof.validate_probe(probe())['network_denial_errno'], 101)
        for key, value in [('network_denial_errno', 51), ('network_denial_errno', None),
                           ('python', '3.11.6'), ('numpy', '1.26.3'),
                           ('fresh_tmp_marker_before_creation', False),
                           ('empty_output_before_prediction', False), ('uid', 0)]:
            wrong = probe(); wrong[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                proof.validate_probe(wrong)
        wrong = probe(); wrong['write_denial_errnos']['data'] = 0
        with self.assertRaises(ValueError): proof.validate_probe(wrong)

    def test_complete_original_scorer_control_and_unavailable_coverage(self):
        support, bundle, targets = full_panel()
        coverage = proof.validate_constant_predictions(endpoint, bundle, support)
        self.assertEqual(coverage['predictions'], 1548)
        score = endpoint.score(support, bundle, targets)
        result = proof.validate_constant_score(score)
        self.assertEqual((result['observed_rows'], result['requested_unavailable_rows']), (731, 43))
        self.assertEqual(score['macro']['no_change_mae'], 1.0)
        # An unavailable target still requires its prediction; omission fails.
        bundle['outputs'][-1]['rows'].pop()
        with self.assertRaises(ValueError): proof.validate_constant_predictions(endpoint, bundle, support)

    def test_nonconstant_output_and_inconsistent_macro_rejected(self):
        support, bundle, targets = full_panel()
        bundle['outputs'][0]['rows'][0]['prediction'] = 1.5
        with self.assertRaises(ValueError): proof.validate_constant_predictions(endpoint, bundle, support)
        bundle['outputs'][0]['rows'][0]['prediction'] = 1.0
        score = endpoint.score(support, bundle, targets)
        score['macro']['baseline_minus_neural_mae'] = 1.0
        with self.assertRaises(ValueError): proof.validate_constant_score(score)

    def test_arbitrary_review_paths_rejected_before_target_access(self):
        plan = {'schema': 'neural031_full40_fixed_control_plan_v1', 'candidate_id': 'NEURAL-031',
                'kind': 'fixed_ratio_one', 'source_sha256': '0' * 64, 'image_id': run.IMAGE,
                'docker_binary': '/generated/docker', 'socket': '/generated/socket',
                'output_root': '/generated/output', 'store_root': '/generated/public',
                'targets': {'path': '/generated/private/targets.json', **run.TARGET},
                'image_inventory_review': run.digest(b'generated image profile'),
                'method_review': run.digest(b'generated method review')}
        run.validate_plan(plan, '0' * 64)
        for path in ('/generated/private/targets.json', '/generated/public/../private/targets.json',
                     '/generated/alias/targets.json'):
            altered = copy.deepcopy(plan)
            altered['method_review']['path'] = path
            with self.subTest(path=path), mock.patch.object(run, 'read', side_effect=AssertionError('body opened')):
                with self.assertRaises(ValueError): run.validate_plan(altered, '0' * 64)

    def test_complete_public_barrier_precedes_original_private_score(self):
        with tempfile.TemporaryDirectory(prefix='neural031-independent-generated-') as temp:
            root = Path(temp) / 'attempt'
            plan, source, bodies, modules, read, write, order, scored, _ = perform_fixture(root)
            run.validate_plan(plan, '0' * 64)
            with mock.patch.object(run, 'read', read), mock.patch.object(run, 'write', write):
                run.perform(plan, '0' * 64, source, bodies, modules, time.monotonic())
            self.assertEqual(len(scored), 1)
            self.assertLess(order.index('producer_closed'), order.index('PUBLIC_BARRIER.json'))
            self.assertLess(order.index('PUBLIC_BARRIER.json'), order.index('private_score'))
            self.assertEqual(order[-1], 'COMPLETE.json')

    def test_last_prediction_failure_prevents_any_private_score(self):
        with tempfile.TemporaryDirectory(prefix='neural031-independent-generated-') as temp:
            root = Path(temp) / 'attempt'
            plan, source, bodies, modules, read, write, order, scored, _ = perform_fixture(root, wrong_prediction=True)
            with mock.patch.object(run, 'read', read), mock.patch.object(run, 'write', write):
                with self.assertRaises(ValueError):
                    run.perform(plan, '0' * 64, source, bodies, modules, time.monotonic())
            self.assertEqual(scored, [])
            self.assertNotIn('PUBLIC_BARRIER.json', order)
            self.assertNotIn('COMPLETE.json', order)
            self.assertEqual(order[-1], 'FAILED.json')

    def test_saved_capture_mismatch_prevents_private_score(self):
        with tempfile.TemporaryDirectory(prefix='neural031-generated-capture-join-') as temp:
            root = Path(temp) / 'attempt'
            plan, source, bodies, modules, read, write, order, scored, _ = perform_fixture(root, wrong_capture=True)
            with mock.patch.object(run, 'read', read), mock.patch.object(run, 'write', write):
                with self.assertRaisesRegex(ValueError, 'capture must equal committed'):
                    run.perform(plan, '0' * 64, source, bodies, modules, time.monotonic())
            self.assertEqual(scored, [])
            self.assertNotIn('PUBLIC_BARRIER.json', order)
            self.assertNotIn('COMPLETE.json', order)
            self.assertEqual(order[-1], 'FAILED.json')

    def test_wrong_source_local_review_fails_before_backend_or_body_read(self):
        with tempfile.TemporaryDirectory(prefix='neural031-independent-generated-') as temp:
            root = Path(temp) / 'attempt'
            plan, source, bodies, modules, _, write, order, scored, constructed = perform_fixture(root, wrong_review=True)
            with (mock.patch.object(run, 'read', side_effect=AssertionError('unexpected body read')),
                  mock.patch.object(run, 'write', write)):
                with self.assertRaises(ValueError):
                    run.perform(plan, '0' * 64, source, bodies, modules, time.monotonic())
            self.assertEqual(constructed, [])
            self.assertEqual(scored, [])
            self.assertEqual(order[-1], 'FAILED.json')


    def test_remaining_time_gates_preserve_whole_batch_and_private_barrier(self):
        # Every gate uses the same initial clock: equality admits the entire
        # minimum window; even a small shortfall refuses without clock reset.
        began = 1000.0
        for seconds in (570, 90, 60):
            now = began + 600 - seconds
            with self.subTest(seconds=seconds):
                self.assertEqual(run.require_remaining(began, seconds, clock=lambda: now), seconds)
                with self.assertRaises(ValueError):
                    run.require_remaining(began, seconds, clock=lambda: now + 0.001)
        for seconds in (True, False, 0, -1, 601, float('nan'), float('inf'), -float('inf')):
            with self.subTest(invalid_seconds=seconds), self.assertRaises(ValueError):
                run.require_remaining(began, seconds, clock=lambda: began)
        # Exercise the actual perform call sites rather than just the helper.
        # The injected clock fails exactly one phase admission. All journal,
        # output, probe and scorer fixtures remain generated and in memory.
        actual_gate = run.require_remaining
        for failed_gate, expected_calls in ((570, [570]), (90, [570, 90]), (60, [570, 90, 60])):
            with self.subTest(failed_gate=failed_gate), tempfile.TemporaryDirectory(
                    prefix='neural031-independent-generated-timing-') as temp:
                root = Path(temp) / 'attempt'
                plan, source, bodies, modules, read, write, order, scored, _ = perform_fixture(root)
                gate_calls = []
                def controlled_gate(original_began, seconds):
                    gate_calls.append(seconds)
                    self.assertEqual(original_began, began)
                    elapsed = 600 - seconds + 0.001 if seconds == failed_gate else 0
                    return actual_gate(original_began, seconds, clock=lambda: began + elapsed)
                with (mock.patch.object(run, 'read', read), mock.patch.object(run, 'write', write),
                      mock.patch.object(run, 'require_remaining', side_effect=controlled_gate)):
                    with self.assertRaisesRegex(ValueError, 'Full minimum phase window'):
                        run.perform(plan, '0' * 64, source, bodies, modules, began)
                self.assertEqual(gate_calls, expected_calls)
                self.assertEqual(scored, [])
                self.assertNotIn('private_score', order)
                self.assertNotIn('COMPLETE.json', order)
                self.assertEqual(order[-1], 'FAILED.json')
                self.assertEqual('producer_closed' in order, failed_gate != 570)
                self.assertEqual('PUBLIC_BARRIER.json' in order, failed_gate == 60)



if __name__ == '__main__':
    unittest.main(verbosity=2)
