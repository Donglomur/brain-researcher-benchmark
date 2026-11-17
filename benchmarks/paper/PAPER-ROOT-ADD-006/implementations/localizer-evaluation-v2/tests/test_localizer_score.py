"""Generated arithmetic controls, never an authentic-data reproduction."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import localizer_score as s


def labels():
    return np.repeat(np.arange(1, 8), 60)


def packet(base):
    y = labels()
    author = np.zeros((420, 1, 2, 3))
    author[..., 0] = 1
    candidate = np.zeros_like(author)
    for i, c in enumerate(y):
        candidate[i, :, :, (c - 1) % 3] = 1
    for name, a in [("author", author), ("candidate", candidate)]:
        np.save(base / f"{name}.npy", a, allow_pickle=False)
    m = {"schema": "localizer-score/v2", "source_revision": s.SOURCE_REVISION,
         "input_kind": "generated_control", "train_ms": [0], "test_ms": [0, 10],
         "fold_count": 5, "participants": []}
    for person in s.COHORT:
        row = {"participant_id": person, "trial_ids": [f"trial-{k}" for k in range(420)],
               "image_class": y.tolist(), "fold_id": np.tile(np.repeat(np.arange(1, 6), 12), 7).tolist()}
        binding = dict(row, train_ms=m["train_ms"], test_ms=m["test_ms"], fold_count=m["fold_count"])
        order_hash = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for name in ("author", "candidate"):
            path = base / f"{name}.npy"
            row[f"{name}_logits"] = {"path": path.name, "sha256": s.digest(path),
                                     "trial_order_sha256": order_hash}
        m["participants"].append(row)
    path = base / "manifest.json"
    path.write_text(json.dumps(m))
    return path, m


class OriginalAccuracy(unittest.TestCase):
    def test_three_outcome_competition_excludes_untrained_channels_and_choice_trials(self):
        a = np.zeros((420, 1, 1, 7))
        a[..., :3] = [-3, -2, -1]
        result = s.score_participant(a, labels(), [0], [0])
        # Correct only for O3: 60 / 180. A seven-channel argmax scores zero.
        self.assertAlmostEqual(result["accuracy"][0, 0], 1 / 3)
        np.testing.assert_array_equal(result["by_class_accuracy"][:, 0, 0], [0, 0, 1])

    def test_logits_avoid_sigmoid_saturation_and_ties_match_first_index(self):
        a = np.full((420, 1, 1, 3), 999.)
        a[..., 1] = 1000
        result = s.score_participant(a, labels(), [0], [0])
        np.testing.assert_array_equal(result["by_class_accuracy"][:, 0, 0], [0, 1, 0])
        self.assertEqual(result["tied_outcome_trials"][0, 0], 0)
        a[:] = 0
        tied = s.score_participant(a, labels(), [0], [0])
        np.testing.assert_array_equal(tied["by_class_accuracy"][:, 0, 0], [1, 0, 0])
        self.assertEqual(tied["tied_outcome_trials"][0, 0], 180)

    def test_diagonal_matches_timestamps_in_rectangular_grid(self):
        a = np.zeros((420, 2, 3, 3))
        a[..., 0] = 1
        r = s.score_participant(a, labels(), [0, 10], [-10, 0, 10])
        self.assertEqual(r["diagonal_ms"], [0, 10])
        np.testing.assert_allclose(r["diagonal"], [1 / 3, 1 / 3])

    def test_missing_labels_nonfinite_unused_channel_and_unsigned_time_order_refused(self):
        a = np.zeros((420, 1, 1, 7))
        a[-1, 0, 0, 6] = np.nan
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            s.score_participant(a, labels(), [0], [0])
        with self.assertRaises(ValueError):
            s.score_participant(np.zeros((420, 1, 1, 3)), np.ones(420, dtype=int), [0], [0])
        with self.assertRaisesRegex(ValueError, "increasing"):
            s.score_participant(np.zeros((420, 2, 1, 3)), labels(), np.array([10, 0], dtype=np.uint64), [0])


class CohortAndSplits(unittest.TestCase):
    def test_paper_exclusion_and_equal_participant_sem(self):
        maps = np.zeros((21, 1, 1))
        maps[5] = maps[18] = 1
        r = s.summarize_cohort(s.COHORT, maps)
        self.assertEqual(r["paper_figure_19"]["mean_accuracy"], [[0.]])
        self.assertAlmostEqual(r["deposited_analysis_21"]["mean_accuracy"][0][0], 2 / 21)
        maps[:, 0, 0] = np.arange(21) / 20
        kept = [float(i) / 20 for i in range(21) if i not in (5, 18)]
        mean = sum(kept) / 19
        expected_sem = (sum((v - mean) ** 2 for v in kept) / 18 / 19) ** .5
        r = s.summarize_cohort(s.COHORT, maps)
        self.assertAlmostEqual(r["paper_figure_19"]["participant_sem"][0][0], expected_sem)

    def test_complete_source_cohort_required(self):
        with self.assertRaisesRegex(ValueError, "21-participant"):
            s.summarize_cohort(s.COHORT[:-1], np.zeros((20, 1, 1)))

    def test_fivefold_stratification_and_sevenfold_distinction(self):
        ids = [str(i) for i in range(420)]
        f = np.tile(np.repeat(np.arange(1, 6), 12), 7)
        s.validate_trials(ids, labels(), f, 5)
        with self.assertRaisesRegex(ValueError, "fold coverage"):
            s.validate_trials(ids, labels(), f, 7)
        changed = f.copy(); changed[0] = 2
        with self.assertRaisesRegex(ValueError, "class/fold"):
            s.validate_trials(ids, labels(), changed, 5)
        ids[1] = ids[0]
        with self.assertRaisesRegex(ValueError, "unique"):
            s.validate_trials(ids, labels(), f, 5)


class OperatorPacket(unittest.TestCase):
    def test_complete_paired_path_has_known_difference_and_no_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = packet(Path(directory))
            r = s.evaluate(path)
            self.assertEqual(len(r["participant_results"]), 21)
            self.assertEqual(r["participant_results"][0]["class_fold_counts"], [[12] * 5] * 7)
            np.testing.assert_allclose(r["paired_candidate_minus_author"]["mean_difference"], [[2 / 3, 2 / 3]])
            self.assertEqual(len(r["paired_candidate_minus_author"]["participant_ids"]), 19)
            self.assertFalse(r["reproduction_qualified"])
            self.assertFalse(r["improvement_qualified"])
            json.dumps(r, allow_nan=False)

    def test_candidate_order_binding_refuses_trial_and_time_relabeling(self):
        with tempfile.TemporaryDirectory() as directory:
            path, m = packet(Path(directory))
            m["participants"][0]["trial_ids"].reverse()
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, "order binding"):
                s.evaluate(path)
            path, m = packet(Path(directory))
            m["test_ms"] = [0, 20]
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, "order binding"):
                s.evaluate(path)

    def test_missing_candidate_and_content_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path, m = packet(Path(directory))
            del m["participants"][0]["candidate_logits"]
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, "all participants"):
                s.evaluate(path)
            path, m = packet(Path(directory))
            m["participants"][0]["author_logits"]["sha256"] = "0" * 64
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, "SHA256"):
                s.evaluate(path)


if __name__ == "__main__":
    unittest.main()
