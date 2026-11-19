"""Generated source controls for private fixed-Generic classification grading.

These controls use the shared generated 94-person/188-row fixture. They perform
no scientific fitting, feature production, original-data reads or artifact writes.
Their existence is not execution evidence. The outer source-check runner owns
module paths and execution authority.
"""

from copy import deepcopy
from fractions import Fraction
import unittest

import classification_grading as grading
import generic_contract as contract
from generic_fixture import fixture


REFERENCE_ARM = "author-batch-range-logistic-reference-v1"
ORIENTATION = ["Category_Selective", "Prefrontal_Cortex"]
EXPECTED_MEAN = Fraction(1157, 1800)
EXPECTED_VARIANCE = Fraction(28501, 3240000)


def fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def reference_report(data):
    selected = [report for report in data["reference"]["results"]
                if report["arm"] == REFERENCE_ARM and report["orientation"] == ORIENTATION]
    if len(selected) != 1:
        raise AssertionError("shared fixture must have one selected reference report")
    return selected[0]


def evaluate(data):
    return grading.grade_classification(data["arms"], data["reference"], data["binding"])


class ClassificationGradingControls(unittest.TestCase):
    def setUp(self):
        self.data = deepcopy(fixture())

    def assertRejected(self, data):
        with self.assertRaises(grading.ClassificationGradingError):
            evaluate(data)

    def choose_row(self, *, correct):
        arm = self.data["arms"]["A"]
        for row in arm["observations"]:
            probability = arm["probabilities_object"][row["id"]]
            prediction = "object" if probability > 0.5 else "face"
            if (prediction == row["label"]) == correct:
                return row
        self.fail("generated reference fixture must contain correct and incorrect predictions")

    def fold_size(self, row):
        return sum(observation["fold"] == row["fold"]
                   for observation in self.data["arms"]["A"]["observations"])

    def test_exact_reference_baseline_outcomes_and_scope(self):
        result = evaluate(self.data)
        self.assertEqual(result["input_mode"], "generic_feature_classification_v1")
        self.assertEqual(result["scope"]["input_mode"], result["input_mode"])
        self.assertEqual(result["scope"]["reference_preprocessing_arm"], REFERENCE_ARM)
        self.assertEqual(result["reference_selector"], {"arm": REFERENCE_ARM, "orientation": ORIENTATION})
        self.assertEqual(result["source_inventory_sha256"], self.data["reference"]["input_sha256"])
        self.assertEqual((result["observations_per_arm"], result["participants"], result["folds"]),
                         (188, 94, 10))
        for name, score in (("reference", result["reference"]), *result["arms"].items()):
            with self.subTest(score=name):
                self.assertEqual(fraction(score["mean_fold_accuracy_exact"]), EXPECTED_MEAN)
                self.assertEqual(fraction(score["population_fold_variance_exact"]), EXPECTED_VARIANCE)
                self.assertEqual(fraction(score["paper_mean_difference_exact"]),
                                 EXPECTED_MEAN - Fraction(643, 1000))
                self.assertAlmostEqual(score["paper_sd_difference"],
                                       float(EXPECTED_VARIANCE) ** 0.5 - 47 / 500, places=15)
                self.assertIs(score["valid_same_case_evaluation"], True)
                self.assertIs(score["published_precision_numerical_reproduction"], True)
                self.assertIs(score["reference_score_exceeded"], False)
                self.assertIsNone(score["scientific_superiority_established"])
                self.assertEqual(fraction(score["candidate_minus_reference_mean_exact"]), 0)
                self.assertEqual(score["hard_prediction_disagreements"], 0)
                self.assertEqual(score["participant_effect_counts"],
                                 {"improved": 0, "unchanged": 94, "worsened": 0})
                self.assertEqual(fraction(score["probability_discrepancies"]["maximum_absolute_exact"]), 0)
                self.assertEqual(fraction(score["probability_discrepancies"]["mean_absolute_exact"]), 0)
                for field in ("raw_feature_reproduction", "distributional_equivalence",
                              "auc_qualification", "whole_paper_reproduction"):
                    self.assertIsNone(score[field])
        self.assertEqual(fraction(result["B_minus_A_mean_fold_accuracy_exact"]), 0)
        self.assertFalse(result["external_reference_authentication_performed_here"])

    def test_shared_contract_produces_the_exact_binding(self):
        self.assertEqual(self.data["binding"], contract.reference_binding(self.data["panel"]))
        self.assertEqual(self.data["binding"]["truth_encoding"], "face_object_strings")
        self.assertEqual(self.data["binding"]["input_mode"], "generic_feature_classification_v1")

    def test_published_precision_lower_edges_are_inclusive_upper_edges_exclusive(self):
        mean_lower, mean_upper = Fraction(257, 400), Fraction(1287, 2000)
        variance_lower, variance_upper = Fraction(187, 2000) ** 2, Fraction(189, 2000) ** 2
        epsilon = Fraction(1, 10**12)
        cases = [
            (mean_lower, variance_lower, True),
            (mean_upper - epsilon, variance_upper - epsilon, True),
            (mean_lower - epsilon, variance_lower, False),
            (mean_lower, variance_lower - epsilon, False),
            (mean_upper, variance_lower, False),
            (mean_lower, variance_upper, False),
            (mean_upper, variance_upper, False),
        ]
        for mean, variance, expected in cases:
            with self.subTest(mean=mean, variance=variance):
                self.assertIs(grading._published_precision({"mean": mean, "variance": variance}), expected)

    def test_one_corrected_error_has_exact_fold_weighted_delta_and_paired_effect(self):
        row = self.choose_row(correct=False)
        fold_size = self.fold_size(row)
        old_probability = self.data["arms"]["A"]["probabilities_object"][row["id"]]
        new_probability = 0.51 if row["label"] == "object" else 0.49
        self.data["arms"]["A"]["probabilities_object"][row["id"]] = new_probability
        result = evaluate(self.data)
        score = result["arms"]["A"]
        self.assertIs(score["reference_score_exceeded"], True)
        self.assertIsNone(score["scientific_superiority_established"])
        self.assertEqual(fraction(score["candidate_minus_reference_mean_exact"]), Fraction(1, 10 * fold_size))
        self.assertEqual(fraction(result["B_minus_A_mean_fold_accuracy_exact"]), Fraction(-1, 10 * fold_size))
        self.assertEqual(score["hard_prediction_disagreements"], 1)
        self.assertEqual(score["participant_effect_counts"], {"improved": 1, "unchanged": 93, "worsened": 0})
        self.assertEqual(result["arms"]["B"]["participant_effect_counts"],
                         {"improved": 0, "unchanged": 94, "worsened": 0})
        changed_folds = [entry for entry in score["fold_comparisons"] if entry["correct_difference"]]
        self.assertEqual(len(changed_folds), 1)
        self.assertEqual(changed_folds[0]["fold"], row["fold"])
        self.assertEqual(changed_folds[0]["correct_difference"], 1)
        self.assertEqual(fraction(changed_folds[0]["accuracy_difference_exact"]), Fraction(1, fold_size))
        self.assertTrue(all(entry["observation_count_difference"] == 0 for entry in score["fold_comparisons"]))
        changed_people = [entry for entry in score["participant_paired_effects"] if entry["correct_difference"]]
        self.assertEqual(len(changed_people), 1)
        self.assertEqual(changed_people[0]["participant"], row["participant"])
        self.assertEqual(changed_people[0]["correct_difference"], 1)
        self.assertEqual(fraction(changed_people[0]["accuracy_difference_exact"]), Fraction(1, 2))
        discrepancy = abs(Fraction(new_probability) - Fraction(old_probability))
        self.assertEqual(fraction(score["probability_discrepancies"]["maximum_absolute_exact"]), discrepancy)
        self.assertEqual(fraction(score["probability_discrepancies"]["mean_absolute_exact"]), discrepancy / 188)

    def test_one_new_error_is_negative_and_not_reference_exceedance(self):
        row = self.choose_row(correct=True)
        fold_size = self.fold_size(row)
        self.data["arms"]["A"]["probabilities_object"][row["id"]] = (
            0.49 if row["label"] == "object" else 0.51)
        score = evaluate(self.data)["arms"]["A"]
        self.assertEqual(fraction(score["candidate_minus_reference_mean_exact"]), Fraction(-1, 10 * fold_size))
        self.assertIs(score["reference_score_exceeded"], False)
        self.assertEqual(score["participant_effect_counts"], {"improved": 0, "unchanged": 93, "worsened": 1})
        changed = [entry for entry in score["participant_paired_effects"] if entry["correct_difference"]]
        self.assertEqual([(entry["participant"], entry["correct_difference"],
                           fraction(entry["accuracy_difference_exact"])) for entry in changed],
                         [(row["participant"], -1, Fraction(-1, 2))])

    def test_exact_half_predicts_face_for_both_truth_classes(self):
        for label, direction in (("face", -1), ("object", 1)):
            with self.subTest(label=label):
                row = next(row for row in self.data["arms"]["A"]["observations"] if row["label"] == label)
                tied, above, below = deepcopy(self.data), deepcopy(self.data), deepcopy(self.data)
                tied["arms"]["A"]["probabilities_object"][row["id"]] = 0.5
                above["arms"]["A"]["probabilities_object"][row["id"]] = 0.5000000000000001
                below["arms"]["A"]["probabilities_object"][row["id"]] = 0.49999999999999994
                tie_score = evaluate(tied)["arms"]["A"]
                above_score = evaluate(above)["arms"]["A"]
                below_score = evaluate(below)["arms"]["A"]
                self.assertEqual(fraction(above_score["mean_fold_accuracy_exact"])
                                 - fraction(tie_score["mean_fold_accuracy_exact"]),
                                 Fraction(direction, 10 * self.fold_size(row)))
                self.assertEqual(tie_score["mean_fold_accuracy_exact"], below_score["mean_fold_accuracy_exact"])
                self.assertEqual(tie_score["participant_paired_effects"], below_score["participant_paired_effects"])

    def test_reference_and_candidate_order_are_joined_by_identity(self):
        original = evaluate(self.data)
        self.data["arms"]["A"]["observations"].reverse()
        rows = self.data["arms"]["B"]["observations"]
        self.data["arms"]["B"]["observations"] = rows[37:] + rows[:37]
        self.data["reference"]["results"].reverse()
        reference_report(self.data)["predictions"].reverse()
        self.data["binding"]["rows"] = dict(reversed(list(self.data["binding"]["rows"].items())))
        for role in ("A", "B"):
            self.data["arms"][role]["probabilities_object"] = dict(
                reversed(list(self.data["arms"][role]["probabilities_object"].items())))
        self.assertEqual(evaluate(self.data), original)

    def test_missing_extra_or_repeated_candidate_support_is_rejected(self):
        for mutation in ("missing_observation", "duplicate_observation", "missing_probability", "extra_probability"):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                arm = data["arms"]["A"]
                if mutation == "missing_observation":
                    arm["observations"].pop()
                elif mutation == "duplicate_observation":
                    arm["observations"][0] = deepcopy(arm["observations"][1])
                elif mutation == "missing_probability":
                    arm["probabilities_object"].pop(arm["observations"][0]["id"])
                else:
                    arm["probabilities_object"]["unexpected-row"] = 0.5
                self.assertRejected(data)

    def test_invalid_probabilities_are_rejected(self):
        identifier = self.data["arms"]["A"]["observations"][0]["id"]
        for probability in (True, False, "0.5", None, -0.01, 1.01, float("nan"), float("inf"), -float("inf")):
            with self.subTest(probability=probability):
                data = deepcopy(self.data)
                data["arms"]["A"]["probabilities_object"][identifier] = probability
                self.assertRejected(data)

    def test_invalid_or_cross_participant_folds_are_rejected(self):
        for fold in (True, -1, 10, "0", 0.0):
            with self.subTest(fold=fold):
                data = deepcopy(self.data)
                data["arms"]["A"]["observations"][0]["fold"] = fold
                self.assertRejected(data)
        data = deepcopy(self.data)
        row = data["arms"]["A"]["observations"][0]
        row["fold"] = (row["fold"] + 1) % 10
        self.assertRejected(data)

    def test_reference_case_metadata_must_match_the_explicit_binding(self):
        for field, replacement in (("participant", "not-the-bound-participant"), ("fold", None), ("truth", None)):
            with self.subTest(field=field):
                data = deepcopy(self.data)
                row = reference_report(data)["predictions"][0]
                if field == "fold":
                    replacement = (row["fold"] + 1) % 10
                elif field == "truth":
                    replacement = "face" if row["truth"] == "object" else "object"
                row[field] = replacement
                self.assertRejected(data)

    def test_reference_support_must_be_complete_and_unique(self):
        for mutation in ("missing", "duplicate", "unknown_key", "missing_field"):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                rows = reference_report(data)["predictions"]
                if mutation == "missing":
                    rows.pop()
                elif mutation == "duplicate":
                    rows[0] = deepcopy(rows[1])
                elif mutation == "unknown_key":
                    rows[0]["row_key"] = "unknown-reference-row"
                else:
                    rows[0].pop("p_object")
                self.assertRejected(data)

    def test_wrong_or_ambiguous_reference_selector_is_rejected(self):
        for mutation in ("arm", "orientation", "duplicate", "schema", "status"):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                report = reference_report(data)
                if mutation == "arm":
                    report["arm"] = "different-reference-arm"
                elif mutation == "orientation":
                    report["orientation"] = list(reversed(ORIENTATION))
                elif mutation == "duplicate":
                    data["reference"]["results"].append(deepcopy(report))
                elif mutation == "schema":
                    data["reference"]["schema"] = "different-schema"
                else:
                    data["reference"]["status"] = "failed"
                self.assertRejected(data)

    def test_source_inventory_hash_and_mode_are_required(self):
        for invalid in (None, "", "0" * 63, "A" * 64, "g" * 64):
            with self.subTest(invalid=invalid):
                data = deepcopy(self.data)
                data["binding"]["source_inventory_sha256"] = invalid
                self.assertRejected(data)
        data = deepcopy(self.data)
        old = data["reference"]["input_sha256"]
        data["reference"]["input_sha256"] = ("1" if old[0] == "0" else "0") + old[1:]
        self.assertRejected(data)
        data = deepcopy(self.data)
        data["binding"].pop("source_inventory_sha256")
        self.assertRejected(data)
        data = deepcopy(self.data)
        data["binding"]["input_mode"] = "raw_window_programme_v1"
        self.assertRejected(data)

    def test_raw_namespace_cannot_enter_fixed_generic_grading(self):
        data = deepcopy(self.data)
        old_id = data["arms"]["A"]["observations"][0]["id"]
        raw_id = old_id.replace("|Generic|", "|Raw|")
        self.assertNotEqual(old_id, raw_id)
        for role in ("A", "B"):
            arm = data["arms"][role]
            row = next(row for row in arm["observations"] if row["id"] == old_id)
            row["id"] = raw_id
            arm["probabilities_object"][raw_id] = arm["probabilities_object"].pop(old_id)
        data["binding"]["rows"][raw_id] = data["binding"]["rows"].pop(old_id)
        self.assertRejected(data)

    def test_binding_row_keys_must_be_bijective_and_metadata_exact(self):
        identifiers = list(self.data["binding"]["rows"])
        for mutation in ("duplicate_key", "swapped_keys", "fold", "missing_source"):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                rows = data["binding"]["rows"]
                first, second = rows[identifiers[0]], rows[identifiers[1]]
                if mutation == "duplicate_key":
                    first["row_key"] = second["row_key"]
                elif mutation == "swapped_keys":
                    first["row_key"], second["row_key"] = second["row_key"], first["row_key"]
                elif mutation == "fold":
                    first["fold"] = (first["fold"] + 1) % 10
                else:
                    rows.pop(identifiers[0])
                self.assertRejected(data)

    def test_reference_truth_encoding_is_strict_without_bool_or_string_coercion(self):
        for truth in (True, False, 0, 1, "0", "1", None):
            with self.subTest(encoding="face_object_strings", truth=truth):
                data = deepcopy(self.data)
                reference_report(data)["predictions"][0]["truth"] = truth
                self.assertRejected(data)
        for truth in (True, False, "0", "1", 0.0, 1.0, None):
            with self.subTest(encoding="integer_face0_object1", truth=truth):
                data = deepcopy(self.data)
                data["binding"]["truth_encoding"] = "integer_face0_object1"
                rows = reference_report(data)["predictions"]
                for row in rows:
                    row["truth"] = 1 if row["truth"] == "object" else 0
                rows[0]["truth"] = truth
                self.assertRejected(data)

    def test_reference_aggregate_metrics_and_stored_predictions_cannot_drive_scores(self):
        expected = evaluate(self.data)
        report = reference_report(self.data)
        report["metrics"] = {"accuracy": 1.0, "accuracy_SD": 0.0,
                             "paper_reproduction_success": False, "reference_score_exceeded": True}
        for row in report["predictions"]:
            row["prediction"] = "face" if row["p_object"] > 0.5 else "object"
        self.assertEqual(evaluate(self.data), expected)

    def test_candidate_self_reported_metrics_are_rejected(self):
        for field in ("metrics", "accuracy", "paper_reproduction_success", "reference_score_exceeded"):
            with self.subTest(field=field):
                data = deepcopy(self.data)
                data["arms"]["A"][field] = 1
                self.assertRejected(data)

    def test_altered_reference_probabilities_cannot_pass_bound_reference_summary(self):
        data = deepcopy(self.data)
        rows = reference_report(data)["predictions"]
        row = rows[0]
        row["p_object"] = 0.49 if row["p_object"] > 0.5 else 0.51
        self.assertRejected(data)

    def test_grading_does_not_mutate_private_inputs(self):
        before = deepcopy(self.data)
        evaluate(self.data)
        self.assertEqual(self.data, before)


if __name__ == "__main__":
    unittest.main()
