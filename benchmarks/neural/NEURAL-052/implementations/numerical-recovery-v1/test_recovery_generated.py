"""Independent generated numerical oracle and portable-entrypoint controls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import encoding_core as core
import grade
import data_io
import report_contract
from test_encoding_generated import fixture

spec = importlib.util.spec_from_file_location("n052_operator", Path(__file__).with_name("run.py"))
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class IndependentNumericalChecks(unittest.TestCase):
    def test_four_models_against_augmented_least_squares_oracle(self):
        subjects, features = fixture()
        subject = subjects[0]
        rows, y = subject["rows"], subject["responses"]
        x = np.array([[r["session"], r["run"], r["within_run_position"],
                       *features[r["concept"]]["image_features"],
                       features[r["concept"]]["animacy"], features[r["concept"]]["size"]]
                      for r in rows])
        ordered = sorted(features, key=lambda c: (hashlib.sha256(("52052\0" + c).encode()).digest(), c))
        folds = {c: i % 5 for i, c in enumerate(ordered)}
        errors = np.zeros((4, y.shape[1]))
        sst = np.zeros(y.shape[1])
        coverage = np.zeros(len(rows), dtype=int)
        base = list(range(x.shape[1] - 2))
        columns = [base, base + [x.shape[1] - 2], base + [x.shape[1] - 1], list(range(x.shape[1]))]
        for f in range(5):
            for lo in (1, 5, 9):
                train = np.array([folds[r["concept"]] != f and not lo <= r["session"] < lo + 4 for r in rows])
                query = np.array([folds[r["concept"]] == f and lo <= r["session"] < lo + 4 for r in rows])
                coverage[query] += 1
                mean, scale = x[train].mean(0), x[train].std(0)
                scale[scale == 0] = 1
                tx, qx = (x[train] - mean) / scale, (x[query] - mean) / scale
                sst += ((y[query] - y[train].mean(0)) ** 2).sum(0)
                for m, cols in enumerate(columns):
                    # Solve an augmented least-squares problem with explicit
                    # unpenalized intercept; do not reuse core's normal equations.
                    design = np.column_stack([np.ones(train.sum()), tx[:, cols]])
                    penalty = np.diag([0.] + [1.] * len(cols))
                    beta = np.linalg.lstsq(np.vstack([design, penalty]),
                        np.vstack([y[train], np.zeros((len(cols) + 1, y.shape[1]))]), rcond=None)[0]
                    pred = np.column_stack([np.ones(query.sum()), qx[:, cols]]) @ beta
                    errors[m] += ((y[query] - pred) ** 2).sum(0)
        np.testing.assert_array_equal(coverage, np.ones(len(rows), dtype=int))
        increments = np.stack([errors[2] - errors[3], errors[1] - errors[3], errors[0] - errors[3]]) / sst
        report = core.analyze(subjects, features, draws=7, strict=False)["participants"][0]
        for roi, mask in subject["roi_masks"].items():
            for mi, metric in enumerate(core.METRICS):
                self.assertAlmostEqual(report["roi_metrics"]["macro_primary"][roi][metric]["value"],
                                       float(increments[mi, mask].mean()), places=12)

    def test_signed_error_is_not_positive_effect_reward(self):
        from test_grade_generated import report
        expected = report()
        for p in expected["participants"]:
            for roi in p["roi_metrics"]["macro_primary"].values():
                for summary in roi.values():
                    summary["value"] = -0.25
        self.assertEqual(grade.compare(expected, expected)["primary_error"], 0.)
        wrong = copy.deepcopy(expected)
        wrong["participants"][0]["roi_metrics"]["macro_primary"]["V1"]["joint"]["value"] = .25
        self.assertAlmostEqual(grade.compare(wrong, expected)["primary_error"], .5 / 18)


class EntrypointChecks(unittest.TestCase):
    def test_recovered_predecessor_bytes_match_manifest(self):
        root = Path(__file__).parent
        manifest = json.loads((root / "SOURCE_RECOVERY.json").read_text())
        self.assertEqual(len(manifest["byte_identical_files"]), 16)
        for record in manifest["byte_identical_files"]:
            body = (root / record["path"]).read_bytes()
            self.assertEqual(len(body), record["bytes"], record["path"])
            self.assertEqual(hashlib.sha256(body).hexdigest(), record["sha256"], record["path"])

    def test_missing_methods_rejected_before_packet_or_analysis(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(grade, "grade_submission", side_effect=AssertionError("numeric path")):
            root = Path(tmp)
            for payload in (None, b"  \n", b"\xff"):
                methods = root / "METHODS.md"
                if payload is not None:
                    methods.write_bytes(payload)
                result = entry.score(root, root / "result.json", methods)
                self.assertEqual(result["status"], "invalid_submission")

    def test_explicit_root_and_methods_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            methods = root / "METHODS.md"
            methods.write_text("Generated explanation.\n")
            submission = root / "result.json"
            with patch.object(grade, "grade_submission", return_value={"status": "scored"}) as numerical:
                result = entry.score(root, submission, methods)
                numerical.assert_called_once_with(submission, root)
            self.assertEqual(result["methods"]["sha256"], hashlib.sha256(methods.read_bytes()).hexdigest())
            self.assertFalse(result["methods"]["interpretation_quality_scored"])

    def test_reference_enforces_full_protocol_and_admission(self):
        root = Path("unused-generated-packet")
        with patch.object(entry, "_design", return_value={"fake": "design"}), \
             patch.object(data_io, "load_packet", return_value=(["subjects"], {"features": 1}, "a" * 64)) as load, \
             patch.object(core, "analyze", return_value={"fake": "analysis"}) as analyze, \
             patch.object(report_contract, "validate_report") as admit:
            result = entry.reference(root)
            load.assert_called_once_with(root)
            analyze.assert_called_once_with(["subjects"], {"features": 1}, draws=1000, strict=True)
            admit.assert_called_once_with(result, {"fake": "design"})

    def test_cli_requires_explicit_packet_and_preserves_existing_output(self):
        with self.assertRaises(SystemExit):
            entry.main(["reference", "--output", "unused.json"])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            output.write_text("original")
            with patch.object(entry, "reference", side_effect=AssertionError("must fail before computation")), self.assertRaises(SystemExit):
                entry.main(["reference", "--packet-root", tmp, "--output", str(output)])
            self.assertEqual(output.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
