"""Focused generated controls for the integer-safe regression successor."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ep = load("integer_safe_endpoints", HERE / "endpoints.py")
np = ep.np

class RegressionNumericBounds(unittest.TestCase):
    def test_signed_and_unsigned_residuals_do_not_wrap(self):
        # Squaring 2**32 in int64/uint64 wraps to zero. Mathematical residuals
        # here give RMSE=2**32 and R2=-3, never a perfect prediction score.
        distance = 2**32
        for dtype in (np.int64, np.uint64):
            with self.subTest(dtype=str(dtype)):
                y = np.array([0, distance], dtype=dtype)
                out = np.array([[distance], [0]], dtype=dtype)
                got = ep.score("SEED-VIG", y, out)
                self.assertEqual(got["metrics"]["rmse"], float(distance))
                self.assertEqual(got["metrics"]["r2"], -3.0)
                self.assertAlmostEqual(got["metrics"]["pearson"], -1.0)
                self.assertEqual(got["undefined_metrics"], [])

    def test_floating_operand_dtype_matches_source_reconstruction(self):
        # Inspect the metric boundary without requiring sklearn's extended-float
        # arithmetic to work. The source converts through tolist(), then array;
        # a longdouble must not be narrowed just to repair integer overflow.
        for dtype in (np.float32, np.float64, np.longdouble):
            with self.subTest(dtype=str(dtype)):
                y = np.array(["0.1", "0.4", "0.7"], dtype=dtype)
                out = np.array([["0.2"], ["0.5"], ["0.6"]], dtype=dtype)
                expected_y = np.array(y.tolist())
                expected_out = np.array(out[:, 0].tolist())
                calls = []
                def metric(name, value):
                    def observe(truth, prediction):
                        self.assertEqual(truth.dtype, expected_y.dtype)
                        self.assertEqual(prediction.dtype, expected_out.dtype)
                        np.testing.assert_array_equal(truth, expected_y)
                        np.testing.assert_array_equal(prediction, expected_out)
                        calls.append(name)
                        return value
                    return observe
                correlation = np.array([[1.0, .5], [.5, 1.0]])
                with patch.object(ep.np, "corrcoef", side_effect=metric("pearson", correlation)), \
                     patch.object(ep, "r2_score", side_effect=metric("r2", .75)), \
                     patch.object(ep, "mean_squared_error", side_effect=metric("mse", 4.0)):
                    result = ep.score("SEED-VIG", y, out)
                self.assertEqual(calls, ["pearson", "r2", "mse"])
                self.assertEqual(result["metrics"], {"pearson": .5, "r2": .75, "rmse": 2.0})

    def test_ordinary_float_scores_retain_predecessor_results(self):
        path = HERE.parent / "original-endpoints-v1" / "endpoints.py"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "84c90f4693beeeac40d9d6e5c0d0904ccbad4a78de143bc62d27e9b0489b76eb")
        previous = load("original_endpoints_v1", path)
        for dtype in (np.float32, np.float64):
            with self.subTest(dtype=str(dtype)):
                y = np.array([.1, .7, .4, .9], dtype=dtype)
                out = np.array([[.2], [.6], [.3], [.8]], dtype=dtype)
                self.assertEqual(ep.score("SEED-VIG", y, out), previous.score("SEED-VIG", y, out))

if __name__ == "__main__":
    unittest.main(verbosity=2)
