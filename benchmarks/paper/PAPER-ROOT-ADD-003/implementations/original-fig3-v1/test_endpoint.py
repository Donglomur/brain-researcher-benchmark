"""Generated controls only. No source archive, neural targets, fitting or models."""
import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fig3_endpoint", HERE / "endpoint.py")
e = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e
spec.loader.exec_module(e)


def rows():
    output = []
    for uid, offset in zip(e.PARTICIPANTS, (-100., 0., 100.)):
        for item in e.ITEMS:
            condition = "B" if item <= 1000 else "D" if item <= 1250 else "S"
            x = item % 17 - 8
            output.append({"target_UID": str(uid), "roi": e.ROI, "item_id": str(item),
                           "sentence": "generated sentence " + str(item), "cond": condition,
                           "cond_approach": "B" if condition == "B" else condition + "_search",
                           "response_target": str(2 * x + offset),
                           "response_target_non_norm": str({"B": 2., "D": 4., "S": 1.}[condition] + offset / 1000),
                           "encoding_model_pred": str(x)})
    return output


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.rows = rows()
        self.panel = e._panel_from_rows(iter(self.rows))
        self.prediction = [float(i % 17 - 8) for i in e.ITEMS]

    def test_exact_item_pooling_not_row_pooling_or_participant_average_r(self):
        result = e.score(self.panel, self.prediction)
        self.assertAlmostEqual(result["metrics"]["all_1500"]["candidate"]["r"], 1.)
        self.assertEqual(result["metrics"]["all_1500"]["candidate"]["n_items"], 1500)
        # Unequal participant slopes give a different mean-of-r than r-of-means.
        altered = copy.deepcopy(self.rows)
        for row in altered:
            i = int(row["item_id"])
            row["response_target"] = str((1 if row["target_UID"] == "797" else -0.1) * (i % 17 - 8))
        report = e.score(e._panel_from_rows(altered), self.prediction)
        self.assertAlmostEqual(report["metrics"]["all_1500"]["candidate"]["r"], 1.)
        self.assertAlmostEqual(sum(v["r"] for v in report["participant_diagnostics"].values()) / 3, -1 / 3)
        pooled = e.pearson(self.prediction * 3, [float(r["response_target"]) for r in self.rows])["r"]
        self.assertLess(pooled, 0.2)

    def test_identity_order_invariance_and_saved_author_is_distinct(self):
        other = e._panel_from_rows(reversed(self.rows))
        self.assertEqual(other, self.panel)
        result = e.score(self.panel, [-v for v in self.prediction])
        metric = result["metrics"]["all_1500"]
        self.assertAlmostEqual(metric["released_author_prediction"]["r"], 1.)
        self.assertAlmostEqual(metric["descriptive_candidate_minus_released_author_r"], -2.)
        self.assertIn("not performed", result["author_replay"])

    def test_complete_crossed_panel_and_no_pseudoreplication(self):
        for bad in (self.rows[:-1], self.rows + [self.rows[0]],
                    [r for r in self.rows if r["target_UID"] != "797"]):
            with self.subTest(n=len(bad)), self.assertRaises(e.InvalidPanel):
                e._panel_from_rows(bad)

    def test_non_target_outcomes_are_never_converted(self):
        unused = [{"target_UID": "837", "roi": e.ROI, "response_target": "secret-invalid"},
                  {"target_UID": "797", "roi": "lang_LH_IFG", "response_target": object()}]
        self.assertEqual(e._panel_from_rows(unused + self.rows), self.panel)

    def test_mismatched_conditions_sentences_and_source_predictions_fail(self):
        for field, value in (("cond_approach", "D_modify"), ("cond", "S"),
                             ("sentence", "swapped stimulus"), ("encoding_model_pred", "900"),
                             ("response_target", "nan"), ("response_target_non_norm", "inf"),
                             ("item_id", "1501")):
            bad = copy.deepcopy(self.rows)
            bad[1000][field] = value
            with self.subTest(field=field), self.assertRaises(e.InvalidPanel):
                e._panel_from_rows(bad)

    def test_zero_variance_is_undefined_and_extreme_finite_values_remain_stable(self):
        report = e.score(self.panel, [5.] * 1500)
        metric = report["metrics"]["all_1500"]
        self.assertIsNone(metric["candidate"]["r"])
        self.assertIsNone(metric["descriptive_candidate_minus_released_author_r"])
        self.assertEqual(metric["candidate"]["undefined_reason"], "constant_prediction")
        self.assertAlmostEqual(e.pearson([-1e308, 0., 1e308], [1e308, 0., -1e308])["r"], -1.)
        for x in (float("nan"), float("inf"), True):
            with self.assertRaises(e.InvalidPanel):
                e.score(self.panel, [x] * 1500)

    def test_raw_bold_percent_uses_unnormalized_units(self):
        report = e.score(self.panel, self.prediction)["response_effect_calibration"]
        self.assertAlmostEqual(report["percent_change_from_baseline"]["D"], 100.)
        self.assertAlmostEqual(report["percent_change_from_baseline"]["S"], -50.)
        bad = copy.deepcopy(self.rows)
        for row in bad:
            if row["cond"] == "B":
                row["response_target_non_norm"] = "0"
        report = e.score(e._panel_from_rows(bad), self.prediction)["response_effect_calibration"]
        self.assertTrue(report["zero_denominator"])
        self.assertEqual(report["percent_change_from_baseline"], {"D": None, "S": None})

    def test_prediction_identity_join_and_strict_roster(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.csv"
            with path.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["item_id", "prediction"])
                for i, p in reversed(list(zip(e.ITEMS, self.prediction))):
                    writer.writerow([i, p])
            self.assertEqual(e.load_predictions(path), self.prediction)
            original = path.read_text()
            for modified in (original + "1,0\n", original.replace("1500,", "1501,", 1),
                             "\n".join(original.splitlines()[:-1]) + "\n",
                             original.replace("item_id,prediction", "item_id,response_target"),
                             original + "1,2,3\n"):
                path.write_text(modified)
                with self.assertRaises(e.InvalidPanel):
                    e.load_predictions(path)

    def test_archive_authentication_fails_before_tar_or_outcome_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.tar"
            path.write_bytes(b"not a source archive")
            with self.assertRaisesRegex(e.InvalidPanel, "length"):
                e.load_original_archive(path)
            with path.open("wb") as handle:
                handle.truncate(e.ARCHIVE_BYTES)
            with self.assertRaisesRegex(e.InvalidPanel, "SHA256"):
                e.load_original_archive(path)

    def test_source_binding_is_readable_and_scope_is_not_a_win(self):
        binding = json.loads((HERE / "source_binding.json").read_text())
        self.assertEqual(binding["data_archive"]["sha256"], e.ARCHIVE_SHA256)
        self.assertEqual(binding["paper_result"]["rounded_r_all_1500"], 0.43)
        report = e.score(self.panel, self.prediction)
        self.assertNotIn("passed", report)
        self.assertNotIn("paper_win", report)
        self.assertEqual(report["primary_endpoint"], "all_1500")
        self.assertTrue(all(math.isfinite(v["candidate"]["r"]) for v in report["metrics"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
