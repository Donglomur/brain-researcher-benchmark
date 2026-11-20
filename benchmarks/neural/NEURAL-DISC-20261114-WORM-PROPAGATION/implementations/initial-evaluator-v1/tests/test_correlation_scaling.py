"""Known correlation oracles on the maintained successor and transport route."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

EVALUATOR = load("worm_stable_correlation", "worm_evaluator.py")
TRANSPORT = load("worm_stable_transport", "../participant-transport-v2/participant_transport.py")

class StableCorrelationTests(unittest.TestCase):
    def test_perfect_affine_correlations_are_scale_invariant(self):
        for scale in (1.0, 1e100, 1e-100):
            target = {"times_s": [0.0, 1.0, 2.0],
                      "values": [-scale, 0.0, scale]}
            for slope in (-1.0, 1.0):
                with self.subTest(scale=scale, slope=slope):
                    prediction = [slope * value for value in target["values"]]
                    result = EVALUATOR.trace_metrics(target, prediction, 2.0)
                    self.assertEqual(result["correlation_status"], "defined")
                    self.assertAlmostEqual(result["correlation"], slope, places=14)
                    if slope == 1.0:
                        self.assertEqual(result["mse"], 0.0)
                        self.assertEqual(result["area_error"], 0.0)

    def test_orthogonal_and_constant_missing_support_oracles(self):
        for scale in (1.0, 1e100, 1e-100):
            target = {"times_s": [0.0, 1.0, 2.0],
                      "values": [-scale, 0.0, scale]}
            result = EVALUATOR.trace_metrics(target, [scale, -2*scale, scale], 2.0)
            self.assertAlmostEqual(result["correlation"], 0.0, places=14)
        constant = {"times_s": [0.0, 1.0], "values": [2.0, 2.0]}
        self.assertEqual(EVALUATOR.trace_metrics(constant, [1.0, 2.0], 2.0)["correlation_status"],
                         "zero_target_variance")
        varying = {"times_s": [0.0, 1.0], "values": [1.0, 2.0]}
        self.assertEqual(EVALUATOR.trace_metrics(varying, [2.0, 2.0], 2.0)["correlation_status"],
                         "zero_prediction_variance")
        unsupported = EVALUATOR.trace_metrics(varying, [1.0, None], 2.0)
        self.assertIsNone(unsupported["correlation"])
        self.assertEqual(unsupported["correlation_status"], "unsupported_prediction")

    def test_transport_selects_hash_bound_stable_evaluator(self):
        selected = TRANSPORT.evaluator()
        self.assertEqual(TRANSPORT.SCHEMA, "worm-participant-transport/v2")
        self.assertEqual(Path(selected.__file__).resolve(), HERE / "worm_evaluator.py")
        target = {"times_s": [0.0, 1.0], "values": [0.0, 1e100]}
        self.assertAlmostEqual(selected.trace_metrics(target, [0.0, 1e100], 2.0)["correlation"],
                               1.0, places=14)

if __name__ == "__main__":
    unittest.main()
