"""Generated controls only; no source neural arrays, targets, or models."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

# Support isolated Python (-I) without package installation.
HERE = Path(__file__).resolve().parent
for name in ('core', 'io_utils', 'artifacts', 'score'):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
import core
import artifacts
import score


def public_fixture():
    people = {}
    counter = 0
    for person in core.PEOPLE:
        people[person] = {}
        for phase, n in [('imagery', 500), ('perception', 1750)]:
            people[person][phase + '_ids'] = ['q%024x' % i for i in range(counter, counter + n)]
            counter += n
    return {'schema': core.VERSION, 'source_design_sha256': 'a' * 64, 'people': people,
            'unit_ids': {f: core.matched_indices(f, 1024 if f == 'gist' else 1000).tolist() for f in core.FAMILIES}}


def submission_fixture():
    return {'schema': 'neural076_predictions_v1', 'source_design_sha256': 'a' * 64,
            'parts': [{'key': key, 'path': 'part%d.npz' % i} for i, key in enumerate(artifacts.part_keys())]}


def gold_fixture():
    gold = {p + '_' + s: np.repeat(np.arange(50), n)
            for p in core.PEOPLE for s, n in [('imagery', 10), ('perception', 35)]}
    bank = np.broadcast_to(np.arange(50, dtype=float)[:, None], (50, 1000))
    gold.update({'bank_' + f: bank for f in core.FAMILIES})
    return gold


class NumericalControls(unittest.TestCase):
    def test_correlates_across_categories_then_averages_signed_units(self):
        # Independent scalar Pearson oracle detects a transposed/flattened score.
        x = np.array([[1, 1, 1], [2, 4, 3], [3, 2, 2], [4, 3, 4]], dtype=float)
        y = np.array([[1, -2, 1], [2, -8, 2], [3, -4, 4], [4, -6, 3]], dtype=float)
        actual, _, _ = core.column_pearson(x, y)
        expected = []
        for j in range(3):
            a, b = x[:, j].tolist(), y[:, j].tolist()
            da = [v - sum(a) / len(a) for v in a]
            db = [v - sum(b) / len(b) for v in b]
            expected.append(sum(u * v for u, v in zip(da, db)) /
                            (sum(u * u for u in da) * sum(v * v for v in db)) ** 0.5)
        np.testing.assert_allclose(actual, expected, atol=1e-14)
        self.assertLess(actual.mean(), 0.4)  # Absolute-value scoring would fail.

    def test_category_averaging_precedes_correlation_and_ignores_row_order(self):
        bank = gold_fixture()['bank_cnn1']
        labels = np.repeat(np.arange(50), 10)
        noise = np.tile(np.arange(10) - 4.5, 50)[:, None] * 100
        predictions = bank[labels] + noise
        order = np.arange(500)[::-1]
        result = core.feature_score(predictions[order], labels[order], bank, 10)
        self.assertAlmostEqual(result['mean_r'], 1.)
        self.assertEqual(result['defined_units'], 1000)

    def test_undefined_unit_is_retained_not_zero_imputed_or_dropped(self):
        labels = np.repeat(np.arange(50), 10)
        bank = gold_fixture()['bank_cnn1'].copy()
        predictions = bank[labels].copy()
        predictions[:, 7] = 0
        bank[:, 12] = 4
        result = core.feature_score(predictions, labels, bank, 10)
        self.assertIsNone(result['mean_r'])
        self.assertEqual(result['defined_units'], 998)
        self.assertEqual(result['constant_prediction_unit_positions'], [7])
        self.assertEqual(result['constant_target_unit_positions'], [12])
        json.dumps(result, allow_nan=False)

    def test_finite_extremes_and_invalid_repeats(self):
        x = np.array([[-1e308, 1], [0, 2], [1e308, 3]])
        r, _, _ = core.column_pearson(x, -x)
        np.testing.assert_allclose(r, [-1, -1], atol=1e-14)
        with self.assertRaises(ValueError):
            core.category_means(np.zeros((100, 2)), np.repeat(np.arange(50), 2), repeats=10)

    def test_current_contrast_does_not_use_legacy_layer_average(self):
        cells = {s: {r: {f: 0. for f in core.FAMILIES} for r in core.ROIS} for s in core.PHASES}
        cells['imagery']['HVC']['cnn7'] = .8
        cells['imagery']['HVC']['cnn1'] = -.2
        cells['imagery']['LVC']['cnn7'] = .3
        cells['imagery']['LVC']['cnn1'] = .1
        result = core.contrasts(cells)
        self.assertAlmostEqual(result[score.PRIMARY], .8)
        self.assertAlmostEqual(result['imagery_legacy_cnn5to8_minus_cnn1to4_HVC_minus_LVC'], .2)
        cells['imagery']['HVC']['cnn1'] = None
        self.assertIsNone(core.contrasts(cells)[score.PRIMARY])

    def test_five_people_are_not_reweighted_or_silently_excluded(self):
        result = core.participant_summary([1., 0., -1., .5, -.5])
        self.assertEqual(result['mean'], 0.)
        self.assertEqual(result['independent_participants'], 5)
        self.assertIsNone(core.participant_summary([1., 0., -1., .5, None])['mean'])
        with self.assertRaises(ValueError):
            core.participant_summary([1., 0., -1., .5])


class BoundaryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = public_fixture()
        cls.submission = submission_fixture()

    def test_missing_final_context_and_late_malformed_block_precede_targets(self):
        bad = copy.deepcopy(self.submission)
        bad['parts'].pop()
        with patch.object(score, 'load') as loader:
            result = score.assess(bad, self.public, '.', lambda: self.fail('Targets read'))
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(result['target_loader_calls'], 0)
        loader.assert_not_called()
        calls = []

        def reader(path, ids, units, expected_sha=None):
            calls.append(path.name)
            if len(calls) == 650:
                raise ValueError('Last block malformed')
            return None, 'b' * 64

        with patch.object(score, 'load', side_effect=reader):
            result = score.assess(self.submission, self.public, '.', lambda: self.fail('Targets read'))
        self.assertEqual(len(calls), 650)
        self.assertEqual(result['target_loader_calls'], 0)

    def test_source_binding_mismatch_precedes_targets(self):
        bad = copy.deepcopy(self.submission)
        bad['source_design_sha256'] = 'c' * 64
        with patch.object(score, 'load') as loader:
            result = score.assess(bad, self.public, '.', lambda: self.fail('Targets read'))
        self.assertEqual(result['status'], 'invalid_submission')
        loader.assert_not_called()

    def test_changed_submission_on_second_pass_is_not_scored(self):
        def reader(path, ids, units, expected_sha=None):
            if expected_sha is not None:
                raise ValueError('Submission changed after complete public validation')
            return None, 'b' * 64

        with patch.object(score, 'load', side_effect=reader):
            result = score.assess(self.submission, self.public, '.', gold_fixture)
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertIsNone(result['primary'])
        self.assertEqual(result['target_loader_calls'], 1)

    def test_real_archive_checks_row_order_unit_order_hash_and_nonfinite(self):
        ids = self.public['people']['Subject1']['imagery_ids'] + self.public['people']['Subject1']['perception_ids']
        units = self.public['unit_ids']['cnn1']
        values = np.zeros((2250, 1000), dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prediction.npz'

            def write(features):
                np.savez_compressed(path, features=features, trial_ids=np.asarray(ids, dtype='<U25'),
                                    unit_ids=np.asarray(units, dtype=np.int64))

            write(values)
            actual, sha = artifacts.load(path, ids, units)
            self.assertEqual(actual.shape, (2250, 1000))
            with self.assertRaises(ValueError):
                artifacts.load(path, ids[::-1], units)
            with self.assertRaises(ValueError):
                artifacts.load(path, ids, units[::-1])
            values[0, 0] = 1
            write(values)
            with self.assertRaises(ValueError):
                artifacts.load(path, ids, units, sha)
            values[0, 0] = np.nan
            write(values)
            with self.assertRaises(ValueError):
                artifacts.load(path, ids, units)

    def test_authenticated_public_and_private_archive(self):
        body = json.dumps(self.public).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'public_manifest.json'
            path.write_bytes(body)
            gold_path = root / 'gold.npz'
            np.savez_compressed(gold_path, **gold_fixture())
            gold_body = gold_path.read_bytes()
            operator = {'schema': 'neural076_operator_v1', 'source_design_sha256': 'a' * 64,
                        'public_manifest': {'path': path.name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()},
                        'gold': {'path': gold_path.name, 'bytes': len(gold_body), 'sha256': hashlib.sha256(gold_body).hexdigest()}}
            self.assertEqual(score.authenticated_public(path, operator), self.public)
            score.validate_gold(score.load_gold(root, operator['gold']))
            path.write_bytes(body + b' ')
            with self.assertRaises(ValueError):
                score.authenticated_public(path, operator)

    def test_full650_generated_numerical_dispatch(self):
        # Two shared broadcast arrays represent every full-size trial/unit block.
        # The production archive reader is exercised separately above. No 5.85GB
        # prediction collection is written merely to exercise the dispatcher.
        labels = np.concatenate([np.repeat(np.arange(50), 10), np.repeat(np.arange(50), 35)])
        positive = np.broadcast_to(labels.astype(float)[:, None], (2250, 1000))
        negative = -positive
        keys = artifacts.part_keys()
        events = []

        def reader(path, ids, units, expected_sha=None):
            index = int(path.stem[4:])
            _, roi, family = keys[index].split('/')
            events.append('preflight' if expected_sha is None else 'score')
            if expected_sha is not None:
                self.assertEqual(expected_sha, hashlib.sha256(keys[index].encode()).hexdigest())
            sign = -1 if (roi, family) in [('HVC', 'cnn1'), ('LVC', 'cnn7')] else 1
            return (positive if sign == 1 else negative), hashlib.sha256(keys[index].encode()).hexdigest()

        def target():
            self.assertEqual(events, ['preflight'] * 650)
            events.append('target')
            return gold_fixture()

        with patch.object(score, 'load', side_effect=reader):
            result = score.assess(self.submission, self.public, '.', target)
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(events, ['preflight'] * 650 + ['target'] + ['score'] * 650)
        self.assertAlmostEqual(result['primary']['mean'], 4.)
        self.assertEqual(result['coverage']['phase_cells'], 1300)
        self.assertEqual(len(result['cell_diagnostics']), 1300)
        for person in core.PEOPLE:
            self.assertAlmostEqual(result['primary']['per_person'][person], 4.)
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    print('Generated-only controls; Python', sys.version.split()[0], 'NumPy', np.__version__)
    unittest.main(verbosity=2)
