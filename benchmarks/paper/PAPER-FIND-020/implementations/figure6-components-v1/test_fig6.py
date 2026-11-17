"""Generated software controls; no authentic images, weights, or model calls."""

import importlib.util
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("fig6", Path(__file__).with_name("fig6.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class Figure6Controls(unittest.TestCase):
    def setUp(self):
        self.targets = [("first", 7), ("second", 4), ("last", 1)]
        self.conditions = [m.Condition("fit-1", "draw-1", 20, mode) for mode in sorted(m.MODES)]
        self.author = [(c, [("last", 9), ("first", 7), ("second", 4)]) for c in self.conditions]
        self.candidate = [(c, [("second", 2), ("last", 1), ("first", 7)]) for c in self.conditions]

    def test_paper_strict_signed_thresholds(self):
        self.assertTrue(m.like_to_like_eligible(0.011, 0.201))
        for w, r in [(0.01, 0.9), (1, 0.2), (-1, 0.9), (1, -0.9)]:
            self.assertFalse(m.like_to_like_eligible(w, r))
        for w, r in [(float("nan"), 1), (1, float("inf")), (1, 1.01), (True, 1)]:
            with self.assertRaises(ValueError):
                m.like_to_like_eligible(w, r)

    def test_accuracy_uses_all_images_and_ids(self):
        scored = m.score_curve(self.targets, self.conditions, self.author)
        for value in scored.values():
            self.assertEqual((value.correct, value.images), (2, 3))
            self.assertEqual(value.fraction, 2 / 3)

    def test_pairing_preserves_discordance_despite_equal_accuracy(self):
        for value in m.paired_differences(self.targets, self.conditions, self.author, self.candidate).values():
            self.assertEqual(value, dict(images=3, candidate_only_correct=1,
                author_only_correct=1, both_correct=1, both_wrong=0, accuracy_difference_fraction=0.0))

    def test_missing_extra_duplicate_image_ids_fail(self):
        bad_rows = [self.targets[:-1], self.targets + [("extra", 0)],
                    self.targets + [("first", 7)], [("first", 7), ("second", 4), ("substitution", 1)]]
        for rows in bad_rows:
            with self.assertRaises(ValueError):
                m.score_curve(self.targets, self.conditions, [(self.conditions[0], rows), self.author[1]])

    def test_empty_and_invalid_labels_fail(self):
        for rows in [[], [("x", True)], [("x", 1.0)], [("x", 10)], [("x", -1)], self.targets * 2]:
            with self.assertRaises(ValueError):
                m.score_curve(rows, self.conditions, self.author)

    def test_complete_control_conditions_required(self):
        for support, rows in [(self.conditions[:1], self.author[:1]),
                              (self.conditions * 2, self.author),
                              (self.conditions, self.author[:1]),
                              (self.conditions, self.author * 2)]:
            with self.assertRaises(ValueError):
                m.score_curve(self.targets, support, rows)

    def test_network_and_realization_are_not_pooled(self):
        more = [m.Condition("fit-2", "draw-1", 20, mode) for mode in sorted(m.MODES)]
        scored = m.score_curve(self.targets, self.conditions + more,
                              self.author + [(c, [(i, 0) for i, _ in self.targets]) for c in more])
        self.assertEqual(len(scored), 4)
        self.assertEqual([scored[c].correct for c in self.conditions + more], [2, 2, 0, 0])

    def test_condition_counts_cannot_be_rounded_or_negative(self):
        for count in [-1, 20.1, True]:
            with self.assertRaises(ValueError):
                m.Condition("fit-1", "draw-1", count, "like_to_like")


if __name__ == "__main__":
    unittest.main()
