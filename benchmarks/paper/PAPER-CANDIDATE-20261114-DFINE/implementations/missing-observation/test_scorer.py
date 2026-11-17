"""Invented full-population controls; no authentic data or native packages."""

import copy
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
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
    with localcontext() as ctx:
        ctx.prec = 80
        x, y = [Decimal(v) for v in x], [Decimal(v) for v in y]
        mx, my = sum(x) / len(x), sum(y) / len(y)
        a, b = [v - mx for v in x], [v - my for v in y]
        return float(sum(u * v for u, v in zip(a, b)) / (sum(u * u for u in a) * sum(v * v for v in b)).sqrt())


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
