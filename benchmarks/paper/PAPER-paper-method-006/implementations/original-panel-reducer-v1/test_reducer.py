"""Generated software controls only; no authentic spikes, data, or targets."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("reducer", Path(__file__).with_name("reducer.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def fixture():
    profile = {"name": "R_source20", "score_encoding": "binary64",
               "implementation_sha256": "1" * 64,
               "event_and_unit_matching_policy_sha256": "2" * 64,
               "quality_definition_sha256": "3" * 64}
    manifest = {"schema": "kilosort4_original_recovery_inputs_v1", "scoring_profile": profile,
                "observation_condition": "paper+data", "cases": []}
    exports = {"schema": "kilosort4_paired_scoring_exports_v1", "arms": []}
    for case_id in r.CASES:
        hybrid = case_id in r.HYBRIDS
        n = 100 if hybrid else 600
        manifest["cases"].append({"case_id": case_id, "kind": "hybrid" if hybrid else "synthetic",
            "source_input_sha256": "4" * 64, "target_unit_ids": [f"u{i}" for i in range(n)],
            "background_unit_ids": [] if hybrid else [f"m{i}" for i in range(600)],
            "duration_seconds": 2700})
    for arm in ("reference", "candidate"):
        cases = []
        for case in manifest["cases"]:
            units, detected = [], []
            for i, unit_id in enumerate(case["target_unit_ids"]):
                # The first three distinguish equality, its next binary64 value,
                # and an ordinary non-recovery. No fixture is a study result.
                score = [0.8, math.nextafter(0.8, math.inf), 0.5][i % 3]
                if arm == "candidate" and i == 0:
                    score = 0.9
                units.append({"unit_id": unit_id, "role": "single-unit-target", "score": score,
                              "false_positive": 0.0, "false_negative": 1.0 - score,
                              "source_initialized_zero": False})
                detected.append({"unit_id": f"d{i}", "good": i % 2 == 0,
                                 "matched_target_ids": [unit_id] if score > 0.8 else []})
            cases.append({"case_id": case["case_id"], "source_input_sha256": case["source_input_sha256"],
                          "units": units, "detected_units": detected,
                          "complete_detected_unit_ids": [d["unit_id"] for d in detected]})
        exports["arms"].append({"arm": arm, "method_id": arm,
            "method_artifact_sha256": ("5" if arm == "reference" else "6") * 64,
            "scoring_profile_sha256": r.digest(profile), "cases": cases})
    exports["manifest_sha256"] = r.digest(manifest)
    return manifest, exports


class ReducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.exports = fixture()

    def inputs(self):
        return deepcopy(self.manifest), deepcopy(self.exports)

    def test_full_original_denominators_boundary_and_paired_delta(self):
        report = r.reduce_panel(self.manifest, self.exports)
        self.assertEqual(report["target_count_per_arm"], 3900)
        self.assertEqual(report["simulation_background_units_per_arm"], 3600)
        self.assertEqual(report["results"]["reference"]["hybrid_300_pooled"]["recovered_count"], 99)
        self.assertEqual(report["results"]["candidate"]["hybrid_300_pooled"]["recovered_count"], 102)
        for case_id, result in report["results"]["reference"]["cases"].items():
            expected = 33 if case_id in r.HYBRIDS else 200
            self.assertEqual(result["recovered_count"], expected)
            if case_id in r.HYBRIDS:
                self.assertIsNone(result["unmatched_good_detected_count"])
            else:
                self.assertEqual(result["good_detected_count"], 300)
                self.assertEqual(result["good_matched_detected_count"], 100)
                self.assertEqual(result["unmatched_good_detected_count"], 200)
        for row in report["paired_case_differences"]:
            self.assertEqual(row["candidate_minus_reference"]["recovered_count"], 1)
        self.assertIsNone(report["paper_improvement_decision"])
        self.assertIsNone(report["paper_reproduction_decision"])
        self.assertEqual(report["observation_condition"], "paper+data")
        for row in report["reproduction_diagnostics"]:
            self.assertEqual(row["score_difference_unit_ids"], ["u0"])
        self.assertNotIn("overall_score", report)

    def test_missing_case_cannot_be_pooled_away(self):
        m, e = self.inputs()
        e["arms"][0]["cases"].pop()
        with self.assertRaisesRegex(r.Invalid, "every original case"):
            r.reduce_panel(m, e)

    def test_same_size_unit_substitution_and_duplicate(self):
        for replacement in ("unknown", "u1"):
            m, e = self.inputs()
            e["arms"][0]["cases"][0]["units"][0]["unit_id"] = replacement
            with self.assertRaises(r.Invalid):
                r.reduce_panel(m, e)

    def test_source_and_profile_substitution(self):
        m, e = self.inputs()
        e["arms"][1]["cases"][0]["source_input_sha256"] = "7" * 64
        with self.assertRaisesRegex(r.Invalid, "source input substitution"):
            r.reduce_panel(m, e)
        m, e = self.inputs()
        e["arms"][1]["scoring_profile_sha256"] = "7" * 64
        with self.assertRaisesRegex(r.Invalid, "shared frozen scoring"):
            r.reduce_panel(m, e)

    def test_complete_mua_construction_roster(self):
        m, e = self.inputs()
        m["cases"][-1]["background_unit_ids"].pop()
        e["manifest_sha256"] = r.digest(m)
        with self.assertRaisesRegex(r.Invalid, "600 MUA"):
            r.reduce_panel(m, e)

    def test_no_nonfinite_or_boolean_scores(self):
        for value in (float("nan"), float("inf"), True):
            m, e = self.inputs()
            e["arms"][0]["cases"][0]["units"][0]["score"] = value
            with self.assertRaises(r.Invalid):
                r.reduce_panel(m, e)

    def test_negative_score_preserved(self):
        m, e = self.inputs()
        m["scoring_profile"]["name"] = "R_paper40"
        e["manifest_sha256"] = r.digest(m)
        for arm in e["arms"]:
            arm["scoring_profile_sha256"] = r.digest(m["scoring_profile"])
        unit = e["arms"][0]["cases"][0]["units"][0]
        unit.update(score=-1.0, false_positive=1.0, false_negative=1.0)
        report = r.reduce_panel(m, e)
        row = report["results"]["reference"]["cases"][r.HYBRIDS[0]]["ordered_unit_scores"][0]
        self.assertEqual(row["score"], -1.0)
        self.assertEqual(row["false_positive"], 1.0)

    def test_source20_cannot_emit_negative_or_concealed_floor(self):
        for score, fp, fn in ((-1.0, 1.0, 1.0), (0.0, 0.0, 0.0)):
            m, e = self.inputs()
            row = e["arms"][0]["cases"][0]["units"][0]
            row.update(score=score, false_positive=fp, false_negative=fn)
            with self.assertRaisesRegex(r.Invalid, "initialized-zero floor"):
                r.reduce_panel(m, e)

    def test_source20_positive_score_error_inconsistency_rejected(self):
        m, e = self.inputs()
        e["arms"][0]["cases"][0]["units"][1]["false_positive"] = 1.0
        with self.assertRaisesRegex(r.Invalid, "score/error arithmetic"):
            r.reduce_panel(m, e)

    def test_source20_empty_detected_failure_cannot_become_zero_recovery(self):
        m, e = self.inputs()
        case = e["arms"][0]["cases"][0]
        for unit in case["units"]:
            unit.update(score=0.0, false_positive=0.0, false_negative=0.0,
                        source_initialized_zero=True)
        case["detected_units"] = []
        case["complete_detected_unit_ids"] = []
        with self.assertRaisesRegex(r.Invalid, "fails on an empty detected-unit roster"):
            r.reduce_panel(m, e)

    def test_literal_source_zero_is_retained_but_not_recovery(self):
        m, e = self.inputs()
        unit = e["arms"][0]["cases"][0]["units"][0]
        unit.update(score=0.0, false_positive=0.0, false_negative=0.0, source_initialized_zero=True)
        report = r.reduce_panel(m, e)
        result = report["results"]["reference"]["cases"][r.HYBRIDS[0]]
        self.assertEqual(result["source_initialized_zero_count"], 1)
        self.assertEqual(result["recovered_count"], 33)

    def test_no_invented_bijection(self):
        m, e = self.inputs()
        case = e["arms"][0]["cases"][3]
        # u1 and u4 both recover. One detected unit may match both under
        # supplied source policy; count it once without introducing assignment.
        case["detected_units"][4]["matched_target_ids"] = ["u1", "u4"]
        case["detected_units"][1]["matched_target_ids"] = []
        result = r.reduce_panel(m, e)["results"]["reference"]["cases"]["no_drift"]
        self.assertEqual(result["recovered_count"], 200)
        self.assertEqual(result["matched_detected_count"], 199)
        self.assertEqual(result["matched_target_count"], 200)
        self.assertEqual(result["good_matched_detected_count"], 100)
        self.assertEqual(result["good_matched_target_count"], 101)

    def test_multiple_selected_best_units_for_one_target_rejected(self):
        m, e = self.inputs()
        case = e["arms"][0]["cases"][3]
        case["detected_units"][0]["matched_target_ids"] = ["u1"]
        with self.assertRaisesRegex(r.Invalid, "one best detected"):
            r.reduce_panel(m, e)

    def test_incomplete_detected_companion_is_not_zero_filled(self):
        m, e = self.inputs()
        e["arms"][0]["cases"][0]["detected_units"].pop()
        with self.assertRaisesRegex(r.Invalid, "complete detected"):
            r.reduce_panel(m, e)

    def test_match_to_threshold_equality_rejected(self):
        m, e = self.inputs()
        e["arms"][0]["cases"][0]["detected_units"][0]["matched_target_ids"] = ["u0"]
        with self.assertRaisesRegex(r.Invalid, "strict recovery threshold"):
            r.reduce_panel(m, e)

    def test_arbitrary_full_panel_method_ids_do_not_become_sota(self):
        m, e = self.inputs()
        e["arms"][0]["method_id"] = "operator-supplied-release-reference"
        report = r.reduce_panel(m, e)
        self.assertIsNone(report["paper_improvement_decision"])
        self.assertIn("source authenticity", report["qualification"])

    def test_observation_conditions_remain_explicit(self):
        m, e = self.inputs()
        m["observation_condition"] = "paper+data+author-code"
        with self.assertRaisesRegex(r.Invalid, "manifest hash join"):
            r.reduce_panel(m, e)
        e["manifest_sha256"] = r.digest(m)
        self.assertEqual(r.reduce_panel(m, e)["observation_condition"], "paper+data+author-code")
        m["observation_condition"] = "pooled-conditions"
        with self.assertRaisesRegex(r.Invalid, "participant observation"):
            r.reduce_panel(m, e)


if __name__ == "__main__":
    unittest.main(verbosity=2)
