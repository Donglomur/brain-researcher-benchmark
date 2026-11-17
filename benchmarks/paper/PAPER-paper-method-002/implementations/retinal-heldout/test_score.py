"""Invented software controls only. No authentic retinal data or model run."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("retinal_heldout_score", HERE / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def fixture():
    sites = []
    roi = {}
    for i in range(147):
        field = i % 15 + 1
        start = roi.get(field, 0) + 1
        ids = list(range(start, start + (2 if i < 85 else 1)))
        roi[field] = ids[-1]
        sites.append({"field": field, "branch": i // 15, "bin": 0, "raw_roi_ids": ids})
    # Unequal per-field support detects accidental observation-count weighting.
    test = [(field - 1) * 1024 + offset for field in range(1, 16)
            for offset in range(6 if field == 1 else 4)]
    val = [1023]
    train = sorted(set(range(15360)) - set(test) - set(val))
    labels, mask = [], []
    for row in test:
        mask.append([int(row // 1024 + 1 == s["field"]) for s in sites])
        labels.append([float(row % 1024 - 2) if present else None for present in mask[-1]])
    operator = {"schema": "jaxley-retinal-target-v1", "cell_id": "20161028_1",
                "sites": sites, "splits": {"train": train, "val": val, "test": test},
                "labels": labels, "mask": mask}
    author = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1",
              "test_row_ids": test[:], "site_keys": [list(score.site_key(s)) for s in sites],
              "predictions": [[0. if value is None else value for value in row] for row in labels]}
    return operator, author, copy.deepcopy(author)


class RetinalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.operator, self.author, self.candidate = fixture()

    def compare(self):
        return score.compare(self.operator, self.author, self.candidate)

    def test_independent_exact_correlation_oracle_and_unweighted_sites(self):
        # Pearson(y, positive*y+offset)=1; Pearson(y,-y)=-1.
        # Invert 73 of the 147 sites; the arithmetic mean must be 1/147,
        # despite unequal field/site support counts.
        for row in self.candidate["predictions"]:
            for j, value in enumerate(row):
                row[j] = -value if j < 73 else 3 * value + 11
        result = self.compare()
        self.assertAlmostEqual(result["author_mean_pearson"], 1.)
        self.assertAlmostEqual(result["candidate_mean_pearson"], 1 / 147)
        self.assertAlmostEqual(result["paired_delta"], 1 / 147 - 1)
        weighted = sum(s["valid_count"] * s["candidate_pearson"] for s in result["sites"])
        weighted /= sum(s["valid_count"] for s in result["sites"])
        self.assertFalse(math.isclose(weighted, 1 / 147, abs_tol=1e-8))
        self.assertIsNone(result["paper_win"])
        self.assertIsNone(result["uncertainty"])

    def test_row_and_site_identity_alignment(self):
        expected = self.compare()
        for packet in (self.author, self.candidate):
            packet["test_row_ids"].reverse()
            packet["site_keys"].reverse()
            packet["predictions"] = [list(reversed(row)) for row in reversed(packet["predictions"])]
        actual = self.compare()
        self.assertEqual(expected["sites"], actual["sites"])
        self.assertEqual(expected["identity_sha256"], actual["identity_sha256"])

    def test_masked_values_do_not_enter_correlations(self):
        for i, row in enumerate(self.candidate["predictions"]):
            for j in range(147):
                if not self.operator["mask"][i][j]:
                    row[j] = 1e30
                    self.operator["labels"][i][j] = -1e30
        self.assertAlmostEqual(self.compare()["candidate_mean_pearson"], 1.)

    def test_constant_candidate_keeps_site_and_undefined_mean(self):
        for row in self.candidate["predictions"]:
            row[0] = 7.
        result = self.compare()
        self.assertIsNone(result["candidate_mean_pearson"])
        self.assertIsNone(result["paired_delta"])
        self.assertEqual(len(result["sites"]), 147)
        self.assertEqual(result["sites"][0]["candidate_undefined"], "insufficient-or-constant-support")
        self.assertFalse(result["undefined_sites_dropped"])

    def test_constant_target_keeps_undefined_site(self):
        for i, row in enumerate(self.operator["labels"]):
            if self.operator["mask"][i][0]:
                row[0] = 4.
        result = self.compare()
        self.assertIsNone(result["author_mean_pearson"])
        self.assertIsNone(result["candidate_mean_pearson"])

    def test_missing_duplicate_or_foreign_prediction_rows_refused(self):
        for mode in ("missing", "duplicate", "foreign", "bool"):
            with self.subTest(mode=mode):
                self.operator, self.author, self.candidate = fixture()
                rows = self.candidate["test_row_ids"]
                if mode == "missing":
                    rows.pop()
                    self.candidate["predictions"].pop()
                elif mode == "duplicate":
                    rows[0] = rows[1]
                else:
                    rows[0] = 999 if mode == "foreign" else True
                with self.assertRaisesRegex(score.Refusal, "prediction:"):
                    self.compare()

    def test_missing_duplicate_or_foreign_sites_refused(self):
        for mode in ("missing", "duplicate", "foreign"):
            with self.subTest(mode=mode):
                self.operator, self.author, self.candidate = fixture()
                keys = self.candidate["site_keys"]
                if mode == "missing":
                    keys.pop()
                elif mode == "duplicate":
                    keys[0] = keys[1]
                else:
                    keys[0] = [1, 999, 0]
                with self.assertRaisesRegex(score.Refusal, "prediction:exact_147_sites"):
                    self.compare()

    def test_changed_mask_refused(self):
        self.operator["mask"][0][0] = 0
        with self.assertRaisesRegex(score.Refusal, "mask:original_field_support"):
            self.compare()

    def test_split_overlap_and_missing_rows_refused(self):
        self.operator["splits"]["train"][0] = self.operator["splits"]["test"][0]
        with self.assertRaisesRegex(score.Refusal, "split:duplicate_or_overlap"):
            self.compare()
        self.operator, self.author, self.candidate = fixture()
        self.operator["splits"]["train"].pop()
        with self.assertRaisesRegex(score.Refusal, "split:complete_15360_rows"):
            self.compare()

    def test_incomplete_roi_lineage_and_reduced_population_refused(self):
        self.operator["sites"][0]["raw_roi_ids"].pop()
        with self.assertRaisesRegex(score.Refusal, "complete_232_roi_lineage"):
            self.compare()
        self.operator, self.author, self.candidate = fixture()
        self.operator["sites"] = self.operator["sites"][:70]
        with self.assertRaisesRegex(score.Refusal, "complete_147_sites"):
            self.compare()

    def test_duplicate_raw_roi_refused(self):
        self.operator["sites"][15]["raw_roi_ids"][0] = self.operator["sites"][0]["raw_roi_ids"][0]
        with self.assertRaisesRegex(score.Refusal, "duplicate_raw_roi"):
            self.compare()

    def test_nonfinite_bool_string_and_lossy_integer_predictions_refused(self):
        for value in (float("nan"), float("inf"), True, "1.0", 2**53 + 1, None):
            with self.subTest(value=value):
                self.candidate["predictions"][0][0] = value
                with self.assertRaisesRegex(score.Refusal, "prediction:finite_real_number"):
                    self.compare()

    def test_none_target_only_allowed_outside_mask(self):
        self.operator["labels"][0][0] = None
        with self.assertRaisesRegex(score.Refusal, "labels:finite_real_number"):
            self.compare()

    def test_source_hash_change_refused(self):
        saved = score.SOURCE_HASHES["retina_model.py"]
        try:
            score.SOURCE_HASHES["retina_model.py"] = "0" * 64
            with self.assertRaisesRegex(score.Refusal, "preserved_metric_source_changed"):
                self.compare()
        finally:
            score.SOURCE_HASHES["retina_model.py"] = saved

    def test_operator_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, obj in (("targets", self.operator), ("author", self.author), ("candidate", self.candidate)):
                (root / (name + ".json")).write_text(json.dumps(obj, allow_nan=False))
            command = [sys.executable, "-I", "-B", str(HERE / "score.py")]
            for name in ("targets", "author", "candidate", "output"):
                command.extend(["--" + name, str(root / (name + ".json"))])
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = (root / "output.json").read_bytes()
            self.assertAlmostEqual(json.loads(output)["paired_delta"], 0.)
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((root / "output.json").read_bytes(), output)

    def test_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for body in ('{"a": 1, "a": 2}', '{"a": NaN}'):
                path.write_text(body)
                with self.assertRaises(score.Refusal):
                    score.read_json(path)

    def test_native_libraries_are_not_imported(self):
        self.compare()
        for name in ("jax", "jaxley", "tensorflow", "torch", "optax"):
            self.assertNotIn(name, sys.modules)


if __name__ == "__main__":
    import numpy as np
    print(json.dumps({"scope": "generated_software_controls_only", "python": sys.version,
                      "executable": sys.executable, "numpy": np.__version__}), flush=True)
    unittest.main(verbosity=2)
