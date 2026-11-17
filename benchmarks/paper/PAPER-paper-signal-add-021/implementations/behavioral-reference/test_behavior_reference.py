"""Invented mathematical/source-behavior controls, not neuroscience observations."""
import copy
import io
import csv
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import behavior_reference as b
import score_behavior as s


def fixture():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["subjID", "day", "TMS_condition", *b.METRICS])
    conditions = [(1, "No TMS"), (2, "TMS intoVF"), (3, "TMS outVF"),
                  (4, "TMS intoVF"), (4, "TMS outVF"),
                  (5, "TMS intoVF"), (5, "TMS outVF")]
    for index, person in enumerate(b.ROSTER):
        for j, (day, label) in enumerate(conditions):
            # Signed toy quantities deliberately distinguish abs figure means.
            value = (index + 1) * (j + 1)
            writer.writerow([person, day, label, -value, value / 100, value * 2])
    return stream.getvalue().encode()


class BehaviorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.intake = b.parse_release(fixture(), authenticate=False)
        cls.reference = b.build_reference(cls.rows, bootstrap_draws=32)

    def test_manual_paired_arithmetic_and_sign_symmetry(self):
        summary = b.paired_summary([1.0, 2.0, 3.0])
        self.assertEqual(summary["mean"], 2)
        self.assertEqual(summary["sample_sd"], 1)
        self.assertAlmostEqual(summary["t"], 2 * math.sqrt(3))
        self.assertEqual(b.exact_sign_flip([1.0, 2.0, 3.0])["p_two_sided"], 0.25)
        self.assertEqual(b.exact_sign_flip([-1.0, -2.0, -3.0])["p_two_sided"], 0.25)
        self.assertEqual(b.exact_sign_flip([1e-14, 2e-14, 3e-14])["p_two_sided"], 0.25)
        self.assertEqual(b.exact_sign_flip([0.0, 0.0])["p_two_sided"], 1)
        zero = b.paired_summary([0.0] * 15)
        self.assertEqual(zero["degenerate"], "all_zero")
        self.assertIsNone(zero["t"])
        self.assertIsNone(zero["cohens_dz"])
        constant = b.paired_summary([1.0] * 15)
        self.assertEqual(constant["degenerate"], "constant_nonzero")
        self.assertIsNone(constant["t"])
        self.assertIsNone(constant["cohens_dz"])

    def test_full_census_and_literal_signed_distinction(self):
        self.assertEqual(self.intake["rows"], 105)
        for metric in b.METRICS:
            self.assertEqual(len(self.reference["metrics"][metric]["participant_cells"]), 105)
            self.assertEqual(len(self.reference["metrics"][metric]["contrasts"]), 6)
        first = self.reference["metrics"]["ierr"]["participant_cells"][0]
        self.assertEqual(first["figure_mean_abs"], 1)
        self.assertEqual(first["source_helper_mean_signed"], -1)
        effect = self.reference["metrics"]["ierr"]["contrasts"]["exp1_in_minus_no"]
        self.assertEqual(effect["figure_paired"]["mean"], 8)
        self.assertEqual(effect["source_helper_signed_paired"]["mean"], -8)
        self.assertEqual(effect["corrected_participant_sign_flip"]["enumerated"], 32768)
        self.assertEqual(len(effect["leave_one_person_out"]), 15)
        self.assertTrue(all(x["summary"]["n"] == 14 for x in effect["leave_one_person_out"]))

    def test_people_not_trials_define_uncertainty(self):
        # Repeating one person's rows changes trial count but not equal-person means.
        rows = self.rows + [copy.deepcopy(r) for r in self.rows if r["person"] == b.ROSTER[0]] * 9
        other = b.build_reference(rows, bootstrap_draws=32)
        for metric in b.METRICS:
            self.assertEqual(other["metrics"][metric]["contrasts"], self.reference["metrics"][metric]["contrasts"])
        self.assertEqual(other["metrics"]["ierr"]["participant_cells"][0]["valid_trials"], 10)

    def test_missing_person_condition_and_bad_release_refuse(self):
        data = fixture().decode().splitlines()
        omitted = "\n".join([data[0]] + [line for line in data[1:] if not line.startswith("1,")]).encode()
        with self.assertRaises(b.InvalidInput): b.parse_release(omitted, authenticate=False)
        rows = [r for r in self.rows if not (r["person"] == 1 and r["condition"] == "No TMS")]
        with self.assertRaises(b.InvalidInput): b.build_reference(rows)
        with self.assertRaises(b.InvalidInput): b.parse_release(fixture())
        with self.assertRaises(b.InvalidInput): b.condition(1, "Unknown")
        with self.assertRaises(b.InvalidInput): b.number("inf", "ierr")
        with self.assertRaises(b.InvalidInput): b.parse_release(b"subjID,day\n1,1\n", authenticate=False)

    def test_grouped_bootstrap_and_multiplicity(self):
        interval = b.bootstrap_interval([2.0] * 15, seed=42, draws=30)
        self.assertEqual((interval["lower"], interval["upper"]), (2, 2))
        self.assertEqual(b.holm({"a": 0.01, "b": 0.04, "c": 0.03}), {"a": 0.03, "c": 0.06, "b": 0.06})

    def test_global_trial_shuffle_can_destroy_pairs(self):
        class ForcedGlobalShuffle:
            def __init__(self, seed): pass
            def shuffle(self, labels): labels[:] = sorted(labels)
        with patch.object(b.random, "Random", ForcedGlobalShuffle):
            with self.assertRaisesRegex(b.InvalidInput, "removes a participant-condition cell"):
                b.literal_global_trial_shuffle(self.rows, "ierr", "mid inPF", "No TMS", draws=1, seed=0)

    def test_grader_requires_complete_correct_outputs(self):
        candidate = copy.deepcopy(self.reference)
        self.assertTrue(s.score(self.reference, candidate)["accepted"])
        self.assertFalse(s.score(self.reference, candidate)["whole_task_qualified"])
        candidate["metrics"]["ierr"]["participant_cells"][0]["figure_mean_abs"] += 1
        scored = s.score(self.reference, candidate)
        self.assertFalse(scored["components"]["deterministic_figure_reproduction"]["passed"])
        self.assertTrue(scored["components"]["deterministic_helper_formula_reproduction"]["passed"])
        candidate = copy.deepcopy(self.reference); candidate["roster"][0] = True
        self.assertFalse(s.score(self.reference, candidate)["accepted"])
        candidate = copy.deepcopy(self.reference); candidate["metrics"]["ierr"]["participant_cells"].pop()
        self.assertFalse(s.score(self.reference, candidate)["accepted"])
        candidate = copy.deepcopy(self.reference)
        candidate["metrics"]["ierr"]["contrasts"]["exp1_in_minus_no"]["corrected_sign_flip_holm_six_contrasts"] = float("nan")
        self.assertFalse(s.score(self.reference, candidate)["accepted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
