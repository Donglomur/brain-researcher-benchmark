"""Generated boundary controls; original numerical payloads are never opened."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run

WRITTEN = 0


def written(path, body):
    global WRITTEN
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)
    if WRITTEN > 32 * 1024**2:
        raise AssertionError('Cumulative generated fixture allocation')


def process_record():
    return {'natural_exit': True, 'exit_code': 0, 'process_reaped': True, 'process_group_absent': True,
            'streams_closed': True, 'timed_out': False, 'kill_sent': False, 'error_type': None}


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (HERE / 'SOURCE.json').read_bytes()
        cls.source = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        cls.b = run.load_bridge(cls.source)
        cls.manifest, cls.captured = cls.b.source(cls.source)
        cls.original = cls.b.original(cls.captured)
        cls.temp = tempfile.TemporaryDirectory(prefix='neural052-generated-')
        cls.root = Path(cls.temp.name).resolve()
        import numpy
        print(json.dumps({'python': sys.version, 'numpy': numpy.__version__, 'scope': 'generated_controls_only'}))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        print(json.dumps({'generated_fixture_write_bytes': WRITTEN, 'generated_fixture_retained_bytes': 0,
                          'authentic_numerical_body_reads': 0, 'native_executions': 0, 'model_or_provider_calls': 0}))

    def case(self, name):
        value = self.root / name
        value.mkdir()
        return value

    def pub(self, path, value):
        body = value if type(value) is bytes else self.b.encode(value)
        written(path, body)
        return self.b.pin(body)

    def closed(self, root, external, selection_pin):
        b = self.b
        common, policy, observer, process, binding, source = self.original
        scope = binding['scope']
        program = self.pub(root / 'commitment/program.py', b'# generated inert source\n')
        outputs = {name: self.pub(root / 'candidate' / name, body)
                   for name, body in {'result.json': b'{"generated":true}\n', 'METHODS.md': b'Generated prose.\n'}.items()}
        prepared = self.pub(root / 'VIEW_PREPARED.json', {'files': {
            str(Path(r['target']).relative_to('public')): common.only_pin(r) for r in binding['files'] if r['visibility'] == 'public'},
            'member_count': 14, 'primitive_files': 3, 'decoded': False})
        retired = self.pub(root / 'VIEW_RETIRED.json', {'schema': 'neural052_full3_public_retired_v1',
            'member_count': 14, 'primitive_files': 3, 'absent': True, 'parent_fsynced': True})
        commitment = self.pub(root / 'commitment/COMMITMENT.json', {'source': source, 'program': program,
            'scope': scope, 'before_any_public_signal_view': True})
        support = {'task_id': 'NEURAL-052', 'status': 'support_consistent_artifact_only', 'participants': ['01', '02', '03'],
            'total_rows': 3600, 'folds_per_person': 15, 'fixed_models': 4, 'shared_concept_draws': 1000,
            'private_reference_calls': 0, 'numerical_values_verified': False, 'scientific_qualification_added': False,
            'operator_entrypoint': 'neural052_full3_support_v1', 'export_manifest_sha256': binding['export_descriptor']['sha256'],
            'requires_observed_cli_exit_zero': True}
        support_pin = self.pub(root / 'admission/support.json', support)
        command = {'phase': 'generated', 'returncode': 0, 'error_type': None, 'observed_retained_bytes': 1, 'seconds': .01,
            'client_reaped': True, 'cleanup_complete': True, 'cleanup_before_original_cutoff': True,
            'owned_group_absence_observed': True, 'leader_exited_with_group_alive': False, 'group_probe_or_cleanup_error': None}
        native = {}
        for phase, phase_outputs in [('candidate', outputs), ('admission', {'support.json': support_pin})]:
            prefix = 'generated-' + phase
            value = {'phase': phase, 'source': source, 'status': 'captured', 'outputs': phase_outputs,
                'all_native_resources_closed': True, 'cli_reaped': True, 'producer_closed_before_capture': True,
                'recovery_may_be_required': False, 'attempt_prefix': prefix,
                'closures': [{'kind': kind, 'name': prefix + '-' + str(i), 'closed': True}
                             for i, kind in enumerate(('container', 'container', 'volume'))],
                'natural_exit': {'Status': 'exited', 'Running': False, 'Dead': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False},
                'command_metadata': [command]}
            native[phase] = self.pub(root / phase / 'NATIVE.json', value)
        sealed = self.pub(root / 'REPORT_COMMITTED.json', {'source': source, 'program': program, 'outputs': outputs,
            'candidate_native': native['candidate'], 'retirement': retired, 'whole_two_artifact_output_captured': True,
            'numerically_validated': False})
        handoff = self.pub(root / 'GRADE_HANDOFF.json', {'outputs': {name: dict(path=str(root / 'candidate' / name), **identity)
            for name, identity in outputs.items()}, 'export_descriptor': binding['export_descriptor'], 'scope': scope,
            'execution_authorized': False, 'scientific_reasoning_or_causality_or_SOTA_established': False})
        complete = self.pub(root / 'COMPLETE.json', {'source': source, 'status': 'complete_unqualified', 'scope': scope,
            'all_public_views_retired': True, 'complete_report_support_validated': True, 'numerical_grading_performed': False,
            'runtime_qualified': False, 'scientific_qualified': False, 'view_prepared': prepared, 'view_retirement': retired,
            'commitment': commitment, 'program': program, 'outputs': outputs, 'outputs_commitment': sealed,
            'candidate_native': native['candidate'], 'admission_native': native['admission'],
            'admission_output': support_pin, 'grade_handoff': handoff})
        external_pin = self.pub(external, {'schema': 'neural052_full3_external_v1', 'status': 'complete_unqualified',
            'source': source, 'selection': selection_pin, 'attempt': str(root), 'child': process_record(), 'complete': complete,
            'outputs': outputs, 'error_type': None, 'full3_source_scope': True, 'scientific_qualified': False,
            'runtime_qualified': False, 'numerical_grading_performed': False, 'nested_cli_and_native_recovery_may_be_required': False})
        return outputs, external_pin

    def test_original_source_and_complete_public_metadata(self):
        common, policy, observer, process, binding, source = self.original
        public = [r for r in binding['files'] if r['visibility'] == 'public']
        self.assertEqual((len(binding['files']), len(public), sum(r['bytes'] for r in public)), (64, 14, 71207593))
        self.assertEqual(binding['scope'], {'participants': ['01', '02', '03'], 'rows_per_person': 1200,
            'total_rows': 3600, 'folds_per_person': 15, 'fixed_models': 4, 'shared_concept_draws': 1000})
        self.assertEqual((common.RETAIN, common.READS, common.WRITES), (201326592, 512000000, 96000000))
        self.assertEqual(policy.whole(100), 1300)

    def test_real_original_fourteen_file_projection_and_retirement(self):
        common = self.original[0]
        directory = HERE / 'producer'
        body = self.captured[str(directory / 'controller.py')]
        controller = self.b.module('generated_projection', directory / 'controller.py', body, c=common)
        source = self.case('projection-source')
        output = self.case('projection-output')
        rows = []
        for i in range(14):
            name = 'public/input/generated-' + str(i) + '.bin'
            identity = self.pub(source / name, ('row-' + str(i)).encode())
            rows.append(dict(target=name, **identity))
        budget = common.Budget(output, 0, time.monotonic() + 30)
        original_save = common.save
        def counting(*args, **kwargs):
            global WRITTEN
            result = original_save(*args, **kwargs)
            WRITTEN += len(args[1])
            return result
        # Tiny generated fixtures do not certify a host's future native capacity.
        with patch.object(common, 'save', side_effect=counting), \
             patch.object(common.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10**12)):
            current, expected, receipt = controller.prepare(source, rows, output, budget)
            self.assertEqual(len(expected), 14)
            for name, identity in expected.items():
                self.assertEqual(self.b.pin((current / name).read_bytes()), identity)
            controller.retire(current, expected, output, budget)
        self.assertFalse(current.exists())

    def test_original_opaque_pair_capture_requires_both_files(self):
        filename = HERE / 'producer/output_bundle.py'
        bundle = self.b.module('generated_bundle', filename, self.captured[str(filename)])
        files = {name: dict(self.b.pin(body), base64=base64.b64encode(body).decode())
                 for name, body in {'result.json': b'{}', 'METHODS.md': b'Generated'}.items()}
        value = {'schema': 'neural052_opaque_capture_v1', 'kind': 'candidate', 'files': files}
        self.assertEqual(set(bundle.decode(self.b.encode(value), 'candidate')), {'result.json', 'METHODS.md'})
        del value['files']['METHODS.md']
        with self.assertRaises(ValueError):
            bundle.decode(self.b.encode(value), 'candidate')

    def test_actual_observer_admission_reuses_all_original_closure_checks(self):
        base = self.case('admission')
        root, external = base / 'producer', base / 'external.json'
        selection = {'output': str(root), 'repository': str(base)}
        selection_pin = self.b.pin(b'generated selection')
        outputs, external_pin = self.closed(root, external, selection_pin)
        admitted = self.b.admit_producer(self.original[0], self.original[2], self.original[4], selection,
            selection_pin, self.original[5], external, external_pin, process_record(), time.monotonic() + 30)
        self.assertEqual(admitted['outputs'], outputs)
        (root / 'candidate/METHODS.md').unlink()
        with self.assertRaises((ValueError, OSError)):
            self.b.admit_producer(self.original[0], self.original[2], self.original[4], selection,
                selection_pin, self.original[5], external, external_pin, process_record(), time.monotonic() + 30)

    def test_outer_actual_process_callback_precedes_original_admission(self):
        base = self.case('outer')
        output = base / 'outer'; output.mkdir()
        selection = {'output': str(base / 'producer'), 'repository': str(base), 'candidate_seconds': 2}
        identity = self.b.pin(b'generated selection')
        cfg = {'producer_selection': {'path': str(base / 'selection.json')}}
        calls = []
        def execute(argv, normal_end, cleanup_end, env):
            calls.append(argv)
            self.assertIn(str(HERE / 'producer/observe.py'), argv)
            self.assertIn('-S', argv)
            self.assertLess(normal_end, cleanup_end)
            self.closed(Path(selection['output']), output / 'producer-external.json', identity)
            return b'', process_record()
        original = list(self.original)
        original[3] = types.SimpleNamespace(run=execute, ChildFailure=RuntimeError)
        saved = self.b.save
        def counting(p, body):
            global WRITTEN
            result = saved(p, body); WRITTEN += len(body); return result
        with patch.object(self.b, 'save', side_effect=counting):
            admitted = run.observe_producer(self.b, cfg, selection, identity, original, output,
                                            time.monotonic(), time.monotonic() + 2000)
        self.assertEqual(len(calls), 1)
        self.assertIn('observed_process', admitted)

    def test_failed_or_unclosed_outer_process_cannot_admit(self):
        for key, value in [('exit_code', 2), ('exit_code', True), ('natural_exit', False),
                           ('process_group_absent', False), ('streams_closed', False), ('kill_sent', True)]:
            with self.subTest(key=key, value=value):
                record = process_record(); record[key] = value
                with self.assertRaises(ValueError):
                    self.b.natural(record)

    def scorer_case(self, name, mutate=None):
        base = self.case(name)
        scorer = HERE.parent / 'numerical-recovery-v1'
        identities = {n: self.b.pin(self.captured[str(scorer / (n + '.py'))]) for n in self.b.NUMERICAL}
        analysis = {'participants': [{'subject_id': person, 'rows': 1200, 'voxel_support': {}, 'roi_overlap_voxels': 0,
            'roi_metrics': {'macro_primary': {roi: {metric: {'status': 'defined', 'value': -.1}
                for metric in ('animacy_given_size', 'size_given_animacy', 'joint')} for roi in ('V1', 'IT')}}}
            for person in ('01', '02', '03')]}
        report = {'task_id': 'NEURAL-052', 'input_manifest_sha256': 'a' * 64, 'analysis': analysis}
        outputs = {'result.json': self.pub(base / 'result.json', report), 'METHODS.md': self.pub(base / 'METHODS.md', b'Generated methods.\n')}
        design_pin = self.pub(base / 'private/DESIGN.json', {})
        calls = []
        with self.b.numerical_modules(scorer, identities) as modules:
            grade = modules['grade']; runner = modules['run']
            original = grade.capture_regular
            def read_result(p, *args, **kwargs):
                if mutate == 'result' and Path(p) == base / 'result.json':
                    changed = dict(report, input_manifest_sha256='b' * 64)
                    written(p, self.b.encode(changed))
                return original(p, *args, **kwargs)
            methods_original = runner.capture_regular
            def read_methods(p, *args, **kwargs):
                if mutate == 'methods':
                    written(p, b'Changed methods')
                return methods_original(p, *args, **kwargs)
            with patch.object(grade, 'DESIGN_SHA', design_pin['sha256']), \
                 patch.object(grade, 'capture_regular', side_effect=read_result), \
                 patch.object(runner, 'capture_regular', side_effect=read_methods), \
                 patch.object(modules['report_contract'], 'validate_report', side_effect=lambda *a: calls.append('support')), \
                 patch.object(modules['data_io'], 'load_packet', side_effect=lambda *a, **k: (calls.append('packet') or ([], {}, 'a' * 64))), \
                 patch.object(modules['encoding_core'], 'analyze', side_effect=lambda *a, **k: (calls.append('reference') or analysis)):
                result = self.b.bound_score(modules, base, base / 'result.json', base / 'METHODS.md', outputs)
        return result, calls

    def test_unchanged_grade_capture_and_full_eighteen_primary_comparisons(self):
        result, calls = self.scorer_case('score-matched')
        self.assertEqual(calls, ['support', 'packet', 'reference'])
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(result['primary_error'], 0)
        self.assertTrue(result['primary_defined'])
        self.assertEqual(result['producer_custody']['exact_capture_observed'], {'result.json': True, 'METHODS.md': True})
        self.assertFalse(result['producer_custody']['prose_quality_scored'])

    def test_result_mutation_at_capture_refuses_before_packet_or_reference(self):
        result, calls = self.scorer_case('score-result-mutation', 'result')
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertNotIn('packet', calls)
        self.assertNotIn('reference', calls)
        self.assertFalse(result['producer_custody']['exact_capture_observed']['result.json'])

    def test_methods_mutation_at_capture_refuses_before_report_or_reference(self):
        result, calls = self.scorer_case('score-methods-mutation', 'methods')
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(calls, [])

    def test_provider_loaded_from_verified_unchanged_source(self):
        Provider, identity, directory = self.b.transport(self.captured)
        self.assertEqual(Provider.__module__, 'neural052_trusted_grade_transport.provider')
        self.assertEqual(directory.name, 'vendor_transport')
        self.assertTrue(callable(identity))

    def native_grade_case(self, name, closed=True):
        b = self.b
        base = self.case(name)
        output = base / 'operator'; output.mkdir()
        control = base / 'control'; control.mkdir(mode=0o700)
        quarantine = base / 'quarantine'; quarantine.mkdir(mode=0o700)
        selection = {'repository': str(base), 'image': 'sha256:' + 'a' * 64,
                     'docker_binary': str(base / 'unused-docker'), 'docker_socket': str(base / 'unused-socket')}
        producer = base / 'producer'
        outputs = {name: self.pub(producer / 'candidate' / name, data)
                   for name, data in {'result.json': b'{"generated":true}', 'METHODS.md': b'Generated prose.'}.items()}
        admitted = {'root': str(producer), 'package': str(base / self.original[4]['package']), 'outputs': outputs}
        authority = {'image_inventory_sha256': 'b' * 64, 'grade_resources': run.limits(5, 536870912)}
        cfg = {'grade_control_root': str(control), 'grade_quarantine_root': str(quarantine)}
        Provider, mount_identity, directory = b.transport(self.captured)
        provider_module = sys.modules[Provider.__module__]
        contract = sys.modules['neural052_trusted_grade_transport.contract']
        bounds = sys.modules['neural052_trusted_grade_transport.bounds']
        calls = []
        def execute(provider, request, mounts, deadline, journal):
            calls.append((request, mounts))
            meter = bounds.Meter(1048576, 1, deadline)
            provider.engine_auth(meter)
            contract.validate_request(request, mounts, deadline)
            exposure = b.parse(b.read(next(iter(provider.exposures.values())), 32768))
            contract.validate_exposure(exposure, request, mounts)
            self.assertEqual(request['role'], 'reference')
            self.assertEqual(len(mounts['/packet/public']['files']), 14)
            self.assertEqual(sum(x['bytes'] for x in mounts['/packet/public']['files'].values()), 71207593)
            self.assertFalse(any('/program.py' in key or 'candidate_entry.py' in key for key in mounts))
            self.assertEqual(set(key for key in mounts if key.startswith('/submission/')),
                             {'/submission/result.json', '/submission/METHODS.md'})
            invocation = b.parse(b.read(mounts['/invocation.json']['path'], 32768))
            score = {'status': 'scored', 'primary_error': 0.0, 'producer_custody': {
                'expected_outputs': invocation['outputs'], 'exact_capture_observed': {'result.json': True, 'METHODS.md': True},
                'prose_quality_scored': False, 'scientific_qualification': False}}
            phase = request['phase_id']; captured = quarantine / phase
            files = {'score.json': self.pub(captured / 'score.json', score),
                     'RESULT.json': self.pub(captured / 'RESULT.json', {
                         'schema': 'neural052_separate_numerical_result_v1', 'status': 'scored',
                         'scientific_qualification': False, 'participant_code_executed': False})}
            request_sha = b.pin(b.encode(request))['sha256']
            header = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': phase,
                      'request_sha256': request_sha, 'files': dict(files)}
            files['OUTPUTS.json'] = self.pub(captured / 'OUTPUTS.json', header)
            contract.output_files(header, request, request_sha,
                {'files': [{'name': name, 'bytes': identity['bytes']} for name, identity in files.items()]})
            receipt = {'phase_id': phase, 'request_sha256': request_sha, 'timing': {'original_deadline': deadline},
                'status': 'captured', 'producer_closed_before_capture': closed, 'all_native_resources_closed': closed,
                'cli_reaped': True, 'error': None, 'natural_exit': {'ExitCode': 0, 'OOMKilled': False},
                'source': request['source'], 'image': request['image'], 'role': request['role'],
                'exposure': request['exposure'], 'input_before': mount_identity(mounts), 'input_after': mount_identity(mounts),
                'quarantine_root': str(captured), 'output_inventory': {'complete': True, 'files': files}}
            receipt_path = control / phase / 'RECEIPT.json'
            return {'receipt_path': str(receipt_path), 'receipt_pin': self.pub(receipt_path, receipt)}
        original_save = b.save
        def counting(p, body):
            global WRITTEN
            value = original_save(p, body); WRITTEN += len(body); return value
        with patch.object(b, 'transport', return_value=(Provider, mount_identity, directory)), \
             patch.object(Provider, 'execute_phase', execute), patch.object(b, 'save', side_effect=counting):
            if closed:
                result = run.score_native(b, cfg, authority, b.pin(b'generated authority'), selection,
                    self.original, self.manifest, self.captured, admitted, output, time.monotonic(), time.monotonic() + 120, self.source)
                self.assertEqual(result['status'], 'scored')
                self.assertFalse(result['scientific_qualification'])
            else:
                with self.assertRaisesRegex(ValueError, 'complete closure'):
                    run.score_native(b, cfg, authority, b.pin(b'generated authority'), selection,
                        self.original, self.manifest, self.captured, admitted, output, time.monotonic(), time.monotonic() + 120, self.source)
        self.assertEqual(len(calls), 1)

    def test_actual_numeric_adapter_provider_construction_and_independent_observer(self):
        self.native_grade_case('numeric-adapter')

    def test_unclosed_numeric_phase_cannot_publish_a_grade(self):
        self.native_grade_case('numeric-unclosed', closed=False)

    def test_actual_main_failed_outer_zero_never_dispatches_numerical_phase(self):
        base = self.case('failed-main')
        cfg = {'operator_output': str(base / 'operator'), 'producer_selection': {'path': str(base / 'selection.json')}}
        selection = {'output': str(base / 'producer'), 'repository': str(base), 'candidate_seconds': 2}
        authority = {'whole_seconds': 2000, 'outside_reserved_bytes': 0, 'additional_artifact_bytes': 4194304}
        original = list(self.original)
        bad = process_record(); bad['exit_code'] = 2
        original[3] = types.SimpleNamespace(run=lambda *a: (b'', bad), ChildFailure=RuntimeError)
        setup = (cfg, authority, self.b.pin(b'authority'), selection, self.b.pin(b'selection'),
                 original, self.manifest, self.captured)
        saved = self.b.save
        def counting(p, body):
            global WRITTEN
            result = saved(p, body); WRITTEN += len(body); return result
        with patch.object(run, 'load_bridge', return_value=self.b), patch.object(run, 'setup', return_value=setup), \
             patch.object(run.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10**12)), \
             patch.object(self.b, 'save', side_effect=counting), patch.object(run, 'score_native') as score:
            with self.assertRaisesRegex(ValueError, 'natural zero'):
                run.main(['--source-pin', json.dumps(self.source), '--configuration', str(base / 'unused.json')])
            score.assert_not_called()
        self.assertTrue((base / 'operator/FAILURE.json').is_file())
        self.assertFalse((base / 'operator/COMPLETE.json').exists())

    def test_explicit_configuration_preserves_original_and_separate_grade_budgets(self):
        base = self.case('configuration')
        b = self.b
        common, policy, observer, process, binding, legacy_source = self.original
        def operand(name, body):
            identity = self.pub(base / name, body)
            return dict(path=str(base / name), **identity)
        selection = {'schema': 'neural052_full3_program_selection_v1', 'execution_selected': True,
            'task_id': 'NEURAL-052', 'repository': str(base), 'output': str(base / 'producer'),
            'program': operand('candidate.py', b'# generated inert source\n'), 'source': legacy_source,
            'docker_binary': str(base / 'unused-docker'), 'docker_socket': str(base / 'unused-socket'),
            'image': 'sha256:' + 'a' * 64, 'candidate_seconds': 2, 'memory_bytes': 536870912,
            'other_future_bytes': 0, 'scope': binding['scope'], 'retained_bytes': common.RETAIN,
            'managed_reads': common.READS + 16000000, 'managed_writes': common.WRITES + 16384,
            'whole_seconds': policy.whole(2), 'method_review': operand('method.json', b'{}'),
            'runtime_review': operand('runtime.json', b'{}'),
            'support_admission_authorized': True, 'numeric_grading_authorized': False}
        selected = operand('selection.json', b.encode(selection))
        selection_pin = {k: selected[k] for k in ('bytes', 'sha256')}
        authority = {'schema': 'neural052_separate_numeric_authority_v1', 'source': self.source,
            'producer_source': legacy_source, 'producer_selection': selection_pin, 'image': selection['image'],
            'image_inventory_sha256': 'b' * 64, 'grade_resources': run.limits(5, 536870912),
            'holder_memory_bytes': 134217728, 'holder_cpu_nanos': 1000000000, 'approved': True,
            'numeric_reference_calls': 1, 'outside_reserved_bytes': 0, 'additional_artifact_bytes': 4194304,
            'whole_seconds': policy.whole(2) + 180 + 5 + 60 + 30,
            'runtime_versions': {'python': '3.12.8', 'numpy': '2.2.6'}, 'runtime_qualification_inherited': False}
        configuration = {'schema': 'neural052_full_panel_configuration_v1', 'source': self.source,
            'producer_selection': selected, 'numeric_authority': operand('authority.json', b.encode(authority)),
            'operator_output': str(base / 'operator'), 'grade_control_root': str(base / 'control'),
            'grade_quarantine_root': str(base / 'quarantine')}
        path = base / 'configuration.json'
        self.pub(path, configuration)
        accepted = run.setup(b, path, self.source)
        self.assertFalse(accepted[3]['numeric_grading_authorized'])
        self.assertEqual(accepted[1]['numeric_reference_calls'], 1)
        for i, (key, value) in enumerate((('approved', False), ('whole_seconds', 1),
                                        ('holder_memory_bytes', 1), ('runtime_qualification_inherited', True))):
            changed = dict(authority, **{key: value})
            configuration['numeric_authority'] = operand('bad-authority-' + str(i) + '.json', b.encode(changed))
            written(path, b.encode(configuration))
            with self.assertRaises(ValueError):
                run.setup(b, path, self.source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
