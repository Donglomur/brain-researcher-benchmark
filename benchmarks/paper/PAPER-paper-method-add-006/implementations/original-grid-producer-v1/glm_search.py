"""Complete source Poisson grid, with a separately labelled OOF export.

This is an independent implementation. The original source's full-session
transforms, callable NaN-aware refit and full-row predictions are preserved.
No estimator or input is loaded and no fit runs on import.
"""
from __future__ import annotations

from dataclasses import asdict
from itertools import product
import importlib.util
from pathlib import Path
import sys
import warnings

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "_population_grid_kernels", Path(__file__).resolve().parents[1]
    / "initial-evaluator-v1/evaluator.py")
K = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = K
_SPEC.loader.exec_module(K)
ContractError = K.ContractError
GRID = tuple(product((5, 10, 15), (3, 6, 12), (10, 50, 100, 150), (10, 40, 80)))
FIGURE_BASIS = (10, 3, 100, 40)
ALPHAS = np.logspace(-0.5, 2, 10)
FOLDS = 10


def source_refit(cv_results):
    """Literal source selection: nanmean then argmax, NOT finite/nanargmax."""
    scores = np.stack([cv_results[f"split{i}_test_score"] for i in range(FOLDS)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return int(np.argmax(np.nanmean(scores, axis=0)))


def score_statistics(scores):
    """Author means, population deviations and non-NaN (not finite) counts."""
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 3 or scores.shape[1:] != (10, 10):
        raise ContractError("scores require unit x 10 alpha x 10 fold")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return (np.nanmean(scores, axis=2), np.nanstd(scores, axis=2),
                (~np.isnan(scores)).sum(axis=2))


def source_fold_ids(nrows):
    from sklearn.model_selection import KFold
    if isinstance(nrows, bool) or not isinstance(nrows, (int, np.integer)) or nrows < FOLDS:
        raise ContractError("all ten contiguous folds require at least ten rows")
    result = np.empty(nrows, dtype=np.int64)
    for fold, (_, test) in enumerate(KFold(FOLDS, shuffle=False).split(np.empty(nrows))):
        result[test] = fold
    return result


def fit_search(design, counts):
    """Fit all 10 alphas x 10 folds for every unit, then author full-row refit.

    The additional ten selected-alpha refits produce an explicitly prospective
    OOF artifact. Hyperparameter choice still saw all ten folds, and transforms
    saw the full session. It is not a protected or nested held-out estimate.
    Source warnings are retained as diagnostics instead of changed into errors.
    Actual fit/scoring exceptions propagate as in error_score='raise'.
    """
    from sklearn.linear_model import PoissonRegressor
    from sklearn.model_selection import GridSearchCV, KFold
    design = K.matrix(design, "standardized full-session covariates")
    x = K.counts_array(counts, len(design))
    folds = source_fold_ids(len(design))
    splits = list(KFold(FOLDS, shuffle=False).split(design))
    full = np.empty_like(x, dtype=float)
    oof = np.empty_like(x, dtype=float)
    scores = np.empty((x.shape[1], 10, 10), dtype=float)
    selected = np.empty(x.shape[1], dtype=np.int64)
    coefficients = np.empty((x.shape[1], design.shape[1]), dtype=float)
    intercepts = np.empty(x.shape[1])
    iterations = np.empty(x.shape[1], dtype=np.int64)
    diagnostics = []
    for unit in range(x.shape[1]):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            search = GridSearchCV(PoissonRegressor(), {"alpha": ALPHAS.copy()},
                                  cv=FOLDS, n_jobs=1, error_score="raise",
                                  refit=source_refit)
            search.fit(design, x[:, unit])
            selected[unit] = search.best_index_
            scores[unit] = np.stack([search.cv_results_[f"split{f}_test_score"]
                                     for f in range(FOLDS)], axis=1)
            model = search.best_estimator_
            full[:, unit] = model.predict(design)
            coefficients[unit] = model.coef_
            intercepts[unit] = model.intercept_
            iterations[unit] = model.n_iter_
            for train, test in splits:
                held = PoissonRegressor(alpha=float(ALPHAS[selected[unit]]))
                held.fit(design[train], x[train, unit])
                oof[test, unit] = held.predict(design[test])
        # Count repeated messages rather than storing unbounded identical text.
        seen = {}
        for warning in captured:
            key = (warning.category.__name__, str(warning.message))
            seen[key] = seen.get(key, 0) + 1
        diagnostics.extend({"unit_index": unit, "category": category,
                            "message": message, "count": count}
                           for (category, message), count in sorted(seen.items()))
    means, deviations, valid = score_statistics(scores)
    return {"counts": x, "predictions": full, "oof_predictions": oof,
            "cv_scores": scores, "selected_alpha_indices": selected,
            "alpha_grid": ALPHAS.copy(), "selected_alphas": ALPHAS[selected],
            "test_scores": means, "test_devs": deviations, "num_valid": valid,
            "fold_ids": folds, "coefficients": coefficients,
            "intercepts": intercepts, "refit_iterations": iterations,
            "fit_count": int(x.shape[1] * 111), "source_fit_count": int(x.shape[1] * 101),
            "additional_oof_fit_count": int(x.shape[1] * 10), "warnings": diagnostics}


def pooled_latents(load_session, animal):
    """All eight source sessions, each centered AFTER recorded-speed filtering."""
    all_z = []
    for session in range(8):
        packet = load_session(animal, session, "CA1")
        z = K.latents(packet["z"])
        z = z[z[:, 2] > 4].copy()
        if len(z) < FOLDS:
            raise ContractError("every source session must support ten folds")
        z[:, :2] -= z[:, :2].mean(axis=0)
        all_z.append(z)
    return np.concatenate(all_z)


def fit_session(packet, pooled, basis_index):
    if isinstance(basis_index, bool) or not isinstance(basis_index, int) or not 0 <= basis_index < 108:
        raise ContractError("basis index must identify one of all 108 source configurations")
    parameters = K.BasisParameters(*GRID[basis_index])
    z, counts, rows, units = K.prepare_glm_session(packet["z"], packet["x"])
    basis = K.fit_basis(pooled, parameters)
    raw = K.design_matrix(z, basis, parameters)
    covs, _, mean, std = K.standardize_train(raw, raw)
    result = fit_search(covs, counts)
    result.update({"latents": z, "covariates": covs, "design_mean": mean,
                   "design_std": std, "row_indices": np.flatnonzero(rows),
                   "unit_indices": np.flatnonzero(units), "row_ids": packet["row_ids"][rows],
                   "unit_ids": packet["unit_ids"][units], "times": packet["t"][rows],
                   "trial_ids": packet["trial"][rows], "basis_position": basis["position"],
                   "basis_vx": basis["vx"], "basis_vy": basis["vy"],
                   "parameters": asdict(parameters), "basis_index": basis_index})
    return result


def job_plan():
    """Complete ordered 13,824 region/basis/session jobs; no source winner invented."""
    for region in K.REGIONS:
        for basis_index, basis in enumerate(GRID):
            for animal in K.ANIMALS:
                for session in range(8):
                    yield {"region": region, "basis_index": basis_index,
                           "basis": list(basis), "animal": animal, "session_index": session,
                           "id": f"{region}-b{basis_index:03d}-{animal}-s{session + 1:02d}"}
