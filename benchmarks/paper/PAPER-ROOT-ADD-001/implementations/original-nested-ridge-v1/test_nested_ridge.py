"""Tiny generated numerical controls; no original arrays or historical parity claim."""
import argparse
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

import numpy as np
from sklearn.linear_model import Ridge as ActualRidge

GRID = (0.001, 0.01, 0.1, 1.0, 10.0)
CANDIDATE = None
OBSERVATIONS = {}


def fixture():
    rng = np.random.default_rng(174)
    x = rng.normal(size=(72, 30)).astype(np.float64)
    x[:, 29] = np.arange(72)
    y = (x[:, 0] + 0.4 * x[:, 1] + 3 * rng.normal(size=72))[:, None]
    q = np.repeat(np.arange(-3, 3, dtype=np.float64), 12)
    query = rng.normal(size=(5, 30)).astype(np.float64)
    query[:, 29] = np.arange(100, 105)
    return x, y, query, {'train_qid': q, 'held_qid': 90.0}


def analytic_ridge(x, y, query, alpha):
    # Independent centered normal-equation solution, not sklearn or candidate helpers.
    mx, my = x.mean(axis=0), y.mean(axis=0)
    xc = x - mx
    coef = np.linalg.solve(xc.T @ xc + alpha * np.eye(x.shape[1]), xc.T @ (y - my))
    return (query - mx) @ coef + my


def oracle(x, y, q):
    groups = sorted(set(q.tolist()))
    scores = {}
    for alpha in GRID:
        p = np.empty_like(y)
        for fold in range(3):
            held = set(groups[fold::3])
            validation = np.asarray([v in held for v in q])
            p[validation] = analytic_ridge(x[~validation], y[~validation], x[validation], alpha)
        scores[alpha] = float(np.corrcoef(y[:, 0], p[:, 0])[0, 1])
    top = max(scores.values())
    tied = [a for a in GRID if top - scores[a] <= 1e-12]
    chosen = 0.01 if 0.01 in tied else min(tied)
    return chosen, scores


class NestedRidgeControls(unittest.TestCase):
    def test_real_estimator_matches_independent_pooled_oracle_and_group_exclusion(self):
        x, y, query, context = fixture()
        alpha, scores = oracle(x, y, context['train_qid'])
        records = []
        class RecordedRidge:
            def __init__(self, **kwargs):
                self.model = ActualRidge(**kwargs)
                self.record = {'alpha': kwargs['alpha']}
            def fit(self, xx, yy):
                self.record['train'] = tuple(xx[:, 29].astype(int))
                self.model.fit(xx, yy)
                records.append(self.record)
                return self
            def predict(self, zz):
                self.record['query'] = tuple(zz[:, 29].astype(int))
                return self.model.predict(zz)
        before = (x.copy(), y.copy(), query.copy(), context['train_qid'].copy())
        with mock.patch.object(CANDIDATE, 'Ridge', RecordedRidge):
            output = CANDIDATE.predict(x, y, query, context)
        self.assertEqual(len(records), 16)
        self.assertEqual(records[-1]['alpha'], alpha)
        full = set(range(len(x)))
        for record in records[:-1]:
            train, valid = set(record['train']), set(record['query'])
            self.assertFalse(train & valid)
            self.assertEqual(train | valid, full)
            self.assertFalse(set(context['train_qid'][list(train)]) & set(context['train_qid'][list(valid)]))
        for a in GRID:
            own = [record for record in records[:-1] if record['alpha'] == a]
            self.assertEqual(len(own), 3)
            self.assertEqual(sorted(i for record in own for i in record['query']), list(range(len(x))))
            groups = sorted(set(context['train_qid']))
            expected = {tuple(np.flatnonzero(np.isin(context['train_qid'], groups[f::3]))) for f in range(3)}
            self.assertEqual({record['query'] for record in own}, expected)
        self.assertEqual(records[-1]['train'], tuple(range(len(x))))
        np.testing.assert_allclose(output, analytic_ridge(x, y, query, alpha), rtol=1e-8, atol=1e-8)
        self.assertEqual(output.shape, (5, 1))
        self.assertEqual(output.dtype, np.dtype('float64'))
        for actual, saved in zip((x, y, query, context['train_qid']), before):
            np.testing.assert_array_equal(actual, saved)
        OBSERVATIONS['independent_oracle'] = {'selected_alpha': alpha, 'inner_pooled_pearson': scores,
                                             'real_sklearn_fits_observed': len(records)}

    def test_query_features_metadata_and_missing_query_labels_do_not_select_alpha(self):
        x, y, query, context = fixture()
        class Forbidden:
            def __array__(self, *args, **kwargs):
                raise AssertionError('Forbidden labels were read')
        context = dict(context, query_targets=Forbidden(), unused_metadata=Forbidden())
        original = CANDIDATE._select_alpha
        selections = []
        def observe(*args, **kwargs):
            self.assertEqual(len(args), 3)
            self.assertFalse(kwargs)
            chosen = original(*args)
            selections.append(chosen)
            return chosen
        with mock.patch.object(CANDIDATE, '_select_alpha', observe):
            first = CANDIDATE.predict(x, y, query, context)
            second = CANDIDATE.predict(x, y, query * 9 + 23, context)
        self.assertEqual(selections[0], selections[1])
        self.assertFalse(np.allclose(first, second))

    def test_exact_tie_and_undefined_policy(self):
        # Balanced identical group distributions give equal pooled correlation for all alphas.
        q = np.repeat(np.arange(6, dtype=np.float64), 3)
        x = np.zeros((18, 30), dtype=np.float64)
        x[:, 0] = np.tile([-1., 0., 1.], 6)
        y = 2 * x[:, :1] + 0.25
        self.assertEqual(CANDIDATE._select_alpha(x, y, q), 0.01)
        self.assertEqual(CANDIDATE._select_alpha(x, np.ones_like(y), q), 0.01)
        # A separate public-entry fallback uses only the available two training groups.
        q2 = np.repeat(np.array([-2., 7.]), 9)
        query = x[:4].copy()
        out = CANDIDATE.predict(x, y, query, {'train_qid': q2, 'held_qid': 90.})
        np.testing.assert_allclose(out, analytic_ridge(x, y, query, 0.01), atol=1e-10, rtol=1e-10)

    def test_training_row_order_does_not_change_group_selection(self):
        x, y, query, context = fixture()
        perm = np.random.default_rng(88).permutation(len(x))
        base_alpha = CANDIDATE._select_alpha(x, y, context['train_qid'])
        reordered_alpha = CANDIDATE._select_alpha(x[perm], y[perm], context['train_qid'][perm])
        self.assertEqual(base_alpha, reordered_alpha)
        out = CANDIDATE.predict(x[perm], y[perm], query,
                                {'train_qid': context['train_qid'][perm], 'held_qid': 90.})
        np.testing.assert_allclose(out, analytic_ridge(x, y, query, base_alpha), atol=1e-8, rtol=1e-8)

    def test_exact_single_output_normalization_keeps_malformed_refusals(self):
        vector = np.array([1., 2., 3.], dtype=np.float64)
        column = vector[:, None]
        np.testing.assert_array_equal(CANDIDATE._prediction(vector, 3), column)
        np.testing.assert_array_equal(CANDIDATE._prediction(column, 3), column)
        for value in (vector[:2], np.ones((3, 2)), np.ones((1, 3)),
                      vector.astype(np.float32), np.array([1., np.nan, 3.]),
                      np.ones((3, 1, 1)), [1., 2., 3.]):
            with self.subTest(shape=getattr(value, 'shape', None)), self.assertRaises(ValueError):
                CANDIDATE._prediction(value, 3)

    def test_invalid_inputs_refused_before_any_fit(self):
        x, y, query, context = fixture()
        cases = [
            (x.astype(np.float32), y, query, context),
            (x[:, :29], y, query, context),
            (x, y[:, 0], query, context),
            (x, y, query[:, :29], context),
            (x, y, query, {'train_qid': context['train_qid'][:-1], 'held_qid': 90.}),
            (x, y, query, {'train_qid': context['train_qid'] + .5, 'held_qid': 90.}),
            (x, y, query, {'train_qid': context['train_qid'], 'held_qid': -3.}),
            (x, y, query, {'train_qid': context['train_qid']}),
            (x, np.full_like(y, np.nan), query, context),
            (x, y, np.full_like(query, np.inf), context),
            (x, y, query, {'train_qid': np.full(72, np.inf), 'held_qid': 90.}),
        ]
        class NoFit:
            def __init__(self, **kwargs):
                raise AssertionError('Invalid input reached estimator construction')
        with mock.patch.object(CANDIDATE, 'Ridge', NoFit):
            for index, args in enumerate(cases):
                with self.subTest(case=index), self.assertRaises((ValueError, TypeError)):
                    CANDIDATE.predict(*args)
        OBSERVATIONS['invalid_cases'] = len(cases)


def main():
    global CANDIDATE
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, default=Path(__file__).with_name('candidate.py'))
    args = p.parse_args()
    raw = args.candidate.read_bytes()
    CANDIDATE = type(importlib.util)('generated_candidate')
    exec(compile(raw, str(args.candidate), 'exec'), CANDIDATE.__dict__)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NestedRidgeControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'schema': 'language-nested-ridge-generated-controls/v1', 'tests_run': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors),
                      'observations': OBSERVATIONS, 'original_data': False,
                      'historical_runtime_parity': False, 'scientific_performance': False}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
