"""Real GridSearchCV controls with a fixed, explicitly nonlearning estimator."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import d2_tweedie_score
from sklearn.model_selection import KFold
from sklearn.utils import _safe_indexing

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dependency_loader import G, K
import recorded_glm as M


class NonlearningPoisson(RegressorMixin, BaseEstimator):
    """Records calls but never learns parameters from X or y."""
    fits = 0
    predictions = 0
    scores = 0
    constructors = 0
    emit_prediction_warning = False
    score_mode = "coherent"
    fail_fit = False

    def __init__(self, alpha=1.0):
        self.alpha = alpha
        type(self).constructors += 1

    def fit(self, X, y):
        type(self).fits += 1
        if type(self).fail_fit:
            raise RuntimeError("fixed fixture fit failure")
        self.coef_ = np.zeros(X.shape[1])
        self.intercept_ = 0.
        self.n_iter_ = 0
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X):
        type(self).predictions += 1
        if type(self).emit_prediction_warning:
            warnings.warn("fixed prediction warning", RuntimeWarning)
        return np.full(len(X), 1 + float(self.alpha))

    def score(self, X, y):
        type(self).scores += 1
        if type(self).score_mode == "nan_slot":
            return np.nan if float(self.alpha).hex() == float(G.ALPHAS[5]).hex() else -np.inf
        return d2_tweedie_score(y, self.predict(X), power=1)

    @classmethod
    def reset(cls):
        cls.fits = cls.predictions = cls.scores = cls.constructors = 0
        cls.emit_prediction_warning = False
        cls.score_mode = "coherent"
        cls.fail_fit = False


def inputs(n=31, u=2):
    # Every row has identical features: feature-value matching cannot identify
    # its source row or test fold. No fitted parameter is learned by the double.
    design = np.ones((n, 3))
    counts = np.column_stack([2 + (np.arange(n) + j) % 5 for j in range(u)]).astype(float)
    return design, counts


def compare_original(testcase, actual, expected):
    for key, value in expected.items():
        with testcase.subTest(original_field=key):
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(actual[key], value)
            else:
                testcase.assertEqual(actual[key], value)


class TestRecordedGLM(unittest.TestCase):
    def setUp(self):
        NonlearningPoisson.reset()

    def test_real_gridsearch_original_outputs_and_fit_counts_unchanged(self):
        X, y = inputs()
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            original = G.fit_search(X, y)
            old_calls = (NonlearningPoisson.fits, NonlearningPoisson.predictions, NonlearningPoisson.scores)
            NonlearningPoisson.reset()
            recorded = M.fit_search_recorded(X, y, max_capture_bytes=100000)
            new_calls = (NonlearningPoisson.fits, NonlearningPoisson.predictions, NonlearningPoisson.scores)
        compare_original(self, recorded, original)
        self.assertEqual(old_calls, (222, 222, 200))
        self.assertEqual(new_calls, (222, 422, 200))
        for alpha, value in enumerate(G.ALPHAS):
            np.testing.assert_array_equal(recorded["alpha_oof_predictions"][:, :, alpha],
                                          np.full(y.shape, 1 + value))
        self.assertEqual(recorded["capture"]["added_fit_count"], 0)
        self.assertEqual(recorded["capture"]["added_predict_call_count"], 200)
        self.assertFalse(recorded["capture"]["native_poisson_numerical_parity_established"])
        self.assertEqual(recorded["capture"]["raw_prediction_bytes"], 31 * 2 * 10 * 8)

    def test_nan_argmax_and_source_warning_census_preserved(self):
        X, y = inputs(u=1)
        NonlearningPoisson.score_mode = "nan_slot"
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            original = G.fit_search(X, y)
            recorded = M.fit_search_recorded(X, y, max_capture_bytes=100000)
        compare_original(self, recorded, original)
        np.testing.assert_array_equal(recorded["selected_alpha_indices"], [5])
        self.assertEqual(recorded["warnings"], original["warnings"])
        self.assertTrue(recorded["warnings"])

    def test_extra_predict_warnings_are_separate_from_original_diagnostics(self):
        X, y = inputs(u=1)
        NonlearningPoisson.emit_prediction_warning = True
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            original = G.fit_search(X, y)
            recorded = M.fit_search_recorded(X, y, max_capture_bytes=100000)
        compare_original(self, recorded, original)
        self.assertEqual(sum(row["count"] for row in original["warnings"]), 111)
        extra = recorded["capture"]["warnings"]
        self.assertEqual(len(extra), 100)
        self.assertEqual({(r["alpha_index"], r["fold_index"]) for r in extra},
                         {(a, f) for a in range(10) for f in range(10)})

    def test_cap_refuses_before_cast_allocation_or_estimator_constructor(self):
        X, y = inputs()
        required = M.capture_array_bound(X, y)
        with mock.patch.object(M.K, "matrix", side_effect=AssertionError("cast occurred")), \
             mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            with self.assertRaisesRegex(M.CaptureError, "before allocation"):
                M.fit_search_recorded(X, y, max_capture_bytes=required - 1)
        self.assertEqual(NonlearningPoisson.constructors, 0)
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            got = M.fit_search_recorded(X, y, max_capture_bytes=required)
        self.assertEqual(got["capture"]["admitted_numeric_array_bound_bytes"], required)

    def test_unmaterialized_object_and_invalid_cap_refused(self):
        X, y = inputs()
        for xx, yy, cap in [(X.tolist(), y, 100000), (X.astype(object), y, 100000),
                            (X, y, True), (X, y, 0), (X, y[:10], 100000)]:
            with self.assertRaises(M.CaptureError):
                M.fit_search_recorded(xx, yy, max_capture_bytes=cap)
        self.assertEqual(NonlearningPoisson.constructors, 0)

    def test_real_safe_indexing_preserves_rows_but_unrelated_views_do_not(self):
        X, y = inputs()
        wrapped = M._IdentifiedRows(K.matrix(X, "test"))
        ids = np.array([30, 2, 8])
        selected = _safe_indexing(wrapped, ids)
        self.assertEqual(selected.source_rows, (30, 2, 8))
        self.assertIs(selected.source_token, wrapped.source_token)
        for value in (wrapped.T, wrapped.copy(), wrapped.reshape(3, 31), wrapped[:, [0, 1, 2]],
                      wrapped[0], wrapped[None, :]):
            self.assertIsNone(value.source_token)
        with self.assertRaises(AttributeError):
            selected.source_rows = (0, 1, 2)

    def test_capture_is_independent_of_callback_order_and_duplicate_features(self):
        X, y = inputs(u=1)
        wrapped = M._IdentifiedRows(X)
        splits = list(KFold(10, shuffle=False).split(X))
        raw = np.empty((len(X), 1, 10))
        recorder = M._ScoreCapture(wrapped, y[:, 0], raw, 0, splits)
        expected_scores = np.empty((10, 10))
        for alpha in reversed(range(10)):
            for fold in reversed(range(10)):
                test = splits[fold][1]
                estimator = mock.Mock()
                estimator.get_params.return_value = {"alpha": G.ALPHAS[alpha]}
                estimator.score.return_value = alpha * 100 + fold
                estimator.predict.return_value = np.full(len(test), alpha * 100 + fold, dtype=np.float64)
                expected_scores[alpha, fold] = alpha * 100 + fold
                recorder(estimator, wrapped[test], y[test, 0])
                estimator.score.assert_called_once()
                estimator.predict.assert_called_once()
        recorder.finish(expected_scores)
        for alpha in range(10):
            for fold, (_, test) in enumerate(splits):
                np.testing.assert_array_equal(raw[test, 0, alpha], np.full(len(test), alpha * 100 + fold))

    def test_duplicate_missing_detached_foreign_and_reordered_capture_refused(self):
        X, y = inputs(u=1)
        wrapped = M._IdentifiedRows(X)
        splits = list(KFold(10, shuffle=False).split(X))
        raw = np.empty((len(X), 1, 10))
        recorder = M._ScoreCapture(wrapped, y[:, 0], raw, 0, splits)
        test = splits[0][1]
        est = mock.Mock()
        est.get_params.return_value = {"alpha": G.ALPHAS[0]}
        est.score.return_value = .25
        est.predict.return_value = np.ones(len(test))
        recorder(est, wrapped[test], y[test, 0])
        with self.assertRaisesRegex(M.CaptureError, "duplicate"):
            recorder(est, wrapped[test], y[test, 0])
        self.assertEqual(est.score.call_count, 1)
        with self.assertRaisesRegex(M.CaptureError, "missing"):
            recorder.finish(np.zeros((10, 10)))
        for bad in (np.asarray(wrapped[test]), M._IdentifiedRows(X)[test], wrapped[test[::-1]]):
            with self.assertRaises(M.CaptureError):
                recorder(est, bad, y[test, 0])

    def test_alpha_and_target_identity_refusals_precede_estimator_score(self):
        X, y = inputs(u=1)
        wrapped = M._IdentifiedRows(X)
        splits = list(KFold(10, shuffle=False).split(X))
        rec = M._ScoreCapture(wrapped, y[:, 0], np.empty((len(X), 1, 10)), 0, splits)
        test = splits[0][1]
        est = mock.Mock()
        est.get_params.return_value = {"alpha": np.nextafter(G.ALPHAS[0], np.inf)}
        with self.assertRaisesRegex(M.CaptureError, "exact original slot"):
            rec(est, wrapped[test], y[test, 0])
        est.get_params.return_value = {"alpha": G.ALPHAS[0]}
        with self.assertRaisesRegex(M.CaptureError, "targets differ"):
            rec(est, wrapped[test], y[test, 0] + 1)
        est.score.assert_not_called()

    def test_raw_nonfinite_capture_preserved_and_wrong_shape_refused(self):
        X, y = inputs(u=1)
        wrapped = M._IdentifiedRows(X)
        splits = list(KFold(10, shuffle=False).split(X))
        raw = np.empty((len(X), 1, 10))
        rec = M._ScoreCapture(wrapped, y[:, 0], raw, 0, splits)
        test = splits[0][1]
        est = mock.Mock()
        est.get_params.return_value = {"alpha": G.ALPHAS[0]}
        est.score.return_value = .1
        est.predict.return_value = np.array([np.nan, np.inf, -1., 0.])
        rec(est, wrapped[test], y[test, 0])
        np.testing.assert_array_equal(raw[test, 0, 0], est.predict.return_value)
        est.get_params.return_value = {"alpha": G.ALPHAS[1]}
        est.predict.return_value = np.ones((len(test), 1))
        with self.assertRaisesRegex(M.CaptureError, "every test row"):
            rec(est, wrapped[test], y[test, 0])
        for dtype in (np.complex128, object, np.float32, np.int64, bool):
            est.predict.return_value = np.ones(len(test), dtype=dtype)
            with self.assertRaisesRegex(M.CaptureError, "without narrowing"):
                rec(est, wrapped[test], y[test, 0])

    def test_original_fit_error_propagates_without_partial_success(self):
        X, y = inputs(u=1)
        NonlearningPoisson.fail_fit = True
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            with self.assertRaisesRegex(RuntimeError, "fixed fixture fit failure"):
                M.fit_search_recorded(X, y, max_capture_bytes=100000)
        self.assertEqual(NonlearningPoisson.fits, 1)

    def test_original_score_error_propagates_before_added_prediction(self):
        X, y = inputs(u=1)
        original_error = RuntimeError("fixed fixture score failure")
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson), \
             mock.patch.object(NonlearningPoisson, "score", side_effect=original_error):
            with self.assertRaises(RuntimeError) as caught:
                M.fit_search_recorded(X, y, max_capture_bytes=100000)
        self.assertIs(caught.exception, original_error)
        self.assertEqual(NonlearningPoisson.fits, 1)
        self.assertEqual(NonlearningPoisson.predictions, 0)

    def test_session_wrapper_keeps_original_preparation_and_native_ids(self):
        X, y = inputs()
        packet = {"z": np.zeros((31, 7)), "x": y,
                  "row_ids": np.arange(31) + 50, "unit_ids": np.arange(2) + 200,
                  "t": np.arange(31) * .5, "trial": np.arange(31) // 3}
        basis = {"position": np.array([[0., 0.]]), "vx": np.array([0.]), "vy": np.array([0.])}
        mask = np.ones(31, dtype=bool)
        with mock.patch.object(K, "prepare_glm_session", return_value=(packet["z"], y, mask, np.ones(2, dtype=bool))), \
             mock.patch.object(K, "fit_basis", return_value=basis), \
             mock.patch.object(K, "design_matrix", return_value=X), \
             mock.patch.object(K, "standardize_train", return_value=(X, X, np.zeros(3), np.ones(3))), \
             mock.patch.object(M, "fit_search_recorded", return_value={"captured": True}) as fit:
            got = M.fit_session_recorded(packet, np.zeros((40, 7)), 0, max_capture_bytes=100000)
        self.assertTrue(got["captured"])
        np.testing.assert_array_equal(got["row_ids"], packet["row_ids"])
        np.testing.assert_array_equal(got["unit_ids"], packet["unit_ids"])
        fit.assert_called_once_with(X, y, max_capture_bytes=100000)
        self.assertEqual(got["parameters"]["position_bin"], 5)


class TestRawProducerGLM(unittest.TestCase):
    def setUp(self):
        import raw_producer
        self.B = raw_producer

    def record(self):
        X, y = inputs(u=1)
        NonlearningPoisson.reset()
        with mock.patch("sklearn.linear_model.PoissonRegressor", NonlearningPoisson):
            result = M.fit_search_recorded(X, y, max_capture_bytes=100000)
        job = next(G.job_plan())
        result.update(job=job, case_id="KL8-s01-CA1", packet_pin={"path": "case", "bytes": 3, "sha256": "c" * 64},
                      row_ids=np.arange(31), unit_ids=np.array([100]))
        return result

    def test_raw_schema_refuses_legacy_and_projects_defensive_candidate(self):
        r = self.record()
        candidate = self.B.glm_candidate(r, method_sha256="a" * 64)
        self.assertEqual(set(candidate), set(self.B.GLB.CANDIDATE_KEYS))
        saved = candidate["alpha_oof_predictions"].copy()
        r["alpha_oof_predictions"][:] = -99
        np.testing.assert_array_equal(candidate["alpha_oof_predictions"], saved)
        del r["alpha_oof_predictions"]
        with self.assertRaisesRegex(ValueError, "legacy"):
            self.B.validate_glm_recorded(r)

    def test_binding_is_distinct_from_original_and_pins_recording_source(self):
        with mock.patch.object(self.B.P, "execution_binding", return_value={"old": True}):
            got = self.B.execution_binding(object())
        self.assertEqual(got["schema"], "population_raw_production_binding_v1")
        self.assertEqual(got["original"], {"old": True})
        self.assertEqual(set(got["recording_code"]), {"dependency_loader.py", "raw_producer.py", "recorded_glm.py", "recorded_geometry.py"})
        self.assertIn("alpha_oof_predictions", got["raw_operands"])

    def test_run_glm_preserves_original_metadata_and_cv_summary_with_fixed_result(self):
        r = self.record()
        packet = {"case_id": "KL8-s01-CA1", "packet_pin": r["packet_pin"],
                  "source_asset_id": "asset", "source_epoch": 3}
        panel = mock.Mock()
        panel.load_session.return_value = packet
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp, \
             mock.patch.object(self.B.P, "require_runtime"), \
             mock.patch.object(self.B, "execution_binding", return_value={"recorded": True}), \
             mock.patch.object(G, "pooled_latents", return_value=np.zeros((31, 7))), \
             mock.patch.object(self.B.RG, "fit_session_recorded", return_value=r) as fit, \
             mock.patch.object(self.B.P, "save_result", return_value={"bytes": 300}) as save:
            got = self.B.run_glm(panel, Path(temp) / "results", max_result_bytes=100000,
                                max_total_bytes=100000, max_capture_bytes=100000, stop=1)
        fit.assert_called_once()
        saved_result = save.call_args.args[1]
        self.assertEqual(saved_result["source_asset_id"], "asset")
        self.assertEqual(saved_result["source_epoch"], 3)
        self.assertEqual(saved_result["job"], next(G.job_plan()))
        self.assertEqual(saved_result["source_session_mean_selected_cv_d2"],
                         float(np.mean(r["test_scores"][np.arange(1), r["selected_alpha_indices"]])))
        self.assertEqual(got["full_job_count"], 13824)
        self.assertEqual(got["charged_successful_output_bytes"], 300)

    def test_result_cap_exhaustion_precedes_next_fit(self):
        r = self.record()
        panel = mock.Mock()
        panel.load_session.return_value = {"case_id": "KL8-s01-CA1", "packet_pin": r["packet_pin"],
                                           "source_asset_id": "asset", "source_epoch": 3}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp, \
             mock.patch.object(self.B.P, "require_runtime"), \
             mock.patch.object(self.B, "execution_binding", return_value={"recorded": True}), \
             mock.patch.object(G, "pooled_latents", return_value=np.zeros((31, 7))), \
             mock.patch.object(self.B.RG, "fit_session_recorded", return_value=r) as fit, \
             mock.patch.object(self.B.P, "save_result", return_value={"bytes": 300}):
            with self.assertRaisesRegex(ValueError, "before any new fit"):
                self.B.run_glm(panel, Path(temp) / "results", max_result_bytes=100000,
                              max_total_bytes=100100, max_capture_bytes=100000, stop=2)
        self.assertEqual(fit.call_count, 1)


if __name__ == "__main__":
    unittest.main()
