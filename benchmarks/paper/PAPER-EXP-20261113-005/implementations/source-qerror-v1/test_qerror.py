"""Small generated controls only; no neural data, native source replay or fitting."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("qerror", Path(__file__).with_name("qerror.py"))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def fixture():
    regions = ["MOs1", "MOs5", "PL5", "PL6", "CA1", "unmapped"]
    units = [{"unit_id": f"u{i}", "recording_id": f"r{i // 2}",
              "animal_id": f"a{i // 4}", "region": region,
              "area": q.area_of(region), "features": [10 + 4 * i, 20, 30]}
             for i, region in enumerate(regions)]
    return {
        "schema": "pfc-source-qerror-packet/v1", "task_id": "PAPER-EXP-20261113-005",
        "source_run": "runC00dMP3_brain", "feature_names": ["B_mean", "M_mean", "rate_mean"],
        "feature_space": "author-loader-output-before-standardization",
        "reference_mean": [10, 20, 30], "reference_std": [2, 3, 4],
        "feature_weights": [1, 1, 1],
        "source_map": {"topology": "hex", "kshape": [1, 2],
                       "prototypes": [[0, 0, 0], [10, 0, 0]]},
        "units": units, "panel_counts": {"ED2c": {"MOs": 2, "PL": 2},
                                        "ED2d": {"PFC": 4, "HPF": 1}},
    }


class QErrorControls(unittest.TestCase):
    def score(self, packet=None, candidate=None):
        packet = packet or fixture()
        candidate = candidate or packet["source_map"]
        return q.score(packet, candidate, require_source_population=False)

    def test_hand_calculated_complete_panels_and_normalization(self):
        packet = fixture()
        result = self.score(packet, {"topology": "hex", "kshape": [1, 2],
                                     "prototypes": [[2, 0, 0], [8, 0, 0]]})
        pfc = result["panels"]["ED2d"]["PFC"]
        self.assertEqual(pfc["source"], {"n_units": 4, "q25": 1.5, "median": 3., "q75": 4.})
        self.assertEqual(pfc["candidate"], {"n_units": 4, "q25": 1.5, "median": 2., "q75": 2.})
        self.assertEqual(pfc["candidate_minus_source_median"], -1)
        self.assertEqual(pfc["median_paired_unit_difference"], -2)
        self.assertEqual((pfc["n_recordings"], pfc["n_animals"]), (2, 1))
        self.assertEqual(list(result["panels"]["ED2c"]), ["MOs", "PL"])
        self.assertEqual(list(result["panels"]["ED2d"]), ["PFC", "HPF"])
        self.assertEqual(result["n_units_without_source_parent"], 1)
        self.assertEqual(result["diagnostic_all_unit_mean"]["source"], 2.)
        self.assertIsNone(result["paper_win"])

    def test_original_map_has_zero_all_region_differences(self):
        result = self.score()
        for panel in result["panels"].values():
            for row in panel.values():
                self.assertEqual(row["source"], row["candidate"])
                self.assertEqual(row["candidate_minus_source_median"], 0)
                self.assertEqual(row["median_paired_unit_difference"], 0)

    def test_euclidean_not_squared_error_and_first_bmu_tie(self):
        errors, bmus = q.distances([(3, 4, 12), (0, 0, 0)],
                                 [(0, 0, 0), (0, 0, 0)])
        self.assertEqual(errors, [13, 0])
        self.assertEqual(bmus, [0, 0])
        self.assertAlmostEqual(q.distances([(1, 1, 1)], [(0, 0, 0)])[0][0], math.sqrt(3))

    def test_percentiles_use_fractional_interpolation_not_nearest_rank(self):
        self.assertEqual(q.describe([0, 2, 4, 8]),
                         {"n_units": 4, "q25": 1.5, "median": 3., "q75": 5.})
        self.assertEqual(q.describe([3]), {"n_units": 1, "q25": 3., "median": 3., "q75": 3.})

    def test_more_nodes_and_changed_shape_are_refused(self):
        for candidate in [
                {"topology": "hex", "kshape": [1, 3], "prototypes": [[0, 0, 0]] * 3},
                {"topology": "hex", "kshape": [2, 1], "prototypes": [[0, 0, 0]] * 2},
                {"topology": "rect", "kshape": [1, 2], "prototypes": [[0, 0, 0]] * 2},
                {"topology": "hex", "kshape": [1, 2], "prototypes": [[0, 0, 0]] * 3}]:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                self.score(candidate=candidate)

    def test_candidate_cannot_supply_scales_features_or_its_own_panel(self):
        for field, value in [("reference_std", [100, 100, 100]), ("units", []),
                             ("panel_counts", {}), ("feature_weights", [0, 0, 0])]:
            candidate = copy.deepcopy(fixture()["source_map"])
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.score(candidate=candidate)

    def test_missing_unit_or_region_or_invented_region_count_is_refused(self):
        for mutation in (lambda p: p["units"].pop(0),
                         lambda p: p["panel_counts"]["ED2c"].pop("PL"),
                         lambda p: p["panel_counts"]["ED2d"].update({"VIS": 1}),
                         lambda p: p["panel_counts"]["ED2d"].update({"HPF": True})):
            packet = fixture()
            mutation(packet)
            with self.assertRaises(ValueError):
                self.score(packet)

    def test_duplicate_unit_wrong_area_and_record_animal_conflict_are_refused(self):
        for field, value in [("unit_id", "u0"), ("area", "PL"), ("animal_id", "another")]:
            packet = fixture()
            packet["units"][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.score(packet)

    def test_nonfinite_zero_std_and_feature_reordering_are_refused(self):
        for field, value in [("reference_std", [1, 0, 1]), ("reference_mean", [math.nan, 0, 0]),
                             ("feature_weights", [2, 1, 1]),
                             ("feature_names", ["rate_mean", "B_mean", "M_mean"])]:
            packet = fixture()
            packet[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.score(packet)
        candidate = fixture()["source_map"]
        candidate["prototypes"][0][1] = math.inf
        with self.assertRaises(ValueError):
            self.score(candidate=candidate)

    def test_source_anatomy_preserves_hippocampus_and_thalamus(self):
        self.assertEqual(q.area_of("CA1"), "CA1")
        self.assertEqual(q.area_of("MOs6a"), "MOs")
        self.assertEqual(q.parent_of("CA1"), "HPF")
        self.assertEqual(q.parent_of("VPL"), "TH")
        self.assertEqual(q.parent_of("AI"), "na")

    def test_original_substring_selection_is_preserved_and_not_silently_fixed(self):
        packet = fixture()
        packet["units"][-1].update(region="VPL", area="VPL")
        packet["panel_counts"]["ED2c"]["PL"] = 3
        packet["panel_counts"]["ED2d"]["TH"] = 1
        result = self.score(packet)
        self.assertEqual(result["panels"]["ED2c"]["PL"]["source"]["n_units"], 3)
        self.assertEqual(result["panels"]["ED2d"]["PFC"]["source"]["n_units"], 4)

    def test_small_fixture_cannot_pass_original_population_entrypoint(self):
        packet = fixture()
        with self.assertRaisesRegex(ValueError, "19,186"):
            q.score(packet, packet["source_map"])

    def test_json_duplicate_and_nonfinite_fields_are_refused(self):
        for body in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                q.strict_json(body)

    def test_cli_authenticates_packet_before_parsing_or_reading_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "packet.json"
            packet.write_text("not JSON")
            args = ["qerror.py", "--packet", str(packet), "--packet-sha256", "0" * 64,
                    "--candidate", str(Path(directory) / "nonexistent.json")]
            with patch("sys.argv", args), self.assertRaisesRegex(ValueError, "SHA256 differs"):
                q.main()


if __name__ == "__main__":
    unittest.main()
