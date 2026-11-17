"""Invented-only scientific indexing and refusal controls."""
import copy
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import occurrence_adapter as api


def fixture(p=None):
    p = [2, 0, 4, 1, 3] if p is None else p
    return {"schema": "consensus_occurrence_input_v1", "animals": [
        {"animal_id": name, "source_trial_count": len(p), "source_condition_pairs": None,
         "folds": [{"fold_id": fold, "companion_indices": list(p), "native_indices": list(p),
                    "configuration": {"branch": "no_condition", "selected_condition_pairs": None,
                                      "entrypoint": "fit", "basis": "declared_scenario"}}
                   for fold in range(3)]} for name in api.ANIMALS]}


def first(document):
    return api.audit(document)["animals"][0]["folds"][0]


def rows(result):
    return [x["original_source_trial_index"] for x in result["occurrences"]]


class OccurrenceControls(unittest.TestCase):
    def test_CLI_serializes_complete_valid_JSON_with_newline(self):
        output = io.BytesIO()
        with patch("sys.stdin", SimpleNamespace(buffer=io.BytesIO(json.dumps(fixture()).encode()))), patch("sys.stdout", SimpleNamespace(buffer=output)):
            api.main()
        body = output.getvalue()
        self.assertTrue(body.endswith(b"\n"))
        decoded = json.loads(body)
        self.assertEqual((decoded["animal_count"], decoded["fold_count"]), (7, 21))

    def test_nonidentity_double_index_is_not_single_index(self):
        r = first(fixture())
        self.assertEqual(rows(r), [4, 2, 3, 0, 1])
        self.assertEqual([x["loader_position"] for x in r["occurrences"]], [2, 0, 4, 1, 3])
        self.assertEqual([x["partition"] for x in r["occurrences"]], ["train"] * 3 + ["test"] * 2)
        self.assertTrue(r["partition_summary"]["source_identity_disjoint"])
        self.assertFalse(r["partition_summary"]["clean_generalization_established"])

    def test_repeats_are_occurrences_not_unique_samples(self):
        r = first(fixture([2, 0, 4, 2, 0]))
        self.assertEqual(rows(r), [4, 2, 0, 4, 2])
        self.assertEqual([x["occurrence_index"] for x in r["occurrences"]], list(range(5)))
        self.assertEqual(r["partition_summary"]["overlap_source_ids"], [2, 4])
        self.assertEqual(r["partition_summary"]["effective_mapping"]["omitted_source_ids"], [1, 3])
        self.assertEqual(r["partition_summary"]["training_count_by_source_id"], [1, 0, 1, 0, 1])
        self.assertEqual(r["partition_summary"]["test_count_by_source_id"], [0, 0, 1, 0, 1])

    def test_condition_rows_enumerate_positions_once_and_append_others(self):
        d = fixture([2, 0, 4, 2, 0]);a = d["animals"][0]
        a["source_condition_pairs"] = [[1, 0], [0, 1], [1, 0], [0, 1], [2, 0]]
        a["folds"][0]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[[1, 0]])
        r = first(d)
        self.assertEqual([x["loader_position"] for x in r["occurrences"]], [0, 1, 3, 4, 2])
        self.assertEqual(rows(r), [2, 0, 2, 0, 4])
        self.assertEqual(r["partition_summary"]["training_occurrences"], 2)
        self.assertEqual(r["partition_summary"]["overlap_source_ids"], [0, 2])
        self.assertEqual([x["selection_group"] for x in r["occurrences"]], ["selected"] * 4 + ["nonselected"])

    def test_empty_condition_selection_preserves_all_test_occurrences(self):
        d = fixture();a = d["animals"][0];a["source_condition_pairs"] = [[1, 0]] * 5
        a["folds"][0]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[])
        r = first(d)
        self.assertEqual(rows(r), [2, 0, 4, 1, 3])
        self.assertEqual(r["partition_summary"]["training_occurrences"], 0)
        self.assertIn("empty_training_partition", r["holds"])
        self.assertEqual(r["partition_summary"]["test_occurrences"], 5)

    def test_native_loader_authority_survives_companion_disagreement(self):
        d = fixture();d["animals"][0]["folds"][0]["companion_indices"] = list(range(5))
        r = first(d)
        self.assertFalse(r["supplied_native_companion_equal"])
        self.assertEqual(rows(r), [4, 2, 3, 0, 1])
        self.assertIn("native_companion_disagreement", r["holds"])
        self.assertFalse(r["historical_native_parity_authenticated"])

    def test_missing_native_never_uses_companion_as_loader_truth(self):
        d = fixture();d["animals"][0]["folds"][0]["native_indices"] = None
        r = first(d)
        self.assertIsNone(r["occurrences"])
        self.assertIsNone(r["supplied_native_companion_equal"])
        self.assertEqual(r["companion_mapping"]["unique_source_ids"], 5)
        self.assertIn("native_mapping_unavailable", r["holds"])

    def test_missing_configuration_is_not_guessed(self):
        d = fixture();d["animals"][0]["folds"][0]["configuration"] = None
        r = first(d)
        self.assertIsNone(r["occurrences"])
        self.assertIn("loader_branch_configuration_unavailable", r["holds"])

    def test_missing_condition_rows_is_explicit(self):
        d = fixture();d["animals"][0]["folds"][0]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[[1, 0]])
        r = first(d)
        self.assertIsNone(r["partition_summary"])
        self.assertIn("original_condition_rows_unavailable", r["holds"])

    def test_all_seven_animals_all_three_folds_retained(self):
        r = api.audit(fixture())
        self.assertEqual([x["animal_id"] for x in r["animals"]], list(api.ANIMALS))
        self.assertEqual(sum(len(x["folds"]) for x in r["animals"]), 21)
        self.assertEqual(r["animals"][0]["three_fold_coverage"]["test_occurrence_count_by_source_id"], [3, 3, 0, 0, 0])
        self.assertFalse(r["scientific_qualification"])

    def test_incomplete_coverage_has_no_misleading_partial_aggregate(self):
        d = fixture();d["animals"][0]["folds"][1]["native_indices"] = None
        r = api.audit(d)["animals"][0]
        self.assertEqual(len(r["folds"]), 3)
        self.assertFalse(r["all_three_mappings_reconstructed"])
        self.assertIsNone(r["three_fold_coverage"])

    def test_animal_and_fold_record_order_does_not_change_trial_order(self):
        d = fixture();before = api.audit(d)
        d["animals"].reverse()
        for a in d["animals"]:
            a["folds"].reverse()
        self.assertEqual(api.audit(d), before)

    def test_no_input_mutation(self):
        d = fixture([2, 0, 4, 2, 0]);before = copy.deepcopy(d)
        api.audit(d)
        self.assertEqual(d, before)

    def test_missing_or_duplicate_animal_rejected(self):
        d = fixture();d["animals"].pop()
        with self.assertRaises(ValueError):api.audit(d)
        d = fixture();d["animals"][1]["animal_id"] = d["animals"][0]["animal_id"]
        with self.assertRaises(ValueError):api.audit(d)

    def test_missing_or_duplicate_fold_rejected(self):
        d = fixture();d["animals"][0]["folds"].pop()
        with self.assertRaises(ValueError):api.audit(d)
        d = fixture();d["animals"][0]["folds"][1]["fold_id"] = 0
        with self.assertRaises(ValueError):api.audit(d)

    def test_bool_and_nonintegral_indices_rejected(self):
        for value in [True, 0.5, float("nan"), float("inf"), -1, 5]:
            with self.subTest(value=value):
                d = fixture();d["animals"][0]["folds"][0]["companion_indices"][0] = value
                with self.assertRaises(ValueError):api.audit(d)

    def test_integral_companion_float_supported_but_native_requires_integer(self):
        d = fixture();d["animals"][0]["folds"][0]["companion_indices"] = [2., 0., 4., 1., 3.]
        self.assertTrue(first(d)["supplied_native_companion_equal"])
        d["animals"][0]["folds"][0]["native_indices"][0] = 2.
        with self.assertRaises(ValueError):api.audit(d)

    def test_sequence_extent_and_trial_bound_rejected(self):
        d = fixture();d["animals"][0]["folds"][0]["native_indices"].append(0)
        with self.assertRaises(ValueError):api.audit(d)
        for n in [0, True, api.MAX_TRIALS + 1]:
            d = fixture();d["animals"][0]["source_trial_count"] = n
            with self.assertRaises(ValueError):api.audit(d)

    def test_condition_bad_types_and_nonfinite_rejected(self):
        for value in [True, "1", float("nan"), float("inf"), 2**100]:
            d = fixture();d["animals"][0]["source_condition_pairs"] = [[value, 0]] * 5
            with self.assertRaises(ValueError):api.audit(d)

    def test_explicit_pairs_do_not_claim_entrypoint_CLI_equivalence(self):
        d = fixture([0, 0, 0]);a = d["animals"][0];a["source_condition_pairs"] = [[1, 0], [5, 0], [0, 5]]
        a["folds"][0]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[[0, 1]], entrypoint="fit")
        a["folds"][1]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[[1, 0]], entrypoint="analyze")
        fs = api.audit(d)["animals"][0]["folds"]
        self.assertEqual(fs[0]["partition_summary"]["selected_occurrences"], 0)
        self.assertEqual(fs[1]["partition_summary"]["selected_occurrences"], 3)
        self.assertTrue(all("CLI_condition_conversion_not_reproduced" in x["holds"] for x in fs))

    def test_duplicate_requested_pairs_are_preserved_and_inert(self):
        d = fixture();a = d["animals"][0];a["source_condition_pairs"] = [[1, 0]] * 5
        a["folds"][0]["configuration"].update(branch="condition_pairs", selected_condition_pairs=[[1, 0], [1, 0]])
        r = first(d)
        self.assertEqual(r["configuration"]["selected_condition_pairs"], [[1, 0], [1, 0]])
        self.assertEqual(rows(r), [2, 0, 4, 1, 3])

    def test_repeated_fold_zero_is_reported_not_repaired(self):
        r = first(fixture([0, 0, 0]))
        self.assertEqual(rows(r), [0, 0, 0])
        self.assertEqual(r["companion_mapping"]["omitted_source_ids"], [1, 2])
        self.assertEqual(r["partition_summary"]["overlap_source_ids"], [0])

    def test_one_trial_keeps_empty_training_and_full_roster(self):
        r = api.audit(fixture([0]))
        self.assertEqual(r["fold_count"], 21)
        for a in r["animals"]:
            for f in a["folds"]:
                self.assertEqual(f["partition_summary"]["training_occurrences"], 0)
                self.assertEqual(f["partition_summary"]["test_occurrences"], 1)

    def test_unknown_fields_and_branches_rejected(self):
        d = fixture();d["extra"] = 0
        with self.assertRaises(ValueError):api.audit(d)
        d = fixture();d["animals"][0]["folds"][0]["configuration"]["branch"] = "auto"
        with self.assertRaises(ValueError):api.audit(d)

    def test_no_condition_forbids_hidden_condition_list(self):
        d = fixture();d["animals"][0]["folds"][0]["configuration"]["selected_condition_pairs"] = [[1, 0]]
        with self.assertRaises(ValueError):api.audit(d)

    def test_claimed_historical_basis_does_not_authenticate_itself(self):
        d = fixture();d["animals"][0]["folds"][0]["configuration"]["basis"] = "supplied_historical_record"
        r = first(d)
        self.assertIn("historical_configuration_and_input_provenance_not_authenticated", r["holds"])
        self.assertFalse(r["historical_native_parity_authenticated"])

    def test_strict_JSON_duplicate_keys_nonfinite_and_byte_bound(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b' ' * (api.MAX_INPUT_BYTES + 1)]:
            with self.assertRaises(ValueError):api.parse_input(raw)
        d = fixture()
        self.assertEqual(api.parse_input(json.dumps(d).encode()), d)


if __name__ == "__main__":
    unittest.main()
