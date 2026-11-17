"""Generated engineering controls; these are not empirical observations."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("estrous_evaluator", PACKAGE / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def trace(base_start, base_zero, post, metadata=100):
    # 301 samples, dt .05; indices 99/100/110 correspond to −.05/0/.5.
    values = [base_zero] * 301
    values[99], values[100] = base_start, base_zero
    values[101:111] = [post] * 10
    return [metadata] + values


def population():
    rows = [
        (1, "Proestrus", 0, [100] + [2] * 301),
        (1, "Proestrus", 2, [10000] + [2000] * 301),
        (2, "Proestrus", 0, trace(1, 3, 6)),
        (2, "Proestrus", 0, trace(5, 1, 6)),
        (3, "Proestrus", 0, trace(1, 1, 2)),
        (2, "Diestrus", 0, trace(0, 0, 1)),
        (3, "Diestrus", 0, trace(0, 0, 0)),
        (2, "Proestrus", 2, trace(0, 0, 100000)),
    ]
    return {"cpin": [row[3] for row in rows], "behavior": [
        {"trial_id": str(i), "unique_day": "20240101" if stage == "Proestrus" else "20240102",
         "block": block, "stage": stage, "prev_trial_type": prev}
        for i, (block, stage, prev, _) in enumerate(rows)
    ]}


def payload():
    return {"schema_version": 1, "input_kind": "generated_engineering_control",
            "figure2_ratlist": ["G127"], "figure2_serum_ratlist": ["G127"],
            "figure2": {"G127": population()}, "figure2_serum": {"G127": population()},
            "serum_table": [{"rat": "G127", "session_date": "2024-01-01", "estradiol_conc": 7},
                            {"rat": "G127", "session_date": "2024-01-02", "estradiol_conc": None}],
            "figure3_manifest": {"ratlist": list(ev.FIGURE3_RATS), "best_fits_supplied": True,
                                 "sessions": [{"rat": "G127", "unique_day": "20240101"}]}}


def multirow_payload():
    """Duplicate identical rows so MATLAB's default mean axis is trialwise."""
    p = payload()
    for field in ("figure2", "figure2_serum"):
        data = p[field]["G127"]
        original_behavior = copy.deepcopy(data["behavior"])
        data["cpin"] += copy.deepcopy(data["cpin"])
        data["behavior"] += [{**b, "trial_id": b["trial_id"] + "-rep"} for b in original_behavior]
    return p


class ScientificControls(unittest.TestCase):
    def test_independent_stage_mean_then_min_reference(self):
        result = ev.evaluate(multirow_payload())
        stage = result["figure2h_stage_contrasts"]["rats"][0]
        pro = stage["stages"]["Proestrus"]
        self.assertAlmostEqual(pro["high"]["baseline_min"], 2)
        self.assertAlmostEqual(pro["high"]["auc"], 1.9)
        self.assertAlmostEqual(pro["low"]["auc"], .475)
        self.assertAlmostEqual(pro["high_minus_low_auc"], 1.425)
        self.assertAlmostEqual(stage["proestrus_minus_diestrus"], .95)
        self.assertEqual(pro["high"]["included_trial_ids"], [["20240101", "2"], ["20240101", "3"],
                                                              ["20240101", "2-rep"], ["20240101", "3-rep"]])

    def test_serum_leading_column_normalization_and_missing_hormone_retained(self):
        result = ev.evaluate(multirow_payload())["figure2i_serum_contrasts"]
        self.assertEqual(result["normalization"][0]["divisor"], 100)
        arrays = result["source_shaped_arrays"]
        self.assertAlmostEqual(arrays["delta_good"][0], .01425)
        self.assertAlmostEqual(arrays["delta_good"][1], .00475)
        self.assertEqual(arrays["E2_good"], [7, None])

    def test_reviewer_endpoint_control(self):
        data = {"cpin": [[100] + [2] * 301, trace(10, 10, 30), trace(10, 10, 20)],
                "behavior": [{"trial_id": str(i), "unique_day": "20240101", "block": i + 1,
                              "stage": "Estrus", "prev_trial_type": 0} for i in range(3)]}
        p = payload()
        data["cpin"] += copy.deepcopy(data["cpin"])
        data["behavior"] += [{**b, "trial_id": b["trial_id"] + "-rep"} for b in list(data["behavior"])]
        p["figure2_serum"]["G127"] = data
        result = ev.evaluate(p)["figure2i_serum_contrasts"]["session_ledger"][0]
        self.assertAlmostEqual(result["high"]["auc"], .095)
        self.assertAlmostEqual(result["low"]["auc"], .0475)
        self.assertAlmostEqual(result["delta_auc"], .0475)
        self.assertEqual(result["stage"], "Estrus")  # Serum is not restricted to Pro/Di.

    def test_nearest_bins_no_nominal_window_interpolation(self):
        times = [-5 + .15 * j for j in range(101)]
        row = [0] + [t + 5 for t in times]
        result = ev.auc_of_mean([row, row.copy()], [0, 1])
        self.assertEqual(result["window_sample_indices_zero_based"], {"baseline_start": 33, "zero": 33, "auc_end": 37})
        self.assertAlmostEqual(result["auc"], .18)

    def test_pearson_source_missing_policy_and_analytic_reference(self):
        self.assertAlmostEqual(ev.pearson_complete_vectors([1, 2, 3], [1, 3, 2]), .5)
        self.assertAlmostEqual(ev.pearson_complete_vectors([1, 2, 3], [3, 2, 1]), -1)
        self.assertIsNone(ev.pearson_complete_vectors([1, None, 3], [1, 3, 2]))
        self.assertIsNone(ev.pearson_complete_vectors([1, 1, 1], [1, 3, 2]))
        self.assertIsNone(ev.evaluate(payload())["figure2i_serum_contrasts"]["pearson_r"])

    def test_singleton_export_trial_axis_policy_is_explicit(self):
        p = payload()
        result = ev.evaluate(p)
        self.assertIn("singleton", result["prospective_export_policy"])
        self.assertTrue(result["singleton_selections_affected_by_export_policy"])
        self.assertEqual(ev.evaluate(multirow_payload())["singleton_selections_affected_by_export_policy"], [])
        self.assertAlmostEqual(result["figure2i_serum_contrasts"]["source_shaped_arrays"]["delta_good"][0], .01425)

    def test_missing_samples_omitted_per_sample_but_integration_gaps_not_filled(self):
        rows = [trace(0, 0, 2), trace(0, 0, 4)]
        rows[0][102] = None
        self.assertGreater(ev.auc_of_mean(rows, [0, 1])["auc"], 1.425)
        rows[1][102] = None
        self.assertIsNone(ev.auc_of_mean(rows, [0, 1])["auc"])

    def test_missing_block_preserved_and_complete_cohort_mean_withheld(self):
        p = payload()
        for b in p["figure2"]["G127"]["behavior"]:
            if b["stage"] == "Diestrus":
                b["block"] = 2
        result = ev.evaluate(p)["figure2h_stage_contrasts"]
        self.assertEqual(result["n_declared_rats"], 1)
        self.assertEqual(result["n_computable_rats"], 0)
        self.assertIsNone(result["mean_rat_effect_complete_cohort_only"])

    def test_all_serum_sessions_ledger_and_source_low_snr_exclusion(self):
        p = payload()
        p["figure2_serum_ratlist"].append("G138")
        extra = population()
        for b in extra["behavior"]:
            b["unique_day"] = "20240627" if b["stage"] == "Proestrus" else "20240628"
        p["figure2_serum"]["G138"] = extra
        p["serum_table"].extend([
            {"rat": "G138", "session_date": "20240627", "estradiol_conc": 99},
            {"rat": "unknown-rat", "session_date": "20240101", "estradiol_conc": 3}])
        result = ev.evaluate(p)
        ledger = result["figure2i_serum_contrasts"]["session_ledger"]
        self.assertEqual([r["status"] for r in ledger[-2:]], ["source_excluded_low_snr", "no_serum_sample"])
        self.assertEqual(result["figure2i_serum_contrasts"]["unmatched_serum_rows"][0]["rat"], "unknown-rat")
        self.assertIn("G138", [r["rat"] for r in result["cross_archive_audit"]["rat_session_map"]])

    def test_source_filters_auc_missing_without_hiding_session(self):
        p = payload()
        for b in p["figure2_serum"]["G127"]["behavior"]:
            if b["block"] == 3 and b["stage"] == "Proestrus":
                b["prev_trial_type"] = 2
        out = ev.evaluate(p)["figure2i_serum_contrasts"]
        self.assertEqual(out["session_ledger"][0]["status"], "source_filtered_missing_auc")
        self.assertEqual(len(out["source_shaped_arrays"]["delta_good"]), 1)

    def test_cohort_does_not_intersect_populations_or_claim_verification(self):
        out = ev.evaluate(payload())
        audit = out["cross_archive_audit"]
        self.assertEqual(len(audit["rat_session_map"]), 9)
        self.assertEqual(len(audit["figure3_missing_session_inventory_rats"]), 8)
        self.assertFalse(audit["native_join_verified"])
        self.assertFalse(out["research_qualified"])


class AdversarialControls(unittest.TestCase):
    def reject(self, change):
        p = payload()
        change(p)
        with self.assertRaises(ev.ContractError):
            ev.evaluate(p)

    def test_missing_roster_member(self):
        self.reject(lambda p: p["figure2_ratlist"].append("G138"))

    def test_duplicate_trial_identity(self):
        self.reject(lambda p: p["figure2"]["G127"]["behavior"][1].update(trial_id="0"))

    def test_ragged_or_nonfinite_data(self):
        self.reject(lambda p: p["figure2"]["G127"]["cpin"][0].append(1))
        self.reject(lambda p: p["figure2"]["G127"]["cpin"][0].__setitem__(0, float("inf")))

    def test_duplicate_serum_join(self):
        self.reject(lambda p: p["serum_table"].append(copy.deepcopy(p["serum_table"][0])))

    def test_ambiguous_stage_same_session(self):
        self.reject(lambda p: p["figure2_serum"]["G127"]["behavior"][0].update(stage="Estrus"))

    def test_undefined_normalization(self):
        self.reject(lambda p: p["figure2_serum"]["G127"]["behavior"][0].update(prev_trial_type=2))

    def test_figure3_population_and_bestfits_not_replaceable(self):
        self.reject(lambda p: p["figure3_manifest"]["ratlist"].pop())
        self.reject(lambda p: p["figure3_manifest"].update(best_fits_supplied=False))

    def test_native_width_and_g127_anchor(self):
        self.reject(lambda p: p["figure2_serum"].update(G138=population()))
        self.reject(lambda p: p["figure2_serum"]["G127"]["behavior"][0].update(unique_day="2024-01-01"))

    def test_cli_roundtrip_and_nonfinite_json_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path, out = Path(temp) / "input.json", Path(temp) / "output.json"
            path.write_text(json.dumps(payload()))
            run = subprocess.run([sys.executable, str(PACKAGE / "evaluator.py"), str(path), "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(out.read_text())["status"], "construction_component_only")
            path.write_text('{"schema_version":NaN}')
            run = subprocess.run([sys.executable, str(PACKAGE / "evaluator.py"), str(path), "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("invalid JSON constant", run.stderr)
            path.write_text('{"schema_version":1,"schema_version":1}')
            run = subprocess.run([sys.executable, str(PACKAGE / "evaluator.py"), str(path), "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("duplicate JSON object key", run.stderr)


if __name__ == "__main__":
    unittest.main()
