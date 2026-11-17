"""Generated scoring controls; no neural observations or fitted models."""
import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location("oddball", Path(__file__).resolve().parents[1] / "oddball_auroc.py")
o = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(o)


def fixture(subject="sub-01"):
    trials = []
    for run in o.run_inventory(subject):
        for shape in o.SHAPES:
            for index, condition in enumerate(("reference", "reference", "outlier")):
                trials.append({"trial_id": f"{run}/{shape}/{index}", "run": run,
                               "shape": shape, "condition": condition, "is_early": "late"})
            trials.append({"trial_id": f"{run}/{shape}/early", "run": run,
                           "shape": shape, "condition": "reference", "is_early": "early"})
    predictions = []
    by_id = {r["trial_id"]: r for r in trials}
    for plan in o.fold_plan(subject, trials):
        ids = plan["test_ids"][::-1]  # Exercise identity alignment.
        margins = np.array([1 if by_id[i]["condition"] == "reference" else -1 for i in ids])
        predictions.append({"fold": plan["fold"], "trial_ids": ids,
                            "scores": np.broadcast_to(margins[:, None], (len(ids), 301)).copy()})
    return trials, predictions


class OddballTests(unittest.TestCase):
    def test_auroc_independent_pairwise_oracle_ties_imbalance_and_orientation(self):
        labels = np.array([1, 0, 1, 1, 0, 1, 1])
        scores = np.array([[4, 7], [2, 7], [2, 5], [1, 2], [1, 2], [1, 1], [-3, 0]])
        positive = scores[labels == 1]
        negative = scores[labels == 0]
        wins = (positive[:, None, :] > negative[None, :, :]).mean(axis=(0, 1))
        ties = (positive[:, None, :] == negative[None, :, :]).mean(axis=(0, 1))
        np.testing.assert_allclose(o.auroc(labels, scores), wins + ties / 2)
        np.testing.assert_allclose(o.auroc(labels, -scores), 1 - wins - ties / 2)
        np.testing.assert_array_equal(o.auroc(labels, np.ones_like(scores)), [.5, .5])

    def test_undefined_and_nonfinite_auroc_fail(self):
        for labels, scores in (([1, 1], [[0], [1]]), ([0, 2], [[0], [1]]),
                               ([0, 1], [[0], [np.nan]]), ([0, 1], [[0j], [1j]])):
            with self.assertRaises(ValueError):
                o.auroc(labels, scores)

    def test_exact_source_partitions_and_missing_run_eight(self):
        self.assertEqual(o.SHAPES[:2], ("rectangle", "square"))
        self.assertEqual(sum(map(lambda s: len(o.run_inventory(s)), o.SUBJECTS)), 158)
        trials, _ = fixture("sub-10")
        by_id = {r["trial_id"]: r for r in trials}
        expected = [({1, 3, 5, 7}, {2, 4, 6}), ({2, 4, 6}, {1, 3, 5, 7}),
                    ({1, 2, 5, 6}, {3, 4, 7}), ({3, 4, 7}, {1, 2, 5, 6}),
                    ({1, 2, 3, 4}, {5, 6, 7}), ({5, 6, 7}, {1, 2, 3, 4})]
        plans = o.fold_plan("sub-10", trials)
        for p, (train, test) in zip(plans, expected):
            self.assertEqual({by_id[i]["run"] for i in p["train_ids"]}, train)
            self.assertEqual({by_id[i]["run"] for i in p["test_ids"]}, test)
            self.assertFalse(set(p["train_ids"]) & set(p["test_ids"]))
            self.assertTrue(all(by_id[i]["is_early"] == "late" for i in p["train_ids"] + p["test_ids"]))
        for row in trials:
            self.assertEqual(sum(row["trial_id"] in p["test_ids"] for p in plans),
                             3 if row["is_early"] == "late" else 0)

    def test_source_equal_fold_average_not_pooled_predictions(self):
        trials, predictions = fixture("sub-10")
        # Fold 0: perfect but only 3 test runs. Fold 1: reversed, 4 runs.
        # Other folds are tied. Equal fold mean=.5; weighting fold observations
        # would give (3 + .5*(3+4+3+4))/21 = 10/21, and is forbidden.
        for idx, p in enumerate(predictions):
            p["scores"] *= 1 if idx == 0 else -1 if idx == 1 else 0
        result = o.score_subject("sub-10", trials, predictions, o.TIMES)
        np.testing.assert_array_equal(result["shape_time_auroc"], .5)
        np.testing.assert_array_equal(result["fold_auroc"][:, 0, 0], [1, 0, .5, .5, .5, .5])
        self.assertEqual(result["test_counts_outlier_reference"].shape, (6, 11, 2))
        self.assertEqual(result["test_counts_outlier_reference"][0, 0].tolist(), [3, 6])

    def test_full_identity_coverage_and_time_axis_failures(self):
        trials, predictions = fixture()
        cases = []
        missing = copy.deepcopy(predictions)
        missing[0]["trial_ids"].pop()
        missing[0]["scores"] = missing[0]["scores"][:-1]
        cases.append(missing)
        duplicate = copy.deepcopy(predictions)
        duplicate[0]["trial_ids"][0] = duplicate[0]["trial_ids"][1]
        cases.append(duplicate)
        leakage = copy.deepcopy(predictions)
        leakage[0]["trial_ids"][0] = o.fold_plan("sub-01", trials)[0]["train_ids"][0]
        cases.append(leakage)
        for case in cases:
            with self.assertRaisesRegex(ValueError, "identities"):
                o.score_subject("sub-01", trials, case, o.TIMES)
        with self.assertRaisesRegex(ValueError, "301 times"):
            o.score_subject("sub-01", trials, predictions, o.TIMES + .05)
        with self.assertRaisesRegex(ValueError, "run inventory"):
            o.fold_plan("sub-01", [r for r in trials if r["run"] != 8])
        with self.assertRaisesRegex(ValueError, "both classes"):
            o.fold_plan("sub-01", [r for r in trials if not (r["shape"] == "square" and r["condition"] == "outlier")])

    def test_full_cohort_preserves_branches_subjects_and_below_chance(self):
        subjects = []
        for subject in o.SUBJECTS:
            trials, predictions = fixture(subject)
            opposite = [{"fold": p["fold"], "trial_ids": p["trial_ids"], "scores": -p["scores"]}
                        for p in predictions]
            subjects.append({"subject": subject, "trials": trials,
                             "branches": {"unsmoothed": predictions, "smoothed": opposite}})
        packet = {"source_revision": o.SOURCE_REVISION, "score_orientation": "higher_is_reference",
                  "times": o.TIMES, "subjects": subjects[::-1]}
        result = o.score_cohort(packet)
        self.assertEqual(result["subject_order"], list(o.SUBJECTS))
        self.assertEqual(result["shape_order"], list(o.SHAPES))
        np.testing.assert_array_equal(result["branches"]["unsmoothed"]["mean_shape_time_auroc"], 1)
        np.testing.assert_array_equal(result["branches"]["smoothed"]["mean_shape_time_auroc"], 0)
        self.assertEqual(np.shape(result["branches"]["unsmoothed"]["subject_fold_shape_time_auroc"]), (20, 6, 11, 301))
        for key, value in (("subjects", subjects[:-1]), ("score_orientation", "higher_is_outlier")):
            with self.assertRaises(ValueError):
                o.score_cohort({**packet, key: value})
        subjects[0]["branches"].pop("smoothed")
        with self.assertRaisesRegex(ValueError, "both smoothing branches"):
            o.score_cohort(packet)


if __name__ == "__main__":
    unittest.main()
