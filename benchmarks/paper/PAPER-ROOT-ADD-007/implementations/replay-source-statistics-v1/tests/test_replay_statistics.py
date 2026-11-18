"""Analytic engineering controls; no authentic recordings or scientific runs."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_statistics import ContractError, score_event, score_stratum


def event(name="event-1", zeros=()):
    active = [i for i in range(10) if i not in zeros]
    n = len(active)
    return {
        "event_id": name, "frame_indices": list(range(100, 110)),
        "true_positions": [i/10 for i in range(10)],
        "decoded_positions": [None if i in zeros else i/10 for i in range(10)],
        "posterior_zero_columns": [i in zeros for i in range(10)],
        "time_permutations": [list(reversed(range(n))) for _ in range(500)] if n >= 5 else [],
    }


def context(condition="reward_L"):
    return {"mouse":"478", "phase":"learning", "cluster":"TC_cluster",
            "decoder_side":"left", "condition":condition}


class ReplayStatisticsTests(unittest.TestCase):
    def test_analytic_forward_reverse_and_frozen_draws(self):
        e = event()
        forward = score_event(e, "reward_L")
        self.assertEqual((forward["rho"], forward["p_forward"], forward["p_backward"]), (1, 0, 1))
        self.assertTrue(forward["significant"])
        self.assertEqual(forward["status"], "tested_zero_null_spread")
        self.assertIsNone(forward["z"])
        self.assertEqual(forward["rmse_normalized_position"], 0)
        e["decoded_positions"].reverse()
        backward = score_event(e, "reward_L")
        self.assertEqual((backward["rho"], backward["p_forward"], backward["p_backward"]), (-1, 1, 0))
        self.assertEqual(len(backward["null_rhos"]), 500)

    def test_ties_are_inclusive_and_not_plus_one_corrected(self):
        e = event()
        e["time_permutations"][:12] = [list(range(10)) for _ in range(12)]
        result = score_event(e, "reward_L")
        self.assertAlmostEqual(result["p_forward"], 12/500)
        self.assertTrue(result["significant"])
        self.assertNotAlmostEqual(result["p_forward"], 13/501)
        e["time_permutations"][12] = list(range(10))
        result = score_event(e, "reward_L")
        self.assertAlmostEqual(result["p_forward"], 13/500)
        self.assertFalse(result["significant"])

    def test_population_null_standard_deviation(self):
        e = event()
        e["time_permutations"][:250] = [list(range(10)) for _ in range(250)]
        result = score_event(e, "reward_L")
        self.assertEqual(result["status"], "tested_finite_statistics")
        self.assertEqual(result["z"], 1)
        self.assertEqual(result["p_forward"], .5)

    def test_average_rank_ties_have_known_correlation(self):
        e = event()
        e["decoded_positions"] = [0]*5 + [1]*5
        result = score_event(e, "reward_L")
        self.assertAlmostEqual(result["rho"], math.sqrt(25/33))

    def test_zero_columns_removed_but_original_indices_preserved(self):
        e = event(zeros=(2, 4, 6, 8))
        result = score_event(e, "reward_L")
        self.assertEqual(result["retained_frame_indices"], [100,101,103,105,107,109])
        self.assertEqual(result["rho"], 1)
        self.assertEqual(result["nonzero_posterior_bins_before_crop"], 6)

    def test_outward_crop_uses_truth_after_zero_column_removal(self):
        e = event()
        e["true_positions"] = [0]*4 + [1]*6
        e["time_permutations"] = []
        result = score_event(e, "outward_L")
        self.assertEqual(result["retained_frame_indices"], [100,101,102,103])
        self.assertEqual(result["status"], "skipped_fewer_than_five_retained_bins")
        self.assertEqual(result["outward_crop_after_compact_index"], 4)
        # Identical discontinuity is not an outward artifact exclusion in reward.
        e["time_permutations"] = [list(reversed(range(10))) for _ in range(500)]
        self.assertEqual(score_event(e, "reward_L")["nonzero_posterior_bins_before_crop"], 10)

    def test_outward_jump_threshold_is_strict(self):
        e = event()
        e["true_positions"] = [0]*4 + [.3]*6
        self.assertIsNone(score_event(e, "outward_R")["outward_crop_after_compact_index"])
        e["true_positions"] = [0]*4 + [.30001]*6
        e["time_permutations"] = []
        self.assertEqual(score_event(e, "outward_R")["outward_crop_after_compact_index"], 4)

    def test_selected_denominator_retains_skipped_events(self):
        active = event("active")
        skipped = event("skipped", zeros=range(6))
        result = score_stratum(context(), ["active", "skipped"], [active, skipped])
        self.assertEqual((result["selected_count"], result["tested_count"], result["skipped_count"]), (2,1,1))
        self.assertEqual(result["source_significant_fraction_all_selected"], .5)
        self.assertEqual(result["diagnostic_significant_fraction_tested"], 1)
        self.assertFalse(result["source_support_authenticated"])
        self.assertIsNone(result["paper_reproduction"])
        self.assertIsNone(result["paper_improvement"])

    def test_constant_trajectory_preserves_literal_non_significance_and_undefined_status(self):
        e = event()
        e["decoded_positions"] = [.5] * 10
        result = score_stratum(context(), [e["event_id"]], [e])
        item = result["events"][0]
        self.assertEqual(item["status"], "tested_undefined_rank_statistic")
        self.assertEqual((item["p_forward"], item["p_backward"]), (1,1))
        self.assertEqual(item["null_rhos"], [None]*500)
        self.assertEqual(result["undefined_tested_count"], 1)
        self.assertEqual(result["source_significant_fraction_all_selected"], 0)

    def test_omissions_extras_reordering_and_duplicate_rosters_rejected(self):
        a, b = event("a"), event("b")
        bad = [(["a","b"],[a]), (["a"],[a,b]), (["a","b"],[b,a]), (["a","a"],[a,a])]
        for roster, values in bad:
            with self.subTest(roster=roster):
                with self.assertRaises(ContractError):
                    score_stratum(context(), roster, values)

    def test_invalid_draws_and_null_draws_for_skipped_events_rejected(self):
        for change in (lambda e:e["time_permutations"].pop(),
                       lambda e:e["time_permutations"].__setitem__(0, [0]*10),
                       lambda e:e["time_permutations"][0].__setitem__(0, True)):
            e = event(); change(e)
            with self.assertRaises(ContractError): score_event(e, "reward_L")
        e=event(zeros=range(6));e["time_permutations"]=[[0,1,2,3]]
        with self.assertRaises(ContractError): score_event(e,"reward_L")

    def test_bad_window_unknown_fields_nonfinite_and_bool_numbers_rejected(self):
        changes = [lambda e:e.update(extra=1), lambda e:e["frame_indices"].__setitem__(2,999),
                   lambda e:e["true_positions"].__setitem__(2,float("nan")),
                   lambda e:e["decoded_positions"].__setitem__(2,True),
                   lambda e:e["decoded_positions"].__setitem__(2,10**400),
                   lambda e:e["posterior_zero_columns"].__setitem__(0,True)]
        for change in changes:
            e = event();change(e)
            with self.assertRaises(ContractError): score_event(e,"reward_L")

    def test_extreme_finite_rmse_and_overflowing_integer_difference(self):
        e = event()
        e["true_positions"] = [1e308] * 10
        e["decoded_positions"] = [0.0] * 10
        result = score_event(e, "reward_L")
        self.assertEqual(result["rmse_normalized_position"], 1e308)
        self.assertTrue(math.isfinite(result["rmse_normalized_position"]))
        e["true_positions"] = [10**308] * 10
        e["decoded_positions"] = [-10**308] * 10
        with self.assertRaisesRegex(ContractError, "finite position differences"):
            score_event(e, "reward_L")

    def test_empty_selected_support_is_unavailable_not_zero_effect(self):
        result=score_stratum(context(),[],[])
        self.assertTrue(result["empty_selection"])
        self.assertIsNone(result["source_significant_fraction_all_selected"])
        self.assertIsNone(result["diagnostic_significant_fraction_tested"])

    def test_unknown_biological_context_rejected(self):
        for key,value in (("mouse","new-mouse"),("phase","all"),("cluster","all"),("decoder_side","both")):
            c=context();c[key]=value
            with self.assertRaises(ContractError): score_stratum(c,[],[])


if __name__ == "__main__":
    unittest.main(verbosity=1)
