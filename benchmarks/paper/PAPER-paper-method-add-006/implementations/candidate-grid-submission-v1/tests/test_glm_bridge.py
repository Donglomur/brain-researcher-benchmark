"""Generated controls; no fits, original arrays or candidate subprocesses."""
import copy
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glm_bridge import evaluate_glm
from deps import G, V


def fixture(nrows=31, nunits=3):
    rows = np.arange(nrows)
    counts = np.column_stack([(rows + u) % (5 + u) for u in range(nunits)]).astype(float)
    job = next(G.job_plan())
    reference = {
        "job": job, "case_id": "KL8-s01-CA1",
        "packet_pin": {"path": "fixed.npz", "bytes": 123, "sha256": "1" * 64},
        "row_ids": np.array([f"bin-{i}" for i in rows]),
        "unit_ids": np.arange(nunits) + 400, "counts": counts,
        "source_asset_id": "operator-asset", "source_epoch": 11,
        "times": rows * .5, "trial_ids": rows // 3,
    }
    held = counts[:, :, None] + np.arange(10)[None, None, :] * .2 + .1
    candidate = {
        "schema": "population_glm_candidate_v1", "job_id": job["id"],
        "method_sha256": "a" * 64, "row_ids": reference["row_ids"].copy(),
        "unit_ids": reference["unit_ids"].copy(), "fold_ids": V.source_fold_ids(nrows),
        "alpha_oof_predictions": held, "full_predictions": counts + .4,
        "selected_alpha_indices": np.zeros(nunits, dtype=np.int64),
    }
    return reference, candidate


def scalar_deviance(y, mu):
    terms = [float(m) if v == 0 else float(v) * math.log(float(v) / float(m)) - float(v) + float(m)
             for v, m in zip(y, mu)]
    return 2 * math.fsum(terms) / len(terms)


class TestGLMBridge(unittest.TestCase):
    def test_independent_scalar_oracle_all_alpha_fold_scores_and_uneven_folds(self):
        ref, sub = fixture()
        got = evaluate_glm(ref, sub)
        expected = np.empty((3, 10, 10))
        for unit in range(3):
            for alpha in range(10):
                for fold in range(10):
                    mask = sub["fold_ids"] == fold
                    y = ref["counts"][mask, unit].tolist()
                    mu = sub["alpha_oof_predictions"][mask, unit, alpha].tolist()
                    numerator = scalar_deviance(y, mu)
                    denominator = scalar_deviance(y, [math.fsum(y) / len(y)] * len(y))
                    expected[unit, alpha, fold] = 1 - numerator / denominator
        np.testing.assert_allclose(got["cv_scores"], expected, rtol=1e-11, atol=1e-12)
        np.testing.assert_allclose(got["test_scores"], expected.mean(axis=2), rtol=1e-11, atol=1e-12)
        np.testing.assert_allclose(got["test_devs"], expected.std(axis=2), rtol=1e-11, atol=1e-12)
        np.testing.assert_array_equal(got["num_valid"], np.full((3, 10), 10))
        np.testing.assert_array_equal(np.bincount(got["fold_ids"]), [4] + [3] * 9)
        np.testing.assert_array_equal(got["oof_predictions"], sub["alpha_oof_predictions"][:, :, 0])
        self.assertAlmostEqual(got["source_session_mean_selected_cv_d2"], expected[:, 0, :].mean(), places=11)
        self.assertFalse(got["training_provenance_attested"])
        self.assertFalse(got["source_producer_exports_all_alpha_held_tensor"])
        self.assertFalse(got["native_cv_score_bitwise_parity_established"])
        self.assertIn("constant-fold zero-null", got["numerical_metric_policy"])
        self.assertFalse(got["paper_improvement_established"])

    def test_perfect_constant_alpha_nan_beats_negative_infinity_with_source_argmax(self):
        ref, sub = fixture(nunits=1)
        ref["counts"][:] = 3
        sub["alpha_oof_predictions"][:] = 4
        sub["alpha_oof_predictions"][:, :, 5] = 3
        sub["selected_alpha_indices"][:] = 5
        got = evaluate_glm(ref, sub)
        self.assertTrue(np.isnan(got["cv_scores"][:, 5, :]).all())
        self.assertTrue(np.isneginf(got["cv_scores"][:, [0, 1, 2, 3, 4, 6, 7, 8, 9], :]).all())
        np.testing.assert_array_equal(got["selected_alpha_indices"], [5])
        self.assertTrue(math.isnan(got["source_session_mean_selected_cv_d2"]))
        np.testing.assert_array_equal(got["num_valid"][0], [10] * 5 + [0] + [10] * 4)

    def test_all_nan_uses_first_alpha_and_preserves_missing_fold_counts(self):
        ref, sub = fixture(nunits=1)
        ref["counts"][:] = 3
        sub["alpha_oof_predictions"][:] = 3
        got = evaluate_glm(ref, sub)
        self.assertTrue(np.isnan(got["cv_scores"]).all())
        np.testing.assert_array_equal(got["selected_alpha_indices"], [0])
        np.testing.assert_array_equal(got["num_valid"], np.zeros((1, 10), dtype=int))
        self.assertTrue(math.isnan(got["source_session_mean_selected_cv_d2"]))

    def test_zero_count_folds_preserve_negative_infinity_as_non_nan(self):
        ref, sub = fixture(nunits=1)
        ref["counts"][:] = 0
        sub["alpha_oof_predictions"][:] = .5
        got = evaluate_glm(ref, sub)
        self.assertTrue(np.isneginf(got["cv_scores"]).all())
        self.assertEqual(got["source_session_mean_selected_cv_d2"], -math.inf)
        self.assertTrue(np.isnan(got["test_devs"]).all())
        np.testing.assert_array_equal(got["num_valid"], np.full((1, 10), 10))

    def test_exact_tie_retains_first_alpha(self):
        ref, sub = fixture()
        sub["alpha_oof_predictions"][:, :, 1] = sub["alpha_oof_predictions"][:, :, 0]
        got = evaluate_glm(ref, sub)
        np.testing.assert_array_equal(got["selected_alpha_indices"], [0, 0, 0])

    def test_declared_selection_cannot_override_computed_scores(self):
        ref, sub = fixture()
        sub["selected_alpha_indices"][1] = 8
        with self.assertRaisesRegex(ValueError, "source nanmean"):
            evaluate_glm(ref, sub)

    def test_row_unit_and_fold_reordering_refused(self):
        for key in ("row_ids", "unit_ids", "fold_ids"):
            with self.subTest(key=key):
                ref, sub = fixture()
                sub[key] = sub[key][::-1]
                with self.assertRaisesRegex(ValueError, "differs|differ"):
                    evaluate_glm(ref, sub)

    def test_duplicate_and_wrong_kind_identities_refused(self):
        for key in ("row_ids", "unit_ids"):
            ref, sub = fixture()
            sub[key][1] = sub[key][0]
            with self.assertRaises(ValueError):
                evaluate_glm(ref, sub)
        for key in ("fold_ids", "selected_alpha_indices"):
            ref, sub = fixture()
            sub[key] = sub[key].astype(bool)
            with self.assertRaises(ValueError):
                evaluate_glm(ref, sub)

    def test_prediction_shape_dtype_and_domain_refusals(self):
        alterations = [lambda a: a[:, :, :9], lambda a: a.astype(object),
                       lambda a: a.astype(complex), lambda a: a.astype(bool),
                       lambda a: np.full_like(a, np.nan), lambda a: np.full_like(a, np.inf),
                       lambda a: np.zeros_like(a), lambda a: -a]
        for alter in alterations:
            ref, sub = fixture()
            sub["alpha_oof_predictions"] = alter(sub["alpha_oof_predictions"])
            with self.assertRaises(ValueError):
                evaluate_glm(ref, sub)
        ref, sub = fixture()
        sub["full_predictions"] = sub["full_predictions"][:, :2]
        with self.assertRaises(ValueError):
            evaluate_glm(ref, sub)

    def test_candidate_cannot_supply_targets_statistics_or_extra_metadata(self):
        for key in ("counts", "cv_scores", "source_session_mean_selected_cv_d2", "extra"):
            ref, sub = fixture()
            sub[key] = 1
            with self.assertRaisesRegex(ValueError, "exact raw GLM candidate"):
                evaluate_glm(ref, sub)
        ref, sub = fixture()
        del sub["full_predictions"]
        with self.assertRaises(ValueError):
            evaluate_glm(ref, sub)

    def test_exact_job_case_and_method_identity_required(self):
        mutations = [lambda r, s: s.update(job_id="PFC-b000-KL8-s01"),
                     lambda r, s: r.update(case_id="KL8-s02-CA1"),
                     lambda r, s: r["job"].update(basis_index=True),
                     lambda r, s: r["job"].update(session_index=8),
                     lambda r, s: r["job"].update(basis=[5, 3, 10, 40]),
                     lambda r, s: s.update(method_sha256="not-a-digest"),
                     lambda r, s: s.update(schema="source_numeric_result_v1")]
        for mutate in mutations:
            ref, sub = fixture()
            mutate(ref, sub)
            with self.assertRaises(ValueError):
                evaluate_glm(ref, sub)

    def test_output_copies_protect_saved_evaluator_operands(self):
        ref, sub = fixture()
        got = evaluate_glm(ref, sub)
        expected = copy.deepcopy(got)
        ref["counts"][:] = 900
        ref["row_ids"][:] = "changed"
        ref["unit_ids"][:] = 999
        ref["times"][:] = -100
        ref["packet_pin"]["bytes"] = 999
        ref["job"]["basis"][:] = [1, 1, 1, 1]
        sub["full_predictions"][:] = 700
        sub["alpha_oof_predictions"][:] = 800
        sub["selected_alpha_indices"][:] = 9
        for key in ("counts", "row_ids", "unit_ids", "times", "predictions", "oof_predictions", "selected_alpha_indices"):
            np.testing.assert_array_equal(got[key], expected[key])
        self.assertEqual(got["job"], expected["job"])
        self.assertEqual(got["packet_pin"], expected["packet_pin"])

    def test_operator_target_and_identity_preconditions(self):
        for bad_value in (-1, .5, np.nan):
            ref, sub = fixture()
            ref["counts"][0, 0] = bad_value
            with self.assertRaises(ValueError):
                evaluate_glm(ref, sub)
        ref, sub = fixture()
        ref["unit_ids"][1] = ref["unit_ids"][0]
        with self.assertRaises(ValueError):
            evaluate_glm(ref, sub)

    def test_cv_scores_come_from_held_operands_not_full_refit_predictions(self):
        ref, sub = fixture()
        first = evaluate_glm(ref, sub)
        sub["full_predictions"][:] = 100
        second = evaluate_glm(ref, sub)
        np.testing.assert_array_equal(first["cv_scores"], second["cv_scores"])
        self.assertFalse(np.array_equal(first["predictions"], second["predictions"]))


if __name__ == "__main__":
    unittest.main()
