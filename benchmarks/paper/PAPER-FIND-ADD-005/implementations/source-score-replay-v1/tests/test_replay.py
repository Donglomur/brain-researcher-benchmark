"""Generated software controls, never authentic neural observations."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import replay


def independent_ll(y, mu):
    return math.log(math.prod(math.exp(-m) * m ** count / math.factorial(count)
                              for count, m in zip(y, mu)))


def fixture():
    y = [0, 2, 1, 3, 0, 1, 2]
    baseline = [1, 1, 1, 1, 1, 1, 1]
    mu = [.5, 1.5, 1, 2, .25, .8, 2.1]
    leaves = []
    for trials, bins in [([1, 3], [1, 2, 4, 5]), ([2, 4, 5], [3, 6, 7])]:
        ly = [y[i - 1] for i in bins]
        lm = [mu[i - 1] for i in bins]
        leaves.append({"trial_indices": trials, "bin_indices": bins, "target_counts": ly,
                       "prediction_means": lm, "reported_cv2_neg_log_likelihood": -independent_ll(ly, lm),
                       "fit_info_equals_progenitor": False, "cv_train_sel_present": False})
    return {"schema": "dentate-author-score-export-v1", "source_commit": replay.SOURCE_COMMIT,
            "source_class_sha256": replay.SOURCE_CLASS_SHA256,
            "cells": [{"monkey": "generated", "cell_id": "control", "status": "fitted",
                       "bin_ms": 25, "source_n_cv_folds": 5, "bias_column_present": True,
                       "selected_source_trial_indices": [1, 3, 4, 7, 8], "source_trial_numbers": [10, 12, 13, 18, 19],
                       "trial_index_by_bin": [1, 1, 2, 3, 3, 4, 5], "target_counts": y,
                       "unspecialized_prediction_means": baseline,
                       "unspecialized_cv2_neg_log_likelihood": -independent_ll(y, baseline),
                       "unspecialized_cv_train_sel_present": False,
                       "native_joint_log_likelihood": independent_ll(y, mu), "hierarchical_leaves": leaves}]}


class ReplayTests(unittest.TestCase):
    def test_source_uses_sum_and_factorial_not_normalized_score(self):
        y, mu = [0, 1, 2], [1, 2, 4]
        expected = -7 + math.log(16)
        score = replay.poisson_log_likelihood(y, mu)
        self.assertAlmostEqual(score, expected)
        self.assertAlmostEqual(replay.poisson_log_likelihood(y * 2, mu * 2), 2 * expected)
        self.assertNotAlmostEqual(score, expected / len(y))

    def test_unequal_trial_lengths_and_nonconsecutive_categories(self):
        result = replay.replay(fixture())
        cell = result["cells"][0]
        self.assertEqual((cell["n_trials"], cell["n_bins"]), (5, 7))
        self.assertAlmostEqual(cell["hierarchical_log_likelihood_nats"], fixture()["cells"][0]["native_joint_log_likelihood"])
        self.assertIsNone(result["cross_cell_score"])
        self.assertFalse(result["fold_identity_verified"])
        self.assertFalse(result["paper_improvement_established"])

    def test_inherited_parent_cv2_not_misreported_as_leaf_score(self):
        doc = fixture()
        leaf = doc["cells"][0]["hierarchical_leaves"][0]
        leaf["reported_cv2_neg_log_likelihood"] = 31.0
        leaf["fit_info_equals_progenitor"] = True
        result = replay.replay(doc)["cells"][0]["hierarchical_leaves"][0]
        self.assertFalse(result["reported_cv2_matches_leaf_support"])
        self.assertNotEqual(result["log_likelihood_nats"], -31.0)

    def test_cv2_mismatch_without_inheritance_rejected(self):
        doc = fixture()
        doc["cells"][0]["hierarchical_leaves"][0]["reported_cv2_neg_log_likelihood"] += 1
        with self.assertRaisesRegex(replay.ReplayError, "without identical"):
            replay.replay(doc)

    def test_source_native_and_unspecialized_scores_reconciled(self):
        for field in ("native_joint_log_likelihood", "unspecialized_cv2_neg_log_likelihood"):
            with self.subTest(field=field):
                doc = fixture()
                doc["cells"][0][field] += .01
                with self.assertRaises(replay.ReplayError):
                    replay.replay(doc)

    def test_missing_or_duplicate_hierarchy_bins_rejected(self):
        doc = fixture()
        doc["cells"][0]["hierarchical_leaves"].pop()
        with self.assertRaisesRegex(replay.ReplayError, "incomplete"):
            replay.replay(doc)
        doc = fixture()
        doc["cells"][0]["hierarchical_leaves"].append(copy.deepcopy(doc["cells"][0]["hierarchical_leaves"][0]))
        with self.assertRaisesRegex(replay.ReplayError, "overlapping"):
            replay.replay(doc)

    def test_whole_trials_and_targets_cannot_be_silently_changed(self):
        doc = fixture()
        doc["cells"][0]["hierarchical_leaves"][0]["trial_indices"] = [1]
        with self.assertRaisesRegex(replay.ReplayError, "complete source trials"):
            replay.replay(doc)
        doc = fixture()
        doc["cells"][0]["hierarchical_leaves"][0]["target_counts"][0] = 1
        with self.assertRaisesRegex(replay.ReplayError, "target differs"):
            replay.replay(doc)

    def test_invalid_targets_and_source_exp_domain(self):
        for y, mu in [([0], [0]), ([1], [0]), ([-1], [1]), ([.5], [1]), ([True], [1]),
                      ([0], [float("inf")]), ([0], [float("nan")]), ([0, 1], [1])]:
            with self.subTest(y=y, mu=mu), self.assertRaises(replay.ReplayError):
                replay.poisson_log_likelihood(y, mu)

    def test_duplicate_source_identity_rejected(self):
        doc = fixture()
        doc["cells"].append(copy.deepcopy(doc["cells"][0]))
        with self.assertRaisesRegex(replay.ReplayError, "duplicate source"):
            replay.replay(doc)

    def candidate(self, doc):
        cell = doc["cells"][0]
        return {"schema": "dentate-candidate-means-v1", "cells": [
            {"monkey": cell["monkey"], "cell_id": cell["cell_id"],
             "source_support_sha256": replay.support_sha256(cell),
             "bin_indices": [7, 6, 5, 4, 3, 2, 1], "prediction_means": [2.1, .8, .25, 2, 1, 1.5, .5]}]}

    def test_candidate_pairs_by_identity_and_bin_not_row_position(self):
        doc = fixture()
        report = replay.replay(doc, self.candidate(doc))["cells"][0]
        self.assertAlmostEqual(report["candidate_minus_source_hierarchical_nats"], 0)

    def test_candidate_missing_extra_or_duplicate_bin_rejected(self):
        doc = fixture()
        for bins in ([7, 6, 5, 4, 3, 2], [7, 6, 5, 4, 3, 2, 8], [7, 6, 5, 4, 3, 2, 2]):
            candidate = self.candidate(doc)
            candidate["cells"][0]["bin_indices"] = bins
            with self.subTest(bins=bins), self.assertRaises(replay.ReplayError):
                replay.replay(doc, candidate)

    def test_candidate_scope_and_cohort_mismatch_rejected(self):
        doc = fixture()
        candidate = self.candidate(doc)
        candidate["cells"][0]["source_support_sha256"] = "0" * 64
        with self.assertRaisesRegex(replay.ReplayError, "hash mismatch"):
            replay.replay(doc, candidate)
        candidate = self.candidate(doc)
        candidate["cells"][0]["monkey"] = "different"
        with self.assertRaisesRegex(replay.ReplayError, "cohort differs"):
            replay.replay(doc, candidate)

    def test_source_exclusions_retained(self):
        doc = fixture()
        doc["cells"].append({"monkey": "generated", "cell_id": "unfitted", "status": "unfitted",
                             "reason": "source_unspecialized_model_is_experiment_struct"})
        result = replay.replay(doc)
        self.assertEqual(len(result["source_unfitted_cells"]), 1)
        self.assertEqual(len(result["cells"]), 1)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "control.json"
            path.write_text('{"cells": [], "cells": [1]}')
            with self.assertRaisesRegex(replay.ReplayError, "duplicate JSON"):
                replay.load_json(path)

    def test_source_pin_and_fold_count_cannot_be_relabelled(self):
        for mutate in (lambda d: d.update(source_commit="other"),
                       lambda d: d.update(source_class_sha256="0" * 64),
                       lambda d: d["cells"][0].update(source_n_cv_folds=3)):
            doc = fixture()
            mutate(doc)
            with self.assertRaises(replay.ReplayError):
                replay.replay(doc)

    def test_cli_receipts_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as folder:
            author = Path(folder) / "author.json"
            output = Path(folder) / "report.json"
            author.write_text(json.dumps(fixture()))
            argv = ["replay.py", "--author-export", str(author), "--output", str(output)]
            with patch.object(sys, "argv", argv):
                replay.main()
                result = json.loads(output.read_text())
                self.assertEqual(len(result["author_export_sha256"]), 64)
                self.assertNotIn("target_counts", output.read_text())
                self.assertNotIn("prediction_means", output.read_text())
                with self.assertRaises(FileExistsError):
                    replay.main()
            argv[-1] = str(author)
            with patch.object(sys, "argv", argv), self.assertRaisesRegex(replay.ReplayError, "overwrite"):
                replay.main()


if __name__ == "__main__":
    unittest.main()
