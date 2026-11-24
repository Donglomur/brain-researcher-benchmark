"""Generated predictions and metadata; no original observations or models."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

SPEC = importlib.util.spec_from_file_location("paired", Path(__file__).resolve().parents[1] / "paired_oddball.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
o = p.scorer


def packet(predictions=False, candidate=False):
    subjects = []
    for subject in o.SUBJECTS:
        trials = []
        for run in o.run_inventory(subject):
            for shape in o.SHAPES:
                for condition in ("reference", "outlier"):
                    trials.append({"trial_id": f"{run}/{shape}/{condition}", "run": run,
                                   "shape": shape, "condition": condition, "is_early": "late"})
            trials.append({"trial_id": f"{run}/early", "run": run, "shape": "square",
                           "condition": "reference", "is_early": "early"})
        branches = {branch: [] for branch in o.BRANCHES}
        if predictions:
            by_id = {r["trial_id"]: r for r in trials}
            for fold_index, fold in enumerate(o.fold_plan(subject, trials)):
                ids = fold["test_ids"][::-1] if candidate else fold["test_ids"]
                margins = np.array([1 if by_id[i]["condition"] == "reference" else -1 for i in ids])
                for branch in o.BRANCHES:
                    sign = (1 if branch == "smoothed" else 0) if not candidate else (
                        0 if branch == "smoothed" else (1 if fold_index == 0 else -1 if fold_index == 1 else 0))
                    scores = np.broadcast_to(sign * margins[:, None], (len(ids), 301)).copy()
                    if candidate and branch == "unsmoothed" and subject == "sub-20" and fold_index == 2:
                        for index, identity in enumerate(ids):
                            if by_id[identity]["shape"] == "square":
                                scores[index, 7] = margins[index]
                    branches[branch].append({"fold": fold["fold"], "trial_ids": ids, "scores": scores})
        subjects.append({"subject": subject, "trials": trials[::-1] if candidate else trials,
                         "branches": branches})
    return {"source_revision": o.SOURCE_REVISION, "score_orientation": "higher_is_reference",
            "times": o.TIMES.copy(), "subjects": subjects[::-1] if candidate else subjects}


class PairedTests(unittest.TestCase):
    def test_complete_real_scorer_panel_retains_local_gains_losses_and_dependence(self):
        result = p.compare_cohorts(packet(predictions=True), packet(predictions=True, candidate=True))
        self.assertFalse(result["research_qualified"])
        self.assertEqual(result["scientific_outcome"], "unknown")
        self.assertEqual(result["superiority_decision"], "not_implemented_source_policy_unresolved")
        self.assertEqual(result["reference"]["subject_order"], list(o.SUBJECTS))
        self.assertEqual(result["candidate"]["fold_order"], [f[0] for f in o.FOLDS])
        expected = np.zeros((20, 6, 11, 301))
        expected[:, 0] = .5
        expected[:, 1] = -.5
        expected[19, 2, 1, 7] = .5
        unsmoothed = result["paired_differences"]["unsmoothed"]
        np.testing.assert_array_equal(unsmoothed["subject_fold_shape_time_auroc_difference"], expected)
        np.testing.assert_array_equal(unsmoothed["subject_shape_time_auroc_difference"], expected.mean(axis=1))
        np.testing.assert_array_equal(unsmoothed["mean_shape_time_auroc_difference"], expected.mean(axis=1).mean(axis=0))
        np.testing.assert_array_equal(result["paired_differences"]["smoothed"]["subject_fold_shape_time_auroc_difference"], -.5)
        counts = np.asarray(result["reference"]["branches"]["unsmoothed"]["test_counts_outlier_reference"])
        self.assertEqual(counts[9, 0, 0].tolist(), [3, 3])
        self.assertEqual(counts[9, 1, 0].tolist(), [4, 4])
        np.testing.assert_array_equal(result["candidate"]["branches"]["unsmoothed"]["test_counts_outlier_reference"], counts)

    def test_equal_counts_do_not_hide_changed_identities_or_labels(self):
        reference = packet()
        cases = []
        renamed = copy.deepcopy(reference)
        renamed["subjects"][0]["trials"][0]["trial_id"] += "/changed"
        cases.append(renamed)
        swapped = copy.deepcopy(reference)
        rows = swapped["subjects"][0]["trials"]
        rows[0]["condition"], rows[1]["condition"] = rows[1]["condition"], rows[0]["condition"]
        cases.append(swapped)
        early = copy.deepcopy(reference)
        early["subjects"][0]["trials"][-1]["condition"] = "outlier"
        cases.append(early)
        shifted = copy.deepcopy(reference)
        shifted["times"][0] += 5e-13  # accepted individually, not the exact same paired axis
        cases.append(shifted)
        for changed in cases:
            with mock.patch.object(o, "score_cohort") as score:
                with self.assertRaisesRegex(ValueError, "support differs"):
                    p.compare_cohorts(reference, changed)
                score.assert_not_called()

    def test_missing_population_run_branch_and_time_fail_before_scoring(self):
        reference = packet()
        cases = []
        missing = copy.deepcopy(reference)
        missing["subjects"].pop()
        cases.append(missing)
        run = copy.deepcopy(reference)
        run["subjects"][0]["trials"] = [r for r in run["subjects"][0]["trials"] if r["run"] != 8]
        cases.append(run)
        branch = copy.deepcopy(reference)
        branch["subjects"][0]["branches"].pop("smoothed")
        cases.append(branch)
        times = copy.deepcopy(reference)
        times["times"] = times["times"][:-1]
        cases.append(times)
        for changed in cases:
            with mock.patch.object(o, "score_cohort") as score:
                with self.assertRaises(ValueError):
                    p.compare_cohorts(reference, changed)
                score.assert_not_called()

    def test_reordered_support_has_the_same_commitment(self):
        self.assertEqual(p.declared_support(packet()), p.declared_support(packet(candidate=True)))


if __name__ == "__main__":
    unittest.main()
