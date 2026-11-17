"""Generated NPZ/real NumPy controls; no authentic recordings or target access."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paired", HERE / "compare.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
CANONICAL = HERE.parent / "registered-runtime"


class Comparison(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.ids = {case: [f"{case}-generated-{i:03d}" for i in range(200)] for case in c.CASES}
        self.names = [item for case in c.CASES for item in self.ids[case]]
        body = (json.dumps(self.names, separators=(",", ":")) + "\n").encode()
        self.roster_patch = patch.object(c, "ROSTER_SHA256", hashlib.sha256(body).hexdigest())
        self.roster_patch.start()
        self.addCleanup(self.roster_patch.stop)
        self.y = {case: np.array([1] * 40 + [0] * 160, dtype=np.int64) for case in c.CASES}
        # Person one: A perfect/B reversed. Person two: A all-positive/B
        # all-negative. BA difference is zero there despite unequal raw accuracy.
        self.a = np.array([.9] * 40 + [.1] * 160 + [.9] * 200)
        self.b = np.array([.1] * 40 + [.9] * 160 + [.1] * 200)
        self.ap, self.bp = self.root / "a.npz", self.root / "b.npz"
        self.write(self.ap, self.a)
        self.write(self.bp, self.b)
        prior_loss = -.2 * math.log(.2) - .8 * math.log(.8)
        rows = [{"person_id": case, "n": 200, "n_target": 40, "n_non_target": 160,
                 "balanced_accuracy": .5, "log_loss": prior_loss} for case in c.CASES]
        self.refs = {"arms": {name: {"per_person": copy.deepcopy(rows),
                                     "participant_macro_balanced_accuracy": .5,
                                     "participant_macro_log_loss": prior_loss}
                               for name in ("prior", "eeg", "eog_site", "gross_amplitude", "behavioral_history", "eeg_history")}}
        self.loads = []

    def write(self, path, probabilities, ids=None):
        np.savez(path, trial_ids=np.asarray(self.names if ids is None else ids),
                 target_probability=probabilities)

    def loader(self, case):
        self.loads.append(case)
        return self.y[case]

    def args(self):
        return dict(a_pin=c.pin(self.ap.read_bytes()), b_pin=c.pin(self.bp.read_bytes()),
                    a_condition="legacy_waveform_no_tools", b_condition="matched_waveform_programme",
                    a_receipt_pin=c.pin(b"generated-a-receipt"), b_receipt_pin=c.pin(b"generated-b-receipt"))

    def run_comparison(self, **changes):
        args = self.args()
        args.update(changes)
        return c.compare_submissions(self.ap, self.bp, self.ids, self.loader, self.refs, CANONICAL, **args)

    def test_hand_calculated_class_conditioned_pairing_and_macro(self):
        result = self.run_comparison()
        delta = result["a_minus_b"]
        self.assertEqual(delta["participant_macro_balanced_accuracy"], .5)
        self.assertEqual([r["balanced_accuracy"] for r in delta["per_person"]], [1., 0.])
        self.assertAlmostEqual(delta["participant_macro_log_loss"], -.2 * math.log(9), places=14)
        second = delta["per_person"][1]["class_specific_pairing"]
        self.assertEqual(second[0], {
            "class": "target", "n": 40, "both_correct": 0, "a_only_correct": 40,
            "b_only_correct": 0, "neither_correct": 0, "a_minus_b_recall": 1.})
        self.assertEqual(second[1]["b_only_correct"], 160)
        self.assertEqual(self.loads, list(c.CASES))
        self.assertEqual(result["private_loader_invocations"], 2)
        self.assertFalse(result["population_confidence_interval"])
        self.assertFalse(result["equal_information_proven"])
        serialized = json.dumps(result, allow_nan=False)
        self.assertNotIn("generated-000", serialized)

    def test_each_canonical_score_and_all_six_references_are_unchanged(self):
        result = self.run_comparison()
        validator, metrics = c.canonical(CANONICAL)
        for key, path in (("a", self.ap), ("b", self.bp)):
            expected = metrics.score_candidate(validator.validate(path, self.ids), lambda case: self.y[case], self.refs)
            self.assertEqual(result[key]["canonical_score"], expected)

    def test_identical_arms_have_zero_discordances_even_with_shared_errors(self):
        self.write(self.bp, self.a)
        delta = self.run_comparison()["a_minus_b"]
        self.assertEqual(delta["participant_macro_balanced_accuracy"], 0.)
        self.assertEqual(delta["participant_macro_log_loss"], 0.)
        for row in delta["per_person"]:
            for group in row["class_specific_pairing"]:
                self.assertEqual(group["a_only_correct"], 0)
                self.assertEqual(group["b_only_correct"], 0)
        self.assertEqual(delta["per_person"][1]["class_specific_pairing"][1]["neither_correct"], 160)

    def test_reordered_npz_rows_join_by_identity_for_both_arms(self):
        expected = self.run_comparison()["a_minus_b"]
        self.write(self.ap, self.a[::-1], self.names[::-1])
        order = np.roll(np.arange(400), 37)
        self.write(self.bp, self.b[order], [self.names[i] for i in order])
        self.assertEqual(self.run_comparison()["a_minus_b"], expected)

    def test_swap_reverses_signed_metrics_and_class_discordances(self):
        forward = self.run_comparison()["a_minus_b"]
        self.write(self.ap, self.b)
        self.write(self.bp, self.a)
        reverse = self.run_comparison()["a_minus_b"]
        self.assertEqual(reverse["participant_macro_balanced_accuracy"], -forward["participant_macro_balanced_accuracy"])
        self.assertAlmostEqual(reverse["participant_macro_log_loss"], -forward["participant_macro_log_loss"], places=15)
        for a, b in zip(forward["per_person"], reverse["per_person"]):
            for aa, bb in zip(a["class_specific_pairing"], b["class_specific_pairing"]):
                self.assertEqual(aa["a_only_correct"], bb["b_only_correct"])

    def test_threshold_endpoints_and_float32_are_preserved(self):
        self.write(self.ap, np.array([.5] * 400, dtype=np.float32))
        self.write(self.bp, np.array([0.] * 40 + [1.] * 160 + [0.] * 40 + [1.] * 160))
        result = self.run_comparison()
        self.assertEqual(result["a"]["canonical_score"]["candidate"]["participant_macro_balanced_accuracy"], .5)
        self.assertEqual(result["b"]["canonical_score"]["candidate"]["participant_macro_balanced_accuracy"], 0.)
        self.assertTrue(math.isfinite(result["a_minus_b"]["participant_macro_log_loss"]))
        with np.load(self.bp) as rows:
            self.assertEqual(rows["target_probability"].tolist(), [0.] * 40 + [1.] * 160 + [0.] * 40 + [1.] * 160)

    def test_missing_duplicate_nan_boolean_and_extra_field_b_prevent_any_private_load(self):
        for bad in ("missing", "duplicate", "nan", "boolean", "extra"):
            with self.subTest(bad=bad):
                if bad == "missing":
                    self.write(self.bp, self.b[:-1], self.names[:-1])
                elif bad == "duplicate":
                    self.write(self.bp, self.b, self.names[:-1] + self.names[:1])
                elif bad == "nan":
                    values = self.b.copy()
                    values[-1] = np.nan
                    self.write(self.bp, values)
                elif bad == "boolean":
                    self.write(self.bp, self.b.astype(bool))
                else:
                    np.savez(self.bp, trial_ids=self.names, target_probability=self.b, extra=np.zeros(1))
                with self.assertRaises(ValueError):
                    self.run_comparison()
                self.assertEqual(self.loads, [])

    def test_bad_reference_precedes_private_access(self):
        self.refs["arms"].pop("prior")
        with self.assertRaises(ValueError):
            self.run_comparison()
        self.assertEqual(self.loads, [])

    def test_bad_source_and_submission_pins_precede_private_access(self):
        args = self.args()
        args["b_pin"] = {"bytes": args["b_pin"]["bytes"], "sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            self.run_comparison(**args)
        copied = self.root / "canonical"
        copied.mkdir()
        for name in c.CANONICAL_PINS:
            shutil.copyfile(CANONICAL / name, copied / name)
        with (copied / "metrics.py").open("ab") as stream:
            stream.write(b"#tampered")
        with self.assertRaises(ValueError):
            c.compare_submissions(self.ap, self.bp, self.ids, self.loader, self.refs, copied, **self.args())
        self.assertEqual(self.loads, [])

    def test_full_roster_binding_rejects_renamed_case_before_private_access(self):
        self.ids[c.CASES[1]][-1] += "-other"
        with self.assertRaises(ValueError):
            self.run_comparison()
        self.assertEqual(self.loads, [])

    def test_private_float_labels_and_wrong_second_person_support_never_return_report(self):
        self.y[c.CASES[0]] = self.y[c.CASES[0]].astype(float)
        with self.assertRaises(ValueError):
            self.run_comparison()
        self.assertEqual(self.loads, [c.CASES[0]])
        self.y[c.CASES[0]] = self.y[c.CASES[0]].astype(int)
        self.y[c.CASES[1]][0] = 0
        self.loads.clear()
        with self.assertRaises(ValueError):
            self.run_comparison()
        self.assertEqual(self.loads, list(c.CASES))

    def test_different_label_budgets_remain_explicit_and_no_matching_claim(self):
        report = self.run_comparison(a_condition="zero_shot", b_condition="ordinary_feature_programme")
        self.assertEqual(report["a"]["training_label_budget"], 0)
        self.assertEqual(report["b"]["training_label_budget"], 1200)
        self.assertFalse(report["same_training_label_budget"])
        self.assertFalse(report["same_representation"])
        self.assertFalse(report["condition_budgets_pooled"])
        with self.assertRaises(ValueError):
            self.run_comparison(a_condition="zero_shot+four_demo")

    def test_original_path_replacement_after_capture_cannot_change_scored_bytes(self):
        expected = self.run_comparison()["a_minus_b"]
        args = self.args()
        original = c.canonical
        def replace_then_load(directory):
            self.write(self.ap, np.full(400, .5))
            self.write(self.bp, np.full(400, .5))
            return original(directory)
        with patch.object(c, "canonical", side_effect=replace_then_load):
            actual = c.compare_submissions(self.ap, self.bp, self.ids, self.loader, self.refs, CANONICAL, **args)
        self.assertEqual(actual["a_minus_b"], expected)
        self.assertNotEqual(actual["a"]["submission_pin"], c.pin(self.ap.read_bytes()))

    def test_special_files_and_symlinks_refused(self):
        link = self.root / "alias.npz"
        link.symlink_to(self.ap)
        with self.assertRaises(ValueError):
            c.captured(link, c.pin(self.ap.read_bytes()), 1048576)
        import os
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            c.captured(fifo, c.pin(b"x"), 1048576)


if __name__ == "__main__":
    unittest.main(verbosity=2)
