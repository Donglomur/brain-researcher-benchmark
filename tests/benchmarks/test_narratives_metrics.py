"""Generated signed-Pearson arithmetic controls; no data or fitting."""
import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-071/implementations/narratives-programme"
NAMESPACE = "_neural071_stable_metrics_controls"
package = ModuleType(NAMESPACE)
package.__path__ = [str(PACKAGE / "n071")]
sys.modules[NAMESPACE] = package

def load(name, path):
    spec = importlib.util.spec_from_file_location(NAMESPACE + "." + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

metrics = load("metrics", PACKAGE / "n071/metrics.py")
legacy = load("legacy_metrics", PACKAGE / "n071/history/pre-stable-pearson/metrics.py")
from _neural071_stable_metrics_controls.errors import Refusal


def panel(scale=1., sign=1.):
    # Centered exact integer patterns have dot=8, squared norms=40 and8.
    x = np.array([-2., -1., 0., 1., 2.] * 4) * scale * sign
    y = np.array([-1., 0., 1., 0., 0.] * 4) * scale
    return np.repeat(x[:, None], 400, axis=1), np.repeat(y[:, None], 400, axis=1)


class StablePearsonTests(unittest.TestCase):
    def test_scale_invariance_and_signed_nonperfect_association(self):
        expected = 2. / math.sqrt(20.)
        for scale in (1., 1e100, 1e-100):
            for sign in (-1., 1.):
                with self.subTest(scale=scale, sign=sign):
                    pred, target = panel(scale, sign)
                    result = metrics.part(pred, target, np.zeros(400))
                    self.assertAlmostEqual(result["signed_r"], sign * expected, places=14)
                    self.assertTrue(all(abs(v - sign * expected) < 1e-14
                                        for v in result["parcel_signed_r"]))
                    self.assertEqual(result["undefined_r"], 0)
                    self.assertTrue(math.isfinite(result["MSE"]))
                    self.assertTrue(math.isfinite(result["Q2"]))

    def test_preserved_predecessor_exposes_both_denominator_failures(self):
        expected = 2. / math.sqrt(20.)
        for scale, historical in ((1e100, 0.), (1e-100, 1.)):
            pred, target = panel(scale)
            with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
                before = legacy.part(pred, target, np.zeros(400))
            after = metrics.part(pred, target, np.zeros(400))
            self.assertEqual(before["signed_r"], historical)
            self.assertNotAlmostEqual(before["signed_r"], expected)
            self.assertAlmostEqual(after["signed_r"], expected, places=14)

    def test_constants_and_nonfinite_input_keep_their_dispositions(self):
        pred, target = panel(1e-100)
        constant_prediction = metrics.part(np.zeros_like(pred), target, np.zeros(400))
        self.assertEqual(constant_prediction["signed_r"], 0.)
        constant_target = metrics.part(pred, np.zeros_like(target), np.zeros(400))
        self.assertIsNone(constant_target["signed_r"])
        self.assertEqual(constant_target["undefined_r"], 400)
        self.assertIsNone(constant_target["Q2"])
        for invalid in (math.nan, math.inf, -math.inf):
            bad = pred.copy()
            bad[0, 0] = invalid
            with self.assertRaises(Refusal):
                metrics.part(bad, target, np.zeros(400))

    def test_case_scoring_uses_repaired_metric_with_original_segment_weights(self):
        x, y = panel(1e100)
        rows = [{"run": "first", "segment": 0} for _ in range(20)]
        rows += [{"run": "first", "segment": 1} for _ in range(20)]
        rows += [{"run": "second", "segment": 0} for _ in range(20)]
        pred = np.concatenate((x, x, -x))
        target = np.concatenate((y, y, y))
        scored = metrics.case_score({"condition": pred}, target, np.zeros(400), rows)
        result = scored["condition"]
        # Equal segments within each run, then equal runs: +r and-r cancel.
        self.assertAlmostEqual(result["values"]["signed_r"], 0., places=14)
        self.assertEqual(len(result["parts"]), 3)
        self.assertAlmostEqual(result["parts"][0]["signed_r"], 2./math.sqrt(20.), places=14)
        self.assertAlmostEqual(result["parts"][2]["signed_r"], -2./math.sqrt(20.), places=14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
