"""Generated R2 precision controls; no authentic data or model execution."""
import copy
from fractions import Fraction
import math
import importlib.util
from pathlib import Path
import unittest
import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neds_r2_precision", PACKAGE / "neds_evaluator.py")
ne = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ne)


class R2Precision(unittest.TestCase):
    def test_constant_target_uses_exact_predictions(self):
        result = ne.r_squared([0.0, 0.0], [0.0, 1e-200])
        self.assertEqual(result, {"r2": 0.0, "constant_target": True, "sample_count": 2})
        self.assertEqual(ne.r_squared([0.0, 0.0], [0.0, 0.0])["r2"], 1.0)

    def test_tiny_nonconstant_target_retains_ratio(self):
        for scale in (1e-200, 4e-162, float(np.nextafter(0.0, 1.0))):
            with self.subTest(scale=scale):
                result = ne.r_squared([0.0, scale], [0.0, 0.0])
                # SSE=scale^2 and SST=scale^2/2, independent of the scale.
                self.assertEqual(result, {"r2": -1.0, "constant_target": False, "sample_count": 2})

    def test_tiny_perfect_and_nonperfect_predictions(self):
        self.assertEqual(ne.r_squared([0.0, 1e-200], [0.0, 1e-200])["r2"], 1.0)
        self.assertEqual(ne.r_squared([0.0, 1e-200], [1e-200, 0.0])["r2"], -3.0)

    def test_common_offset_preserves_exact_binary_variation(self):
        step = math.ldexp(1.0, -700)
        offset = 3 * 2**52
        y = np.asarray([offset, offset + 2, offset + 4], dtype=float) * step
        p = y + 2 * step
        exact_y = [Fraction.from_float(float(v)) for v in y]
        exact_p = [Fraction.from_float(float(v)) for v in p]
        mean = sum(exact_y) / len(exact_y)
        expected = 1 - sum((a-b)**2 for a, b in zip(exact_y, exact_p)) / sum((a-mean)**2 for a in exact_y)
        self.assertEqual(expected, Fraction(-1, 2))
        result = ne.r_squared(y, p)
        self.assertEqual(result["r2"], float(expected))
        self.assertFalse(result["constant_target"])

    def test_normal_range_preserves_literal_source_arithmetic(self):
        for target, prediction in (([1, 2, 3], [3, 2, 1]), ([0.1, 0.4, -0.7], [0.2, 0.6, 0.4])):
            y, p = np.asarray(target), np.asarray(prediction)
            expected = float(1.0 - float(np.sum((y-p)**2)) / float(np.sum((y-y.mean())**2)))
            actual = ne.r_squared(target, prediction)
            self.assertEqual(actual["r2"].hex(), expected.hex())
            self.assertFalse(actual["constant_target"])

    def test_nonfinite_shape_and_unrepresentable_scores_still_fail(self):
        for y, p in (([0, float("nan")], [0, 0]), ([0, 1], [0]),
                     ([1, 2], [1e308, -1e308]), ([0, 1e-200], [1e100, -1e100])):
            with self.subTest(y=y, p=p), self.assertRaises(ne.ContractError):
                ne.r_squared(y, p)

    def test_validated_complete_session_uses_corrected_endpoints(self):
        session = {"eid": "generated-session", "animal_id": "generated-animal", "bin_width_seconds": 0.02,
                   "unit_ids": ["unit"], "source_identity": {"kind": "generated_engineering"}}
        for split in ("train", "validation", "test"):
            session[split] = {"trial_ids": [split+"0", split+"1"],
                              "spike": np.ones((2, 100, 1)).tolist(),
                              "choice": [-1, 1], "block": [0.2, 0.8],
                              "wheel": np.tile([0.0, 1e-200], (2, 50)).tolist(),
                              "whisker": np.zeros((2, 100)).tolist()}
        ne.validate_session(session)
        predictions = {task: {field: copy.deepcopy(session["test"][field])
                             for field in (("spike",) if task in ne.ENCODING else ne.BEHAVIORS)}
                       for task in ne.TASKS}
        predictions["decode_all"]["wheel"] = np.zeros((2, 100)).tolist()
        predictions["decode_all"]["whisker"] = np.full((2, 100), 1e-200).tolist()
        result = ne.score_session(session, predictions)
        self.assertEqual(len(result["endpoints"]), 9)
        self.assertEqual(result["endpoints"]["wheel:r2"], -1.0)
        self.assertEqual(result["endpoints"]["whisker:r2"], 0.0)
        self.assertFalse(result["metrics"]["decode_all"]["wheel"]["constant_target"])
        self.assertTrue(result["metrics"]["decode_all"]["whisker"]["constant_target"])


if __name__ == "__main__":
    unittest.main()
