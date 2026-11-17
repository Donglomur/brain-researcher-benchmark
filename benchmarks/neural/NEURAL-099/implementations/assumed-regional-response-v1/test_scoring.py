"""Generated arithmetic and schema controls; no authentic data or file I/O."""

import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location("neural099_scoring", Path(__file__).with_name("scoring.py"))
scoring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scoring)


def case(key, animal="a", asset="asset-a", region="MGv", row=0, clusters=1):
    return {"case_id": key, "animal_id": animal, "asset_id": asset, "region": region,
            "source_trial_row": row, "source_cluster_count": clusters}


def gold(cases, counts):
    return [{"case": copy.deepcopy(descriptor), "counts": vector}
            for descriptor, vector in zip(cases, counts)]


def predictions(cases, values):
    return [{"case_id": descriptor["case_id"], "rates": vector}
            for descriptor, vector in zip(cases, values)]


class ReferenceArithmeticTests(unittest.TestCase):
    def test_ragged_animal_region_trial_weighting_and_session_pooling(self):
        cases = [case("a-v-0"), case("a-v-1", row=1),
                 case("a-m-0", region="MGm"), case("a-m-1", region="MGm", row=1),
                 case("a-v-session2", asset="asset-a2"),
                 case("b-v", animal="b", asset="asset-b")]
        # A/MGv: (0+0+12)/3=4 MSE. A/MGm:4 MSE. B/MGv:16 MSE.
        # Equal animal score is10; neither extra sessions nor region count
        # supplies an extra animal weight. The non-square error uses 3 bins.
        values = [[0, 0, 0], [0, 0, 0], [2, 2, 2], [2, 2, 2], [6, 0, 0], [4, 4, 4]]
        result = scoring.score(cases, predictions(cases, values), gold(cases, [[0, 0, 0]] * 6),
                               edges_seconds=[0, 1, 2, 3])
        metric = result["native_resolution"]
        self.assertEqual(metric["animal_macro_mse"]["value"], 10)
        self.assertEqual(metric["per_animal"]["a"]["mse"]["value"], 4)
        self.assertAlmostEqual(metric["animal_macro_mae"]["value"], 8 / 3)
        self.assertEqual(result["animal_region_cells"], 3)

    def test_counts_use_source_clusters_and_explicit_bin_widths(self):
        cases = [case("k", clusters=2)]
        rates = scoring.rates_from_gold(cases, gold(cases, [[1, 4]]), edges_seconds=[0, 0.5, 2.5])
        self.assertEqual(rates["k"], [1, 1])
        result = scoring.score(cases, predictions(cases, [[1, 1]]), gold(cases, [[1, 4]]),
                               edges_seconds=[0, 0.5, 2.5])
        self.assertEqual(result["native_resolution"]["animal_macro_mse"]["value"], 0)
        self.assertFalse(result["source_cluster_is_individual_neuron"])
        self.assertFalse(result["observation_coverage_verified"])

    def test_selected_decimal_grid_has_constant_exact_nominal_exposure(self):
        cases = [case("selected", clusters=2)]
        edges = [index / 1000 for index in range(101)]
        result = scoring.score(cases, predictions(cases, [[500] * 100]),
                               gold(cases, [[1] * 100]), edges_seconds=edges,
                               coarsening_factor=5)
        self.assertEqual(result["native_resolution"]["animal_macro_mse"]["value"], 0)
        self.assertEqual(result["coarsened_resolution"]["animal_macro_mse"]["value"], 0)
        self.assertEqual(result["coarsened_resolution"]["bins_per_case"], 20)

    def test_coarsening_has_time_weights_and_can_cancel_opposing_errors(self):
        cases = [case("k")]
        result = scoring.score(cases, predictions(cases, [[0, 4]]), gold(cases, [[3, 9]]),
                               edges_seconds=[0, 1, 4], coarsening_factor=2)
        self.assertEqual(result["native_resolution"]["animal_macro_mse"]["value"], 5)
        self.assertEqual(result["coarsened_resolution"]["animal_macro_mse"]["value"], 0)
        with self.assertRaises(ValueError):
            scoring.score(cases, predictions(cases, [[0, 4, 0]]), gold(cases, [[0, 0, 0]]),
                          edges_seconds=[0, 1, 2, 3], coarsening_factor=2)

    def test_final_mean_survives_individual_squared_error_overflow(self):
        cases = [case("k")]
        result = scoring.score(cases, predictions(cases, [[1.5e154, 0]]), gold(cases, [[0, 0]]),
                               edges_seconds=[0, 1, 2])
        value = result["native_resolution"]["animal_macro_mse"]
        self.assertEqual(value["state"], "finite")
        self.assertAlmostEqual(value["value"] / 1.125e308, 1)

    def test_final_mae_survives_individual_difference_overflow(self):
        cases = [case("k")]
        result = scoring.score(cases, predictions(cases, [[-1e308, 0, 0, 0]]),
                               gold(cases, [[10 ** 308, 0, 0, 0]]), edges_seconds=[0, 1, 2, 3, 4])
        metric = result["native_resolution"]
        self.assertAlmostEqual(metric["animal_macro_mae"]["value"] / 5e307, 1)
        self.assertEqual(metric["animal_macro_mse"], {"value": None, "state": "outside_float_range"})
        json.dumps(result, allow_nan=False)

    def test_huge_integer_ratio_and_coarse_width_sum_are_exact(self):
        cases = [case("k", clusters=10 ** 400)]
        rates = scoring.rates_from_gold(cases, gold(cases, [[10 ** 400]]), edges_seconds=[0, 1])
        self.assertEqual(rates["k"], [1])
        wide = [case("wide")]
        result = scoring.score(wide, predictions(wide, [[1, 1]]),
                               gold(wide, [[0, 0]]), edges_seconds=[-1e308, 0, 1e308],
                               coarsening_factor=2)
        self.assertEqual(result["coarsened_resolution"]["animal_macro_mse"]["value"], 1)

    def test_underflow_is_explicit_and_per_animal_precision_is_retained(self):
        cases = [case("tiny"), case("huge", animal="b", asset="asset-b")]
        result = scoring.score(cases, predictions(cases, [[1e-200], [1e308]]), gold(cases, [[0], [0]]),
                               edges_seconds=[0, 1])
        metric = result["native_resolution"]
        self.assertEqual(metric["per_animal"]["a"]["mse"], {"value": 0.0, "state": "underflow_to_zero"})
        self.assertEqual(metric["per_animal"]["a"]["mae"]["value"], 1e-200)
        self.assertEqual(metric["animal_macro_mse"]["state"], "outside_float_range")

    def test_baseline_uses_animal_means_and_explicit_unseen_region_fallback(self):
        train = [case("av0"), case("av1", row=1),
                 case("am0", region="MGm"), case("am1", region="MGm", row=1),
                 case("bv", animal="b", asset="asset-b")]
        query = [case("qv", animal="q", asset="asset-q"),
                 case("qs", animal="q", asset="asset-q", region="SG")]
        result = scoring.training_mean_baseline(train, gold(train, [[0], [4], [10], [10], [8]]),
                                                query, edges_seconds=[0, 1])
        by_id = {row["case_id"]: row["rates"] for row in result["predictions"]}
        self.assertEqual(by_id["qv"], [5])  # mean(A/MGv=2, B/MGv=8)
        self.assertEqual(by_id["qs"], [7])  # mean(A/regions=6, B/regions=8)
        self.assertEqual(result["fallback_cells"], [{"animal_id": "q", "asset_id": "asset-q", "region": "SG"}])
        with self.assertRaises(ValueError):
            scoring.training_mean_baseline(train, gold(train, [[0], [4], [10], [10], [8]]),
                                            [case("leak", animal="a", asset="new")], edges_seconds=[0, 1])

    def test_baseline_mean_does_not_overflow_sum(self):
        train = [case("a"), case("b", animal="b", asset="b")]
        query = [case("q", animal="q", asset="q")]
        result = scoring.training_mean_baseline(train, gold(train, [[10 ** 308], [10 ** 308]]),
                                                query, edges_seconds=[0, 1])
        self.assertEqual(result["predictions"][0]["rates"], [1e308])


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.cases = [case("k")]
        self.pred = predictions(self.cases, [[0, 1]])
        self.gold = gold(self.cases, [[0, 1]])
        self.edges = [0, 1, 2]

    def test_prediction_admission_precedes_any_gold_access(self):
        class Trap:
            def __iter__(self):
                raise AssertionError("Gold was accessed before prediction admission")
        with self.assertRaisesRegex(ValueError, "Complete prediction"):
            scoring.score(self.cases, [], Trap(), edges_seconds=self.edges)

    def test_prediction_completeness_identity_and_finite_numeric_schema(self):
        bad = [[], self.pred + self.pred,
               [{"case_id": "other", "rates": [0, 1]}],
               [{"case_id": "k", "rates": [0]}],
               [{"case_id": "k", "rates": [True, 1]}],
               [{"case_id": "k", "rates": [math.inf, 1]}],
               [{"case_id": "k", "rates": [math.nan, 1]}],
               [{"case_id": "k", "rates": [0, 1], "extra": 1}]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                scoring.admit_predictions(self.cases, value, edges_seconds=self.edges)
        two = [case("k"), case("j", row=1)]
        with self.assertRaises(ValueError):
            scoring.admit_predictions(two, self.pred * 2, edges_seconds=self.edges)

    def test_gold_descriptor_strict_identity_boolean_and_count_validation(self):
        for field, value in (("animal_id", "other"), ("source_trial_row", True),
                             ("source_cluster_count", True), ("source_cluster_count", 2),
                             ("region", "MGm")):
            changed = copy.deepcopy(self.gold)
            changed[0]["case"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                scoring.score(self.cases, self.pred, changed, edges_seconds=self.edges)
        for count in (-1, True, 0.0, math.inf):
            changed = copy.deepcopy(self.gold)
            changed[0]["counts"][0] = count
            with self.subTest(count=count), self.assertRaises(ValueError):
                scoring.score(self.cases, self.pred, changed, edges_seconds=self.edges)

    def test_unsupported_regions_denominators_and_partial_trial_grid_refuse(self):
        bad = [[case("k", clusters=0)], [case("k", clusters=True)],
               [case("k", region=" ")], [case("k", region="MGN")],
               [case("k"), case("different-id")],
               [case("k"), case("other", animal="b", row=1)],
               [case("k"), case("other", row=1, clusters=2)],
               [case("k"), case("v1", row=1), case("m0", region="MGm")]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                scoring.validate_cases(value)

    def test_edges_and_coarsening_are_explicit_valid_choices(self):
        for edges in ([0], [0, 0, 1], [0, 2, 1], [0, True, 2], [0, math.inf, 2]):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                scoring.score(self.cases, self.pred, self.gold, edges_seconds=edges)
        for factor in (0, True, -1, 1.5, 3):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                scoring.score(self.cases, self.pred, self.gold, edges_seconds=self.edges,
                              coarsening_factor=factor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
