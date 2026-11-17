"""Independent hand-derived controls; generated data are not scientific evidence."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("structured_independent", Path(__file__).parents[1] / "evaluator.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


# Literal source cohort, independently transcribed from the frozen contract.
SL = ["M2_2202025_g0", "M2_2212025_g0", "M1_2182025_g0", "M1_2202025_g0",
      "M4_2252025_g0", "M4_2272025_g1", "M5_2272025_g0", "M5_3012025_g0"]
STANDARD = ["AC01_01292025_g0", "j2_05092024_g0", "AB02_08272024_g0",
            "AB02_08282024_g0", "AB04_09092024_g0"]


def generated_roster(contexts=None):
    contexts = contexts or ["LS", "SL", "SL", "SS", "SS", "SS"] * 10
    sessions = []
    for j, sid in enumerate(SL + STANDARD):
        # Deliberately synthetic, explicit mapping; never inferred from filenames.
        mouse = "synthetic-a" + str(j // 2) if j < 8 else "synthetic-b" + str(min(j - 8, 3))
        sessions.append({"session_id": sid, "mouse_id": mouse,
                         "shaping_group": "SL_only_shaping" if j < 8 else "standard_shaping",
                         "trials": [{"trial_id": "generated-trial-" + str(k), "context": context,
                                     "has_any_retained_event": True} for k, context in enumerate(contexts)]})
    return {"schema": "structured_experience_owner_roster_v1",
            "evidence_kind": "generated_engineering_control",
            "method_route": "prospective_pointwise_0p5s",
            "provenance": {name: "a" * 64 for name in (
                "behavior_sha256", "unit_roster_sha256", "trial_order_sha256",
                "animal_mapping_sha256", "inclusion_policy_sha256")}, "sessions": sessions}


def make_expected(roster):
    mice = {session["mouse_id"] for session in roster["sessions"]}
    return evaluator.build_expected(roster, b"independent-engineering-secret-32bytes", "b" * 64,
                                    {mouse: "c" * 64 for mouse in mice})


def predictions(expected, offset):
    return [{"query_id": row["query_id"],
             "predicted_bin": (row["true_bin"] + offset(row)) % 40} for row in expected["rows"]]


class IndependentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = generated_roster()
        cls.expected = make_expected(cls.roster)

    def test_circle_wrap_half_period_and_strict_classes(self):
        self.assertEqual(evaluator.circular_squared_seconds(39, 0), 0.25)
        self.assertEqual(evaluator.circular_squared_seconds(0, 39), 0.25)
        self.assertEqual(evaluator.circular_squared_seconds(20, 0), 100)
        for invalid in (True, False, 39.5, -1, 40, float("nan")):
            with self.subTest(value=invalid), self.assertRaises(evaluator.AdmissionError):
                evaluator.circular_squared_seconds(invalid, 0)

    def test_unequal_context_counts_do_not_reweight_pairs(self):
        offsets = {("LS", "SL"): 0, ("LS", "SS"): 2,
                   ("SL", "LS"): 4, ("SL", "SS"): 6,
                   ("SS", "LS"): 8, ("SS", "SL"): 10}
        result = evaluator.score_predictions(self.expected, predictions(
            self.expected, lambda row: offsets.get((row["source_context"], row["test_context"]), 2)))
        # Six losses: 0,1,4,9,16,25. Unequal target trial counts would give25/3 if pooled.
        self.assertAlmostEqual(result["loss"], 55 / 6)
        self.assertNotAlmostEqual(result["loss"], 25 / 3)
        for session in result["sessions"]:
            self.assertEqual(session["within_mse_seconds2"], 1)
            self.assertAlmostEqual(session["signed_across_minus_within_seconds2"], 49 / 6)
            self.assertEqual(len(session["context_pair_mse_seconds2"]), 3)

    def test_mouse_macro_not_thirteen_session_pool(self):
        session_index = {sid: index for index, sid in enumerate(SL + STANDARD)}
        result = evaluator.score_predictions(self.expected, predictions(
            self.expected, lambda row: 0 if row["source_context"] == row["test_context"]
            else session_index[row["session_id"]]))
        # Sessionj has lossj²/4. Pairing0..7 and then singles8,9,10/pair11,12:
        self.assertEqual(result["shaping_strata"]["SL_only_shaping"], 4.375)
        self.assertEqual(result["shaping_strata"]["standard_shaping"], 23.59375)
        self.assertEqual(result["loss"], 13.984375)
        self.assertNotEqual(result["loss"], 12.5)
        self.assertEqual(len(result["mice"]), 8)

    def test_trials_not_fold_means_receive_equal_weights(self):
        roster = generated_roster((["LS", "SL", "SS"] * 11)[:31])
        expected = make_expected(roster)
        result = evaluator.score_predictions(expected, predictions(
            expected, lambda row: 20 if row["trial_id"] == "generated-trial-0" else 0))
        first = result["sessions"][0]
        self.assertEqual([len(fold) for fold in evaluator.ordered_folds(roster["sessions"][0]["trials"])],
                         [4, 3, 3, 3, 3, 3, 3, 3, 3, 3])
        for source in ("LS", "SL", "SS"):
            self.assertAlmostEqual(first["context_pair_mse_seconds2"][source]["LS"], 100 / 11)
            self.assertEqual(first["context_pair_mse_seconds2"][source]["SL"], 0)
            self.assertEqual(first["context_pair_mse_seconds2"][source]["SS"], 0)

    def test_all_fit_units_are_source_restricted_and_exclude_held_mouse(self):
        self.assertEqual(len(self.expected["fit_units"]), 13 * 10 * 3)
        sessions = {session["session_id"]: session for session in self.roster["sessions"]}
        for unit in self.expected["fit_units"]:
            session = sessions[unit["session_id"]]
            context_by_trial = {trial["trial_id"]: trial["context"] for trial in session["trials"]}
            self.assertEqual(len(unit["development_mouse_ids"]), 7)
            self.assertNotIn(unit["held_mouse_id"], unit["development_mouse_ids"])
            self.assertFalse(set(unit["calibration_trial_ids"]) & set(unit["query_trial_ids"]))
            self.assertTrue(unit["calibration_trial_ids"])
            self.assertTrue(all(context_by_trial[trial] == unit["source_context"]
                                for trial in unit["calibration_trial_ids"]))

    def test_symmetry_tails_are_descriptive_and_include_ties(self):
        perfect = predictions(self.expected, lambda row: 0)
        shifted = predictions(self.expected, lambda row: 2)
        compared = evaluator.compare_predictions(self.expected, perfect, shifted)
        self.assertEqual([row["baseline_minus_candidate_seconds2"]
                          for row in compared["paired_mouse_differences"]], [1] * 8)
        diagnostic = compared["sign_symmetry_diagnostic"]
        self.assertEqual(diagnostic["enumerations"], 256)
        self.assertEqual(diagnostic["two_sided_tail_count"], 2)
        self.assertEqual(diagnostic["two_sided_tail_fraction"], 1 / 128)
        self.assertIs(diagnostic["calibrated_p_value"], False)
        tied = evaluator.compare_predictions(self.expected, perfect, perfect)
        self.assertEqual(tied["sign_symmetry_diagnostic"]["two_sided_tail_fraction"], 1)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "source-defined t-test needs existing SciPy")
    def test_session_t_statistic_uses_source_group_order_and_pooled_variance(self):
        tables = {}
        for j, sid in enumerate(SL + STANDARD):
            tables[sid] = {source: {target: 0 if source == target else j * j / 4
                                   for target in ("LS", "SL", "SS")}
                           for source in ("LS", "SL", "SS")}
        result = evaluator.summarize_reproduction(self.roster, tables, method_route="source_concordance_0p5s")
        test = result["published_session_test"]
        # Eight gaps mean4.375/sample variance19.875; five mean25.5/variance62.71875.
        # Pooled variance390/11; squared SE507/44. Session weighting is intentional here.
        self.assertAlmostEqual(test["statistic"], -21.125 / math.sqrt(507 / 44), places=12)
        self.assertEqual(test["df"], 11)
        self.assertEqual(test["experimental_unit"], "session")
        self.assertIs(test["equal_var"], True)
        self.assertIs(test["independent_animal_inference"], False)
        self.assertIs(result["source_workflow_verified"], False)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "source-defined t-test needs existing SciPy")
    def test_negative_signed_gap_is_retained_alongside_absolute_gap(self):
        tables = {sid: {source: {target: 4 if source == target else 1
                                for target in ("LS", "SL", "SS")}
                        for source in ("LS", "SL", "SS")} for sid in SL + STANDARD}
        result = evaluator.summarize_reproduction(self.roster, tables, method_route="source_concordance_0p5s")
        for session in result["sessions"]:
            self.assertEqual(session["signed_across_minus_within_seconds2"], -3)
            self.assertEqual(session["absolute_gap_seconds2"], 3)
        self.assertEqual(result["published_session_test"]["status"], "undefined_degenerate_variance")
        self.assertIsNone(result["published_session_test"]["pvalue"])

    def test_prediction_order_invariance_and_incomplete_refusal(self):
        complete = predictions(self.expected, lambda row: 1)
        forward = evaluator.score_predictions(self.expected, complete)
        backward = evaluator.score_predictions(self.expected, list(reversed(complete)))
        self.assertEqual(forward, backward)
        for altered in (complete[:-1], complete + [complete[0]]):
            with self.assertRaises(evaluator.AdmissionError):
                evaluator.score_predictions(self.expected, altered)

    def test_no_population_deletion_or_zero_event_admission(self):
        missing = copy.deepcopy(self.roster)
        missing["sessions"].pop()
        zero_event = copy.deepcopy(self.roster)
        zero_event["sessions"][0]["trials"][0]["has_any_retained_event"] = False
        empty_support = copy.deepcopy(self.roster)
        empty_support["sessions"][0]["trials"] = empty_support["sessions"][0]["trials"][:9]
        paper_only = copy.deepcopy(self.roster)
        paper_only["method_route"] = "paper_only_unspecified_bins"
        for altered in (missing, zero_event, empty_support, paper_only):
            with self.assertRaises(evaluator.AdmissionError):
                evaluator.validate_roster(altered)


if __name__ == "__main__":
    unittest.main()
