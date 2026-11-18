"""Generated arithmetic and support controls; no biological observations."""
import copy
from fractions import Fraction
from itertools import combinations
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_input import WEIGHTS, reduce_common_inputs


def fixture(n=10, projection="V1_to_V1", pre="pre"):
    ids = [f"post-{i}" for i in range(n)]
    edges = []
    for i, post in enumerate(ids):
        edge = {"post_id": post, "population": "Connected"}
        edge.update({name: 1.0 for name in WEIGHTS})
        edge["n_synapses"] = 2 if i == 0 else 1
        edges.append(edge)
    pairs = [(a, b, 1.0 if (a, b) == (ids[0], ids[1]) else 0.0)
             for a, b in combinations(ids, 2)]
    row = {"projection": projection, "pre_id": pre, "edges": edges,
           "post_pairs": pairs, "pre_post": [(p, float(i == 0)) for i, p in enumerate(ids)]}
    return {(projection, pre): ids}, row


def weight(result, name):
    return next(row for row in result["weight_summaries"] if row["weight"] == name)


class CommonInputControls(unittest.TestCase):
    def test_nonuniform_hand_calculation_and_unpooled_effects(self):
        roster, record = fixture()
        result = reduce_common_inputs(roster, [record])[0]
        actual = weight(result, "n_synapses")
        self.assertAlmostEqual(actual["post"], 1 / 27)
        self.assertAlmostEqual(actual["pre_post"], 2 / 11)
        self.assertEqual(actual["n_post_pairs"], 45)
        self.assertAlmostEqual(weight(result, "pred_n_synapses")["post"], 1 / 45)
        self.assertEqual(len(result["paired_differences"]), 6)
        self.assertEqual(result["scientific_qualification"], "not_established")

    def test_matches_explicit_ordered_pair_equation(self):
        roster, record = fixture(11)
        for i, edge in enumerate(record["edges"]):
            for name in WEIGHTS:
                edge[name] = i + 1
        record["post_pairs"] = [(a, b, (i % 13 - 6) / 7)
                                for i, (a, b, _) in enumerate(record["post_pairs"])]
        values = {frozenset((a, b)): v for a, b, v in record["post_pairs"]}
        weights = {row["post_id"]: row["n_synapses"] for row in record["edges"]}
        numerator = denominator = 0.0
        for a, wa in weights.items():
            for b, wb in weights.items():
                if a != b:
                    numerator += values[frozenset((a, b))] * wa * wb
                    denominator += wa * wb
        actual = weight(reduce_common_inputs(roster, [record])[0], "n_synapses")["post"]
        self.assertAlmostEqual(actual, numerator / denominator)

    def test_identity_alignment_and_weight_scale_invariance(self):
        roster, record = fixture()
        reference = reduce_common_inputs(roster, [record])[0]
        changed = copy.deepcopy(record)
        changed["edges"].reverse()
        changed["pre_post"].reverse()
        changed["post_pairs"] = [(b, a, v) for a, b, v in reversed(changed["post_pairs"])]
        for row in changed["edges"]:
            for name in WEIGHTS:
                row[name] *= 100
        result = reduce_common_inputs(roster, [changed])[0]
        for first, second in zip(reference["weight_summaries"], result["weight_summaries"]):
            self.assertAlmostEqual(first["post"], second["post"])
            self.assertAlmostEqual(first["pre_post"], second["pre_post"])

    def test_source_count_threshold_is_before_weight_specific_filter(self):
        roster, record = fixture(9)
        result = reduce_common_inputs(roster, [record])[0]
        self.assertFalse(result["eligible"])
        self.assertEqual(result["status"], "ineligible_source_connected_count")
        roster, record = fixture(10)
        record["edges"][0]["population"] = "ADP"
        self.assertFalse(reduce_common_inputs(roster, [record])[0]["eligible"])

    def test_zero_weight_support_is_explicit_not_silently_omitted(self):
        roster, record = fixture()
        for row in record["edges"]:
            row["pred_dend_len"] = 0
        record["edges"][0]["pred_dend_len"] = 1
        result = reduce_common_inputs(roster, [record])[0]
        self.assertEqual(result["status"], "undefined_weight_support")
        summary = weight(result, "pred_dend_len")
        self.assertIsNone(summary["post"])
        self.assertEqual(summary["pre_post"], 1)
        self.assertEqual(len(result["weight_summaries"]), 5)

    def test_large_finite_predicted_weights_do_not_overflow_products(self):
        roster, record = fixture()
        for row in record["edges"]:
            row["pred_n_synapses"] = 1e308
        result = reduce_common_inputs(roster, [record])[0]
        self.assertAlmostEqual(weight(result, "pred_n_synapses")["post"], 1 / 45)

    def test_duplicate_missing_extra_group_and_post_rejected(self):
        roster, record = fixture()
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [])
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [record, record])
        changed = copy.deepcopy(record); changed["pre_id"] = "other"
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        for mode in ("duplicate", "missing", "extra"):
            changed = copy.deepcopy(record)
            if mode == "duplicate": changed["edges"].append(changed["edges"][0])
            elif mode == "missing": changed["edges"].pop()
            else: changed["edges"][0]["post_id"] = "unknown"
            with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])

    def test_missing_reversed_duplicate_and_diagonal_pairs_rejected(self):
        roster, record = fixture()
        for mode in ("missing", "duplicate", "diagonal"):
            changed = copy.deepcopy(record)
            a, b, value = changed["post_pairs"][0]
            if mode == "missing": changed["post_pairs"].pop()
            elif mode == "duplicate": changed["post_pairs"].append((b, a, value))
            else: changed["post_pairs"].append((a, a, 1))
            with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])

    def test_invalid_numbers_and_self_edges_rejected(self):
        roster, record = fixture()
        for value in (float("nan"), float("inf"), -1, True, 10**1000,
                      Fraction(-1, 10**400), 2**54 + 1):
            changed = copy.deepcopy(record); changed["edges"][0]["dend_len"] = value
            with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        changed = copy.deepcopy(record); changed["edges"][0]["n_synapses"] = 1.5
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        for value in (Fraction(2**54 + 1, 2**54), 2**54 + 1):
            changed = copy.deepcopy(record); changed["edges"][0]["n_synapses"] = value
            with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        changed = copy.deepcopy(record)
        changed["post_pairs"][0] = ("post-0", "post-1", Fraction(2**54 + 1, 2**54))
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        changed = copy.deepcopy(record); changed["post_pairs"][0] = ("post-0", "post-1", 1.0001)
        with self.assertRaises(ValueError): reduce_common_inputs(roster, [changed])
        bad_roster = {("V1_to_V1", "post-0"): roster[("V1_to_V1", "pre")]}
        with self.assertRaises(ValueError): reduce_common_inputs(bad_roster, [record])

    def test_all_projection_groups_remain_separate(self):
        expected, records = {}, []
        for projection in ("V1_to_V1", "V1_to_HVA", "HVA_to_V1", "HVA_to_HVA"):
            roster, record = fixture(projection=projection)
            expected.update(roster); records.append(record)
        result = reduce_common_inputs(expected, reversed(records))
        self.assertEqual(len(result), 4)
        self.assertEqual({row["projection"] for row in result}, {key[0] for key in expected})
        self.assertTrue(all(row["pre_id"] == "pre" for row in result))


if __name__ == "__main__":
    unittest.main()
