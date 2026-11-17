"""Generated engineering controls; no observations from the study."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location("evaluator", Path(__file__).parents[1] / "evaluator.py")
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)


def fixture():
    reference = {"schema_version": 1, "task_id": E.TASK_ID, "source_revision": E.REVISION,
                 "artifact_kind": "generated_engineering_control", "joint_names": E.JOINT_NAMES,
                 "time_ms": E.TIME_MS, "sessions": []}
    submission = {"schema_version": 1, "task_id": E.TASK_ID, "predictions": []}
    for (mouse, session), region in E.SESSIONS.items():
        record = {"mouse": mouse, "session": session, "region": region,
                  "neural_trials": [], "kinematic_trials": [], "folds": []}
        arrays = {}
        for trial in range(1, 21):
            angles = [[i * 0.01 + trial * 0.2 + j for j in range(24)] for i in range(51)]
            arrays[trial] = angles
            record["neural_trials"].append({"trial_number": trial, "locked": True})
            record["kinematic_trials"].append({"trial_number": trial, "locked": True,
                "LR": "L" if trial % 2 else "R", "joint_angles": angles,
                "eligibility": {"success": 1, "grabTimeC": 500, "liftRT": 200, "goodDLC": 1,
                    "wrongZoneFirst": 0, "movementTime": 200, "timeToContact": 600, "has_radical": 1}})
        # Explicit balanced trial folds; not a claim to match MATLAB rng(240926).
        for repeat in range(5):
            for fold in range(10):
                test = [t for t in arrays if (t - 1 + repeat) % 10 == fold]
                train = [t for t in arrays if t not in test]
                record["folds"].append({"repeat": repeat, "fold": fold, "train_trials": train, "test_trials": test})
                for trial in test:
                    submission["predictions"].append({"mouse": mouse, "session": session,
                        "repeat": repeat, "fold": fold, "trial_number": trial, "joint_angles": arrays[trial]})
        reference["sessions"].append(record)
    return reference, submission


class ScientificControls(unittest.TestCase):
    def test_source_ve_differs_from_r2_under_constant_bias(self):
        actual = np.array([[0], [1], [2]], dtype=float)
        score = E.score_arrays(actual, actual + 10)
        self.assertAlmostEqual(score["source_ve"][0], 1)
        self.assertAlmostEqual(score["r2_diagnostic"][0], -149)
        self.assertEqual(score["mean_error"], [-10])

    def test_source_ve_analytic_nonconstant_residual(self):
        score = E.score_arrays([[0], [2], [4]], [[0], [1], [2]])
        self.assertAlmostEqual(score["source_ve"][0], .75)
        self.assertAlmostEqual(score["r2_diagnostic"][0], .375)

    def test_complete_population_phase_contrast_and_mouse_unit(self):
        ref, sub = fixture()
        result = E.evaluate(ref, sub)
        # Two held-out trials differ by 2; var(time)=0.0216666667.
        expected = 1 / (1 + 26 / 1200)
        self.assertEqual(len(result["sessions"]), 10)
        self.assertAlmostEqual(result["M1_phase_advantage"]["mean"], expected)
        self.assertAlmostEqual(result["M1_phase_advantage"]["two_sided_exact_signflip_p"], 2 / 32)
        self.assertAlmostEqual(result["paired_M1_minus_S1_phase_advantage"]["mean"], 0)
        self.assertEqual(result["paired_M1_minus_S1_phase_advantage"]["two_sided_exact_signflip_p"], 1)
        self.assertFalse(result["full_contract_complete"])

    def test_train_only_template_is_unchanged_by_test_values(self):
        eligible = {1: {"LR": "L", "angles": np.ones((51, 24))},
                    2: {"LR": "R", "angles": np.full((51, 24), 2)},
                    3: {"LR": "L", "angles": np.full((51, 24), 999)}}
        original = E.phase_template(eligible, [1, 2])
        eligible[3]["angles"][:] = -999
        after = E.phase_template(eligible, [1, 2])
        np.testing.assert_array_equal(original["L"], after["L"])

    def test_exact_animal_reference(self):
        result = E.animal_summary([1, 1, 1, 1, 1])
        self.assertEqual(result["two_sided_exact_signflip_p"], .0625)
        self.assertEqual(result["bootstrap_percentile_95"], [1, 1])
        self.assertEqual(result["bootstrap_assignments"], 3125)
        self.assertEqual(E.animal_summary([0] * 5)["two_sided_exact_signflip_p"], 1)
        self.assertEqual(E.animal_summary([1e-14] * 5)["two_sided_exact_signflip_p"], .0625)

    def test_opto_source_filter_cue_clock_edges_and_denominator(self):
        records = []
        for mouse in ("cfaVG1", "cfaVG4"):
            for trial, (group, grab, lift) in enumerate([(0, 1000, 500), (1, 9000, 8000),
                                                       (1, 10000, 8000), (1, 100, 200)], 1):
                records.append({"mouse": mouse, "session": "explicit-session", "trial_number": trial,
                                "success": 1, "optoProblem": 0, "optoTrial": group,
                                "grabTimeC": grab, "liftTimeC": lift, "wrongGrabFirst": 0})
        result = E.optogenetic_timing(records)
        self.assertEqual(len(result["source_histogram_edges_seconds"]), 30)
        self.assertEqual(len(result["histograms"]["opto"]["probability"]), 29)
        self.assertEqual(sum(result["histograms"]["opto"]["probability"]), .5)
        self.assertEqual(result["histograms"]["opto"]["counts"][-1], 2)
        self.assertEqual(result["prospective_equal_mouse_mean_delay_seconds"], 8.5)
        self.assertEqual(len(result["excluded_trial_keys"]), 2)


class RejectionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference, cls.submission = fixture()

    def test_population_not_subset(self):
        ref = {**self.reference, "sessions": self.reference["sessions"][:-1]}
        with self.assertRaisesRegex(E.ContractError, "all ten"):
            E.evaluate(ref, self.submission)

    def test_prediction_population_exact(self):
        sub = {**self.submission, "predictions": self.submission["predictions"][:-1]}
        with self.assertRaisesRegex(E.ContractError, "missing heldout"):
            E.evaluate(self.reference, sub)

    def test_duplicate_prediction(self):
        sub = {**self.submission, "predictions": self.submission["predictions"] + self.submission["predictions"][:1]}
        with self.assertRaisesRegex(E.ContractError, "duplicate identity"):
            E.evaluate(self.reference, sub)

    def test_source_region_date_binding(self):
        ref = copy.deepcopy(self.reference)
        ref["sessions"][-1]["region"] = "M1"
        with self.assertRaisesRegex(E.ContractError, "region assignment"):
            E.evaluate(ref, self.submission)

    def test_whole_trial_leakage(self):
        ref = copy.deepcopy(self.reference)
        f = ref["sessions"][0]["folds"][0]
        f["train_trials"].append(f["test_trials"][0])
        with self.assertRaisesRegex(E.ContractError, "leakage"):
            E.evaluate(ref, self.submission)

    def test_unbalanced_folds_rejected(self):
        s = copy.deepcopy(self.reference["sessions"][0])
        for f in s["folds"]:
            test = [f["fold"] + 1] if f["fold"] < 9 else list(range(10, 21))
            f["test_trials"] = test
            f["train_trials"] = [t for t in range(1, 21) if t not in test]
        eligible, _ = E.join_trials(s["neural_trials"], s["kinematic_trials"])
        with self.assertRaisesRegex(E.ContractError, "balanced"):
            E.validate_folds(s["folds"], eligible)

    def test_metadata_join_does_not_trust_position(self):
        s = self.reference["sessions"][0]
        actual, _ = E.join_trials(s["neural_trials"][::-1], s["kinematic_trials"])
        self.assertEqual(len(actual), 20)
        with self.assertRaisesRegex(E.ContractError, "identity mismatch"):
            E.join_trials(s["neural_trials"][:-1], s["kinematic_trials"])

    def test_eligibility_includes_radical_even_for_sdeconv(self):
        s = copy.deepcopy(self.reference["sessions"][0])
        s["kinematic_trials"][0]["eligibility"]["has_radical"] = 0
        eligible, excluded = E.join_trials(s["neural_trials"], s["kinematic_trials"])
        self.assertNotIn(1, eligible)
        self.assertEqual(excluded, [{"trial_number": 1, "reasons": ["has_radical"]}])

    def test_undefined_metric_and_nonfinite_rejected(self):
        with self.assertRaises(E.ContractError):
            E.score_arrays([[1], [1]], [[1], [1]])
        with self.assertRaises(E.ContractError):
            E.score_arrays([[1], [2]], [[float("nan")], [2]])

    def test_strict_json_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "reference.json"
            for text in ('{"task_id":1,"task_id":2}', '{"x":NaN}'):
                p.write_text(text)
                with self.assertRaises(E.ContractError):
                    E.read_json(p)


if __name__ == "__main__":
    unittest.main()
