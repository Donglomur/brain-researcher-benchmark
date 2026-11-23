"""Generated support and algebraic checks; no authentic CA1 observations."""
import copy
from collections import Counter
import itertools
import unittest

from decoder_information import (KEYS, RUNS, TASK_ID, confusion_counts, digest,
                                 evaluate, score_fold)


def fixture(fold_count=2):
    support = {"schema_version": 1, "task_id": TASK_ID,
               "data_kind": "generated_engineering_control",
               "outer_fold_count": fold_count, "label_order": list(range(12)), "sessions": []}
    submission = {"schema_version": 1, "task_id": TASK_ID, "folds": []}
    for s in range(11):
        ids = [f"sample{i}" for i in range(4 * fold_count)]
        session = {"session_id": f"session{s}", "animal_id": f"animal{s % 7}",
                   "sample_ids": ids, "targets": [i % 2 for i in range(len(ids))], "runs": []}
        for kernel, condition, repeat in sorted(RUNS):
            run = {"kernel": kernel, "condition": condition, "conditional_shuffle": repeat, "folds": []}
            for f in range(fold_count):
                own = ids[4*f:4*f+4]
                fold = {"fold_id": f"fold{f}", "sample_ids": own,
                        "null_orders": [{"prediction": [0, 1, 2, 3], "target": [0, 2, 1, 3]}
                                        for _ in range(30)]}
                run["folds"].append(fold)
                key = (session["session_id"], kernel, condition, repeat, fold["fold_id"])
                submission["folds"].append({**dict(zip(KEYS, key)),
                    "predictions": [{"sample_id": sample, "label": i % 2} for i, sample in enumerate(own)]})
            session["runs"].append(run)
        support["sessions"].append(session)
    submission["support_sha256"] = digest(support)
    return support, submission


class DecoderInformationTests(unittest.TestCase):
    def test_perfect_decoding_with_zero_information_null(self):
        orders = [{"prediction": [0, 1, 2, 3], "target": [0, 2, 1, 3]} for _ in range(30)]
        result = score_fold([0, 1, 0, 1], [0, 1, 0, 1], list(range(12)), orders)
        self.assertEqual(result["plugin_bits"], 1.0)
        self.assertEqual(result["null_plugin_bits"], [0.0] * 30)
        self.assertEqual(result["shuffsub_bits"], 1.0)
        self.assertEqual(sum(map(sum, result["confusion_counts"])), 4)
        self.assertEqual(result["confusion_counts"][11], [0] * 12)

    def test_both_permutation_streams_are_applied_and_negative_is_retained(self):
        orders = [{"prediction": [0, 2, 1, 3], "target": [1, 0, 3, 2]} for _ in range(30)]
        result = score_fold([0, 1, 0, 1], [0, 0, 1, 1], [0, 1], orders)
        self.assertEqual(result["plugin_bits"], 0.0)
        self.assertEqual(result["null_plugin_bits"], [1.0] * 30)
        self.assertEqual(result["shuffsub_bits"], -1.0)
        self.assertEqual(result["null_confusion_counts"][0], [[0, 2], [2, 0]])

    def test_exact_binary_noisy_channel(self):
        import math
        targets, predictions = [], []
        for target, prediction in itertools.product((0, 1), repeat=2):
            count = 3 if target == prediction else 1
            targets.extend([target] * count)
            predictions.extend([prediction] * count)
        orders = [{"prediction": list(range(8)), "target": list(range(8))} for _ in range(30)]
        result = score_fold(targets, predictions, [1, 0], orders)
        entropy = -0.25 * math.log2(0.25) - 0.75 * math.log2(0.75)
        self.assertAlmostEqual(result["plugin_bits"], 1 - entropy)
        self.assertEqual(result["shuffsub_bits"], 0.0)

    def test_explicit_class_order_and_confusion_orientation(self):
        self.assertEqual(confusion_counts([2, 2, 7], [7, 7, 7], [7, 2, 4]),
                         [[1, 0, 0], [2, 0, 0], [0, 0, 0]])

    def test_complete_panel_and_prediction_id_join(self):
        support, submission = fixture()
        for row in submission["folds"]:
            row["predictions"].reverse()
        result = evaluate(support, submission)
        self.assertEqual(len(result["folds"]), 132)
        self.assertEqual({r["shuffsub_bits"] for r in result["folds"]}, {1.0})
        self.assertEqual(Counter(r["condition"] for r in result["folds"]),
                         {"real": 44, "conditionally_shuffled": 88})
        self.assertIsNone(result["aggregate"])
        self.assertEqual(result["scientific_qualification"], "unknown")

    def test_fivefold_and_run_specific_membership_remain_explicit(self):
        support, submission = fixture(5)
        # A second decoder run may partition the same session differently.
        run = support["sessions"][0]["runs"][1]
        run["folds"][0]["sample_ids"], run["folds"][1]["sample_ids"] = (
            run["folds"][1]["sample_ids"], run["folds"][0]["sample_ids"])
        submission["folds"][5]["predictions"], submission["folds"][6]["predictions"] = (
            submission["folds"][6]["predictions"], submission["folds"][5]["predictions"])
        submission["support_sha256"] = digest(support)
        result = evaluate(support, submission)
        self.assertEqual(len(result["folds"]), 330)
        self.assertEqual(result["outer_fold_count"], 5)

    def test_missing_or_duplicate_fold_rejected(self):
        for mutate in (lambda rows: rows.pop(), lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0]))):
            support, submission = fixture()
            mutate(submission["folds"])
            with self.assertRaises(ValueError):
                evaluate(support, submission)

    def test_missing_duplicate_or_foreign_prediction_rejected(self):
        for mutation in ("missing", "duplicate", "foreign", "boolean_label"):
            support, submission = fixture()
            rows = submission["folds"][0]["predictions"]
            if mutation == "missing": rows.pop()
            elif mutation == "duplicate": rows[1] = copy.deepcopy(rows[0])
            elif mutation == "foreign": rows[0]["sample_id"] = "absent"
            else: rows[0]["label"] = True
            with self.assertRaises(ValueError):
                evaluate(support, submission)

    def test_support_mutation_is_rejected(self):
        support, submission = fixture()
        support["sessions"][0]["targets"][0] = 1
        with self.assertRaisesRegex(ValueError, "bound"):
            evaluate(support, submission)

    def test_incomplete_population_or_conditional_controls_rejected(self):
        for mutate in (lambda s: s["sessions"].pop(),
                       lambda s: s["sessions"][0]["runs"].pop(),
                       lambda s: s["sessions"][6].__setitem__("animal_id", "animal1")):
            support, submission = fixture()
            mutate(support)
            submission["support_sha256"] = digest(support)
            with self.assertRaises(ValueError):
                evaluate(support, submission)

    def test_overlapping_outer_folds_rejected(self):
        support, submission = fixture()
        folds = support["sessions"][0]["runs"][0]["folds"]
        folds[1]["sample_ids"][0] = folds[0]["sample_ids"][0]
        submission["support_sha256"] = digest(support)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            evaluate(support, submission)

    def test_wrong_null_count_and_invalid_permutations_rejected(self):
        for mutation in ("count", "duplicate", "boolean", "missing_stream"):
            support, submission = fixture()
            nulls = support["sessions"][0]["runs"][0]["folds"][0]["null_orders"]
            if mutation == "count": nulls.pop()
            elif mutation == "duplicate": nulls[0]["prediction"] = [0, 0, 2, 3]
            elif mutation == "boolean": nulls[0]["target"][0] = False
            else: del nulls[0]["target"]
            submission["support_sha256"] = digest(support)
            with self.assertRaises(ValueError):
                evaluate(support, submission)


if __name__ == "__main__":
    unittest.main()
