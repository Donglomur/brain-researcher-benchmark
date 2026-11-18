"""Mocked author-estimator controls; no numerical imports, arrays or fitting."""
from __future__ import annotations

import builtins
from contextlib import contextmanager
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


VERSIONS = {'numpy': '1.24.3', 'sklearn': '1.2.2', 'scipy': '1.10.1'}
PROGRAMME = Path(__file__).with_name('author_programme.py')


def load_programme():
    with PROGRAMME.open('rb') as stream:
        raw = stream.read(4097)
    if not 0 < len(raw) <= 4096:
        raise AssertionError('Bounded author programme source required')
    module = types.ModuleType('_generated_author_programme')
    module.__file__ = str(PROGRAMME)
    exec(compile(raw, str(PROGRAMME), 'exec'), module.__dict__)
    return module


@contextmanager
def numerical_doubles(versions=None):
    """Replace every numerical module in this programme's import surface."""
    versions = VERSIONS if versions is None else versions
    modules = {}
    calls, instances = [], []
    for name, version in versions.items():
        module = types.ModuleType(name)
        module.__version__ = version
        modules[name] = module
    modules['sklearn'].__path__ = []
    linear = types.ModuleType('sklearn.linear_model')

    class Estimator:
        def __init__(self):
            self.fit_calls = []
            self.predict_calls = []
            self.output = object()

        def fit(self, train_x, train_y):
            self.fit_calls.append((train_x, train_y))
            return self

        def predict(self, query_x):
            self.predict_calls.append(query_x)
            return self.output

    def ridge(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        estimator = Estimator()
        instances.append(estimator)
        return estimator

    linear.Ridge = ridge
    modules['sklearn.linear_model'] = linear
    modules['sklearn'].linear_model = linear
    with mock.patch.dict(sys.modules, modules):
        yield calls, instances


class AuthorProgrammeControls(unittest.TestCase):
    def setUp(self):
        self.programme = load_programme()
        # Opaque Python objects deliberately cannot perform numerical fitting.
        self.train_x = {'training_features': [[1, 2], [3, 4]]}
        self.train_y = {'permitted_training_responses': [5, 6]}
        self.query_x = {'query_features': [[7, 8]]}
        self.context = {'session': 'generated', 'held_qid': 9.0,
                        'train_qid': [1.0, 2.0],
                        'train_time_indices': [10, 11],
                        'test_time_indices': [12]}

    def call(self):
        return self.programme.predict(self.train_x, self.train_y,
                                      self.query_x, self.context)

    def assert_version_refused_before_estimator(self, name):
        versions = dict(VERSIONS)
        versions[name] = 'wrong-version'
        original_import = builtins.__import__
        estimator_imports = []

        def guarded_import(module_name, *args, **kwargs):
            if module_name == 'sklearn.linear_model':
                estimator_imports.append(module_name)
                raise AssertionError('Estimator import before version refusal')
            return original_import(module_name, *args, **kwargs)

        before = copy.deepcopy((self.train_x, self.train_y,
                                self.query_x, self.context))
        with numerical_doubles(versions) as (calls, instances):
            with mock.patch('builtins.__import__', side_effect=guarded_import):
                with self.assertRaisesRegex(ValueError, 'historical author numerical stack'):
                    self.call()
            self.assertEqual(calls, [])
            self.assertEqual(instances, [])
        self.assertEqual(estimator_imports, [])
        self.assertEqual((self.train_x, self.train_y, self.query_x, self.context), before)

    def test_wrong_numpy_refuses_before_estimator(self):
        self.assert_version_refused_before_estimator('numpy')

    def test_wrong_sklearn_refuses_before_estimator(self):
        self.assert_version_refused_before_estimator('sklearn')

    def test_wrong_scipy_refuses_before_estimator(self):
        self.assert_version_refused_before_estimator('scipy')

    def test_literal_ridge_options_exact_operands_and_unchanged_context(self):
        before = copy.deepcopy((self.train_x, self.train_y,
                                self.query_x, self.context))
        with numerical_doubles() as (calls, instances):
            result = self.call()
        self.assertEqual(calls, [((), {'alpha': 0.01})])
        self.assertEqual(len(instances), 1)
        estimator = instances[0]
        self.assertEqual(len(estimator.fit_calls), 1)
        self.assertIs(estimator.fit_calls[0][0], self.train_x)
        self.assertIs(estimator.fit_calls[0][1], self.train_y)
        self.assertEqual(len(estimator.predict_calls), 1)
        self.assertIs(estimator.predict_calls[0], self.query_x)
        self.assertIs(result, estimator.output)
        self.assertEqual((self.train_x, self.train_y, self.query_x, self.context), before)

    def test_fresh_estimator_for_every_call(self):
        with numerical_doubles() as (calls, instances):
            first = self.call()
            second = self.call()
        self.assertEqual(calls, [((), {'alpha': 0.01}), ((), {'alpha': 0.01})])
        self.assertEqual(len(instances), 2)
        self.assertIsNot(instances[0], instances[1])
        self.assertIs(first, instances[0].output)
        self.assertIs(second, instances[1].output)
        self.assertIsNot(first, second)
        for estimator in instances:
            self.assertEqual(len(estimator.fit_calls), 1)
            self.assertEqual(len(estimator.predict_calls), 1)

    def test_source_loading_does_not_import_numerical_modules(self):
        original_import = builtins.__import__

        def no_numerical_import(module_name, *args, **kwargs):
            if module_name.split('.')[0] in VERSIONS:
                raise AssertionError('Numerical import while loading source')
            return original_import(module_name, *args, **kwargs)

        with mock.patch('builtins.__import__', side_effect=no_numerical_import):
            programme = load_programme()
        self.assertEqual(programme.HISTORICAL, VERSIONS)
        self.assertTrue(callable(programme.predict))


if __name__ == '__main__':
    unittest.main()
