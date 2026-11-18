"""Generated spy-estimator controls only: no empirical data or statistical fit."""
import copy
import hashlib
import importlib
from pathlib import Path
import sys
import unittest

import numpy as np

PROGRAM = Path(__file__).resolve().parents[1] / 'program'


class SpyBNB:
    calls = []
    mode = 'normal'

    def __init__(self, **kwargs):
        if kwargs != {'fit_prior': False}:
            raise AssertionError('author constructor arguments changed')
        self.classes_ = np.array([0, 1], dtype=np.int64)
        if self.mode == 'reverse_classes':
            self.classes_ = self.classes_[::-1]

    def fit(self, X, y):
        if self.mode == 'fail_third' and len(self.calls) == 2:
            raise RuntimeError('generated estimator refusal')
        self.calls.append((X[:, 1].tolist(), y.tolist()))
        return self

    def predict_proba(self, X):
        p = np.where(X[:, 0] > 0, .8, .2)
        if self.mode == 'tie':
            p[:] = .5
        if self.mode == 'nonfinite':
            p[:] = np.nan
        return np.column_stack((1 - p, p))

    def get_params(self, deep=False):
        return {'alpha': .5 if self.mode == 'wrong_alpha' else 1,
                'binarize': 0, 'fit_prior': False, 'class_prior': None}


class SpySplit:
    def __init__(self, **kwargs):
        if kwargs != {'n_splits': 5, 'shuffle': True, 'random_state': 622}:
            raise AssertionError('source fold arguments changed')

    def split(self, X, y):
        for f in range(5):
            test = np.array([f, f + 5], dtype=np.int64)
            train = np.array([i for i in range(10) if i not in test], dtype=np.int64)
            yield train, test


class AuthorReplayControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ('common', 'prepare', 'support', 'author_replay')
        prior = {name: sys.modules.pop(name, None) for name in names}
        sys.path.insert(0, str(PROGRAM))
        try:
            cls.module = importlib.import_module('author_replay')
        finally:
            sys.path.remove(str(PROGRAM))
            for name, value in prior.items():
                sys.modules.pop(name, None)
                if value is not None:
                    sys.modules[name] = value
        cls.source = (PROGRAM / 'author/PythonCode/EventClassification/HierarchicalEventClassifier.py').read_bytes()

    def setUp(self):
        SpyBNB.calls = []
        SpyBNB.mode = 'normal'

    def fixture(self):
        records, arrays = [], {}
        for i in range(40):
            member = f'EventClassificationData_4C/#engineering-{i:02d}_PL_eventClassificationData.mat'
            sid = hashlib.sha256(member.encode()).hexdigest()[:24]
            folds = []
            for f in range(5):
                test = [f, f + 5]
                train = [j for j in range(10) if j not in test]
                folds.append({'fold': f + 1, 'train_positions0': train,
                              'test_positions0': test, 'train_order0': train[::-1],
                              'query_order0': test[::-1]})
            row = {'session_id': sid, 'source_session_token': f'#engineering-{i:02d}_PL',
                   'source_member': member, 'source_R': 20, 'rows': 10, 'features': 40,
                   'unit_blocks': 1, 'native_supported': True, 'nested3_supported': True,
                   'prepared': dict.fromkeys(('X.npy', 'y.npy', 'source_rows.npy', 'fold_ids.npy')),
                   'folds': folds, 'source_HW_counts': {'avoidance': 5, 'escape': 5},
                   'window_seconds': [-1, 1], 'bin_seconds': .05, 'clip': [-5, 5],
                   'native_fold_seed': 622, 'upstream_whole_session_normalized': True,
                   'private_row_maps_candidate_visible': False}
            records.append(row)
            y = np.array([0] * 5 + [1] * 5, dtype=np.int64)
            X = np.zeros((10, 40), dtype=np.float64)
            X[:, 0] = y * 2 - 1
            X[:, 1] = np.arange(10) / 2  # Unique bounded row markers for spying.
            arrays[sid] = (X, y)
        bundle = {'schema': 'foraging_full40_prepared_v1', 'task_id': self.module.TASK,
                  'complete_native_support': True, 'complete_nested3_support': True,
                  'archive': dict(self.module.ARCHIVE), 'records': records,
                  'archive_inventory': [{'name': r['source_member'],
                                         'disposition': 'full_original_classification_MAT'}
                                        for r in records]}
        return bundle, arrays

    def run_fixture(self, bundle, arrays, source=None, cap=3200, loader=None):
        runtime = (np, SpyBNB, SpySplit, {'scope': 'generated spy dependencies, not admitted runtime'})
        return self.module._replay_with_dependencies(
            bundle, self.source if source is None else source,
            loader or (lambda row: arrays[row['session_id']]), lambda: None, runtime, cap)

    def test_complete_original_order_and_exact200_author_calls(self):
        bundle, arrays = self.fixture()
        before = copy.deepcopy(bundle)
        report, probabilities = self.run_fixture(bundle, arrays)
        self.assertEqual(bundle, before)
        self.assertEqual(len(SpyBNB.calls), 200)
        self.assertEqual(report['completed_real_fits'], 200)
        self.assertEqual(set(probabilities), set(arrays))
        for row in bundle['records']:
            np.testing.assert_array_equal(probabilities[row['session_id']], [.2] * 5 + [.8] * 5)
        first_train = bundle['records'][0]['folds'][0]['train_positions0']
        self.assertEqual(SpyBNB.calls[0][0], [i / 2 for i in first_train])
        self.assertEqual(len(SpyBNB.calls[0][1]), 8)  # No test labels passed into fit.
        self.assertEqual(report['equal_session_balanced_accuracy'], 1)
        self.assertFalse(report['unchanged_whole_script_execution'])
        self.assertFalse(report['source_shuffle_companions_executed'])
        self.assertFalse(report['historical_environment_equivalence'])
        self.assertIsNone(report['paper_reproduced'])
        self.assertIsNone(report['paper_win'])
        self.assertFalse(report['improvement_ready'])

    def test_exact_source_required_without_whole_script_execution(self):
        bundle, arrays = self.fixture()
        with self.assertRaisesRegex(ValueError, 'exact retained author'):
            self.run_fixture(bundle, arrays, source=self.source + b'\n')
        self.assertFalse(SpyBNB.calls)

    def test_missing_session_or_unselected_member_refused_before_fits(self):
        for mutation in ('session', 'member'):
            bundle, arrays = self.fixture()
            if mutation == 'session':
                bundle['records'].pop()
            else:
                bundle['archive_inventory'][0]['name'] = 'other.mat'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.run_fixture(bundle, arrays)
            self.assertFalse(SpyBNB.calls)

    def test_source_recipe_and_capacity_cannot_be_weakened(self):
        for key, value in [('native_fold_seed', 623), ('window_seconds', [-1, 0]),
                           ('private_row_maps_candidate_visible', True)]:
            bundle, arrays = self.fixture()
            bundle['records'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_fixture(bundle, arrays)
        bundle, arrays = self.fixture()
        with self.assertRaisesRegex(ValueError, 'output numerical capacity'):
            self.run_fixture(bundle, arrays, cap=3199)
        self.assertFalse(SpyBNB.calls)

    def test_class_count_metadata_rejects_coercion_and_incomplete_support(self):
        for counts in ({'avoidance': True, 'escape': 9},
                       {'avoidance': 5., 'escape': 5},
                       {'avoidance': 5, 'escape': 4},
                       {'avoidance': 5, 'escape': 5, 'other': 0}):
            bundle, arrays = self.fixture()
            bundle['records'][0]['source_HW_counts'] = counts
            with self.subTest(counts=counts), self.assertRaisesRegex(ValueError, 'source HW class counts'):
                self.run_fixture(bundle, arrays)
            self.assertFalse(SpyBNB.calls)

    def test_valid_partition_from_different_fold_draw_is_rejected(self):
        bundle, arrays = self.fixture()
        row = bundle['records'][0]
        for f, test in [(0, [1, 5]), (1, [0, 6])]:
            train = [i for i in range(10) if i not in test]
            row['folds'][f].update(test_positions0=test, query_order0=test[::-1],
                                   train_positions0=train, train_order0=train[::-1])
        with self.assertRaises(self.module.ReplayFailure) as caught:
            self.run_fixture(bundle, arrays)
        self.assertIn('canonical seed622', str(caught.exception))
        self.assertEqual(caught.exception.attempted_fits, 0)

    def test_invalid_feature_or_label_inputs_refused_before_estimator(self):
        for mutation in ('nan', 'clip', 'counts', 'dtype'):
            bundle, arrays = self.fixture()
            sid = bundle['records'][0]['session_id']
            X, y = arrays[sid]
            if mutation == 'nan': X[0, 0] = np.nan
            if mutation == 'clip': X[0, 0] = 6
            if mutation == 'counts': y[0] = 1
            if mutation == 'dtype': arrays[sid] = X, y.astype(bool)
            with self.subTest(mutation=mutation), self.assertRaises(self.module.ReplayFailure) as caught:
                self.run_fixture(bundle, arrays)
            self.assertEqual(caught.exception.attempted_fits, 0)
            self.assertFalse(SpyBNB.calls)

    def test_estimator_mismatch_or_nonfinite_output_never_returns_result(self):
        for mode, attempted in [('reverse_classes', 1), ('wrong_alpha', 1), ('nonfinite', 5)]:
            SpyBNB.calls, SpyBNB.mode = [], mode
            bundle, arrays = self.fixture()
            with self.subTest(mode=mode), self.assertRaises(self.module.ReplayFailure) as caught:
                self.run_fixture(bundle, arrays)
            self.assertEqual(caught.exception.attempted_fits, attempted)
            self.assertEqual(caught.exception.completed_sessions, 0)

    def test_later_failure_preserves_attempt_counts_not_partial_success(self):
        bundle, arrays = self.fixture()
        second = bundle['records'][1]['session_id']
        def loader(row):
            if row['session_id'] == second:
                raise ValueError('generated second-session input failure')
            return arrays[row['session_id']]
        with self.assertRaises(self.module.ReplayFailure) as caught:
            self.run_fixture(bundle, arrays, loader=loader)
        self.assertEqual(caught.exception.attempted_fits, 5)
        self.assertEqual(caught.exception.completed_sessions, 1)

    def test_fit_exception_counts_attempt_that_did_not_complete(self):
        bundle, arrays = self.fixture()
        SpyBNB.mode = 'fail_third'
        with self.assertRaises(self.module.ReplayFailure) as caught:
            self.run_fixture(bundle, arrays)
        self.assertEqual(caught.exception.attempted_fits, 3)
        self.assertEqual(len(SpyBNB.calls), 2)

    def test_source_tie_threshold_is_escape(self):
        bundle, arrays = self.fixture()
        SpyBNB.mode = 'tie'
        report, _ = self.run_fixture(bundle, arrays)
        self.assertEqual(report['equal_session_balanced_accuracy'], .5)
        self.assertTrue(all(r['confusion_counts'] == [[0, 5], [0, 5]]
                            for r in report['sessions'].values()))


if __name__ == '__main__':
    unittest.main()
