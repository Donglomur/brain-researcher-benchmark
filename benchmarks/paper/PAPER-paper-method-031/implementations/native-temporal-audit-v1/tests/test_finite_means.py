"""Generated finite-mean controls; no model or original signal is loaded."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("fast_temporal_finite_controls", Path(__file__).resolve().parents[1] / "temporal.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FiniteMeanTests(unittest.TestCase):
    def test_augmented_mean_preserves_representable_extreme(self):
        value = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(module.augmented_mean([value, value], 1), value)

    def test_augmented_mean_preserves_cancellation_after_intermediate_overflow(self):
        value = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(module.augmented_mean([value, value, -value, -value], 1), 0.0)

    def test_overlap_preserves_representable_extreme(self):
        value = float.fromhex("0x1.fffffffffffffp+1023")
        plan = module.TemporalPlan(3, 2, "cli")
        windows = [(0, [[value], [value]]), (1, [[value], [value]])]
        result = module.reconstruct_traces(plan, windows, 0.0)
        self.assertEqual(result["float_traces"], [[value], [value], [value]])
        self.assertEqual(result["uint16_traces"], [[65535], [65535], [65535]])

    def test_regular_and_subnormal_rounding_and_genuine_overflow(self):
        self.assertEqual(module.augmented_mean([4, 8, 12], 2), 4.0)
        tiny = math.ulp(0.0)
        self.assertEqual(module.augmented_mean([tiny, tiny], 1), tiny)
        plan = module.TemporalPlan(3, 2, "cli")
        for value in (tiny, 12.0):
            result = module.reconstruct_traces(plan, [(0, [[value], [value]]), (1, [[value], [value]])], 0.0)
            self.assertEqual(result["float_traces"], [[value], [value], [value]])
        with self.assertRaises(module.TemporalError):
            module.reconstruct_traces(module.TemporalPlan(1, 1, "cli"), [(0, [[1e308]])], 1e308)


if __name__ == "__main__":
    unittest.main()
