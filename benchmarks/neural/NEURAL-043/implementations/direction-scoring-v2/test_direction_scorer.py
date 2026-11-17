"""Generated software controls only; no authentic observations or targets."""
import copy
import math
import unittest

from direction_scorer import ScoringError, score_cohort, score_matched_features


def case(name, labels, predictions, mouse="mouse-A", width=16,
         claim="held_block_within_session", family="neural"):
    classes = ["direction-" + str(i) for i in range(width)]
    ids = [name + "-trial-" + str(i) for i in range(len(labels))]
    public = {"task": "NEURAL-043", "case_id": name, "classes": classes, "claim": claim,
              "feature_kind": family, "ids": ids}
    private = {"case_id": name, "ids": ids, "labels": [classes[i] for i in labels],
               "units": [mouse] * len(labels)}
    submission = {"case_id": name, "ids": ids, "classes": classes,
                  "probabilities": [[float(i == prediction) for i in range(width)] for prediction in predictions]}
    return submission, public, private


def evaluate(cases, expected=None, mode="frozen_program"):
    return score_cohort([c[0] for c in cases], [c[1] for c in cases], [c[2] for c in cases],
                        expected_case_ids=expected or [c[1]["case_id"] for c in cases], access_mode=mode)


class DirectionScorerControls(unittest.TestCase):
    def uneven(self):
        return [case("a1", [0, 0], [0, 0]), case("a2", [0, 1], [1, 1]),
                case("b1", [0, 1], [1, 0], mouse="mouse-B")]

    def test_pool_before_recall_and_equal_mouse_weight(self):
        # A has class recalls 2/3 and 1; B has 0 and 0. Thus 5/12,
        # whereas averaging blocks gives 1/2 and pooling all mice gives 1/2.
        row = evaluate(self.uneven())["strata"][0]
        self.assertAlmostEqual(row["balanced_accuracy"], 5 / 12)
        self.assertAlmostEqual(row["mouse_values"][0]["balanced_accuracy"], 5 / 6)
        self.assertEqual(row["mouse_values"][0]["class_support"], [3, 1] + [0] * 14)
        self.assertEqual(len(row["mouse_values"][0]["missing_classes"]), 14)
        self.assertAlmostEqual(row["log_loss"], (-math.log(1e-15) / 4 - math.log(1e-15)) / 2)
        # With two mice, the t distribution is Cauchy; its quantile has this
        # closed-form check independent of the scorer's scipy implementation.
        radius = math.tan(math.pi * (.975 - .5)) * (5 / 12)
        self.assertAlmostEqual(row["uncertainty"]["balanced_accuracy"]["ci95"][1], 5 / 12 + radius, places=8)

    def test_single_mouse_has_no_population_interval(self):
        row = evaluate([case("a", [0, 1], [0, 1])])["strata"][0]
        self.assertEqual(row["balanced_accuracy"], 1)
        self.assertIsNone(row["uncertainty"]["balanced_accuracy"])

    def test_separate_layouts_and_claims(self):
        cases = [case("a", [0], [0]), case("b", [0], [0], width=25),
                 case("c", [0], [0], claim="held_mouse_anatomical_alignment")]
        result = evaluate(cases)
        self.assertEqual(len(result["strata"]), 3)
        self.assertFalse(result["unlike_class_spaces_pooled"])

    def test_all_modes_retained_without_delivery_claim(self):
        for mode in ("direct_observation", "typed_viewer", "tool_assisted", "frozen_program"):
            result = evaluate([case("a", [0], [0])], mode=mode)
            self.assertEqual(result["access_mode"], mode)
            self.assertFalse(result["access_mode_delivery_verified"])
            self.assertFalse(result["scientific_qualification"])
        with self.assertRaisesRegex(ScoringError, "access mode"):
            evaluate([case("a", [0], [0])], mode="unspecified")

    def test_case_lists_join_by_identity(self):
        a, b = case("a", [0], [0]), case("b", [1], [1])
        result = score_cohort([b[0], a[0]], [a[1], b[1]], [b[2], a[2]],
                              expected_case_ids=["a", "b"], access_mode="frozen_program")
        self.assertEqual(result["strata"][0]["balanced_accuracy"], 1)

    def test_compensating_private_lengths_rejected(self):
        # Legacy cohort concatenation allowed 0 + 2 labels against 1 + 1 IDs.
        a, b = case("a", [0], [0]), case("b", [1], [1])
        a[2]["labels"] = []
        b[2]["labels"] = ["direction-0", "direction-1"]
        with self.assertRaises(ScoringError):
            evaluate([a, b])

    def test_compensating_private_unit_counts_rejected(self):
        a, b = case("a", [0, 1], [0, 1]), case("b", [0, 1], [0, 1])
        a[2]["units"].pop()
        b[2]["units"].append("mouse-A")
        with self.assertRaisesRegex(ScoringError, "per-case"):
            evaluate([a, b])

    def test_private_case_identity_required(self):
        a = case("a", [0], [0])
        a[2]["case_id"] = "wrong-case"
        with self.assertRaises(ScoringError):
            evaluate([a])

    def test_complete_expected_roster_required(self):
        with self.assertRaisesRegex(ScoringError, "complete expected"):
            evaluate([case("a", [0], [0])], expected=["a", "missing-failed-case"])
        with self.assertRaisesRegex(ScoringError, "duplicate"):
            evaluate([case("a", [0], [0]), case("a", [0], [0])], expected=["a"])

    def test_exact_trial_order_and_duplicate_trial_checks(self):
        a = case("a", [0, 1], [0, 1])
        a[0]["ids"] = list(reversed(a[0]["ids"]))
        with self.assertRaisesRegex(ScoringError, "ID/order"):
            evaluate([a])
        a, b = case("a", [0], [0]), case("b", [0], [0])
        for packet in b:
            packet["ids"] = a[1]["ids"][:]
        with self.assertRaisesRegex(ScoringError, "duplicate held-out"):
            evaluate([a, b])

    def test_shared_trial_across_tracks_requires_identical_truth(self):
        a = case("a", [0], [0])
        b = case("b", [0], [0], claim="held_mouse_anatomical_alignment")
        for packet in b:
            packet["ids"] = a[1]["ids"][:]
        self.assertEqual(len(evaluate([a, b])["strata"]), 2)
        b[2]["labels"] = ["direction-1"]
        with self.assertRaisesRegex(ScoringError, "inconsistent target"):
            evaluate([a, b])

    def test_class_space_order_and_mouse_unit_checks(self):
        a = case("a", [0], [0])
        a[1]["classes"] = a[1]["classes"][:2]
        with self.assertRaisesRegex(ScoringError, "16 or 25"):
            evaluate([a])
        a, b = case("a", [0], [0]), case("b", [0], [0])
        b[0]["classes"] = b[1]["classes"] = list(reversed(b[1]["classes"]))
        with self.assertRaisesRegex(ScoringError, "within native layout"):
            evaluate([a, b])
        a = case("a", [0, 1], [0, 1])
        a[2]["units"][1] = "mouse-B"
        with self.assertRaisesRegex(ScoringError, "one mouse"):
            evaluate([a])

    def test_probability_failures_and_constant_control(self):
        for value in (True, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value):
                a = case("a", [0], [0])
                a[0]["probabilities"][0][0] = value
                with self.assertRaises(ScoringError):
                    evaluate([a])
        for row in ([0.] * 16, [1.] * 15):
            a = case("a", [0], [0])
            a[0]["probabilities"] = [row]
            with self.assertRaises(ScoringError):
                evaluate([a])
        a = case("a", [0, 1], [0, 0])
        a[0]["probabilities"] = [[1 / 16] * 16] * 2
        score = evaluate([a])["strata"][0]
        self.assertEqual(score["balanced_accuracy"], .5)
        self.assertAlmostEqual(score["log_loss"], math.log(16))

    def matched(self):
        cases = self.uneven()
        public, submissions = {}, {}
        for family in ("history_time", "neural", "neural_history_time"):
            public[family] = copy.deepcopy([c[1] for c in cases])
            submissions[family] = copy.deepcopy([c[0] for c in cases])
            for packet, submission, original in zip(public[family], submissions[family], cases):
                packet["feature_kind"] = family
                if family != "neural":
                    predictions = ([0] * len(packet["ids"]) if family == "history_time"
                                   else [packet["classes"].index(label) for label in original[2]["labels"]])
                    submission["probabilities"] = [[float(i == prediction) for i in range(16)] for prediction in predictions]
        return submissions, public, [c[2] for c in cases]

    def test_paired_mouse_differences(self):
        submissions, public, private = self.matched()
        result = score_matched_features(submissions, public, private,
                                       expected_case_ids=["a1", "a2", "b1"], access_mode="tool_assisted")
        neural, combined = result["paired_differences"]
        self.assertAlmostEqual(neural["balanced_accuracy"], -1 / 12)
        self.assertAlmostEqual(neural["mouse_differences"][0]["balanced_accuracy"], 1 / 3)
        self.assertEqual(neural["mouse_differences"][1]["balanced_accuracy"], -.5)
        self.assertEqual(combined["balanced_accuracy"], .5)
        self.assertLess(combined["log_loss"], 0)

    def test_paired_matching_cannot_drop_or_exchange_trials(self):
        submissions, public, private = self.matched()
        public["neural"][0]["ids"] = ["different-trial", "another-trial"]
        with self.assertRaisesRegex(ScoringError, "identical held trials"):
            score_matched_features(submissions, public, private,
                                   expected_case_ids=["a1", "a2", "b1"], access_mode="frozen_program")
        submissions, public, private = self.matched()
        del submissions["history_time"]
        with self.assertRaisesRegex(ScoringError, "three matched"):
            score_matched_features(submissions, public, private,
                                   expected_case_ids=["a1", "a2", "b1"], access_mode="frozen_program")


if __name__ == "__main__":
    unittest.main(verbosity=2)
