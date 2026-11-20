"""Generated integral-JSON-index regressions; no source data or fitting."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("dentate_index_replay", HERE / "replay.py")
replay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay)


def fixture():
    counts, means = [0, 1, 2], [.5, 1.25, 1.75]
    ll = -3.5 + math.log(1.25) + 2 * math.log(1.75) - math.log(2)
    base = -3 - math.log(2)
    leaf = {"trial_indices": [1, 2], "bin_indices": [1, 2, 3],
            "target_counts": counts, "prediction_means": means,
            "reported_cv2_neg_log_likelihood": -ll,
            "fit_info_equals_progenitor": False, "cv_train_sel_present": False}
    cell = {"monkey": "generated", "cell_id": "index-boundary", "status": "fitted",
            "bin_ms": 25, "source_n_cv_folds": 5, "bias_column_present": True,
            "selected_source_trial_indices": [1, 7], "source_trial_numbers": [10, 20],
            "trial_index_by_bin": [1, 1, 2], "target_counts": counts,
            "unspecialized_prediction_means": [1, 1, 1],
            "unspecialized_cv2_neg_log_likelihood": -base,
            "unspecialized_cv_train_sel_present": False,
            "native_joint_log_likelihood": ll, "hierarchical_leaves": [leaf]}
    return {"schema": "dentate-author-score-export-v1", "source_commit": replay.SOURCE_COMMIT,
            "source_class_sha256": replay.SOURCE_CLASS_SHA256, "cells": [cell]}


class IntegralIndexControls(unittest.TestCase):
    def test_integral_float_leaf_indices_replay_without_changing_support(self):
        integer_document = fixture()
        float_document = copy.deepcopy(integer_document)
        leaf = float_document["cells"][0]["hierarchical_leaves"][0]
        leaf["trial_indices"] = [1.0, 2.0]
        leaf["bin_indices"] = [1.0, 2.0, 3.0]
        before = copy.deepcopy(float_document)
        self.assertEqual(replay.replay(float_document), replay.replay(integer_document))
        self.assertEqual(float_document, before)
        report = replay.replay(float_document)
        self.assertFalse(report["paper_improvement_established"])

    def test_candidate_float_indices_preserve_identity_alignment(self):
        doc = fixture(); cell = doc["cells"][0]
        proposed = {"monkey": cell["monkey"], "cell_id": cell["cell_id"],
                    "source_support_sha256": replay.support_sha256(cell),
                    "bin_indices": [3.0, 1.0, 2.0], "prediction_means": [1.75, .5, 1.25]}
        candidate = {"schema": "dentate-candidate-means-v1", "cells": [proposed]}
        result = replay.replay(doc, candidate)["cells"][0]
        self.assertAlmostEqual(result["candidate_minus_source_hierarchical_nats"], 0.)
        self.assertTrue(all(type(x) is int for x in replay.unique_indices([3.0, 1, 2.0], "indices")))

    def test_nonintegral_and_duplicate_index_refusals_are_preserved(self):
        for indices in ([1.5], [0.0], [-1.0], [True], [float("nan")],
                        [float("inf")], [1, 1.0]):
            with self.subTest(indices=indices), self.assertRaises(replay.ReplayError):
                replay.unique_indices(indices, "indices")


if __name__ == "__main__":
    unittest.main()
