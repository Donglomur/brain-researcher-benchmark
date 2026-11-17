"""Generated mathematical and cohort controls; no authentic study observations."""
import copy
import importlib.util
from pathlib import Path
import statistics
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("original_time_score", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def fixtures():
    roster = {"schema": "h_original_time_roster_v1", "input_sha256": score.SOURCE_SHA256,
              "sessions": [{"animal": animal, "day": day, "condition_codes": [11, 12, 21, 22] * 35,
                            "recorded_delay_seconds": [2.5, 2.5, 5, 5] * 35}
                           for animal in score.ANIMALS for day in score.DAYS]}
    sessions = score.validate_roster(roster)
    document = {"schema": "h_original_time_predictions_v1", "roster_sha256": score.canonical_hash(roster),
                "panels": [{"animal": animal, "day": day, "cue": cue, "control": control,
                            "trials": [{"trial_index": trial, "status": "finite", "predicted_bins": list(range(1, 8))}
                                       for trial in sessions[(animal, day)][cue]]}
                           for animal, day, cue, control in score.panel_keys()]}
    return roster, document


class OriginalTimeControls(unittest.TestCase):
    def test_correlation_is_not_accuracy(self):
        rows = [{"trial_index": 0, "status": "finite", "predicted_bins": [2, 3, 4, 5, 6, 7, 7]}]
        value = score.score_panel([0], rows)
        self.assertAlmostEqual(value["pearson_r"], statistics.correlation(range(1, 8), rows[0]["predicted_bins"]))
        self.assertGreater(value["pearson_r"], .98)
        self.assertEqual(value["confusion_predicted_by_actual"][1][0], 1)
        self.assertEqual(value["confusion_predicted_by_actual"][0][1], 0)

    def test_pool_trials_before_correlation(self):
        values = [[1, 2, 3, 4, 5, 6, 7], [1, 1, 1, 1, 1, 1, 2]]
        rows = [{"trial_index": i, "status": "finite", "predicted_bins": bins} for i, bins in enumerate(values)]
        result = score.score_panel([0, 1], rows)
        self.assertAlmostEqual(result["pearson_r"], statistics.correlation(list(range(1, 8)) * 2, sum(values, [])))
        trial_macro = statistics.mean(statistics.correlation(range(1, 8), row) for row in values)
        self.assertNotAlmostEqual(result["pearson_r"], trial_macro)
        for column in zip(*result["confusion_predicted_by_actual"]):
            self.assertEqual(sum(column), 1)

    def test_undefined_and_failed_remain_distinct(self):
        constant = [{"trial_index": 0, "status": "finite", "predicted_bins": [4] * 7}]
        self.assertEqual(score.score_panel([0], constant)["status"], "source_undefined")
        failed = [{"trial_index": 0, "status": "failed", "reason": "native fit failure"}]
        result = score.score_panel([0, 1], failed)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual([x["status"] for x in result["failures"]], ["failed", "unstarted"])
        self.assertIsNone(result["confusion_predicted_by_actual"])

    def test_reject_trial_leakage_and_bad_labels(self):
        row = {"trial_index": 0, "status": "finite", "predicted_bins": list(range(1, 8))}
        for rows in ([row, row], [{**row, "trial_index": 1}], [{**row, "predicted_bins": [True] * 7}],
                     [{**row, "predicted_bins": [0] * 7}], [{**row, "predicted_bins": [1] * 6}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                score.score_panel([0], rows)

    def test_full_cohort_keeps_cues_and_controls_separate(self):
        roster, author = fixtures()
        candidate = copy.deepcopy(author)
        for panel in candidate["panels"]:
            if panel["cue"] == "long" and panel["control"] == "real":
                for trial in panel["trials"]:
                    trial["predicted_bins"] = list(range(7, 0, -1))
        result = score.compare(roster, author, candidate)
        self.assertEqual(result["candidate"]["finite_panel_count"], 176)
        self.assertEqual(len(result["separate_panel_deltas"]), 16)
        for panel in result["separate_panel_deltas"]:
            expected = -2 if panel["cue"] == "long" and panel["control"] == "real" else 0
            self.assertEqual(panel["equal_animal_mean_delta"], expected)
        self.assertIsNone(result["paper_win"])

    def test_missing_mouse_trial_cannot_shrink_denominator(self):
        roster, author = fixtures()
        candidate = copy.deepcopy(author)
        candidate["panels"][0]["trials"].pop()
        result = score.compare(roster, author, candidate)
        self.assertEqual(len(result["candidate"]["panels"]), 176)
        self.assertFalse(result["candidate"]["complete_prediction_support"])
        self.assertIsNone(result["separate_panel_deltas"][0]["equal_animal_mean_delta"])
        self.assertEqual(result["separate_panel_deltas"][0]["finite_pairs"], 10)

    def test_roster_authentication_boundary_and_complete_cohort(self):
        roster, author = fixtures()
        for modification in ("cohort", "preprocessing", "membership", "bool"):
            changed = copy.deepcopy(roster)
            if modification == "cohort":
                changed["sessions"].pop()
            elif modification == "preprocessing":
                changed["input_sha256"] = "0" * 64
            elif modification == "membership":
                changed["sessions"][0]["condition_codes"][0] = 511
            else:
                changed["sessions"][0]["condition_codes"][0] = True
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                score.score_run(changed, author)

    def test_reversal_trials_are_excluded_by_source_cue_membership(self):
        roster, _ = fixtures()
        roster["sessions"][2]["condition_codes"][:4] = [511, 512, 521, 522]
        support = score.validate_roster(roster)[(score.ANIMALS[0], "reversal1")]
        self.assertEqual(len(support["short"]), 68)
        self.assertEqual(len(support["long"]), 68)
        self.assertTrue(set(range(4)).isdisjoint(support["short"] + support["long"]))

    def test_recorded_delay_controls_membership_with_exact_source_equality(self):
        roster, _ = fixtures()
        session = roster["sessions"][2]
        session["recorded_delay_seconds"][:5] = [5, 2.5000000000000004, 2.5, 3, 2.5]
        session["condition_codes"][4] = 511
        support = score.validate_roster(roster)[(score.ANIMALS[0], "reversal1")]
        # code11/delay5 belongs to long; code21/delay2.5 belongs to short.
        # Near-2.5, other delays and reversal codes belong to neither source mask.
        self.assertIn(0, support["long"])
        self.assertNotIn(0, support["short"])
        self.assertIn(2, support["short"])
        self.assertNotIn(2, support["long"])
        self.assertTrue({1, 3, 4}.isdisjoint(support["short"] + support["long"]))

    def test_missing_invalid_or_inferred_delay_vector_is_rejected(self):
        roster, _ = fixtures()
        for delays in (None, [2.5] * 139, [True] * 140, [float("nan")] * 140):
            changed = copy.deepcopy(roster)
            if delays is None:
                del changed["sessions"][0]["recorded_delay_seconds"]
            else:
                changed["sessions"][0]["recorded_delay_seconds"] = delays
            with self.subTest(delays=str(delays)[:25]), self.assertRaises(ValueError):
                score.validate_roster(changed)

    def test_duplicate_json_keys_and_nonfinite_constants_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ('{"panels": [], "panels": []}', '{"x": NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    score.read_json(path)


if __name__ == "__main__":
    unittest.main()
