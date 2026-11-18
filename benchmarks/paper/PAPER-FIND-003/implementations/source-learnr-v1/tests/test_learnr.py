"""Generated mathematical and source-selection controls; no authentic data."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "learnr.py"
SPEC = importlib.util.spec_from_file_location("ripple_learnr", PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def bank(n=10):
    return [{"channel": "contact_s1", "subject": "s1", "phase": phase,
             "ACC": "correct", "trial": i + 1, "ripple": i % 3}
            for phase in M.PHASES for i in range(n)]


class SourceLearnRTests(unittest.TestCase):
    def test_no_ties_known_spearman_coefficient(self):
        # One adjacent swap has sum(d_i^2)=2 in Spearman's closed form.
        y = list(range(1, 11)); y[-2:] = reversed(y[-2:])
        result = M.learn_r_group(list(range(1, 11)), y)
        expected = 1 - 12 / 990
        self.assertAlmostEqual(result["spearman_r"], expected, places=14)
        self.assertAlmostEqual(result["fisher_z"], math.atanh(expected), places=13)

    def test_average_ranks_for_tied_rates(self):
        result = M.learn_r_group(list(range(1, 11)), [0] * 5 + [1] * 5)
        self.assertAlmostEqual(result["spearman_r"], 5 / math.sqrt(33), places=14)

    def test_positive_and_negative_perfect_rank_states_are_json_safe(self):
        for y, state in [(list(range(10)), "positive_infinite_fisher"),
                         (list(reversed(range(10))), "negative_infinite_fisher")]:
            result = M.learn_r_group(list(range(10)), y)
            self.assertEqual(result["state"], state)
            self.assertIsNone(result["fisher_z"])
            json.dumps(result, allow_nan=False)

    def test_constant_vector_is_not_zero_correlation(self):
        result = M.learn_r_group(list(range(10)), [1] * 10)
        self.assertEqual(result["state"], "source_constant_nan")
        self.assertIsNone(result["spearman_r"])

    def test_minimum_observations_and_exact_positive_fraction_boundary(self):
        self.assertEqual(M.learn_r_group(list(range(9)), [1] * 9)["eligibility"], "ineligible")
        eligible = M.learn_r_group(list(range(10)), [0] * 9 + [1])
        self.assertEqual(eligible["eligibility"], "eligible")
        self.assertEqual(eligible["state"], "finite")
        self.assertEqual(M.learn_r_group(list(range(11)), [0] * 10 + [1])["eligibility"], "ineligible")

    def test_missing_pairs_are_not_silently_deleted(self):
        result = M.learn_r_group(list(range(10)), [None] + [1] * 9)
        self.assertEqual(result["n_observations"], 10)
        self.assertEqual(result["n_positive_rates"], 9)
        self.assertEqual(result["state"], "source_missing_nan")
        self.assertEqual(result["n_missing_pairs"], 1)

    def test_eligibility_gate_precedes_missing_correlation(self):
        result = M.learn_r_group([None] * 9, [None] * 9)
        self.assertEqual(result["state"], "source_eligibility_nan")

    def test_phase_filter_precedes_correct_selection_and_preserves_full_partition(self):
        rows = bank(100)
        for offset in (0, 100, 200):
            for i in range(100): rows[offset + i]["ripple"] = 1
            rows[offset + 99]["ripple"] = 100
            rows[offset + 99]["ACC"] = "wrong"
            rows[offset + 98]["ACC"] = "wrong"
        result = M.analyze_rows(rows)
        self.assertEqual(result["source99_excluded_raw_row_ids"], [100, 200, 300])
        self.assertEqual(result["retained_wrong_raw_row_ids"], [99, 199, 299])
        covered = result["source99_excluded_raw_row_ids"] + result["retained_wrong_raw_row_ids"]
        for record in result["channel_records"]:
            self.assertEqual(record["n_observations"], 98)
            covered += record["raw_row_ids"]
        self.assertEqual(sorted(covered), list(range(1, 301)))

    def test_empty_positive_set_and_threshold_ties_are_retained(self):
        rows = bank()
        for row in rows: row["ripple"] = 0 if row["phase"] == "feedback" else 2
        result = M.analyze_rows(rows)
        self.assertIsNone(result["phase_positive_p99"]["feedback"])
        self.assertEqual(result["source99_excluded_raw_row_ids"], [])

    def test_channel_name_collision_cannot_pool_patients(self):
        rows = bank()
        rows[4]["subject"] = "other_patient"
        with self.assertRaisesRegex(ValueError, "merge distinct subjects"):
            M.analyze_rows(rows)

    def test_duplicate_and_partial_phase_support_are_rejected(self):
        rows = bank()
        with self.assertRaisesRegex(ValueError, "duplicate source cell"):
            M.analyze_rows(rows + [dict(rows[0])])
        with self.assertRaisesRegex(ValueError, "all three original phases"):
            M.analyze_rows([r for r in rows if r["phase"] != "interval"])

    def test_no_input_mutation_and_row_order_is_bound(self):
        rows = bank(); before = json.dumps(rows)
        original = M.analyze_rows(rows)
        reversed_bank = M.analyze_rows(list(reversed(rows)))
        self.assertEqual(json.dumps(rows), before)
        self.assertNotEqual(original["input_representation_sha256"], reversed_bank["input_representation_sha256"])
        a = {(r["channel"], r["phase"]): r["spearman_r"] for r in original["channel_records"]}
        b = {(r["channel"], r["phase"]): r["spearman_r"] for r in reversed_bank["channel_records"]}
        self.assertEqual(a, b)

    def test_invalid_numeric_values_and_unknown_accuracy_are_rejected(self):
        for value in (True, float("nan"), float("inf"), "1"):
            with self.assertRaises(ValueError): M.learn_r_group(list(range(10)), [value] * 10)
        rows = bank(); rows[0]["ACC"] = "unknown"
        with self.assertRaises(ValueError): M.analyze_rows(rows)

    def test_all_wrong_rows_are_accounted_without_invented_channel_estimates(self):
        rows = bank()
        for row in rows: row["ACC"] = "wrong"
        result = M.analyze_rows(rows)
        self.assertEqual(result["channel_records"], [])
        self.assertEqual(result["retained_wrong_raw_row_ids"], list(range(1, 31)))
        self.assertEqual(result["downstream_status"], "not_computed")
        self.assertEqual(result["scientific_qualification"], "unestablished")


if __name__ == "__main__":
    unittest.main()
