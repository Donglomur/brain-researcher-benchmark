"""Generated software controls only; no MEG, fitted models, or source targets."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import (CONDITIONS, PARTICIPANTS, PIPELINES, FoldKey, Predictions,
                     ScoreError, Targets, compare_panel, pinned_sound_folds, score_fold)


TRAIN = np.array([0., .01])
TEST = np.array([-.01, 0., .01])
FOLDS = (0, 1, 2, 3, 4)


def prediction(ids, labels):
    values = np.broadcast_to(np.asarray(labels, dtype=np.int8)[:, None, None],
                             (len(ids), len(TRAIN), len(TEST))).copy()
    return Predictions(ids, TRAIN, TEST, values)


def fixture():
    """One 1-trial fold plus four 2-trial folds; every required panel identity."""
    rows = []
    for participant in PARTICIPANTS:
        for pipeline in PIPELINES:
            for condition in CONDITIONS:
                for fold in FOLDS:
                    # Deliberately unequal sizes: equal-fold candidate accuracy
                    # is 20%, whereas a pooled-trial implementation gives 1/9.
                    n = 1 if fold == 0 else 2
                    ids = tuple(f"f{fold}/event{i}" for i in range(n))
                    target = Targets(ids, np.ones(n, dtype=np.int8))
                    author = prediction(ids, np.full(n, 2))
                    candidate = prediction(ids, np.full(n, 1 if fold == 0 else 2))
                    rows.append((FoldKey(participant, pipeline, condition, fold), target, author, candidate))
    return rows


def compare(rows, *, frozen=None, **overrides):
    arguments = dict(stimulus="sound", train_times=TRAIN, test_times=TEST,
                     fold_ids=FOLDS,
                     frozen_trials={row[0]: row[1].trial_ids for row in rows} if frozen is None else frozen)
    arguments.update(overrides)
    return compare_panel(iter(rows), **arguments)


class ScoringTests(unittest.TestCase):
    def test_pinned_kfold_test_edges_are_not_returned_to_training(self):
        ids = tuple(f"event{i}" for i in range(27))
        folds = pinned_sound_folds(ids)
        # Independently enumerated KFold raw sizes 6,6,5,5,5 and source trims.
        wanted_test = ((0, 1, 2, 3, 4), (8, 9, 10), (14, 15), (19, 20), (24, 25, 26))
        wanted_removed = ((5,), (6, 7, 11), (12, 13, 16), (17, 18, 21), (22, 23))
        for fold, tested, removed in zip(folds, wanted_test, wanted_removed):
            self.assertEqual(fold.test_ids, tuple(ids[i] for i in tested))
            self.assertEqual(fold.boundary_excluded_ids, tuple(ids[i] for i in removed))
            self.assertFalse(set(fold.train_ids) & set(fold.test_ids + fold.boundary_excluded_ids))
            self.assertEqual(set(fold.train_ids + fold.test_ids + fold.boundary_excluded_ids), set(ids))
        self.assertEqual(sum(len(f.test_ids) for f in folds), 27 - 12)
        with self.assertRaisesRegex(ScoreError, "emptied"):
            pinned_sound_folds(tuple(f"event{i}" for i in range(10)))

    def test_confusion_and_ordinary_accuracy_from_independent_enumeration(self):
        ids = ("a", "b", "c", "d", "e")
        labels = np.array([1, 1, 2, 4, 4])
        guessed = prediction(ids, [1, 2, 2, 3, 4])
        guessed.labels[0, 1, 2] = 4
        result = score_fold(Targets(ids, labels), guessed, train_times=TRAIN, test_times=TEST)
        expected = np.zeros((2, 3, 4, 4), dtype=int)
        for trial, actual in enumerate(labels):
            for i in range(2):
                for j in range(3):
                    expected[i, j, actual - 1, guessed.labels[trial, i, j] - 1] += 1
        np.testing.assert_array_equal(result.confusion_counts, expected)
        np.testing.assert_array_equal(result.correct, expected.diagonal(axis1=2, axis2=3).sum(axis=-1))
        np.testing.assert_array_equal(result.confusion_counts.sum(axis=(-1, -2)), np.full((2, 3), 5))
        self.assertEqual(result.tested, 5)
        self.assertEqual(result.correct[0, 0], 3)  # 60%, not balanced-class accuracy
        np.testing.assert_array_equal(result.confusion_counts[:, :, 2], 0)  # absent true class retained

    def test_complete_panel_equal_fold_average_and_signed_paired_gain(self):
        result = compare(fixture())
        self.assertEqual(result["candidate_accuracy_percent"].shape, (33, 2, 4, 2, 3))
        np.testing.assert_allclose(result["candidate_accuracy_percent"], 20.)
        np.testing.assert_allclose(result["participant_gain_percentage_points"], 20.)
        np.testing.assert_allclose(result["group_gain_percentage_points"], 20.)
        np.testing.assert_allclose(result["participant_reconstruction_absolute_error_percentage_points"], 20.)
        np.testing.assert_array_equal(result["fold_test_counts"][0, 0, 0], [1, 2, 2, 2, 2])
        reversed_rows = [(key, target, candidate, author) for key, target, author, candidate in fixture()]
        negative = compare(reversed_rows)
        np.testing.assert_allclose(negative["participant_gain_percentage_points"], -20.)
        np.testing.assert_allclose(negative["group_mean_reconstruction_absolute_error_percentage_points"], 20.)
        self.assertIsNone(result["qualified_reward"])

    def test_group_unit_is_participant_and_temporal_cells_are_retained(self):
        rows = fixture()
        for index, (key, target, author, candidate) in enumerate(rows):
            if key.participant == PARTICIPANTS[0]:
                # Tenfold more trials must not give this participant tenfold
                # weight in the group map.
                ids = tuple(f"{trial}/copy{copy}" for trial in target.trial_ids for copy in range(10))
                target = replace(target, trial_ids=ids, labels=np.repeat(target.labels, 10))
                author = replace(author, trial_ids=ids, labels=np.repeat(author.labels, 10, axis=0))
                candidate = replace(candidate, trial_ids=ids, labels=np.repeat(candidate.labels, 10, axis=0))
                candidate.labels[:] = 1
                candidate.labels[:, 1, 2] = 2
                rows[index] = key, target, author, candidate
        result = compare(rows)
        self.assertAlmostEqual(result["group_candidate_accuracy_percent"][0, 0, 0, 0],
                               (100. + 32 * 20.) / 33)
        self.assertAlmostEqual(result["group_candidate_accuracy_percent"][0, 0, 1, 2], 32 * 20. / 33)

    def test_reproduction_error_cannot_cancel_between_participants(self):
        rows = fixture()
        for key, _, author, candidate in rows:
            author.labels[:] = 1
            candidate.labels[:] = 1
            if key.participant == PARTICIPANTS[0]:
                author.labels[:] = 2
            if key.participant == PARTICIPANTS[1]:
                candidate.labels[:] = 2
        result = compare(rows)
        np.testing.assert_allclose(result["group_gain_percentage_points"], 0.)
        np.testing.assert_allclose(result["group_mean_reconstruction_absolute_error_percentage_points"], 200. / 33)

    def test_wrong_trial_order_or_time_axis_refused_even_with_same_shape(self):
        ids = ("first", "second")
        target = Targets(ids, np.array([1, 2]))
        pred = prediction(ids, [1, 2])
        for wrong in (replace(pred, trial_ids=tuple(reversed(ids))),
                      replace(pred, train_times=TRAIN + .01),
                      replace(pred, test_times=TEST[::-1])):
            with self.subTest(wrong=wrong), self.assertRaises(ScoreError):
                score_fold(target, wrong, train_times=TRAIN, test_times=TEST)

    def test_invalid_tones_shape_and_duplicate_ids_refused(self):
        ids = ("x", "y")
        target = Targets(ids, np.array([1, 2]))
        pred = prediction(ids, [1, 2])
        invalid = (pred.labels.astype(float), pred.labels[:, 0],
                   np.full_like(pred.labels, 0), np.full_like(pred.labels, 5),
                   np.full_like(pred.labels, True, dtype=bool))
        for values in invalid:
            with self.subTest(dtype=values.dtype, shape=values.shape), self.assertRaises(ScoreError):
                score_fold(target, replace(pred, labels=values), train_times=TRAIN, test_times=TEST)
        with self.assertRaises(ScoreError):
            score_fold(replace(target, trial_ids=("x", "x")), pred, train_times=TRAIN, test_times=TEST)

    def test_missing_extra_duplicate_and_shortened_support_refused(self):
        rows = fixture()
        manifest = {row[0]: row[1].trial_ids for row in rows}
        for bad in (rows[:-1], rows + [rows[0]],
                    [(replace(rows[0][0], participant="invented"), *rows[0][1:])] + rows[1:]):
            with self.assertRaises(ScoreError):
                compare(bad, frozen=manifest)
        key, target, author, candidate = rows[1]
        shorter = (key, replace(target, trial_ids=target.trial_ids[:1], labels=target.labels[:1]),
                   replace(author, trial_ids=author.trial_ids[:1], labels=author.labels[:1]),
                   replace(candidate, trial_ids=candidate.trial_ids[:1], labels=candidate.labels[:1]))
        with self.assertRaisesRegex(ScoreError, "frozen trial manifest"):
            compare([rows[0], shorter] + rows[2:], frozen=manifest)

    def test_fold_overlap_refused_before_double_counting(self):
        rows = fixture()
        key, target, author, candidate = rows[1]
        overlapping = ("f0/event0", "f1/event1")
        rows[1] = (key, replace(target, trial_ids=overlapping), replace(author, trial_ids=overlapping),
                   replace(candidate, trial_ids=overlapping))
        with self.assertRaisesRegex(ScoreError, "more than one fold"):
            compare(rows)

    def test_sound_and_omission_are_not_pooled_or_silently_relabelled(self):
        with self.assertRaises(ScoreError):
            compare(fixture(), stimulus="sound_and_omission")
        with self.assertRaises(ScoreError):
            compare(fixture(), fold_ids=(0,))
        result = compare(fixture(), stimulus="omission")
        self.assertEqual(result["stimulus"], "omission")
        np.testing.assert_allclose(result["group_candidate_accuracy_percent"], 20.)


if __name__ == "__main__":
    unittest.main(verbosity=2)
