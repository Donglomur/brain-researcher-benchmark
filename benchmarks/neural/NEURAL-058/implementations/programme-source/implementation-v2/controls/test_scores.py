"""Generated controls only: no authentic observations, target files, or fitting."""
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = ROOT.parent / 'implementation-v1' / 'program'
sys.path.insert(0, str(PREDECESSOR))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load('neural058_scores_predecessor', PREDECESSOR / 'scores.py')
scores = load('neural058_scores_repaired', ROOT / 'scores.py')
ROSTER = ['generated-animal-' + str(i) for i in range(13)]


class ScoreControls(unittest.TestCase):
    def test_original_macro_counterexample_and_repair(self):
        # Actual finite animal_score output, not an invented aggregate receipt.
        target = np.array([[0., 0.], [2., 2.]])
        prediction = np.full((2, 2), 7.8e153)
        animal = old.animal_score([[(target, prediction)]])
        self.assertTrue(all(math.isfinite(v) for v in animal['r2']))
        animals = {name: animal for name in ROSTER}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            self.assertFalse(math.isfinite(old.macro(animals, ROSTER)['velocity']))
        result = scores.macro(animals, ROSTER)
        self.assertAlmostEqual(result['velocity'] / animal['r2'][0], 1.)
        json.dumps(result, allow_nan=False)

    def test_original_paired_overflow_and_repair(self):
        left = {name: [-6e307] * 3 for name in ROSTER}
        right = {name: [0.] * 3 for name in ROSTER}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            self.assertFalse(math.isfinite(old.paired_contrast(left, right, ROSTER)['estimate']))
        result = scores.paired_contrast(left, right, ROSTER)
        self.assertAlmostEqual(result['estimate'] / -6e307, 1.)
        for bound in result['interval']:
            self.assertAlmostEqual(bound / -6e307, 1.)
        json.dumps(result, allow_nan=False)

    def test_ragged_hierarchical_weighting_against_rational_oracle(self):
        raw = [[[-2, 0], [4]], [[-1, 1, 3]]]
        sessions = []
        atoms = []
        for session in raw:
            windows = []
            for window in session:
                y = np.array([[v, abs(v)] for v in window], dtype=np.float64)
                windows.append((y, np.zeros_like(y)))
                for row in y.astype(int):
                    atoms.append((list(map(int, row)), Fraction(1, len(raw) * len(session) * len(window))))
            sessions.append(windows)
        result = scores.animal_score(sessions)
        for h in range(2):
            mean = sum(Fraction(y[h]) * w for y, w in atoms)
            sse = sum(Fraction(y[h]) ** 2 * w for y, w in atoms)
            sst = sum((Fraction(y[h]) - mean) ** 2 * w for y, w in atoms)
            self.assertAlmostEqual(result['mean'][h], float(mean))
            self.assertAlmostEqual(result['mse'][h], float(sse))
            self.assertAlmostEqual(result['r2'][h], float(1 - sse / sst))
        self.assertEqual(result['support']['timestamps'], 6)
        self.assertNotEqual(result['mean'][0], float(np.mean([-2, 0, 4, -1, 1, 3])))

    def test_constant_speed_does_not_erase_signed_velocity(self):
        y = np.array([[-1., 1.], [1., 1.]])
        animal = scores.animal_score([[(y, y.copy())]])
        result = scores.macro({name: animal for name in ROSTER}, ROSTER)
        self.assertEqual(result['velocity'], 1.)
        self.assertIsNone(result['speed'])
        self.assertEqual(result['animals'][ROSTER[0]]['undefined_reason'][1], 'exact constant target')

    def test_bootstrap_preserves_pairing_seed_and_linear_percentiles(self):
        left = {a: [i / 10, i / 10 + .02, i / 10 - .03] for i, a in enumerate(ROSTER)}
        right = {a: [.1, .2, .3] for a in ROSTER}
        delta = [sum(l - r for l, r in zip(left[a], right[a])) / 3 for a in ROSTER]
        rng = np.random.Generator(np.random.PCG64(580058))
        reference = [sum(delta[i] for i in rng.integers(0, 13, size=13)) / 13 for _ in range(10000)]
        result = scores.paired_contrast(left, right, ROSTER)
        self.assertAlmostEqual(result['estimate'], sum(delta) / 13)
        np.testing.assert_allclose(result['animal_deltas'], delta, atol=1e-15)
        np.testing.assert_allclose(result['interval'], np.quantile(reference, [.025, .975], method='linear'), atol=1e-15)
        self.assertEqual((result['replicates'], result['seed']), (10000, 580058))

    def test_nonfinite_value_cannot_hide_behind_undefined_animal(self):
        animals = {a: {'r2': [0., 0.]} for a in ROSTER}
        animals[ROSTER[0]]['r2'][0] = None
        animals[ROSTER[1]]['r2'][0] = float('nan')
        with self.assertRaises(ValueError):
            scores.macro(animals, ROSTER)

    def test_missing_realizations_rejected_before_undefined_endpoint(self):
        left = {a: [0., 0., 0.] for a in ROSTER}
        right = {a: [0., 0., 0.] for a in ROSTER}
        left[ROSTER[0]] = [None]
        with self.assertRaises(ValueError):
            scores.paired_contrast(left, right, ROSTER)

    def test_roster_must_be_nonempty_and_unique(self):
        with self.assertRaises(ValueError):
            scores.macro({}, [])
        with self.assertRaises(ValueError):
            scores.macro({'a': {'r2': [1., 1.]}}, ['a', 'a'])
        with self.assertRaises(ValueError):
            scores.macro({'a': {'r2': [1., 1.]}}, ['a', 'b'])

    def test_unrepresentable_r2_refused_at_metric_boundary(self):
        y = np.array([[0., 0.], [2e-160, 2e-160]])
        with self.assertRaisesRegex(ValueError, 'R-squared outside finite'):
            scores.animal_score([[(y, np.ones_like(y))]])

    def test_opposite_sign_quantile_does_not_overflow_interpolation(self):
        self.assertEqual(scores._linear_quantile([-1.7e308, 1.7e308], .5), 0.)

    def test_maximum_finite_mean_rounds_once_after_sum_overflow(self):
        largest = sys.float_info.max
        for sign in (-1., 1.):
            for count in (3, 13):
                self.assertEqual(scores._mean([sign * largest] * count), sign * largest)
        self.assertEqual(scores._mean([largest, largest, -largest]), largest / 3)

    def test_maximum_finite_paired_scores_and_constant_interval(self):
        largest = sys.float_info.max
        left = {name: [-largest] * 3 for name in ROSTER}
        right = {name: [0.] * 3 for name in ROSTER}
        result = scores.paired_contrast(left, right, ROSTER)
        self.assertEqual(result['estimate'], -largest)
        self.assertEqual(result['interval'], [-largest, -largest])
        self.assertEqual(result['animal_deltas'], [-largest] * 13)
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
