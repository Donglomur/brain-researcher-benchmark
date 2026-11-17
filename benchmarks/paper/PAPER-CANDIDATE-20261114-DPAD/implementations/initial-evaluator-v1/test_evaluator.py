"""Meaningful generated engineering controls; no scientific qualification."""
import copy
import itertools
import math
import tempfile
import unittest
from pathlib import Path

import evaluator as e
import generated_control as g


class ScientificDefinitions(unittest.TestCase):
    def test_channel_cc_independent_orthogonal_construction(self):
        # x,z are orthogonal and equally scaled; corr(x,.6*x+.8*z)=.6.
        x, z = [-1, -1, 1, 1], [-1, 1, -1, 1]
        result = e.channel_cc([[v, v] for v in x], [[v, .6*v + .8*w] for v, w in zip(x, z)])
        self.assertAlmostEqual(result["mean_cc"], .8)
        self.assertAlmostEqual(result["per_channel"][1], .6)

    def test_cc_flat_and_nonfinite_never_silently_drop(self):
        self.assertIsNone(e.channel_cc([[1], [1]], [[2], [3]])["mean_cc"])
        self.assertIsNone(e.channel_cc([[1], [2]], [[3], [3]])["mean_cc"])
        for value in (None, float("nan"), float("inf")):
            with self.assertRaises(e.ContractError):
                e.channel_cc([[1], [2]], [[1], [value]])

    def test_cc_large_finite_values(self):
        self.assertAlmostEqual(e.channel_cc([[-1e308], [1e308]], [[-1e308], [1e308]])["mean_cc"], 1)

    def test_grid_cardinality_and_fixed_loci(self):
        self.assertEqual(len(e.ARCHITECTURES), 90)
        self.assertEqual(sum(x["Aprime"] == "LSTM" for x in e.ARCHITECTURES.values()), 29)
        for key in e.FIXED.values():
            self.assertIn(key, e.ARCHITECTURES)

    def test_dimension_is_larger_smallest_peak(self):
        curve = {d: {"training_neural_cc": .4, "training_behavior_cc": .2} for d in e.DIMENSIONS}
        curve[2]["training_neural_cc"] = .8
        curve[4]["training_behavior_cc"] = .8
        curve[8]["training_behavior_cc"] = .8
        self.assertEqual(e.choose_dimension(curve), 4)

    def test_architecture_uses_maximum_lower_sem_bound(self):
        candidates = {k: {"inner_neural_cc": [.1, .1], "inner_behavior_cc": [.1, .1]} for k in e.ARCHITECTURES}
        candidates["Aprime:1x64"] = {"inner_neural_cc": [.2, .2], "inner_behavior_cc": [.6, 1.]}
        candidates["Cy:1x64"] = {"inner_neural_cc": [.7, .7], "inner_behavior_cc": [.75, .75]}
        candidates["Cz:1x64"] = {"inner_neural_cc": [.9, .9], "inner_behavior_cc": [.7, .7]}
        self.assertEqual(e.choose_architecture(candidates, "decoding"), "Cy:1x64")

    def test_signed_rank_independent_exhaustive_sign_oracle(self):
        differences = [1, 1, -2, 0]
        # Nonzero absolute ranks are 1.5,1.5,3; observed positive sum3.
        signs = list(itertools.product((-1, 1), repeat=3))
        oracle = sum(sum(r for r, s in zip((1.5, 1.5, 3), mask) if s > 0) >= 3 for mask in signs)/8
        self.assertEqual(e.signed_rank_greater(differences, [0]*4), oracle)
        self.assertEqual(e.signed_rank_greater([1]*5, [0]*5), 1/32)
        self.assertEqual(e.signed_rank_greater([0]*5, [0]*5), 1)

    def test_frontier_requires_effect_and_significance(self):
        vectors = {"a": {"neural_cc": [.5]*35, "behavior_cc": [.5]*35},
                   "b": {"neural_cc": [.501]*35, "behavior_cc": [.501]*35}}
        self.assertEqual(set(e.frontier(vectors)["methods"]), {"a", "b"})
        vectors["b"] = {"neural_cc": [.6]*35, "behavior_cc": [.6]*35}
        self.assertEqual(e.frontier(vectors)["methods"], ["b"])
        vectors["b"]["behavior_cc"] = [.4]*35
        self.assertEqual(set(e.frontier(vectors)["methods"]), {"a", "b"})

    def test_frontier_signed_rank_direction_not_mean_direction(self):
        av, bv = [.8]*34 + [-.9], [.79]*34 + [.9]
        vectors = {"a": {"neural_cc": av, "behavior_cc": av},
                   "b": {"neural_cc": bv, "behavior_cc": bv}}
        self.assertLess(sum(av), sum(bv))
        self.assertEqual(e.frontier(vectors)["methods"], ["a"])

    def test_parser_rejects_duplicate_keys_and_json_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"input.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(content)
                with self.assertRaises(e.ContractError): e.read_json(path)


class FullGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = g.make_training()
        cls.plan = e.select(cls.training)
        cls.targets, cls.predictions = g.make_artifacts(cls.training, cls.plan)

    def test_complete_scoring_and_source_selected_profiles(self):
        result = e.evaluate(self.targets, self.predictions, self.plan)
        self.assertEqual(len(result["all_grid_scores"]), 1960)
        self.assertEqual(len(result["selected_scores"]), 245)
        self.assertEqual(len(result["session_summary"]), 49)
        self.assertEqual(len(result["animal_summary"]), 7)
        self.assertEqual(result["scientific_qualification"], "unknown")
        row = self.plan["cases"][0]["methods"]
        self.assertEqual(row["flexible_decoding"]["architectures"]["8"], "Cz:1x64")
        self.assertEqual(row["flexible_prediction"]["architectures"]["8"], "Cy:1x64")
        self.assertTrue(all(v["selected_dimension"] == 8 for v in row.values()))
        self.assertAlmostEqual(result["paper_unit_summary"]["linear"]["neural_cc"]["mean"], .2)

    def test_held_truth_has_no_dimension_selection_input(self):
        original = e.digest(self.plan)
        targets = copy.deepcopy(self.targets)
        for row in targets["cases"]:
            row["behavior"] = [[-x for x in sample] for sample in row["behavior"]]
        result = e.evaluate(targets, self.predictions, self.plan)
        self.assertEqual(e.digest(self.plan), original)
        self.assertTrue(all(row["dimension"] == 8 for row in result["selected_scores"]))
        self.assertAlmostEqual(result["paper_unit_summary"]["linear"]["behavior_cc"]["mean"], -.6)

    def test_missing_duplicate_shuffled_or_nonfinite_prediction_rejected(self):
        for mutation in ("missing", "duplicate", "order", "nan", "flat"):
            bad = copy.deepcopy(self.predictions)
            if mutation == "missing": bad["cases"].pop()
            if mutation == "duplicate": bad["cases"].append(bad["cases"][0])
            if mutation == "order": bad["cases"][0]["sample_ids"].reverse()
            if mutation == "nan": bad["cases"][0]["neural"][0][0] = float("nan")
            if mutation == "flat": bad["cases"][0]["neural"] = [[1, 1]]*4
            with self.subTest(mutation=mutation), self.assertRaises(e.ContractError):
                e.evaluate(self.targets, bad, self.plan)

    def test_selection_rejects_held_provenance_and_incomplete_search(self):
        for mutation in ("held", "missing_architecture", "missing_dimension", "missing_fold"):
            bad = copy.deepcopy(self.training)
            if mutation == "held": bad["cases"][0]["selection_sample_ids"].append(0)
            if mutation == "missing_architecture": del bad["cases"][0]["dimensions"]["1"]["linear"]
            if mutation == "missing_dimension": del bad["cases"][0]["dimensions"]["128"]
            if mutation == "missing_fold": bad["cases"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(e.ContractError): e.select(bad)

    def test_filter_future_and_support_leakage(self):
        p = copy.deepcopy(self.training["protocol"])
        p["filter_future_support_samples"] = 2
        with self.assertRaises(e.ContractError): e.protocol(p)
        p["filter_future_support_samples"] = 0
        p["filter_past_support_samples"] = 1
        with self.assertRaises(e.ContractError): e.check_provenance(p, self.training["cases"][0])

    def test_plan_binding(self):
        bad = copy.deepcopy(self.plan)
        bad["cases"][0]["methods"]["linear"]["selected_dimension"] = 1
        with self.assertRaises(e.ContractError): e.evaluate(self.targets, self.predictions, bad)

    def test_bound_plan_cannot_change_fixed_architecture_or_n1(self):
        for field in ("architecture", "n1"):
            bad = copy.deepcopy(self.plan)
            if field == "architecture":
                bad["cases"][0]["methods"]["linear"]["architectures"]["1"] = "Cy:1x64"
            else:
                bad["cases"][0]["methods"]["linear"]["n1"] = 128
            pred = copy.deepcopy(self.predictions)
            pred["selection_plan_sha256"] = e.digest(bad)
            with self.subTest(field=field), self.assertRaises(e.ContractError): e.evaluate(self.targets, pred, bad)


if __name__ == "__main__":
    unittest.main()
