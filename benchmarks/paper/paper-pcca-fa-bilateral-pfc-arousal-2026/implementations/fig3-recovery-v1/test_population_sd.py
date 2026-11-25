"""Generated complete-panel numerical controls; no observed or fitted data."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def tiny_panel(scale, condition):
    rows, candidate_rows = [], []
    zero = {c: {"psv_percent": 0, "dshared": 0} for c in ev.COMPONENTS}
    for n, i in ev.KEYS:
        key = {"trials": n, "draw": i,
               "observations_sha256": hashlib.sha256(f"generated-sd:{n}:{i}".encode()).hexdigest()}
        rows.append({**key, "truth": copy.deepcopy(zero), "author": copy.deepcopy(zero),
                     "pcca": {c: copy.deepcopy(zero[c]) for c in ev.COMPONENTS[:2]}})
        estimate = copy.deepcopy(zero)
        estimate["across_1"] = {"psv_percent": 2 * scale, "dshared": 1}
        candidate_rows.append({**key, "estimates": estimate})
    support = {"schema": "pcca-fig3-support-v1", "task": ev.TASK,
               "preparation_sha256": "1" * 64, "protocol_sha256": "2" * 64, "rows": rows}
    support_bytes = encode(support)
    candidate = {"schema": "pcca-fig3-submission-v1", "task": ev.TASK,
                 "support_sha256": hashlib.sha256(support_bytes).hexdigest(),
                 "condition": condition, "rows": candidate_rows}
    return support_bytes, encode(candidate)


class PopulationSDTests(unittest.TestCase):
    def check_complete_panel(self, scale):
        for condition in ev.CONDITIONS:
            support, candidate = tiny_panel(scale, condition)
            report = ev.compare(support, candidate)
            self.assertEqual(len(report["per_draw"]), 180)
            self.assertEqual(len(report["source_curves"]), 24)
            self.assertEqual(report["condition"], condition)
            self.assertIsNone(report["reproduction_pass"])
            self.assertIsNone(report["improvement_pass"])
            for curve, reproduction in zip(report["source_curves"], report["reproduction_discrepancies"]):
                if curve["component"] == "across" and curve["metric"] == "psv_percent":
                    for moment in (curve["signed_error"]["candidate"], reproduction["candidate_minus_author"]):
                        self.assertEqual(moment["n_area_values"], 60)
                        self.assertAlmostEqual(moment["mean"] / scale, 1.0, places=12)
                        self.assertAlmostEqual(moment["std_population"] / scale, 1.0, places=12)
                    self.assertEqual(curve["signed_error"]["author"]["std_population"], 0.0)

    def test_representable_sd_with_zero_variance_intermediate(self):
        self.check_complete_panel(1e-200)

    def test_representable_sd_with_subnormal_variance_intermediate(self):
        self.check_complete_panel(1e-160)

    def test_original_normal_and_constant_population_semantics(self):
        values = [-2.0] * 30 + [2.0] * 30
        self.assertEqual(ev.moments(values), {"mean": 0.0, "std_population": 2.0, "n_area_values": 60})
        self.assertEqual(ev.moments([1e-200] * 60), {"mean": 1e-200, "std_population": 0.0, "n_area_values": 60})
        varied = [-4.0, 2.0, 8.0, 9.0, -1.0] * 12
        avg = math.fsum(varied) / len(varied)
        original = math.sqrt(math.fsum((x - avg) ** 2 for x in varied) / len(varied))
        self.assertEqual(ev.moments(varied)["std_population"], original)


if __name__ == "__main__":
    unittest.main()
