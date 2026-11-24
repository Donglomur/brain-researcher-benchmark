"""Generated controls for the actual H/I reconstruction-to-statistics path."""
import json
import math
import unittest
from collections import Counter

import numpy as np

from context_response import CONDITIONS, RESPONSE_NAMES
from source_statistics import reconstruct_statistics, SOURCE_PAIRS
from test_context_response import fixture


def independent_asymptotic_u(first, second):
    # Direct pair counting and the normal approximation with tie correction.
    # This does not call SciPy or copy its rank-sum implementation.
    n, m = len(first), len(second)
    u = sum((a > b) + 0.5 * (a == b) for a in first for b in second)
    counts = Counter(first + second)
    total = n + m
    variance = n * m / 12 * ((total + 1) -
                  sum(t ** 3 - t for t in counts.values()) / (total * (total - 1)))
    z = (max(u, n * m - u) - n * m / 2 - 0.5) / math.sqrt(variance)
    return u, min(1.0, math.erfc(z / math.sqrt(2)))


class SourceStatisticsTests(unittest.TestCase):
    def test_complete_source_pairs_and_independent_tied_rank_oracle(self):
        result = reconstruct_statistics(*fixture())
        expected = {
            "matched": [5.] * 9 + [7.] * 13 + [9.] * 10 + [11.] * 108,
            "unmatched": [1.] * 9 + [2.] * 13 + [3.] * 10 + [7.] * 108,
            "opto_only": [float(x) for n in (9, 13, 10) for x in range(2*n-1, 0, -2)] + [5.] * 108,
        }
        self.assertEqual(len(result["response_reconstruction"]["rows"]), 140)
        self.assertEqual([(t["first_condition"], t["second_condition"])
                          for t in result["source_tests"]], list(SOURCE_PAIRS))
        for test, (first, second) in zip(result["source_tests"], SOURCE_PAIRS):
            u, p = independent_asymptotic_u(expected[first], expected[second])
            self.assertEqual(test["source_row_counts"], [140, 140])
            self.assertEqual(test["statistic"], u)
            self.assertTrue(math.isclose(test["pvalue"], p, rel_tol=1e-12, abs_tol=1e-300))
            self.assertEqual(test["status"], "finite")

    def test_nonfinite_invalidates_only_affected_pairs_without_row_deletion(self):
        original, revision = fixture()
        revision["matched"][107, 124] = np.nan
        result = reconstruct_statistics(original, revision)
        self.assertEqual(len(result["response_reconstruction"]["rows"]), 140)
        for test in result["source_tests"][:2]:
            self.assertEqual(test["source_row_counts"], [140, 140])
            self.assertEqual(test["undefined_response_counts"], [1, 0])
            self.assertEqual(test["status"], "undefined_source_response")
            self.assertIsNone(test["statistic"])
            self.assertIsNone(test["pvalue"])
        self.assertEqual(result["source_tests"][2]["status"], "finite")
        json.dumps(result, allow_nan=False)

    def test_identical_complete_conditions_have_midpoint_u_and_unit_pvalue(self):
        original, revision = fixture()
        for experiment in original.values():
            for key in CONDITIONS:
                experiment["conditions"][key][:] = 0.
        for key in RESPONSE_NAMES:
            revision[key][:] = 0.
        result = reconstruct_statistics(original, revision)
        for test in result["source_tests"]:
            self.assertEqual(test["statistic"], 140 * 140 / 2)
            self.assertEqual(test["pvalue"], 1.)

    def test_incomplete_source_panel_is_rejected_by_real_reconstruction(self):
        original, revision = fixture()
        revision["matched"] = revision["matched"][:107]
        with self.assertRaises(ValueError):
            reconstruct_statistics(original, revision)
        original, revision = fixture()
        del original["expt3"]
        with self.assertRaises(ValueError):
            reconstruct_statistics(original, revision)

    def test_runtime_and_scientific_limits_remain_explicit(self):
        result = reconstruct_statistics(*fixture())
        self.assertTrue(result["software"]["scipy_version"])
        self.assertEqual(result["software"]["explicit_options"]["method"], "auto")
        self.assertEqual(result["software"]["explicit_options"]["alternative"], "two-sided")
        for flag in ("biological_independent_units_verified", "complete_primary_reproduction_established",
                     "paper_improvement_established"):
            self.assertIs(result[flag], False)
        self.assertIs(result["software"]["exact_historical_pvalue_parity_established"], False)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
