"""Generated software controls only: these are not scientific observations."""
import csv
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from fractions import Fraction

from counts import CountError, Counts, reduce_rows, rows_from_csv, validate_displayed_metric
from inspect_author_table import inspect_table


COHORT = tuple((f"generated_cutout_{index}", f"generated_neuropil_{index}", "generated_region")
               for index in range(16))
POOLED = ("generated_pool", "generated_pool_neuropil", "generated_cns")


def row(identity, tp, fp, fn):
    # Independent decimal expressions for generated fixture serialization.
    return {"cutouts": identity[0], "neuropil": identity[1], "region": identity[2],
            "true_positives": str(tp), "false_positives": str(fp),
            "false_negatives": str(fn),
            "precision": str(tp / (tp + fp)),
            "recall": str(tp / (tp + fn)),
            "f1_score": str(2 * tp / (2 * tp + fp + fn))}


def fixture():
    # Fifteen small perfect regions and one large complete failure distinguish
    # pooled counts (3/23) from mean per-region F1 (15/16).
    return ([row(identity, 1, 0, 0) for identity in COHORT[:-1]]
            + [row(COHORT[-1], 0, 100, 100), row(POOLED, 15, 100, 100)])


class CountControls(unittest.TestCase):
    def test_pooled_micro_metric_not_macro_or_double_count(self):
        report = reduce_rows(fixture(), COHORT, POOLED)
        self.assertEqual(report["cutout_count"], 16)
        self.assertEqual(report["aggregate"]["true_positives"], 15)
        self.assertEqual(report["aggregate"]["false_positives"], 100)
        self.assertEqual(report["aggregate"]["false_negatives"], 100)
        self.assertAlmostEqual(report["aggregate"]["f1_score"], 3 / 23)
        self.assertNotAlmostEqual(report["aggregate"]["f1_score"], 15 / 16)
        self.assertEqual(len(report["per_cutout"]), 16)

    def test_actual_source_shape_has_no_pooled_row(self):
        report = reduce_rows(fixture()[:-1], COHORT)
        self.assertEqual(report, reduce_rows(fixture(), COHORT, POOLED))

    def test_permutation_preserves_frozen_output_order(self):
        expected = reduce_rows(fixture(), COHORT, POOLED)
        actual = reduce_rows(list(reversed(fixture())), COHORT, POOLED)
        self.assertEqual(actual, expected)

    def test_missing_duplicate_foreign_region_and_pooled_mismatch_fail(self):
        for bad in (fixture()[:-1], fixture()[1:], fixture() + [fixture()[0]]):
            with self.subTest(bad=bad):
                with self.assertRaises(CountError):
                    reduce_rows(bad, COHORT, POOLED)
        bad = fixture()
        bad[0]["region"] = "different_region"
        with self.assertRaises(CountError):
            reduce_rows(bad, COHORT, POOLED)
        bad = fixture()
        bad[-1] = row(POOLED, 16, 100, 100)
        with self.assertRaisesRegex(CountError, "Pooled source counts"):
            reduce_rows(bad, COHORT, POOLED)

    def test_counts_are_strict_integers(self):
        for value in (True, -1, 0.1, 1.0, "1"):
            with self.subTest(value=value):
                with self.assertRaises(CountError):
                    Counts(value, 1, 1)
        for value in ("1.0", "-1", "nan", "1e2", ""):
            bad = fixture()
            bad[0]["true_positives"] = value
            with self.subTest(value=value):
                with self.assertRaises(CountError):
                    reduce_rows(bad, COHORT, POOLED)

    def test_undefined_is_not_perfect_or_zero(self):
        self.assertEqual(Counts(0, 0, 0).metrics(),
                         {"precision": None, "recall": None, "f1_score": None})
        self.assertEqual(Counts(0, 1, 0).metrics(),
                         {"precision": Fraction(0), "recall": None,
                          "f1_score": Fraction(0)})

    def test_source_metrics_cannot_override_counts(self):
        for value in ("0.9", "NaN", "Infinity", "-0.1", "1.1", ""):
            bad = fixture()
            bad[-1]["f1_score"] = value
            with self.subTest(value=value):
                with self.assertRaises(CountError):
                    reduce_rows(bad, COHORT, POOLED)

    def test_source_decimal_rounding_is_preserved(self):
        rows = fixture()
        for name in ("precision", "recall", "f1_score"):
            rows[-1][name] = "0.13"
        self.assertAlmostEqual(reduce_rows(rows, COHORT, POOLED)["aggregate"]["f1_score"],
                               3 / 23)

    def test_csv_roundtrip_and_malformed_shapes(self):
        rows = fixture()
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        payload = stream.getvalue().encode()
        self.assertEqual(rows_from_csv(payload), rows)
        for corrupt in (payload.replace(b"neuropil,", b"region,", 1),
                        payload + b"extra,short\n",
                        payload + b"1,2,3,4,5,6,7,8,9,10\n",
                        b"\xff"):
            with self.subTest(corrupt=corrupt[:40]):
                with self.assertRaises(CountError):
                    rows_from_csv(corrupt)

    def test_wrong_roster_size_is_rejected(self):
        for roster in (COHORT[:-1], COHORT + (COHORT[0],),
                       COHORT[:-1] + (COHORT[0],)):
            with self.assertRaises(CountError):
                reduce_rows(fixture(), roster, POOLED)

    def test_non_nearest_source_display_is_reported(self):
        self.assertTrue(validate_displayed_metric("0.400", Fraction(4009, 10000), "f1_score"))
        self.assertFalse(validate_displayed_metric("0.401", Fraction(4009, 10000), "f1_score"))

    def test_literal_geometry_flags_small_box_without_repair(self):
        rows = fixture()[:-1]
        for index, item in enumerate(rows):
            item.update({"Resolution": "(16, 16, 45)", "Bbox start": "(0, 0, 0)",
                         "Bbox end": "(12, 10, 2)" if index == 0 else "(128, 128, 16)"})
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        payload = stream.getvalue().encode()
        pin = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
               "commit": "generated-geometry-only", "cutout_rows": COHORT}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.csv"
            path.write_bytes(payload)
            geometry = inspect_table(path, pin)["source_geometry"]
        self.assertEqual(geometry[0]["extent_nm"], [192, 160, 90])
        self.assertFalse(geometry[0]["matches_majority_box_shape"])
        self.assertTrue(all(item["matches_majority_box_shape"] for item in geometry[1:]))

    def test_authenticated_inspection_rejects_changed_source_bytes(self):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(fixture()[0]))
        writer.writeheader()
        writer.writerows(fixture())
        payload = stream.getvalue().encode()
        pin = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
               "commit": "generated-source-not-an-author-result", "cutout_rows": COHORT,
               "pooled_row": POOLED}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.csv"
            path.write_bytes(payload)
            report = inspect_table(path, pin)
            self.assertEqual(report["cutout_count"], 16)
            self.assertFalse(report["candidate_scored"])
            path.write_bytes(payload.replace(b"generated", b"alteredXX", 1))
            with self.assertRaisesRegex(CountError, "SHA-256"):
                inspect_table(path, pin)


if __name__ == "__main__":
    unittest.main()
