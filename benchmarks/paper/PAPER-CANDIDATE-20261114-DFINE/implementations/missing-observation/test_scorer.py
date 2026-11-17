"""Invented full-population controls; no authentic data or native packages."""

import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dfine_component", HERE / "scorer.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    sessions = ["invented-session-%s" % i for i in range(7)]
    p = {"schema": "dfine_missing_observation_profile_v1", "task_id": s.TASK,
         "contract_sha256": s.CONTRACT_SHA256, "sessions": sessions,
         "folds": [0, 1, 2, 3, 4], "dimensions": s.DIMENSIONS,
         # These four ratios exercise the component; this is NOT the original grid.
         "observed_percents": [20, 30, 60, 100], "replicate_ids": ["invented-mask"],
         "supports": [], "masks": []}
    targets = []
    for session in sessions:
        for fold in range(5):
            ids = list(range(fold * 100, (fold + 1) * 100))
            p["supports"].append({"session_id": session, "fold": fold, "sample_ids": ids})
            targets.append({"session_id": session, "fold": fold, "sample_ids": ids,
                            "values": [[i + 1, i % 7 - 3, i * 3 % 17, i * 7 % 23] for i in range(100)]})
            for ratio in p["observed_percents"]:
                p["masks"].append({"session_id": session, "fold": fold, "observed_percent": ratio,
                                   "replicate_id": "invented-mask", "bits": "1" * ratio + "0" * (100 - ratio)})
    support, expected = s.admit_profile(p)
    truth = {(t["session_id"], t["fold"]): t["values"] for t in targets}
    candidate, reference = [], []
    for key, (mask_sha, (_, ids_sha, _)) in expected.items():
        row = dict(zip((*s.KEY_FIELDS, "method"), key))
        row.update(mask_sha256=mask_sha, sample_ids_sha256=ids_sha, values=truth[key[:2]])
        candidate.append(row)
        reference.append({**row, "values": [[0.0] * 4 for _ in range(100)]})
    return p, candidate, reference, targets


def decimal_pearson(x, y):
    # Exact rational centering keeps the oracle independent of floating-point
    # subtraction, including tiny representable differences at large offsets.
    x, y = [Fraction(v) for v in x], [Fraction(v) for v in y]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    a, b = [v - mx for v in x], [v - my for v in y]
    covariance = sum(u * v for u, v in zip(a, b))
    variance_product = sum(u * u for u in a) * sum(v * v for v in b)
    with localcontext() as ctx:
        ctx.prec = 80
        cov = Decimal(covariance.numerator) / Decimal(covariance.denominator)
        var = Decimal(variance_product.numerator) / Decimal(variance_product.denominator)
        return float(cov / var.sqrt())


class Controls(unittest.TestCase):
    def test_complete_relocated_cli_and_target_last(self):
        p, candidate, reference, targets = fixture()
        opened = []
        result = s.grade(p, candidate, reference, lambda: opened.append(True) or targets)
        self.assertEqual(opened, [True])
        self.assertEqual(result["declared_prediction_cells"], 595)
        self.assertEqual(len(result["curves"]), 17)
        for curve in result["curves"]:
            self.assertAlmostEqual(curve["candidate_cc"], 1.0, places=14)
            self.assertEqual(curve["reference_cc"], 0.0)
            self.assertEqual(curve["session_fold_count"], 35)
        self.assertIsNone(result["overall_scalar"])
        self.assertFalse(result["claims"]["scientific_qualification"])
        with tempfile.TemporaryDirectory(prefix="dfine relocated ") as td:
            d = Path(td)
            (d / "scorer.py").write_bytes((HERE / "scorer.py").read_bytes())
            for name, data in [("profile", p), ("candidate", candidate), ("reference", reference), ("targets", targets)]:
                (d / (name + ".json")).write_bytes(s.json_bytes(data))
            cmd = [sys.executable, "-I", "-S", "-B", str(d / "scorer.py"), "--profile", str(d / "profile.json"),
                   "--profile-sha256", hashlib.sha256((d / "profile.json").read_bytes()).hexdigest(),
                   "--candidate", str(d / "candidate.json"), "--reference", str(d / "reference.json"),
                   "--private-targets", str(d / "targets.json"), "--output", str(d / "scores.json")]
            done = subprocess.run(cmd, capture_output=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr.decode())
            self.assertEqual(json.loads((d / "scores.json").read_bytes()), result)

    def test_malformed_predictions_never_open_private_target(self):
        p, c, r, t = fixture()
        mutations = [lambda rows: rows.pop(), lambda rows: rows.append(rows[0]),
                     lambda rows: rows.__setitem__(1, rows[0]),
                     lambda rows: rows[0].__setitem__("mask_sha256", "f" * 64),
                     lambda rows: rows[0].__setitem__("sample_ids_sha256", "f" * 64),
                     lambda rows: rows[0].__setitem__("values", [[0, 0, 0, float("nan")]] * 100),
                     lambda rows: rows[0].__setitem__("values", [[0, 0, True, 0]] * 100)]
        for label in ["candidate", "reference"]:
            for mutate in mutations:
                rows = [dict(x) for x in (c if label == "candidate" else r)]
                mutate(rows)
                opened = []
                with self.assertRaises(s.Invalid):
                    s.grade(p, rows if label == "candidate" else c, rows if label == "reference" else r,
                            lambda: opened.append(True) or t)
                self.assertEqual(opened, [])

    def test_exact_block_counts_not_global_or_channel_mask(self):
        self.assertEqual(len(s.validate_mask("1" * 30 + "0" * 70, 30)), 64)
        with self.assertRaisesRegex(s.Invalid, "block"):
            s.validate_mask("1" * 60 + "0" * 140, 30)
        for bits in ["1" * 30 + "0" * 71, "1" * 100 + "?" * 100, [1] * 100]:
            with self.assertRaises(s.Invalid):
                s.validate_mask(bits, 30)

    def test_pearson_math_and_source_constant_policy(self):
        for x, y in [([1, 2, 4, 9], [4, 0, 1, 3]),
                     ([1e308, -1e308, 0.0], [1e308, -1e308, 0.0]),
                     ([1e-300, -1e-300, 0.0], [-1e-300, 1e-300, 0.0])]:
            value, constant = s.pearson_cc(x, y)
            self.assertFalse(constant)
            self.assertAlmostEqual(value, decimal_pearson(x, y), places=14)
        self.assertEqual(s.pearson_cc([1, 2, 3], [0, 0, 0]), (0.0, True))
        self.assertEqual(s.pearson_cc([2, 2, 2], [1, 2, 3]), (0.0, True))

    def test_pearson_near_offset_translation_sign_and_scale(self):
        for exponent in (-1000, -500, 0, 500, 1000):
            origin = math.ldexp(1.0, exponent)
            step = math.ulp(origin)
            for sign in (-1, 1):
                x = [sign * origin + i * step for i in range(3)]
                for direction in (-1, 1):
                    y = [direction * v for v in (-1, 0, 1)]
                    with self.subTest(exponent=exponent, sign=sign, direction=direction):
                        value, constant = s.pearson_cc(x, y)
                        self.assertFalse(constant)
                        self.assertAlmostEqual(value, direction, places=14)

    def test_pearson_near_offset_non_affine_and_anchor_permutations(self):
        residuals, y = [0, 1, 2, 4, 9], [3, -1, 2, 0, 4]
        for origin in (1.0, -1.0, 1e300, -1e300):
            x = [origin + i * math.ulp(origin) for i in residuals]
            expected = decimal_pearson(x, y)
            for order in itertools.permutations(range(len(x))):
                with self.subTest(origin=origin, order=order):
                    value, constant = s.pearson_cc([x[i] for i in order], [y[i] for i in order])
                    self.assertFalse(constant)
                    self.assertAlmostEqual(value, expected, places=14)

    def test_pearson_extreme_spans_and_subnormal_variation(self):
        largest = sys.float_info.max
        smallest = math.ulp(0.0)
        for x, y in [([largest, -largest, 0.0, largest / 2], [3, 2, -1, 4]),
                     ([-largest, largest, smallest, -largest / 2], [-1, 2, 0, 3]),
                     ([largest, math.nextafter(largest, 0), math.nextafter(math.nextafter(largest, 0), 0)], [0, 2, 1]),
                     ([smallest, 2 * smallest, 4 * smallest, 9 * smallest], [3, -2, 4, 1]),
                     ([-smallest, 0, smallest], [1, 0, -1])]:
            with self.subTest(x=x):
                value, constant = s.pearson_cc(x, y)
                self.assertFalse(constant)
                self.assertTrue(math.isfinite(value))
                self.assertAlmostEqual(value, decimal_pearson(x, y), places=14)
        for constant in (0.0, -0.0, largest, -largest, smallest, -smallest):
            self.assertEqual(s.pearson_cc([constant] * 3, [1, 2, 3]), (0.0, True))
            self.assertEqual(s.pearson_cc([1, 2, 3], [constant] * 3), (0.0, True))

    def test_pearson_invalid_support_and_values(self):
        for x, y in [([], []), ([1], [2]), ([1, 2], [1, 2, 3])]:
            with self.assertRaises(s.Invalid):
                s.pearson_cc(x, y)
        for invalid in (float("nan"), float("inf"), -float("inf"), True, "1", 10 ** 400):
            for x, y in (([invalid, 1], [0, 1]), ([0, 1], [invalid, 1])):
                with self.assertRaises(s.Invalid):
                    s.pearson_cc(x, y)

    def test_near_offset_columns_propagate_through_complete_grade(self):
        p, candidate, reference, targets = fixture()
        translated = [[1.0 + i * math.ulp(1.0)] * 4 for i in range(100)]
        predictions = [[i] * 4 for i in range(100)]
        for target in targets:
            target["values"] = translated
        for row in candidate:
            row["values"] = predictions
        result = s.grade(p, candidate, reference, lambda: targets)
        for cell in result["cells"]:
            self.assertEqual(cell["candidate_constant_dimensions"], [])
            self.assertEqual(cell["reference_constant_dimensions"], [0, 1, 2, 3])
            for value in cell["candidate_dimension_cc"]:
                self.assertAlmostEqual(value, 1.0, places=14)
        for curve in result["curves"]:
            self.assertAlmostEqual(curve["candidate_cc"], 1.0, places=14)
            self.assertAlmostEqual(curve["delta_cc"], 1.0, places=14)

    def test_missing_timepoints_still_scored(self):
        truth = list(range(100))
        prediction = [v if i < 30 else -v for i, v in enumerate(truth)]
        self.assertAlmostEqual(s.pearson_cc(truth[:30], prediction[:30])[0], 1)
        self.assertLess(s.pearson_cc(truth, prediction)[0], 0)

    def test_complete_cohort_and_fold_separation(self):
        p, _, _, _ = fixture()
        p["sessions"].pop()
        with self.assertRaisesRegex(s.Invalid, "seven"):
            s.admit_profile(p)
        p, _, _, _ = fixture()
        p["supports"][1]["sample_ids"] = p["supports"][0]["sample_ids"]
        with self.assertRaisesRegex(s.Invalid, "overlap"):
            s.admit_profile(p)

    def test_duplicate_json_keys_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(s.Invalid, "duplicate"):
                s.load_json(p)


if __name__ == "__main__":
    unittest.main()
