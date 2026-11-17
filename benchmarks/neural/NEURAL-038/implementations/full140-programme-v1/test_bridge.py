"""Generated full-panel connection controls; native and physical-capacity boundaries are scripted."""
import copy
import json
import os
from pathlib import Path
import platform
import tempfile
import time
import types
import unittest
from unittest.mock import patch

for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np

HERE = Path(__file__).absolute().parent
REPOSITORY = HERE.parents[4]


def local(name):
    module = types.ModuleType('_test038_' + name)
    module.__file__ = str(HERE / (name + '.py'))
    exec(compile((HERE / (name + '.py')).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


lib, grade, runner = local('library'), local('grade'), local('run')
fixtures, producer = local('generated_fixtures'), local('test_producer')


def closed():
    return {'natural_exit': True, 'exit_code': 0, 'process_reaped': True, 'process_group_absent': True,
            'streams_closed': True, 'timed_out': False, 'kill_sent': False, 'error_type': None,
            'timer_disable_error': None, 'timer_restore_error': None}


def rewrite(path, raw):
    mode = path.stat().st_mode & 0o777
    path.chmod(0o600)
    try: fixtures.write(path, raw)
    finally: path.chmod(mode)


def authority(selection, identity, source=None):
    return {'schema': 'neural038_full140_numerical_authority_v1', 'numeric_grading_authorized': True,
            'source': source or lib.SOURCE, 'program': {k: selection['program'][k] for k in ('bytes', 'sha256')},
            'wrapper_sources': identity, 'profile': lib.profile(60), 'authoring_context_id': 'invented-control-context',
            'one_frozen_program': True, 'public_files': 25, 'primitive_arrays': 18,
            'private_source_visible': False, 'source_history_attested_by_root': True}


class ProducerControls(unittest.TestCase):
    def test_original_full_panel_producer(self):
        result = producer.run_controls(fixtures=fixtures)
        self.assertTrue(result['passed'])
        print(json.dumps(result))


class BridgeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neural038-complete-generated-')
        cls.base = Path(cls.temp.name).resolve()
        cls.case = producer.build_attempt(cls.base, fixtures=fixtures)
        cls.c = cls.case['common']
        cls.old_save = cls.c.save
        def counted_save(path, raw, cap, tick=lambda: None, charge=lambda count: None):
            return fixtures.publication(raw, lambda: cls.old_save(path, raw, cap, tick, charge))
        cls.c.save = counted_save

    @classmethod
    def tearDownClass(cls):
        cls.c.save = cls.old_save
        cls.temp.cleanup()

    def receipt(self):
        case = self.case; info = case['observer_admission']
        return {'schema': 'neural038_full140_external_v1', 'status': 'complete_unqualified',
                'source': case['source'], 'selection': self.c.pin(self.c.encoded(case['selection'])),
                'attempt': str(case['root']), 'error_type': None, 'full140_source_scope': True,
                'numerical_grading_performed': False, 'scientific_qualified': False, 'runtime_qualified': False,
                'nested_cli_and_native_recovery_may_be_required': False, 'automatic_retry': False,
                'origin_monotonic': 100., 'whole_deadline': 1900., 'outer_deadline': 1960.,
                'elapsed_before_publication': 1., 'child': closed(),
                'report': info['report_pin'], 'complete': info['complete_pin']}

    def captured(self):
        case = self.case
        return grade.stopped_report(self.c, case['bodies'], case['root'], self.receipt(),
                                    case['source'], case['binding'], time.monotonic() + 30, lambda count: None)

    def numerics(self, raw, binding=None):
        evaluate, transport, _ = lib.evaluator(REPOSITORY, self.c)
        charges = []
        budget = types.SimpleNamespace(tick=lambda: None, read=charges.append)
        result = grade.current_numerics(self.c, evaluate, transport, self.case['package'],
                                        binding or self.case['binding'], raw, budget)
        return result, charges

    def test_01_complete_captured_report_recomputes_all866_operands(self):
        result, charges = self.numerics(self.captured())
        self.assertEqual(result['status'], 'scored')
        self.assertTrue(result['full_numeric_reconstruction'])
        self.assertEqual(result['numeric_fields_within_tolerance'], 866)
        self.assertEqual(len(charges), 20)  # Two metadata captures plus exactly eighteen arrays.
        self.assertIsNone(result['access_mode_result'])

    def test_02_post_capture_valid_replacement_cannot_replace_scored_object(self):
        raw = self.captured()
        path = self.case['root'] / 'candidate/report.json'
        original = path.read_bytes()
        changed = self.c.parse(original); changed['blocks'][0]['cells'][0]['context_interaction'] += 1
        try:
            rewrite(path, self.c.encoded(changed))
            result, _ = self.numerics(raw)
            self.assertTrue(result['full_numeric_reconstruction'])
            with self.assertRaises(ValueError): self.captured()
        finally: rewrite(path, original)

    def test_03_original_native_closure_remains_required(self):
        path = self.case['root'] / 'candidate/NATIVE.json'; original = path.read_bytes()
        changed = self.c.parse(original); changed['producer_closed_before_capture'] = False
        try:
            rewrite(path, self.c.encoded(changed))
            with self.assertRaises(ValueError): self.captured()
        finally: rewrite(path, original)

    def test_04_full_structure_refuses_before_array_recomputation(self):
        bad = copy.deepcopy(self.case['report']); bad['blocks'][3]['cells'].pop()
        evaluate, transport, _ = lib.evaluator(REPOSITORY, self.c)
        with patch.object(evaluate, 'load_array', side_effect=AssertionError('Array read too early')):
            with self.assertRaises(ValueError):
                grade.current_numerics(self.c, evaluate, transport, self.case['package'], self.case['binding'],
                                       self.c.encoded(bad), types.SimpleNamespace(tick=lambda: None, read=lambda n: None))

    def test_05_array_metadata_must_join_same_candidate_export(self):
        binding = copy.deepcopy(self.case['binding'])
        row = next(r for r in binding['files'] if r['target'].endswith('.npy'))
        row['sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.numerics(self.captured(), binding)

    def test_06_changed_public_array_is_rejected(self):
        path = self.case['public_root'] / self.case['inputs']['blocks'][0]['arrays']['visF1']['path']
        original = path.read_bytes()
        try:
            rewrite(path, original[:-8] + b'CHANGED!')
            with self.assertRaises(ValueError): self.numerics(self.captured())
        finally: rewrite(path, original)

    def test_07_wrong_but_valid_full_report_is_scored_as_wrong(self):
        bad = copy.deepcopy(self.case['report']); bad['blocks'][0]['cells'][0]['context_interaction'] += 1
        result, _ = self.numerics(self.c.encoded(bad))
        self.assertFalse(result['full_numeric_reconstruction'])
        self.assertEqual(result['numeric_fields_within_tolerance'], 865)

    def test_08_external_receipt_rejects_late_failed_or_wrong_source(self):
        selection = self.case['selection']; pin = self.c.pin(self.c.encoded(selection))
        for key, value in [('source', {'bytes': 1, 'sha256': '0' * 64}),
                           ('elapsed_before_publication', 1800), ('nested_cli_and_native_recovery_may_be_required', True),
                           ('numerical_grading_performed', True)]:
            receipt = self.receipt(); receipt[key] = value
            with self.assertRaises(ValueError): grade.external_receipt(self.c, receipt, selection, pin, self.case['source'])

    def test_09_exact_outer_process_closure(self):
        lib.closed(closed())
        for name, value in [('natural_exit', False), ('exit_code', True), ('process_group_absent', False),
                            ('timed_out', True), ('kill_sent', True), ('timer_restore_error', 'failed')]:
            record = closed(); record[name] = value
            with self.assertRaises(ValueError): lib.closed(record)

    def test_10_numerical_authority_and_exposure_are_separate(self):
        identity = lib.source_identity(self.c)
        value = authority(self.case['selection'], identity)
        lib.authority(value, self.case['selection'], identity, 60)
        for name, wrong in [('numeric_grading_authorized', False), ('private_source_visible', True),
                            ('source_history_attested_by_root', False), ('primitive_arrays', 17), ('public_files', True),
                            ('authoring_context_id', ''), ('schema', 'structural_only')]:
            changed = copy.deepcopy(value); changed[name] = wrong
            with self.assertRaises(ValueError): lib.authority(changed, self.case['selection'], identity, 60)

    def test_11_root_separation_rejects_ancestor_relationships(self):
        lib.disjoint_roots(self.c, self.base / 'one', self.base / 'two', REPOSITORY)
        for pair in [(self.base, self.base / 'data'), (self.base / 'data', self.base), (REPOSITORY, REPOSITORY / 'output')]:
            with self.assertRaises(ValueError): lib.disjoint_roots(self.c, *pair)

    def test_12_current_floor_and_legacy_holds_remain_additive(self):
        other = lib.FLOOR_UPLIFT + lib.WRITES + 123
        required = lib.FLOOR + 123 + 456 + lib.WRITES
        with patch.object(lib.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=required)):
            lib.floor(self.c, self.base, other, legacy_remaining=456)
            with self.assertRaises(ValueError): lib.floor(self.c, self.base, other, legacy_remaining=457)
            with self.assertRaises(ValueError): lib.floor(self.c, self.base, other - 124)

    def test_13_slow_startup_preserves_original_observer_envelope(self):
        end, overall = runner.deadlines(100., 145., 60)
        self.assertEqual(end - 145., 1860 + 30)
        self.assertEqual(overall, 100 + 1860 + 150 + 60)
        self.assertLessEqual(end + 60 + 60, overall)
        with self.assertRaises(ValueError): runner.deadlines(100., 160., 60)
        with self.assertRaises(ValueError): runner.execute(types.SimpleNamespace(), origin=time.monotonic() - 61)

    def test_14_complete_internal_grade_uses_original_admission_and_current_evaluator(self):
        # Only generated source bindings, native closure, authority and physical capacity are scripted.
        case, c = self.case, self.c
        output = self.base / 'numerical-bridge'; output.mkdir()
        identity = grade.lib.source_identity(c)
        selected_raw = c.encoded(case['selection']); selected_pin = c.pin(selected_raw)
        auth_raw = c.encoded(authority(case['selection'], identity, case['source']))
        c.save(output / 'SELECTION.json', selected_raw, 32768)
        auth_pin = c.save(output / 'AUTHORITY.json', auth_raw, 65536)
        commit = {'schema': 'neural038_numerical_bridge_commitment_v1', 'source': case['source'],
                  'wrapper_sources': identity, 'selection': selected_pin, 'authority': auth_pin,
                  'source_repository': str(REPOSITORY), 'operator_repository': str(case['operator_repository']),
                  'profile': grade.lib.profile(60)}
        commit_pin = c.save(output / 'BRIDGE_COMMITMENT.json', c.encoded(commit), 65536)
        external = c.save(output / 'EXTERNAL.json', c.encoded(self.receipt()), 8192)
        proof = {'schema': 'neural038_original_observer_exit_v1', 'source': case['source'],
                 'commitment': commit_pin, 'observed': 1., 'deadline': 2., 'lifecycle': closed(), 'external_receipt': external}
        proof_pin = c.save(output / 'OUTER_EXIT.json', c.encoded(proof), 65536)
        with patch.object(grade.lib, 'runtime', return_value=(c, case['manifest'], case['bodies'], case['source'])), \
             patch.object(grade.lib, 'SOURCE', case['source']), patch.object(grade.lib, 'floor'):
            pin = grade.grade(REPOSITORY, output / 'BRIDGE_COMMITMENT.json', commit_pin,
                              output / 'OUTER_EXIT.json', proof_pin, output / 'NUMERICAL.json', time.monotonic() + 30)
        result = c.parse(c.capture(output / 'NUMERICAL.json', 2 * 2**20, pin))
        self.assertEqual(result['result']['numeric_fields_within_tolerance'], 866)
        self.assertFalse(result['runtime_qualified'])
        self.assertEqual(result['costs']['write_charges_and_reservations'], 3 * 2**20)
        self.assertEqual(result['report_write_reservation'], 2 * 2**20)
        self.assertFalse((case['package'] / 'private').exists())


class CallerControls(unittest.TestCase):
    def attempt(self, failure=None):
        c, manifest, bodies, source = lib.runtime(time.monotonic() + 30)
        policy = c.module(bodies, 'policy.py', HERE / 'runtime', c=c)
        original_module = c.module
        calls = []
        old_save = c.save
        def counted(path, raw, cap, tick=lambda: None, charge=lambda n: None):
            return fixtures.publication(raw, lambda: old_save(path, raw, cap, tick, charge))
        c.save = counted
        with tempfile.TemporaryDirectory(prefix='neural038-caller-generated-') as folder:
            base = Path(folder).resolve(); operator = base / 'operator'; operator.mkdir()
            program = base / 'program.py'; fixtures.write(program, b'# Invented programme; never executed.\n')
            program_pin = c.pin(program.read_bytes())
            other = lib.FLOOR_UPLIFT + lib.WRITES
            method = {'schema': 'neural038_full140_method_review_v1', 'task_id': 'NEURAL-038', 'approved': True,
                      'source': source, 'program': program_pin, 'scope': policy.SCOPE, 'other_future_bytes': other}
            for key in ('all140_memberships_and_four_blocks', 'one_program_before_public_input_access',
                        'full_public_covariates_intentionally_visible', 'fixed_native_frames_and_separate_revision',
                        'all_null_and_support_dispositions_preserved', 'complete_report_before_feedback', 'no_private_answer_exposure'):
                method[key] = True
            for key in ('numeric_agreement_proves_neural_understanding', 'heldout_generalization_or_paper_parity',
                        'hashes_alone_prove_chronology'):
                method[key] = False
            runtime = {'schema': 'neural038_runtime_profile_review_v1', 'task_id': 'NEURAL-038', 'approved': True,
                       'source': source, 'program': program_pin, 'scope': policy.SCOPE, 'other_future_bytes': other,
                       'image': 'sha256:' + 'b' * 64, 'candidate_seconds': 600, 'memory_bytes': 2**30,
                       'docker_binary': '/INVENTED_UNEXECUTED_DOCKER', 'docker_socket': '/INVENTED_UNOPENED_SOCKET',
                       'runtime_versions': {'python': '3.12', 'numpy': '2.2.6'},
                       'native_full_panel_qualification_required_before_campaign': True, 'qualification_inherited': False,
                       'independent_cli_groups_and_native_failure_recovery_acknowledged': True}
            review_pins = {}
            for name, value in [('method_review', method), ('runtime_review', runtime)]:
                path = base / (name + '.json'); raw = c.encoded(value); fixtures.write(path, raw)
                review_pins[name] = {'path': str(path), **c.pin(raw)}
            original_output = base / 'original'; output = base / 'bridge'
            selected = {'schema': 'neural038_full140_program_selection_v1', 'execution_selected': True,
                        'task_id': 'NEURAL-038', 'repository': str(operator), 'output': str(original_output),
                        'program': {'path': str(program), **program_pin}, 'source': source,
                        'docker_binary': runtime['docker_binary'], 'docker_socket': runtime['docker_socket'],
                        'image': runtime['image'], 'candidate_seconds': 600, 'memory_bytes': 2**30,
                        'other_future_bytes': other, 'scope': policy.SCOPE, 'retained_bytes': 96000000,
                        'managed_reads': 240000000, 'managed_writes': 64016384, 'whole_seconds': 1800,
                        'support_admission_authorized': True, 'numeric_grading_authorized': False, **review_pins}
            selection = base / 'selection.json'; raw = c.encoded(selected); fixtures.write(selection, raw)
            selected_pin = c.pin(raw)
            ident = runner.lib.source_identity(c)
            auth = authority(selected, ident)
            if failure == 'authority': auth['numeric_grading_authorized'] = False
            authorization = base / 'authority.json'; raw = c.encoded(auth); fixtures.write(authorization, raw)
            args = types.SimpleNamespace(selection=str(selection), selection_pin=json.dumps(selected_pin),
                    authority=str(authorization), authority_pin=json.dumps(c.pin(raw)),
                    operator_repository=str(operator), source_repository=str(REPOSITORY),
                    numerical_seconds=60, output=str(output))
            proc = original_module(bodies, 'process.py', HERE / 'runtime')
            def scripted(argv, normal_end, cleanup_end, env):
                calls.append(argv)
                self.assertTrue((output / 'BRIDGE_COMMITMENT.json').is_file())
                self.assertLess(time.monotonic(), normal_end); self.assertLess(normal_end, cleanup_end)
                record = closed()
                if len(calls) == 1:
                    original_output.mkdir()
                    c.save(output / 'EXTERNAL.json', b'{"invented_caller_boundary":true}\n', 8192)
                    if failure == 'outer': record['process_group_absent'] = False
                    return b'', record
                pin = c.save(output / 'NUMERICAL.json', b'{"invented_numerical_boundary":true}\n', 2 * 2**20)
                if failure == 'numerical': record['timed_out'] = True
                return c.encoded({'score': pin}), record
            proc.run = scripted
            def module_override(all_bodies, name, here, **bindings):
                return proc if name == 'process.py' else original_module(all_bodies, name, here, **bindings)
            c.module = module_override
            old_time = runner.time
            try:
                if failure == 'flush':
                    def late(*args, **kwargs): runner.time = types.SimpleNamespace(monotonic=lambda: float('inf'))
                    runner.__dict__['print'] = late
                with patch.object(runner.lib, 'runtime', return_value=(c, manifest, bodies, source)), \
                     patch.object(runner.lib, 'floor'):
                    if failure:
                        with self.assertRaises((ValueError, TimeoutError)): runner.execute(args)
                        self.assertEqual((output / 'COMPLETE.json').exists(), failure == 'flush')
                    else:
                        runner.execute(args)
                        self.assertTrue((output / 'COMPLETE.json').is_file())
            finally:
                runner.time = old_time; runner.__dict__.pop('print', None)
        return calls

    def test_15_caller_dispatches_observer_before_numerics(self):
        calls = self.attempt()
        self.assertEqual(len(calls), 2)
        self.assertTrue(any(arg.endswith('runtime/observe.py') for arg in calls[0]))
        self.assertTrue(any(arg.endswith('grade.py') for arg in calls[1]))

    def test_16_failed_outer_closure_prevents_numerical_dispatch(self):
        self.assertEqual(len(self.attempt('outer')), 1)

    def test_17_failed_numerical_closure_prevents_completion(self):
        self.assertEqual(len(self.attempt('numerical')), 2)

    def test_18_separate_authority_rejected_before_any_process(self):
        self.assertEqual(self.attempt('authority'), [])

    def test_19_late_final_flush_is_not_a_successful_exit(self):
        self.assertEqual(len(self.attempt('flush')), 2)


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'numpy': np.__version__, 'numerical_threads': 1,
                     'authentic_payload_reads': 0, 'native_runs': 0, 'model_calls': 0}))
    result = unittest.main(exit=False, verbosity=2).result
    print(json.dumps({'current_process_generated_write_counts': fixtures.snapshot(), 'tests': result.testsRun,
                     'failures': len(result.failures), 'errors': len(result.errors),
                     'scope': 'Native execution and physical disk capacity are scripted; original software and complete invented arrays are real.',
                     'prior_attempt_costs_not_in_this_process_counter': True, 'temporary_fixtures_removed': True}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
