"""Bounded generated controls; no authentic neurons or author inference."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
SPEC = importlib.util.spec_from_file_location("peth_v2", MODULE)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def peth_pair(r=0.5):
    s = math.sqrt(1 - r * r)
    return [4, 4, 6, 6] * 750, [5-r-s, 5-r+s, 5+r-s, 5+r+s] * 750


def packet(n=100, dataset="A"):
    first, second = peth_pair()
    units, assignments = [], []
    for i in range(n):
        for session, peth in ((1, first), (2, second)):
            uid = 2 * i + session - 1
            units.append({"dataset": dataset, "unit_id": uid, "session_id": session,
                          "recording_date": f"2020-01-0{session}", "shank": 0,
                          "mean_rate_hz": 5, "peth": peth})
            assignments.append({"dataset": dataset, "unit_id": uid, "track_id": i + 1})
    return {"schema_version": "figure5-peth/v2", "source_kind": "generated_engineering_control",
            "peth_schema": "press_release_poke_3x1000_bins_1ms_plus_minus_500ms",
            "rate_unit": "Hz", "rate_measurement_provenance": "generated fixture, Hz",
            "population_provenance": "generated fixture, complete assignments",
            "units": units, "methods": {name: {"peth_excluded_from_matching_and_selection": True,
                "execution_provenance": "generated fixture", "assignments": copy.deepcopy(assignments)}
                for name in scorer.BASELINES}}


class Controls(unittest.TestCase):
    def test_independent_correlation_oracle_and_affine_endpoint(self):
        # Orthogonal centered unit patterns x,z; y=.5*x+sqrt(.75)*z.
        a, b = peth_pair()
        self.assertAlmostEqual(scorer.fisher_z(a, b), math.log(3) / 2, places=13)
        self.assertEqual(scorer.fisher_z(a, [9*x+2 for x in a]), math.inf)
        self.assertEqual(scorer.fisher_z(a, [10-x for x in a]), -math.inf)
        self.assertIsNone(scorer.fisher_z(a, [1] * 3000))

    def test_exact_100_pair_boundary_and_source_median(self):
        result = scorer.score(packet())
        self.assertEqual(result["original_method_common_support"], ["A"])
        for report in result["methods"].values():
            self.assertEqual(report["A"]["valid_pairs"], 100)
            self.assertAlmostEqual(report["A"]["median_fisher_z"], math.log(3)/2)
        self.assertEqual(scorer.score(packet(99))["original_method_common_support"], [])

    def test_calendar_gap_is_not_consecutive_session(self):
        fixture = packet(1)
        fixture["units"][1]["recording_date"] = "2020-01-03"
        report = scorer.score(fixture)["methods"]["DANT"]["A"]
        self.assertEqual(report["all_track_pairs"], 1)
        self.assertEqual(report["not_consecutive_day_pairs"], 1)
        self.assertEqual(report["valid_pairs"], 0)

    def test_same_day_multiple_sessions_do_not_count_as_next_day(self):
        fixture = packet(1)
        fixture["units"][1]["recording_date"] = "2020-01-01"
        report = scorer.score(fixture)["methods"]["DANT"]["A"]
        self.assertEqual(report["not_consecutive_day_pairs"], 1)

    def test_rate_thresholds_are_inclusive_and_apply_to_both_units(self):
        fixture = packet(3)
        fixture["units"][0]["mean_rate_hz"] = 1
        fixture["units"][1]["peth"] = [5*x/max(fixture["units"][1]["peth"]) for x in fixture["units"][1]["peth"]]
        fixture["units"][3]["mean_rate_hz"] = 0.999
        fixture["units"][4]["peth"] = [4.999*x/6 for x in fixture["units"][4]["peth"]]
        report = scorer.score(fixture)["methods"]["DANT"]["A"]
        self.assertEqual(report["valid_pairs"], 1)
        self.assertEqual(report["rate_ineligible_pairs"], 2)

    def test_constant_peth_is_not_a_zero_or_valid_pair(self):
        fixture = packet(100)
        fixture["units"][0]["peth"] = [5] * 3000
        result = scorer.score(fixture)
        self.assertEqual(result["methods"]["DANT"]["A"]["constant_peth_pairs"], 1)
        self.assertEqual(result["methods"]["DANT"]["A"]["valid_pairs"], 99)
        self.assertEqual(result["original_method_common_support"], [])

    def test_three_original_methods_define_common_support(self):
        fixture = packet()
        fixture["methods"]["EMD"]["assignments"][0]["track_id"] = -1
        result = scorer.score(fixture)
        self.assertEqual(result["original_method_common_support"], [])
        self.assertEqual(result["excluded_datasets"]["A"]["methods"], ["EMD"])

    def test_candidate_cannot_change_original_support(self):
        fixture = packet()
        candidate = copy.deepcopy(fixture["methods"]["DANT"])
        for row in candidate["assignments"]:
            row["track_id"] = -1
        fixture["methods"]["candidate"] = candidate
        result = scorer.score(fixture)
        self.assertEqual(result["original_method_common_support"], ["A"])
        self.assertEqual(result["candidate_on_original_support"]["A"]["valid_pairs"], 0)
        self.assertFalse(result["candidate_on_original_support"]["A"]["meets_100_pair_support"])
        self.assertIsNone(result["candidate_on_original_support"]["A"]["median_fisher_z"])

    def test_long_track_only_adjacent_day_pairs(self):
        fixture = packet(1)
        row = copy.deepcopy(fixture["units"][1])
        row.update(unit_id=2, session_id=3, recording_date="2020-01-03")
        fixture["units"].append(row)
        for method in fixture["methods"].values():
            method["assignments"].append({"dataset": "A", "unit_id": 2, "track_id": 1})
        report = scorer.score(fixture)["methods"]["DANT"]["A"]
        self.assertEqual(report["all_track_pairs"], 3)
        self.assertEqual(report["not_consecutive_day_pairs"], 1)
        self.assertEqual(report["valid_pairs"], 2)

    def test_median_is_not_all_pair_mean(self):
        fixture = packet(3)
        fixture["units"][5]["peth"] = peth_pair(0.99)[1]
        report = scorer.score(fixture)["methods"]["DANT"]["A"]
        self.assertAlmostEqual(report["median_fisher_z"], math.atanh(.5))
        self.assertNotAlmostEqual(report["median_fisher_z"], (2*math.atanh(.5)+math.atanh(.99))/3)

    def test_friedman_hand_rank_oracles(self):
        result = scorer.friedman_three([[3, 2, 1]] * 8)
        self.assertEqual(result["statistic"], 16)
        self.assertAlmostEqual(result["p_asymptotic"], math.exp(-8))
        tied = scorer.friedman_three([[3, 1, 1]] * 8)
        self.assertEqual(tied["tie_correction"], 0.75)
        self.assertEqual(tied["statistic"], 16)
        self.assertIsNone(scorer.friedman_three([[1, 1, 1]]*8)["statistic"])

    def test_rejects_missing_duplicate_and_unknown_assignments(self):
        for mutation in ("missing", "duplicate", "unknown"):
            fixture = packet(1)
            rows = fixture["methods"]["DANT"]["assignments"]
            if mutation == "missing":
                rows.pop()
            elif mutation == "duplicate":
                rows.append(copy.deepcopy(rows[0]))
            else:
                rows[0]["unit_id"] = 999
            with self.subTest(mutation=mutation), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_rejects_collisions_and_feature_leak(self):
        for mutation in ("session", "shank", "peth"):
            fixture = packet(1)
            if mutation == "session":
                fixture["units"][1].update(session_id=1, recording_date="2020-01-01")
            elif mutation == "shank":
                fixture["units"][1]["shank"] = 1
            else:
                fixture["methods"]["DANT"]["peth_excluded_from_matching_and_selection"] = False
            with self.subTest(mutation=mutation), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_bad_rate_calendar_or_invented_unit_order_rejected(self):
        for field, value in (("mean_rate_hz", float("nan")), ("mean_rate_hz", -1),
                             ("unit_id", True), ("recording_date", "20200102"),
                             ("recording_date", "2019-12-31")):
            fixture = packet(1)
            fixture["units"][1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_no_invented_13_dataset_or_train_test_requirement(self):
        fixture = packet(1)
        result = scorer.score(fixture)
        self.assertEqual(result["input_dataset_count"], 1)
        self.assertIn("unverified", result["qualification"])
        self.assertNotIn("paper_win", result)

    def test_cli_and_strict_json_output(self):
        import sys
        from unittest.mock import patch
        fixture = packet(1)
        fixture["units"][1]["peth"] = fixture["units"][0]["peth"]
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/"packet.json", Path(directory)/"result.json"
            source.write_text(json.dumps(fixture))
            with patch.object(sys, "argv", [str(MODULE), str(source), str(target)]):
                scorer.main()
            result = json.loads(target.read_text())
            self.assertEqual(result["methods"]["DANT"]["A"]["median_fisher_z"], "positive_infinity")
            self.assertEqual(len(result["input_sha256"]), 64)
            with patch.object(sys, "argv", [str(MODULE), str(source), str(target)]), self.assertRaises(FileExistsError):
                scorer.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
