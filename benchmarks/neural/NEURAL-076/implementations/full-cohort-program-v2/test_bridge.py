"""Generated controls only: no real pool, labels, Docker, candidate or model."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import tempfile
import time
import types
import unittest

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
import numpy as np

HERE = Path(__file__).absolute().parent
REPOSITORY = HERE.parents[4]
WRITTEN = 0


def module(name):
    obj = types.ModuleType('_test076_' + name)
    obj.__file__ = str(HERE / (name + '.py'))
    exec(compile((HERE / (name + '.py')).read_bytes(), obj.__file__, 'exec'), obj.__dict__)
    return obj


support = module('support')
bridge = module('score_closed')
runner = module('run')
loader, bodies, _, source = support.runtime()
common, coordinator = loader('common'), loader('coordinator')


def write(path, body):
    global WRITTEN
    WRITTEN += len(body)
    assert WRITTEN <= 32 * 2**20
    path.write_bytes(body)
    return common.short(body)


def good_record():
    return {'natural_exit': True, 'exit_code': 0, 'process_reaped': True, 'process_group_absent': True,
            'streams_closed': True, 'streams_eof': True, 'timed_out': False, 'error_type': None,
            'timer_disable_error': None, 'timer_restore_error': None}


def metadata():
    pin = common.short(b'one invented prediction')
    selection = common.short(b'one invented selection')
    rows = [{'key': key, 'path': key.replace('/', '__') + '.npz', 'prediction': dict(pin)} for key in common.KEYS]
    terminal = {'observation': pin, 'complete': pin, 'full_contexts': 650,
                'runtime_qualified': False, 'scientific_qualified': False}
    observation = {'schema': 'neural076_whole_command_observation_v1', 'source': source,
                   'selection': selection, 'complete': pin, 'error': None, 'completed': True,
                   'requires_observed_observer_exit_zero': True, 'observed': 1., 'deadline': 2.,
                   'runtime_qualified': False, 'scientific_scoring': False, 'scientific_qualified': False,
                   'lifecycle': good_record()}
    complete = {'schema': 'neural076_full650_collection_v1', 'status': 'complete_pending_external_natural_exit',
                'source': source, 'context_count': 650, 'contexts': rows,
                **{name: False for name in ('private_gold_opened', 'scientific_scoring', 'feedback_released',
                                            'runtime_qualified', 'scientific_qualified')}}
    submission = {'schema': 'neural076_predictions_v1', 'source_design_sha256': 'a' * 64,
                  'parts': [{'key': r['key'], 'path': r['path']} for r in rows]}
    commitment = {'schema': 'neural076_frozen_program_v1', 'source': source,
                  'keys': list(common.KEYS), 'feedback_before_commitment': False}
    return [common, coordinator, source, selection, terminal, good_record(), observation, complete, submission, commitment]


class Controls(unittest.TestCase):
    def test_01_recovered_complete_controller(self):
        results = module('test_controller').run_controls()
        self.assertTrue(results['passed'])
        self.assertFalse(results['native_execution'])
        print(json.dumps({'recovered_controller_groups': results['groups'], 'results': results['results']}))

    def test_02_complete_metadata_admission(self):
        self.assertEqual(len(bridge.admit(*metadata())), 650)

    def test_03_missing_or_reordered_context(self):
        for change in ('missing', 'reordered'):
            args = metadata()
            if change == 'missing':
                args[7]['contexts'].pop()
            else:
                args[7]['contexts'][:2] = reversed(args[7]['contexts'][:2])
            with self.assertRaises(ValueError): bridge.admit(*args)

    def test_04_no_file_only_completion(self):
        for field in ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed', 'streams_eof'):
            args = metadata(); args[5][field] = False
            with self.assertRaises(ValueError): bridge.admit(*args)

    def test_05_inner_failure_and_deadline(self):
        args = metadata(); args[6]['lifecycle']['timed_out'] = True
        with self.assertRaises(ValueError): bridge.admit(*args)
        args = metadata(); args[6]['observed'] = args[6]['deadline']
        with self.assertRaises(ValueError): bridge.admit(*args)

    def test_06_source_selection_and_commitment(self):
        for index, key in ((6, 'source'), (6, 'selection'), (7, 'source'), (9, 'source')):
            args = metadata(); args[index][key] = common.short(b'wrong')
            with self.assertRaises(ValueError): bridge.admit(*args)

    def test_07_output_identity_and_pin_bounds(self):
        for change in ('filename', 'oversize', 'invalid_hash'):
            args = metadata(); row = args[7]['contexts'][0]
            if change == 'filename': row['path'] = '../predictions.npz'
            if change == 'oversize': row['prediction']['bytes'] = common.PRED + 1
            if change == 'invalid_hash': row['prediction']['sha256'] = 'z' * 64
            with self.assertRaises(ValueError): bridge.admit(*args)

    def test_08_current_dependency_and_metric(self):
        scorer, _, manifest = support.current_scorer(REPOSITORY, common)
        self.assertEqual(scorer.PRIMARY, 'imagery_cnn7_minus_cnn1_HVC_minus_LVC')
        self.assertEqual(len(manifest['files']), 4)
        instruction = (HERE / 'INSTRUCTIONS.md').read_text()
        for phrase in ('35 perception', 'propagate null', 'not ten folds', 'not direct'):
            self.assertIn(phrase, instruction)

    def test_09_real_generated_full_shape_and_capture_mutation(self):
        _, artifacts, _ = support.current_scorer(REPOSITORY, common)
        ids = ['q' + format(i, '024x') for i in range(2250)]
        units = list(range(1000))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'full.npz'
            def archive(value):
                stream = io.BytesIO()
                np.savez_compressed(stream, features=np.full((2250, 1000), value, dtype=np.float32),
                                    trial_ids=np.asarray(ids, dtype='<U25'), unit_ids=np.asarray(units))
                return stream.getvalue()
            captured = write(path, archive(0))
            values, sha = artifacts.load(path, ids, units, captured['sha256'])
            self.assertEqual(values.shape, (2250, 1000)); self.assertEqual(sha, captured['sha256'])
            write(path, archive(1))  # Valid same-geometry replacement after capture.
            with self.assertRaises(ValueError): artifacts.load(path, ids, units, captured['sha256'])
            with self.assertRaises(ValueError): artifacts.load(path, list(reversed(ids)), units)

    def full_score(self, mutate_at=None):
        scorer, artifacts, _ = support.current_scorer(REPOSITORY, common)
        public = {'schema': 'neural076_matched_hierarchy_v1', 'source_design_sha256': 'a' * 64,
                  'people': {}, 'unit_ids': {f: artifacts.matched_indices(f, 1024 if f == 'gist' else 1000).tolist()
                                            for f in common.FAMILIES}}
        for i, person in enumerate(common.PEOPLE):
            ids = ['q' + format(i * 2250 + j, '024x') for j in range(2250)]
            public['people'][person] = {'imagery_ids': ids[:500], 'perception_ids': ids[500:]}
        submission = metadata()[8]
        calls, targets = [], []
        block = np.zeros((2250, 1000), dtype=np.float32)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            pins = {row['path']: write(base / row['path'], b'x') for row in submission['parts']}
            def fake_load(path, ids, units, expected_sha=None):
                calls.append((path.name, expected_sha))
                # Opaque invented artifacts exercise custody; they are not numerical archives.
                if mutate_at == len(calls): write(path, b'y')
                self.assertEqual(len(ids), 2250); self.assertEqual(len(units), 1000)
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
                    raise ValueError('post-capture replacement')
                return block, expected_sha
            scorer.load = fake_load
            scorer.feature_score = lambda *args: {'mean_r': 0.25}
            scorer.validate_gold = lambda gold: None
            def private():
                targets.append(len(calls))
                return {**{p + '_' + s: None for p in common.PEOPLE for s in ('imagery', 'perception')},
                        **{'bank_' + f: None for f in common.FAMILIES}}
            result = bridge.assess_bound(scorer, common, submission, public, base, private, pins)
        return result, calls, targets

    def test_10_all650_both_passes_exact_capture_binding(self):
        result, calls, targets = self.full_score()
        self.assertEqual(result['status'], 'scored'); self.assertEqual(len(calls), 1300)
        self.assertEqual(targets, [650]); self.assertEqual(calls[:650], calls[650:])

    def test_11_changed_capture_refuses_before_targets(self):
        result, calls, targets = self.full_score(650)
        self.assertEqual(result['status'], 'invalid_submission'); self.assertEqual(targets, [])

    def test_12_changed_second_pass_has_no_primary(self):
        result, calls, targets = self.full_score(651)
        self.assertEqual(result['status'], 'invalid_submission'); self.assertIsNone(result['primary'])
        self.assertEqual(targets, [650])

    def execute_fake(self, failure=None):
        rloader, rbodies, rmanifest, rsource = support.runtime()
        com, coord, proc = rloader('common'), rloader('coordinator'), rloader('process')
        calls = []
        original_runtime = runner.support.runtime
        original_deps = runner.support.current_scorer
        original_identity = runner.support.source_identity
        original_time = runner.time
        try:
            runner.support.runtime = lambda: (rloader, rbodies, rmanifest, rsource)
            runner.support.current_scorer = lambda *_: None
            coord.validate_selection = lambda *_: None  # Selection rules independently exercised above.
            with tempfile.TemporaryDirectory() as folder:
                base = Path(folder).resolve()
                candidate = base / 'candidate.py'; candidate_pin = write(candidate, b'# invented nonexecuted candidate\n')
                selection = {'whole_seconds': 120, 'other_future_bytes': support.SCORE_WRITES,
                             'program': {'path': str(candidate), **candidate_pin}, 'output': str(base / 'collection-output'),
                             'collection': str(base / 'operator-input')}
                selected = base / 'selection.json'; selected_pin = write(selected, common.encode(selection))
                out = base / 'bridge'
                args = types.SimpleNamespace(selection=str(selected), selection_sha256=selected_pin['sha256'],
                        instructions_sha256=original_identity(com)['INSTRUCTIONS.md']['sha256'], repository=str(REPOSITORY),
                        score_seconds=30, external_scoring_memory_bytes=support.SCORE_MEMORY, output=str(out))
                def fake_process(argv, normal_end, cleanup_end, env, **kwargs):
                    calls.append(argv)
                    self.assertTrue((out / 'BINDING.json').is_file())
                    self.assertLess(time.monotonic(), normal_end); self.assertLess(normal_end, cleanup_end)
                    record = good_record()
                    if failure == 'closure' and len(calls) == 1: record['process_group_absent'] = False
                    if failure == 'late' and len(calls) == 1:
                        record['timed_out'] = True; raise proc.ChildFailure(record)
                    if len(calls) == 1:
                        terminal = metadata()[4]
                        if failure == 'source':
                            runner.support.source_identity = lambda *_: {'changed': True}
                    else:
                        report = com.write(out / 'SCORE.json', b'{"invented_software_fixture":true}\n', 65536)
                        terminal = {'report': report}
                        if failure == 'report': terminal['report'] = common.short(b'different bytes')
                    return {'stdout': com.encode(terminal), 'stderr': b''}, record
                proc.run = fake_process
                if failure == 'instructions': args.instructions_sha256 = '0' * 64
                if failure == 'flush':
                    def late_flush(*args, **kwargs):
                        runner.time = types.SimpleNamespace(monotonic=lambda: float('inf'))
                    runner.__dict__['print'] = late_flush
                if failure:
                    with self.assertRaises((ValueError, TimeoutError, proc.ChildFailure)): runner.execute(args)
                    self.assertEqual((out / 'COMPLETE.json').exists(), failure == 'flush')
                else:
                    runner.execute(args)
                    self.assertTrue((out / 'COMPLETE.json').is_file())
        finally:
            runner.support.runtime = original_runtime
            runner.support.current_scorer = original_deps
            runner.support.source_identity = original_identity
            runner.time = original_time
            runner.__dict__.pop('print', None)
        return calls

    def test_13_actual_caller_orchestration_generated_services(self):
        calls = self.execute_fake(); self.assertEqual(len(calls), 2)
        self.assertTrue(any(x.endswith('runtime/observe.py') for x in calls[0]))
        self.assertTrue(any(x.endswith('score_closed.py') for x in calls[1]))

    def test_14_failed_closure_prevents_scoring(self):
        self.assertEqual(len(self.execute_fake('closure')), 1)

    def test_15_late_outer_exit_prevents_scoring(self):
        self.assertEqual(len(self.execute_fake('late')), 1)

    def test_16_current_instruction_binding_required(self):
        self.assertEqual(self.execute_fake('instructions'), [])

    def test_17_changed_bridge_source_prevents_scoring(self):
        self.assertEqual(len(self.execute_fake('source')), 1)

    def test_18_changed_report_prevents_completion(self):
        self.assertEqual(len(self.execute_fake('report')), 2)

    def test_19_separate_scoring_budget(self):
        budget = support.score_budget(60)
        self.assertEqual(budget['managed_read_reservation'], 2 * 650 * 24 * 2**20 + 32 * 2**20)
        self.assertFalse(budget['runtime_qualified'])
        for invalid in (True, 0, 7201):
            with self.assertRaises(ValueError): support.score_budget(invalid)

    def test_20_false_missing_or_wrong_schema_score_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            for mode in ('false', 'missing', 'schema'):
                binding = {'schema': 'neural076_current_instructions_binding_v2',
                           'separate_scoring_explicitly_selected': True}
                if mode == 'false': binding['separate_scoring_explicitly_selected'] = False
                if mode == 'missing': binding.pop('separate_scoring_explicitly_selected')
                if mode == 'schema': binding['schema'] = 'legacy_collection_only'
                path = base / (mode + '.json'); pin = write(path, common.encode(binding))
                with self.assertRaises(ValueError):
                    bridge.grade(REPOSITORY, path, pin['sha256'], base / 'unopened-proof', '0' * 64,
                                 base / 'no-report', time.monotonic() + 10)
                self.assertFalse((base / 'no-report').exists())

    def test_21_expired_startup_refuses_before_source_preflight(self):
        with self.assertRaises(ValueError):
            runner.execute(types.SimpleNamespace(), origin=time.monotonic() - 61)

    def test_22_final_flush_deadline_is_not_completion(self):
        # A retained COMPLETE file cannot override the caller's raised timeout.
        self.assertEqual(len(self.execute_fake('flush')), 2)

    def test_23_slow_preflight_preserves_complete_original_collection_duration(self):
        collection, overall = runner.execution_deadlines(100., 145., 1000, 30)
        self.assertEqual(collection, 1175.)
        self.assertEqual(overall, 1250.)
        self.assertEqual(collection - 145., 1000 + 30)
        self.assertLessEqual(collection + 30 + 30, overall)
        with self.assertRaises(ValueError): runner.execution_deadlines(100., 160., 1000, 30)


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'numpy': np.__version__, 'numerical_threads': 1,
                     'authentic_payloads': 0, 'native_runs': 0, 'model_calls': 0}))
    result = unittest.main(exit=False, verbosity=2).result
    print(json.dumps({'fixture_write_counter_bytes': WRITTEN,
                     'counter_scope': 'explicit write() fixture calls only; excludes controller opaque files and bridge receipts',
                     'temporary_fixtures_removed': True, 'tests': result.testsRun,
                     'failures': len(result.failures), 'errors': len(result.errors)}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
