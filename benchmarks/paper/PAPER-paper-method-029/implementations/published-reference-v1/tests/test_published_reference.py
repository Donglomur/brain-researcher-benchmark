"""Generated table/replay controls; none is an authentic scientific replay."""
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("published_reference", PACKAGE / "published_reference.py")
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


def generated_csv():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Source", "Target", "ROI", "Method", "pattern_mean", "profile_mean"])
    for roi_index, roi in enumerate(["VC", "V1", "V2", "V3", "V4", "HVC"]):
        for method_index, method in enumerate(["brain_loss", "content_loss"]):
            for source in range(1, 6):
                for target in range(1, 6):
                    if source != target:
                        value = (source - target) / 20 + roi_index / 40 + method_index / 80
                        writer.writerow([f"sub{source:02d}", f"sub{target:02d}", roi, method, value, -value])
    return stream.getvalue().encode()


def generated_replay(values):
    return {"task_id": reference.TASK_ID, "source_commit": reference.SOURCE_COMMIT,
            "population": "public_deeprecon", "images": 50, "repeats": 24, "source_pairs": 20,
            "methods": list(reference.METHODS), "rois": list(reference.ROIS),
            "normalized": {"pair_rows": [dict(zip(("source", "target", "roi", "method", "axis"), key),
                                                 mean_r=value, eligible_count=40 if key[-1] == "pattern" else 3,
                                                 total_count=50 if key[-1] == "pattern" else 5, undefined_count=0)
                                          for key, value in values.items()]}}


class PublishedReferenceControls(unittest.TestCase):
    def test_complete_table_and_analytic_pair_mean(self):
        values = reference.parse_source_csv(generated_csv())
        self.assertEqual(len(values), 480)
        summary = reference.source_summary(values)
        self.assertEqual(len(summary["summaries"]), 24)
        # Sum of (source-target) over all directed nonself pairs is exactly zero.
        for row in summary["summaries"]:
            roi_index = ["VC", "V1", "V2", "V3", "V4", "HVC"].index(row["roi"])
            method_index = ["brain_loss", "content_loss"].index(row["method"])
            expected = roi_index / 40 + method_index / 80
            self.assertAlmostEqual(row["observed_pair_mean"], expected if row["axis"] == "pattern" else -expected)
        self.assertIn("not_figure_bootstrap", summary["summary_statistic"])

    def test_source_identity_is_not_schema_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            path.write_bytes(generated_csv())
            with self.assertRaisesRegex(reference.ReferenceError, "byte identity"):
                reference.load_reference(path)

    def test_strict_source_schema_coverage_and_correlations(self):
        payload = generated_csv()
        cases = {"missing": b"\r\n".join(payload.split(b"\r\n")[:-2]) + b"\r\n",
                 "duplicate": payload + payload.split(b"\r\n")[1] + b"\r\n",
                 "wrong_subject": payload.replace(b"sub01", b"sub06", 1),
                 "self_pair": payload.replace(b"sub01,sub02", b"sub01,sub01", 1),
                 "wrong_header": payload.replace(b"pattern_mean", b"raw_pattern_mean", 1),
                 "extra_column": payload.replace(b"profile_mean", b"profile_mean,other", 1),
                 "nonfinite": payload.replace(b"-0.05,0.05", b"nan,0.05", 1),
                 "out_of_range": payload.replace(b"-0.05,0.05", b"1.01,0.05", 1),
                 "invalid_utf8": b"\xff" + payload,
                 "oversized": b"x" * 65537}
        for name, bad in cases.items():
            with self.subTest(name=name), self.assertRaises(reference.ReferenceError):
                reference.parse_source_csv(bad)

    def test_exact_arithmetic_match_does_not_claim_reproduction(self):
        values = reference.parse_source_csv(generated_csv())
        report = reference.compare(values, generated_replay(values), 0, "generated exact-match control")
        self.assertTrue(report["all_values_within_tolerance"])
        self.assertEqual(report["scientific_reproduction"], "not_established_by_arithmetic_comparison")
        self.assertEqual(report["scientific_improvement"], "not_evaluated")

    def test_opposite_pair_errors_cannot_cancel_reproduction_check(self):
        values = reference.parse_source_csv(generated_csv())
        replay = generated_replay(values)
        rows = replay["normalized"]["pair_rows"]
        rows[0]["mean_r"] += .125
        rows[2]["mean_r"] -= .125
        report = reference.compare(values, replay, .1, "generated error-cancellation control")
        group = next(row for row in report["summaries"] if (row["roi"], row["method"], row["axis"]) == ("VC", "brain_loss", "pattern"))
        self.assertEqual(group["mean_signed_error"], 0)
        self.assertEqual(group["maximum_absolute_pair_error"], .125)
        self.assertAlmostEqual(group["root_mean_square_pair_error"], .125 / math.sqrt(10))
        self.assertEqual(group["pairs_within_tolerance"], 18)
        self.assertFalse(report["all_values_within_tolerance"])

    def test_missing_duplicate_or_undefined_replay_rejected(self):
        values = reference.parse_source_csv(generated_csv())
        for kind in ("missing", "duplicate", "undefined", "no_eligible", "wrong_pattern_count", "bool_count", "nonfinite"):
            replay = generated_replay(values)
            rows = replay["normalized"]["pair_rows"]
            if kind == "missing": rows.pop()
            elif kind == "duplicate": rows[-1] = rows[0]
            elif kind == "undefined": rows[0]["undefined_count"] = 1
            elif kind == "no_eligible": rows[0]["eligible_count"] = 0
            elif kind == "wrong_pattern_count": rows[0]["total_count"] = 49
            elif kind == "bool_count": rows[0]["undefined_count"] = False
            else: rows[0]["mean_r"] = float("nan")
            with self.subTest(kind=kind), self.assertRaises(reference.ReferenceError):
                reference.compare(values, replay, .01, "generated negative control")

    def test_raw_generated_and_wrong_source_replays_rejected(self):
        values = reference.parse_source_csv(generated_csv())
        for field, bad in (("normalized", None), ("population", "generated_engineering_control"),
                           ("source_commit", "unbound"), ("images", 49), ("repeats", 12),
                           ("source_pairs", 19), ("rois", ["VC"]), ("methods", ["content_loss"])):
            replay = generated_replay(values)
            replay[field] = bad
            with self.subTest(field=field), self.assertRaises(reference.ReferenceError):
                reference.compare(values, replay, .01, "generated negative control")

    def test_tolerance_must_be_explicit_finite_and_explained(self):
        values = reference.parse_source_csv(generated_csv())
        for tolerance in (None, True, -.1, float("nan"), float("inf"), 2.1):
            with self.subTest(tolerance=tolerance), self.assertRaises(reference.ReferenceError):
                reference.compare(values, generated_replay(values), tolerance, "control")
        with self.assertRaises(reference.ReferenceError):
            reference.compare(values, generated_replay(values), .01, " ")

    def test_order_invariance(self):
        lines = generated_csv().splitlines(keepends=True)
        values = reference.parse_source_csv(lines[0] + b"".join(reversed(lines[1:])))
        self.assertEqual(values, reference.parse_source_csv(generated_csv()))
        replay = generated_replay(values)
        replay["normalized"]["pair_rows"].reverse()
        self.assertTrue(reference.compare(values, replay, 0, "generated permutation control")["all_values_within_tolerance"])

    def test_compact_export_drops_feature_values_and_extra_fields(self):
        values = reference.parse_source_csv(generated_csv())
        replay = generated_replay(values)
        replay["rows"] = ["generated per-feature payload intentionally omitted"]
        replay["raw"] = {"not": "the source endpoint"}
        replay["normalized"]["pair_rows"][0]["private_note"] = "not exported"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compact.json"
            reference.export_replay_summary(replay, path)
            compact = json.loads(path.read_text())
            self.assertNotIn("rows", compact)
            self.assertNotIn("raw", compact)
            self.assertNotIn("private_note", compact["normalized"]["pair_rows"][0])
            self.assertLess(path.stat().st_size, 256 * 1024)
            self.assertTrue(reference.compare(values, compact, 0, "generated compact export")["all_values_within_tolerance"])
            with self.assertRaises(FileExistsError):
                reference.export_replay_summary(replay, path)


if __name__ == "__main__":
    unittest.main()
