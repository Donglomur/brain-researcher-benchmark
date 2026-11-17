"""Generated controls with independent source-index and identity expectations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reward_history_inputs", PACKAGE / "prepare.py")
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)


def rat_data():
    behavior = []
    for day, stage, count in (("20240101", "Proestrus", 10), ("20240102", "Diestrus", 8)):
        for trial in range(1, count + 1):
            behavior.append({"unique_day": day, "trial_number": trial,
                             "reward": 2 ** trial, "stages": [stage],
                             "block": 2 if trial % 2 else 1,
                             "trial_type": 2 if trial == 8 else 0})
    return {"cpin": [list(range(302)) for _ in behavior], "behavior": behavior}


def payload():
    return {"schema_version": 1, "input_kind": "generated_engineering_control",
            "ratlist": list(prep.RATS), "figure3_cpin": {r: rat_data() for r in prep.RATS}}


class SourceSemantics(unittest.TestCase):
    def test_unshifted_inclusive_rectangular_auc(self):
        result = prep.prepare(payload())["rats"][0]
        # T has 301 samples, 0 and .5 are MATLAB indices 101 and 111.
        # pstruct values are column number minus 1: sum(100..110)*.05.
        self.assertAlmostEqual(result["row_ledger"][0]["auc"], 57.75)
        self.assertEqual(result["window"]["pstruct_columns_one_based_inclusive"], [101, 111])
        self.assertFalse(result["window"]["leading_column_removed"])
        self.assertEqual(result["stages"]["Proestrus"]["n_selected_rows"], 10)

    def test_missing_auc_sample_is_not_omitted_but_outside_sample_is(self):
        p = payload()
        data = p["figure3_cpin"][prep.RATS[0]]
        data["cpin"][0][100] = None
        data["cpin"][1][111] = None  # first column AFTER the source AUC window
        rows = prep.prepare(p)["rats"][0]["row_ledger"]
        self.assertIsNone(rows[0]["auc"])
        self.assertAlmostEqual(rows[1]["auc"], 57.75)
        self.assertEqual(len(rows), 18)

    def test_lags_bridge_days_before_stage_selection(self):
        result = prep.prepare(payload())["rats"][0]
        row = result["row_ledger"][10]
        self.assertEqual(row["identity"], ["20240102", 1])
        self.assertEqual(row["predictors_log2_reward_current_through_lag7"], [1, 10, 9, 8, 7, 6, 5, 4])
        self.assertEqual(row["predictor_trial_identities"][1], ["20240101", 10])
        self.assertEqual(row["cross_session_lag_numbers"], list(range(1, 8)))
        self.assertTrue(row["complete_numeric_row"])
        self.assertEqual(result["stages"]["Diestrus"]["X_without_intercept"][0], [1, 10, 9, 8, 7, 6, 5, 4])

    def test_trial_number_gaps_remain_lag_gaps(self):
        p = payload()
        data = p["figure3_cpin"][prep.RATS[0]]
        del data["behavior"][4]
        del data["cpin"][4]
        result = prep.prepare(p)["rats"][0]
        row = next(r for r in result["row_ledger"] if r["identity"] == ["20240101", 8])
        self.assertEqual(row["predictors_log2_reward_current_through_lag7"], [8, 7, 6, None, 4, 3, 2, 1])
        self.assertEqual(row["missing_predictor_lag_numbers"], [3])
        self.assertEqual(result["n_source_rows"], 17)
        self.assertEqual(result["n_padded_source_positions"], 18)
        self.assertEqual(result["sessions"][1]["concatenated_offset_zero_based"], 10)

    def test_stage_only_mask_retains_nonmixed_and_violation_trials(self):
        result = prep.prepare(payload())["rats"][0]["stages"]["Proestrus"]
        self.assertEqual(result["selected_despite_comment_mixed_nonviolation_filter"],
                         [["20240101", t] for t in (1, 3, 5, 7, 8, 9)])
        self.assertEqual(result["n_complete_numeric_rows"], 3)
        self.assertEqual(result["n_selected_rows"], 10)

    def test_source_any_stage_membership_is_preserved(self):
        p = payload()
        p["figure3_cpin"][prep.RATS[0]]["behavior"][0]["stages"] = ["Proestrus", "Diestrus"]
        result = prep.prepare(p)["rats"][0]["stages"]
        self.assertEqual(result["Proestrus"]["n_selected_rows"], 10)
        self.assertEqual(result["Diestrus"]["n_selected_rows"], 9)

    def test_all_nine_rats_and_no_coefficient_claim(self):
        result = prep.prepare(payload())
        self.assertEqual([r["rat"] for r in result["rats"]], list(prep.RATS))
        self.assertEqual(len(result["coefficient_order_for_native_robustfit"]), 9)
        self.assertFalse(result["research_qualified"])
        self.assertFalse(result["improvement_eligible"])
        self.assertNotIn("coefficients", result)

    def test_unclassified_stage_rows_still_supply_reward_history(self):
        p = payload()
        p["figure3_cpin"][prep.RATS[0]]["behavior"][9]["stages"] = []
        result = prep.prepare(p)["rats"][0]
        self.assertEqual(result["n_source_rows"], 18)
        self.assertEqual(result["stages"]["Proestrus"]["n_selected_rows"], 9)
        self.assertEqual(result["stages"]["Diestrus"]["X_without_intercept"][0][1], 10)


class RejectionAndCLI(unittest.TestCase):
    def reject(self, mutate, message):
        p = payload()
        mutate(p)
        with self.assertRaisesRegex(prep.ContractError, message):
            prep.prepare(p)

    def test_nonchronological_original_mask_is_rejected_not_reordered(self):
        def reorder(p):
            data = p["figure3_cpin"][prep.RATS[0]]
            data["behavior"][0], data["behavior"][1] = data["behavior"][1], data["behavior"][0]
            data["cpin"][0], data["cpin"][1] = data["cpin"][1], data["cpin"][0]
        self.reject(reorder, "positional stage mask")

    def test_duplicate_trial_is_rejected_before_assignment_overwrites(self):
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["behavior"][1].update(trial_number=1), "duplicate day/trial")

    def test_bad_current_reward_cannot_silently_delete_or_complexify_row(self):
        for value in (None, 0, -1, True, float("inf")):
            with self.subTest(reward=value):
                self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["behavior"][0].update(reward=value),
                            "finite|positive")

    def test_roster_and_correspondence_required(self):
        self.reject(lambda p: p["ratlist"].pop(), "nine-rat")
        self.reject(lambda p: p["figure3_cpin"].pop(prep.RATS[-1]), "full source roster")
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["cpin"].pop(), "row mismatch")
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["cpin"][0].pop(), "ragged")

    def test_clock_stage_date_and_trial_guards(self):
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["behavior"][0].update(trial_number=True), "integer")
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["behavior"][0].update(unique_day="20240230"), "YYYYMMDD")
        self.reject(lambda p: p["figure3_cpin"][prep.RATS[0]]["behavior"][0].update(stages="Proestrus"), "stage-label")
        with self.assertRaisesRegex(prep.ContractError, "does not resolve"):
            prep.source_window(4)

    def test_source_lag_assignment_requires_seven_padded_positions(self):
        data = rat_data()
        for name in ("cpin", "behavior"):
            data[name] = data[name][:6]
        with self.assertRaisesRegex(prep.ContractError, "at least 7 padded trial positions"):
            prep.prepare_rat(prep.RATS[0], data)
        full = rat_data()
        for name in ("cpin", "behavior"):
            data[name] = full[name][:7]
        result = prep.prepare_rat(prep.RATS[0], data)
        self.assertEqual(result["n_padded_source_positions"], 7)
        self.assertEqual(result["row_ledger"][-1]["predictors_log2_reward_current_through_lag7"],
                         [7, 6, 5, 4, 3, 2, 1, None])

    def test_cli_roundtrip_and_duplicate_json_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            source, output = Path(root) / "input.json", Path(root) / "output.json"
            source.write_text(json.dumps(payload()))
            command = [sys.executable, str(PACKAGE / "prepare.py"), str(source), "--output", str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())["source_figure"], "3k")
            for malformed, expected in (("{\"x\":1,\"x\":2}", "duplicate JSON key"),
                                         ("{\"x\":NaN}", "invalid JSON constant")):
                source.write_text(malformed)
                run = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)
                self.assertIn(expected, run.stderr)


if __name__ == "__main__":
    unittest.main()
