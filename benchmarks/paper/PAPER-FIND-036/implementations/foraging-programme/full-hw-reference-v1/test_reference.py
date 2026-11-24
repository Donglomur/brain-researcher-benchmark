"""Generated source-path controls; no authentic data or sklearn model run."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
PROGRAM = Path(os.environ.get('FORAGING_EXISTING_SOURCE_ROOT', str(HERE.parent / 'program')))


class EquationEstimator:
    """Generated equation-based test double, not a qualified sklearn baseline."""
    calls = []
    mode = 'normal'

    def __init__(self, **kwargs):
        assert kwargs == {'fit_prior': False}

    def fit(self, X, y):
        if self.mode == 'fail_shuffle' and len(self.calls) == 1:
            raise RuntimeError('generated second-fit failure')
        self.calls.append((X.copy(), y.copy()))
        self.classes_ = np.array([0, 1], dtype=np.int64)
        self.n_features_in_ = X.shape[1]
        self.class_count_ = np.array([(y == c).sum() for c in (0, 1)], dtype=np.float64)
        self.feature_count_ = np.stack([(X[y == c] > 0).sum(axis=0, dtype=np.float64) for c in (0, 1)])
        self.feature_log_prob_ = np.log(self.feature_count_ + 1) - np.log(self.class_count_[:, None] + 2)
        self.class_log_prior_ = np.full(2, -np.log(2), dtype=np.float64)
        if self.mode == 'wrong_count':
            self.feature_count_[0, 0] += 1
        return self

    def predict_proba(self, X):
        ln = np.log(1 - np.exp(self.feature_log_prob_))
        scores = (X > 0).astype(float) @ (self.feature_log_prob_ - ln).T
        scores += ln.sum(axis=1) + self.class_log_prior_
        probs = np.exp(scores - np.logaddexp(scores[:, 0], scores[:, 1])[:, None])
        if self.mode == 'nonfinite':
            probs[:] = np.nan
        if self.mode == 'exact_tie':
            probs[:] = .5
        return probs

    def get_params(self, deep=False):
        return {'alpha': 1.0, 'binarize': 0.0, 'fit_prior': False, 'class_prior': None}


class FixedGeneratedSplit:
    def __init__(self, **kwargs):
        assert kwargs == {'n_splits': 5, 'shuffle': True, 'random_state': 622}

    def split(self, X, y):
        for fold in range(5):
            test = np.array([fold, fold + 5], dtype=np.int64)
            yield np.array([i for i in range(10) if i not in test], dtype=np.int64), test


class FullReferenceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names = ('common', 'prepare', 'support', 'array_io', 'author_replay', 'full_hw_reference')
        cls.previous = {name: sys.modules.pop(name, None) for name in cls.names}
        spec = importlib.util.spec_from_file_location('_full_hw_cli_test', HERE / 'cli.py')
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)
        cls.modules, _ = cls.cli.load_components(PROGRAM)
        cls.ref, cls.c = cls.modules['full_hw_reference'], cls.modules['common']
        cls.source = (PROGRAM / 'author/PythonCode/EventClassification/HierarchicalEventClassifier.py').read_bytes()

    @classmethod
    def tearDownClass(cls):
        for name in cls.names:
            sys.modules.pop(name, None)
            if cls.previous[name] is not None:
                sys.modules[name] = cls.previous[name]

    def setUp(self):
        EquationEstimator.calls, EquationEstimator.mode = [], 'normal'
        self.rng = {'schema': self.ref.RNG_SCHEMA, 'seed': 2**100 + 17,
                    'bit_generator': 'PCG64', 'stream': 'source-member-sorted-HW-only'}
        self.runtime = (np, EquationEstimator, FixedGeneratedSplit,
                        {'scope': 'generated equation double and split; not admitted runtime'})

    def fixture(self):
        records, arrays = [], {}
        for i in range(40):
            member = f'EventClassificationData_4C/#generated-{i:02d}_PL_eventClassificationData.mat'
            sid = hashlib.sha256(member.encode()).hexdigest()[:24]
            folds = []
            for f in range(5):
                test = [f, f + 5]
                train = [v for v in range(10) if v not in test]
                folds.append({'fold': f + 1, 'train_positions0': train, 'test_positions0': test,
                              'train_order0': train[::-1], 'query_order0': test[::-1]})
            records.append({'session_id': sid, 'source_member': member,
                            'source_session_token': f'#generated-{i:02d}_PL', 'source_R': 20,
                            'rows': 10, 'features': 40, 'unit_blocks': 1,
                            'native_supported': True, 'nested3_supported': True,
                            'prepared': dict.fromkeys(('X.npy', 'y.npy', 'source_rows.npy', 'fold_ids.npy')),
                            'folds': folds, 'source_HW_counts': {'avoidance': 5, 'escape': 5},
                            'window_seconds': [-1, 1], 'bin_seconds': .05, 'clip': [-5, 5],
                            'native_fold_seed': 622, 'upstream_whole_session_normalized': True,
                            'private_row_maps_candidate_visible': False})
            y = np.array([0] * 5 + [1] * 5, dtype=np.int64)
            X = np.zeros((10, 40), dtype=np.float64)
            X[:, 0] = y * 2 - 1
            X[:, 1] = np.arange(10) / 2
            arrays[sid] = (X, y)
        return {'schema': 'foraging_full40_prepared_v1', 'task_id': self.c.TASK,
                'archive': dict(self.ref.prior.ARCHIVE), 'records': records,
                'complete_native_support': True, 'complete_nested3_support': True,
                'archive_inventory': [{'name': r['source_member'],
                                       'disposition': 'full_original_classification_MAT'} for r in records]}, arrays

    def run_panel(self, prepared=None, arrays=None, source=None, capacity=6400, rng=None, capture=None):
        if prepared is None:
            prepared, arrays = self.fixture()
        audits = []
        def save(audit):
            raw = self.c.encode(audit)
            audits.append(self.c.parse(raw))
            return self.c.pin(raw)
        report, outputs = self.ref._with_dependencies(
            prepared, self.source if source is None else source,
            lambda row: arrays[row['session_id']], lambda: None, self.runtime, capacity,
            self.rng if rng is None else rng, save if capture is None else capture)
        return report, outputs, audits

    def test_complete_source400_fits_real_parity_and_numeric_state_roundtrip(self):
        prepared, arrays = self.fixture()
        frozen = copy.deepcopy(prepared)
        report, outputs, audits = self.run_panel(prepared, arrays)
        self.assertEqual(prepared, frozen)
        self.assertEqual(len(EquationEstimator.calls), 400)
        self.assertEqual(report['fit_counts'], dict.fromkeys(
            ('real_attempted', 'real_completed', 'shuffle_attempted', 'shuffle_completed'), 200))
        self.assertEqual(len(audits), 200)
        self.assertEqual(report['rng']['selection']['seed'], 2**100 + 17)
        self.assertEqual(audits[0]['rng']['before'], report['rng']['initial_state'])
        self.assertEqual(audits[-1]['rng']['after'], report['rng']['final_state'])
        for a in audits:
            X, y = arrays[a['session_id']]
            train, test = a['train_positions0'], a['test_positions0']
            shuffled_y = y[train][a['rng']['training_permutation0']]
            for role, labels in (('real', y[train]), ('shuffle', shuffled_y)):
                state = a['models'][role]
                np.testing.assert_allclose(self.ref.predict_state(np, state, X[test]),
                                           outputs[(a['session_id'], role)][test], rtol=0, atol=1e-12)
                self.assertEqual(state['class_count'], [(labels == c).sum() for c in (0, 1)])
            self.assertEqual(sorted(a['rng']['training_permutation0']), list(range(len(train))))
        _, old = self.ref.prior._replay_with_dependencies(
            prepared, self.source, lambda row: arrays[row['session_id']], lambda: None, self.runtime, 3200)
        for sid, p in old.items():
            np.testing.assert_array_equal(p, outputs[(sid, 'real')])
        self.assertTrue(report['source_shuffle_companions_executed'])
        self.assertFalse(report['historical_shuffle_realization_reproduced'])
        self.assertFalse(report['unchanged_whole_script_execution'])
        self.assertIsNone(report['paper_reproduced'])
        self.assertIsNone(report['paper_win'])

    def test_frozen_seed_stream_reconstructs_training_shuffle_without_query_labels(self):
        _, _, audits = self.run_panel()
        clone = np.random.default_rng(self.rng['seed'])
        prepared, arrays = self.fixture()
        for index, a in enumerate(audits):
            expected = arrays[a['session_id']][1][a['train_positions0']].copy()
            clone.shuffle(expected)
            np.testing.assert_array_equal(EquationEstimator.calls[2 * index + 1][1], expected)
            self.assertEqual(len(EquationEstimator.calls[2 * index][1]), 8)
        self.assertEqual(clone.bit_generator.state, audits[-1]['rng']['after'])

    def test_invalid_seed_algorithm_source_or_full_capacity_refused_before_fits(self):
        for change in ({'seed': True}, {'seed': -1}, {'seed': 2**128}, {'bit_generator': 'PCG64DXSM'}):
            spec = {**self.rng, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_panel(rng=spec)
        with self.assertRaisesRegex(ValueError, 'exact retained author'):
            self.run_panel(source=self.source + b'\n')
        with self.assertRaisesRegex(ValueError, 'capacity'):
            self.run_panel(capacity=6399)
        self.assertEqual(EquationEstimator.calls, [])

    def test_missing_session_and_changed_source_window_refused(self):
        for mode in ('missing', 'window'):
            prepared, arrays = self.fixture()
            if mode == 'missing':
                prepared['records'].pop()
            else:
                prepared['records'][0]['window_seconds'] = [-1, 0]
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.run_panel(prepared, arrays)
        self.assertEqual(EquationEstimator.calls, [])

    def test_changed_original_fold_membership_refused_before_fit(self):
        prepared, arrays = self.fixture()
        row = prepared['records'][0]
        for f, test in ((0, [1, 5]), (1, [0, 6])):
            train = [i for i in range(10) if i not in test]
            row['folds'][f].update(test_positions0=test, query_order0=test[::-1],
                                   train_positions0=train, train_order0=train[::-1])
        with self.assertRaises(self.ref.ReferenceFailure) as caught:
            self.run_panel(prepared, arrays)
        self.assertIn('canonical source-order', str(caught.exception))
        self.assertEqual(caught.exception.fit_counts['real_attempted'], 0)

    def test_second_fit_failure_retains_exact_attempted_and_completed_counts(self):
        EquationEstimator.mode = 'fail_shuffle'
        with self.assertRaises(self.ref.ReferenceFailure) as caught:
            self.run_panel()
        self.assertEqual(caught.exception.fit_counts, {
            'real_attempted': 1, 'real_completed': 1, 'shuffle_attempted': 1, 'shuffle_completed': 0})
        self.assertEqual(caught.exception.completed_sessions, 0)

    def test_deadline_after_successful_fit_preserves_known_completion(self):
        prepared, arrays = self.fixture()
        def tick():
            if len(EquationEstimator.calls) == 1:
                raise ValueError('generated post-fit deadline')
        with self.assertRaises(self.ref.ReferenceFailure) as caught:
            self.ref._with_dependencies(
                prepared, self.source, lambda row: arrays[row['session_id']], tick,
                self.runtime, 6400, self.rng, lambda _: {})
        self.assertEqual(caught.exception.fit_counts, {
            'real_attempted': 1, 'real_completed': 1, 'shuffle_attempted': 0, 'shuffle_completed': 0})
        self.assertEqual(caught.exception.completed_sessions, 0)

    def test_wrong_fitted_state_or_prediction_refused(self):
        for mode in ('wrong_count', 'nonfinite'):
            EquationEstimator.calls, EquationEstimator.mode = [], mode
            with self.subTest(mode=mode), self.assertRaises(self.ref.ReferenceFailure):
                self.run_panel()

    def test_missing_audit_capture_cannot_be_success(self):
        with self.assertRaises(self.ref.ReferenceFailure) as caught:
            self.run_panel(capture=lambda _: {})
        self.assertEqual(caught.exception.fit_counts['shuffle_completed'], 1)
        self.assertEqual(caught.exception.completed_sessions, 0)

    def test_tie_is_escape_and_state_tampering_is_rejected(self):
        prepared, arrays = self.fixture()
        EquationEstimator.mode = 'exact_tie'
        for X, _ in arrays.values():
            X[:] = 0
        report, _, audits = self.run_panel(prepared, arrays)
        self.assertEqual(report['equal_session_balanced_accuracy'], {'real': .5, 'shuffle': .5})
        self.assertTrue(all(s['real']['confusion_counts'] == [[0, 5], [0, 5]]
                            for s in report['sessions'].values()))
        state = audits[0]['models']['real']
        state['feature_count'][0][0] += 1
        with self.assertRaisesRegex(ValueError, 'state equations'):
            self.ref.predict_state(np, state, np.zeros((2, 40), dtype=np.float64))

    def test_cli_persists_complete_panel_and_rejects_resume(self):
        prepared, arrays = self.fixture()
        temp_root = Path(os.environ.get('FORAGING_TEST_TMP', tempfile.gettempdir())).resolve()
        with tempfile.TemporaryDirectory(dir=temp_root) as tmp:
            root = Path(tmp)
            for row in prepared['records']:
                for name, a in zip(('X.npy', 'y.npy'), arrays[row['session_id']]):
                    file = root / (row['session_id'] + name)
                    np.save(file, a, allow_pickle=False)
                    raw = file.read_bytes()
                    row['prepared'][name] = {'path': str(file), **self.c.pin(raw)}
            raw = self.c.encode(prepared)
            pfile = root / 'prepared.json'; pfile.write_bytes(raw)
            source = PROGRAM / 'author/PythonCode/EventClassification/HierarchicalEventClassifier.py'
            limits = {'read_bytes': 16 << 20, 'write_bytes': 8 << 20, 'retained_bytes': 8 << 20,
                      'other_future_bytes': 0, 'free_floor_bytes': 1, 'wall_seconds': 30}
            selection = {'schema': self.cli.SCHEMA, 'task_id': self.c.TASK, 'limits': limits,
                         'prepared': {'path': str(pfile), **self.c.pin(raw)},
                         'author_source': {'path': str(source), **self.c.pin(self.source)},
                         'output_root': str(root / 'output'), 'output_numeric_capacity_bytes': 6400,
                         'metadata_cap_bytes': 1 << 20, 'fold_audit_cap_bytes': 65536,
                         'audit_total_capacity_bytes': 2 << 20, 'rng': self.rng,
                         'component_scope_acknowledged': True}
            budget = self.c.Budget(limits, time.monotonic())
            with mock.patch.object(self.ref.prior, '_load_adopted_runtime', return_value=self.runtime):
                result = self.cli._execute(selection, budget, self.modules, {})
            self.assertEqual(result['status'], 'complete_source_reference_component_only')
            saved = self.c.parse((root / 'output/COMPONENT_RESULT.json').read_bytes())
            self.assertEqual(saved['fitted_states'], 400)
            self.assertEqual(saved['model_audit_files'], 200)
            self.assertEqual(len(list((root / 'output').iterdir())), 282)
            self.assertIsNone(saved['paper_win'])
            print(json.dumps({'generated_persistence_control': {
                'managed_write_charge_bytes': budget.write,
                'managed_read_charge_bytes': budget.read,
                'fixture_payload_bytes': sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
                'retained_output_bytes': sum(p.stat().st_size for p in (root / 'output').iterdir())}}))
            with self.assertRaisesRegex(ValueError, 'fresh private output'):
                self.cli._execute(selection, self.c.Budget(limits, time.monotonic()), self.modules, {})


if __name__ == '__main__':
    unittest.main()
