"""Source-derived GLM search with raw all-alpha held-prediction recording.

The original estimator score remains the GridSearchCV score. Recording adds one
predict call per existing scoring call and no fits. Capture-only warnings are
kept separately. This module performs no fitting or input loading on import.
"""
from __future__ import annotations

from dataclasses import asdict
import warnings

import numpy as np

from dependency_loader import G, K


class CaptureError(ValueError):
    """A capture identity, completeness or resource condition failed."""


def _need(condition, message):
    if not condition:
        raise CaptureError(message)


def capture_array_bound(design, counts):
    """Conservative allowance for enumerated recorder/source arrays, before casts.

    Inputs must already be materialized ndarrays; constructing an arbitrary
    Python sequence is not an admitted allocation path. This bound includes
    input casts, retained results, all-alpha payload and index/score tracking.
    It is not a simultaneous-live-memory bound: original caller storage,
    sklearn's train/test copies, temporary validation/statistics arrays, Python
    objects and estimator work require separate working-memory/CPU admission.
    This is not an OS memory limit.
    """
    for value, name in ((design, "design"), (counts, "counts")):
        _need(isinstance(value, np.ndarray) and value.ndim == 2
              and value.dtype.kind in "fiu" and min(value.shape) > 0,
              name + " must be an already-materialized plain numeric matrix")
    n, d = design.shape
    _need(counts.shape[0] == n and n >= 10, "aligned counts and all ten folds required")
    u = counts.shape[1]
    # Float64 input casts; counts/full/OOF plus10-alpha raw tensor; source
    # CV/summary/coefficient arrays; split/index copies and one capture table.
    return int(8 * (n * d + 13 * n * u + 100 * u + 30 * u
                    + d * u + 3 * u + 12 * n + 120) + 100)


def _admit_arrays(design, counts, max_capture_bytes):
    _need(type(max_capture_bytes) is int and max_capture_bytes > 0,
          "explicit positive capture-array byte ceiling required")
    required = capture_array_bound(design, counts)
    _need(required <= max_capture_bytes, "capture-array ceiling exceeded before allocation or estimator call")
    return required


class _IdentifiedRows(np.ndarray):
    """Only exact row indexing propagates immutable row-position tuples.

    Other ndarray operations, including transpose/copy/reshape/column selection,
    deliberately lose capture provenance. The fixed sklearn indexing path uses
    ``array[row_indices, ...]``. This is trusted-source bookkeeping, not a
    security boundary against a malicious estimator mutating Python attributes.
    """

    def __new__(cls, matrix):
        obj = np.asarray(matrix).view(cls)
        obj._source_rows = tuple(range(len(matrix)))
        obj._source_token = object()
        obj._source_columns = matrix.shape[1]
        return obj

    def __array_finalize__(self, original):
        self._source_rows = None
        self._source_token = None
        self._source_columns = None

    @property
    def source_rows(self):
        return self._source_rows

    @property
    def source_token(self):
        return self._source_token

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if not isinstance(result, _IdentifiedRows) or self._source_rows is None:
            return result
        if isinstance(key, tuple):
            if len(key) != 2 or not (key[1] is Ellipsis or
                                    isinstance(key[1], slice) and key[1] == slice(None)):
                return result
            row_key = key[0]
        else:
            row_key = slice(None) if key is Ellipsis else key
        if row_key is None or np.isscalar(row_key):
            return result
        selected = np.asarray(self._source_rows, dtype=np.int64)[row_key]
        if (result.ndim == 2 and result.shape[1] == self._source_columns
                and np.asarray(selected).ndim == 1 and len(selected) == len(result)):
            result._source_rows = tuple(int(v) for v in selected)
            result._source_token = self._source_token
            result._source_columns = self._source_columns
        return result


class _ScoreCapture:
    def __init__(self, design, y, raw, unit, splits):
        self.token = design.source_token
        self.nfeatures = design.shape[1]
        self.y = y
        self.raw = raw
        self.unit = unit
        self.fold_by_rows = {tuple(int(v) for v in test): fold
                             for fold, (_, test) in enumerate(splits)}
        _need(len(self.fold_by_rows) == 10, "ten distinct frozen test folds required")
        self.alpha_by_hex = {float(a).hex(): index for index, a in enumerate(G.ALPHAS)}
        _need(len(self.alpha_by_hex) == 10, "ten distinct original alpha slots required")
        self.seen = np.zeros((10, 10), dtype=bool)
        self.scores = np.empty((10, 10), dtype=np.float64)
        self.prediction_warnings = []
        self.calls = 0

    def __call__(self, estimator, x_test, y_test):
        _need(isinstance(x_test, _IdentifiedRows) and x_test.source_token is self.token,
              "scorer lost original row lineage")
        _need(x_test.ndim == 2 and x_test.shape[1] == self.nfeatures,
              "scorer feature support differs")
        rows = x_test.source_rows
        _need(isinstance(rows, tuple) and rows in self.fold_by_rows,
              "scorer rows do not equal an ordered original test fold")
        fold = self.fold_by_rows[rows]
        try:
            alpha = self.alpha_by_hex[float(estimator.get_params(deep=False)["alpha"]).hex()]
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise CaptureError("scorer alpha is not an exact original slot") from error
        _need(not self.seen[alpha, fold], "duplicate alpha/fold prediction capture")
        positions = np.asarray(rows, dtype=np.int64)
        _need(np.array_equal(np.asarray(y_test), self.y[positions]),
              "scorer targets differ from immutable original row assignment")
        # Preserve the original score call and its failures/warnings exactly.
        score = estimator.score(x_test, y_test)
        with warnings.catch_warnings(record=True) as added:
            warnings.simplefilter("always")
            prediction = np.asarray(estimator.predict(x_test))
        _need(prediction.shape == (len(rows),), "capture prediction must contain every test row exactly once")
        _need(prediction.dtype == np.dtype(np.float64),
              "source capture requires float64 predictions without narrowing or complex conversion")
        # No finite/positive clipping or replacement: unsupported source output
        # can be refused by the later candidate evaluator, not silently repaired.
        self.raw[positions, self.unit, alpha] = prediction
        self.scores[alpha, fold] = score
        self.seen[alpha, fold] = True
        self.calls += 1
        self.prediction_warnings.extend({"unit_index": self.unit, "alpha_index": alpha,
                                        "fold_index": fold, "category": type(w.message).__name__,
                                        "message": str(w.message)} for w in added)
        return score

    def finish(self, source_scores):
        _need(self.calls == 100 and bool(self.seen.all()), "missing alpha/fold prediction capture")
        _need(np.array_equal(self.scores, source_scores, equal_nan=True),
              "GridSearchCV score placement differs from captured alpha/fold identity")


def fit_search_recorded(design, counts, *, max_capture_bytes):
    """Original111 fits/unit, plus100 prediction-only captures/unit.

    The fixed source has full-session transforms and all-fold alpha selection.
    The separately retained ten selected-alpha OOF refits remain unchanged;
    this operation does not turn them into nested or independent evaluation.
    """
    required = _admit_arrays(design, counts, max_capture_bytes)
    from sklearn.linear_model import PoissonRegressor
    from sklearn.model_selection import GridSearchCV, KFold

    # K.matrix strips ndarray subclass state. Wrap only after source validation.
    ordinary_design = K.matrix(design, "standardized full-session covariates")
    x = K.counts_array(counts, len(ordinary_design))
    design = _IdentifiedRows(ordinary_design)
    folds = G.source_fold_ids(len(design))
    splits = list(KFold(G.FOLDS, shuffle=False).split(design))
    raw = np.empty((len(design), x.shape[1], 10), dtype=np.float64)
    full = np.empty_like(x, dtype=float)
    oof = np.empty_like(x, dtype=float)
    scores = np.empty((x.shape[1], 10, 10), dtype=float)
    selected = np.empty(x.shape[1], dtype=np.int64)
    coefficients = np.empty((x.shape[1], design.shape[1]), dtype=float)
    intercepts = np.empty(x.shape[1])
    iterations = np.empty(x.shape[1], dtype=np.int64)
    diagnostics, capture_warnings = [], []
    capture_calls = 0
    for unit in range(x.shape[1]):
        recorder = _ScoreCapture(design, x[:, unit], raw, unit, splits)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            search = GridSearchCV(PoissonRegressor(), {"alpha": G.ALPHAS.copy()},
                                  cv=G.FOLDS, n_jobs=1, error_score="raise",
                                  refit=G.source_refit, scoring=recorder)
            search.fit(design, x[:, unit])
            selected[unit] = search.best_index_
            scores[unit] = np.stack([search.cv_results_[f"split{f}_test_score"]
                                     for f in range(G.FOLDS)], axis=1)
            recorder.finish(scores[unit])
            model = search.best_estimator_
            full[:, unit] = model.predict(design)
            coefficients[unit] = model.coef_
            intercepts[unit] = model.intercept_
            iterations[unit] = model.n_iter_
            for train, test in splits:
                held = PoissonRegressor(alpha=float(G.ALPHAS[selected[unit]]))
                held.fit(design[train], x[train, unit])
                oof[test, unit] = held.predict(design[test])
        seen = {}
        for warning in captured:
            key = (warning.category.__name__, str(warning.message))
            seen[key] = seen.get(key, 0) + 1
        diagnostics.extend({"unit_index": unit, "category": category,
                            "message": message, "count": count}
                           for (category, message), count in sorted(seen.items()))
        capture_warnings.extend(recorder.prediction_warnings)
        capture_calls += recorder.calls
    means, deviations, valid = G.score_statistics(scores)
    return {"counts": x, "predictions": full, "oof_predictions": oof,
            "cv_scores": scores, "selected_alpha_indices": selected,
            "alpha_grid": G.ALPHAS.copy(), "selected_alphas": G.ALPHAS[selected],
            "test_scores": means, "test_devs": deviations, "num_valid": valid,
            "fold_ids": folds, "coefficients": coefficients,
            "intercepts": intercepts, "refit_iterations": iterations,
            "fit_count": int(x.shape[1] * 111), "source_fit_count": int(x.shape[1] * 101),
            "additional_oof_fit_count": int(x.shape[1] * 10), "warnings": diagnostics,
            "alpha_oof_predictions": raw,
            "capture": {"schema": "original_glm_raw_capture_v1", "complete": True,
                        "added_fit_count": 0, "added_predict_call_count": capture_calls,
                        "original_score_call_count": capture_calls,
                        "raw_prediction_bytes": int(raw.nbytes),
                        "admitted_numeric_array_bound_bytes": required,
                        "array_bound_scope": "enumerated recorder/source arrays; excludes caller storage, sklearn slicing, temporary statistics, Python objects and estimator work",
                        "max_capture_bytes": max_capture_bytes,
                        "identity": "exact original row positions carried through sklearn row indexing; exact alpha float identity",
                        "warnings": capture_warnings,
                        "warning_policy": "extra predict-only warnings retained separately from original source warnings",
                        "prediction_policy": "unaltered values; no finite replacement or positivity clipping",
                        "native_poisson_numerical_parity_established": False,
                        "training_policy": "unchanged full-session exposure and all-fold alpha selection"}}


def fit_session_recorded(packet, pooled, basis_index, *, max_capture_bytes):
    """Unchanged source session design, then the bounded raw recorder.

    Session preprocessing/basis construction happens before the search-level
    bound can know its design dimension. The operator must separately admit
    those original preprocessing allocations; the search cap is not a bound
    on the entire session or the estimator's internal working memory.
    """
    if isinstance(basis_index, bool) or not isinstance(basis_index, int) or not 0 <= basis_index < 108:
        raise G.ContractError("basis index must identify one of all 108 source configurations")
    _need(type(max_capture_bytes) is int and max_capture_bytes > 0,
          "explicit positive capture-array byte ceiling required")
    parameters = K.BasisParameters(*G.GRID[basis_index])
    z, counts, rows, units = K.prepare_glm_session(packet["z"], packet["x"])
    basis = K.fit_basis(pooled, parameters)
    raw = K.design_matrix(z, basis, parameters)
    covs, _, mean, std = K.standardize_train(raw, raw)
    result = fit_search_recorded(covs, counts, max_capture_bytes=max_capture_bytes)
    result.update({"latents": z, "covariates": covs, "design_mean": mean,
                   "design_std": std, "row_indices": np.flatnonzero(rows),
                   "unit_indices": np.flatnonzero(units), "row_ids": packet["row_ids"][rows],
                   "unit_ids": packet["unit_ids"][units], "times": packet["t"][rows],
                   "trial_ids": packet["trial"][rows], "basis_position": basis["position"],
                   "basis_vx": basis["vx"], "basis_vy": basis["vy"],
                   "parameters": asdict(parameters), "basis_index": basis_index})
    return result
