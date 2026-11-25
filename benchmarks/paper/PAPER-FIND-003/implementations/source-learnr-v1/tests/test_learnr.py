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

    def test_unrepresentable_integer_rank_inputs_are_refused(self):
        # Binary64 would introduce ties into this strictly increasing sequence.
        large = [2**53 + i for i in range(10)]
        for trials, rates in ((large, list(range(1, 11))),
                              (list(range(1, 11)), large)):
            with self.subTest(trials=trials, rates=rates):
                with self.assertRaisesRegex(ValueError, "exactly representable"):
                    M.learn_r_group(trials, rates)

    def test_exact_large_integers_and_explicit_floats_keep_rank_semantics(self):
        large = [2**53 + 2*i for i in range(10)]
        expected = M.learn_r_group(list(range(10)), list(range(1, 11)))
        self.assertEqual(M.learn_r_group(large, list(range(1, 11))), expected)
        self.assertEqual(M.learn_r_group([float(v) for v in large],
                                        list(range(1, 11))), expected)
        self.assertEqual(expected["state"], "positive_infinite_fisher")

    def test_lossy_integer_is_rejected_before_row_bookkeeping(self):
        for field in ("trial", "ripple"):
            with self.subTest(field=field):
                rows = bank(); rows[0][field] = 2**53
                accepted = M.analyze_rows(rows)
                rows[0][field] = 2**53 + 1
                # This API refuses a different integer that would normalize to
                # the accepted binary64 value before grouping and ranking.
                with self.assertRaisesRegex(ValueError, "exactly representable"):
                    M.analyze_rows(rows)
                self.assertEqual(accepted["raw_row_count"], 30)

    def test_subnormal_equal_rates_retain_complete_phase_support(self):
        # All300 rows are valid and equal, so none can exceed a phase quantile.
        tiny = math.ulp(0.0)
        rows = bank(100)
        for row in rows:
            row["ripple"] = tiny
        result = M.analyze_rows(rows)
        self.assertEqual(result["phase_positive_p99"], dict.fromkeys(M.PHASES, tiny))
        self.assertEqual(result["source99_excluded_raw_row_ids"], [])
        self.assertEqual(len(result["channel_records"]), 3)
        self.assertEqual(sorted(i for record in result["channel_records"]
                                for i in record["raw_row_ids"]), list(range(1, 301)))
        for record in result["channel_records"]:
            self.assertEqual(record["n_observations"], 100)
            self.assertEqual(record["state"], "source_constant_nan")

    def test_subnormal_midpoint_retains_exact_type5_cutoff(self):
        from fractions import Fraction
        tiny = math.ulp(0.0)
        rows = bank(100)
        for start in (0, 100, 200):
            for row in rows[start:start + 100]:
                row["ripple"] = tiny
            rows[start + 99]["ripple"] = 2 * tiny
        expected = float((Fraction.from_float(tiny) +
                          Fraction.from_float(2 * tiny)) / 2)
        result = M.analyze_rows(rows)
        self.assertEqual(result["phase_positive_p99"], dict.fromkeys(M.PHASES, expected))
        self.assertEqual(result["source99_excluded_raw_row_ids"], [])
        self.assertEqual(sum(record["n_observations"]
                             for record in result["channel_records"]), 300)

    def test_ordinary_percentile_retains_existing_arithmetic(self):
        rows = bank(100)
        for start in (0, 100, 200):
            for i, row in enumerate(rows[start:start + 100]):
                row["ripple"] = 0.25 + i / 8
        # For100 values, the original type-5 index is99.5.
        expected = (0.25 + 98 / 8) * 0.5 + (0.25 + 99 / 8) * 0.5
        result = M.analyze_rows(rows)
        self.assertEqual(result["phase_positive_p99"], dict.fromkeys(M.PHASES, expected))
        self.assertEqual(result["source99_excluded_raw_row_ids"], [100, 200, 300])
        self.assertEqual(sum(record["n_observations"]
                             for record in result["channel_records"]), 297)

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
