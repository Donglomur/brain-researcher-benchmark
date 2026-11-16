"""Original, deterministic train-only ridge baselines for binned lick counts.

Rows are already-frozen trial/bin observations, columns are numeric features.
This module neither defines source eligibility nor parses an authentic dataset.
"""
from dataclasses import dataclass
import numpy as np


def _matrix(value, name):
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.ndim != 2:
        raise ValueError(f"{name} must be a real numeric [rows, features] matrix")
    result = raw.astype(np.float64, copy=True)
    if not all(result.shape) or not np.isfinite(result).all():
        raise ValueError(f"{name} must have positive dimensions and finite values")
    return result


def _counts(value, rows, name):
    if isinstance(value, (list, tuple)) and any(isinstance(v, (bool, np.bool_)) for v in value):
        raise ValueError(f"{name} cannot contain booleans")
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.shape != (rows,):
        raise ValueError(f"{name} must be a real numeric vector of length {rows}")
    result = raw.astype(np.float64, copy=True)
    if (not np.isfinite(result).all() or (result < 0).any()
            or (result > 2**53 - 1).any() or (result != np.floor(result)).any()):
        raise ValueError(f"{name} must contain finite nonnegative exact integer counts")
    return result


def _ids(value, rows, name):
    if not isinstance(value, (list, tuple)) or len(value) != rows:
        raise ValueError(f"{name} must have one ID per matrix row")
    if any(not isinstance(item, str) or not item or item.strip() != item for item in value):
        raise ValueError(f"{name} must contain nonempty opaque string IDs")
    return tuple(value)


def _features(value, columns):
    names = _ids(value, columns, "feature_names")
    if len(set(names)) != len(names):
        raise ValueError("feature names must be unique")
    return names


def _readonly(value):
    result = np.array(value, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class CountModel:
    """One fit; normalization and coefficients originate only in training rows."""
    feature_names: tuple
    mean: np.ndarray
    scale: np.ndarray
    coefficient: np.ndarray
    intercept: float
    alpha: float
    dev_mse_by_alpha: tuple
    train_trial_ids: frozenset
    dev_trial_ids: frozenset


def _predict_values(x, mean, scale, coefficient, intercept):
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = np.maximum(0.0, ((x - mean) / scale) @ coefficient + intercept)
    except FloatingPointError as exc:
        raise ValueError("prediction arithmetic is not finite") from exc
    if not np.isfinite(result).all():
        raise ValueError("prediction arithmetic is not finite")
    return result


def fit_baseline(x_train, y_train, x_dev, y_dev, *, train_trial_ids,
                 dev_trial_ids, feature_names, alphas=(0.1, 1.0, 10.0, 100.0)):
    """Fit clipped ridge, selecting alpha by dev MSE (ties choose smaller alpha).

    X shapes: [n_train_bins,p] and [n_dev_bins,p]; y shapes: [n_*_bins].
    A row's opaque trial ID repeats for all bins of that trial. Train and dev
    trial-ID sets must be disjoint. The caller, not this function, establishes
    chronological trial blocks, features, QC, sample windows and biological IDs.
    The fitted objective is mean squared training residual + alpha*||coef||²;
    the unpenalized intercept is mean(y_train). No refit on dev occurs.
    """
    xt, xd = _matrix(x_train, "x_train"), _matrix(x_dev, "x_dev")
    if xt.shape[1] != xd.shape[1]:
        raise ValueError("train and dev feature dimensions differ")
    yt, yd = _counts(y_train, len(xt), "y_train"), _counts(y_dev, len(xd), "y_dev")
    names = _features(feature_names, xt.shape[1])
    train_ids = frozenset(_ids(train_trial_ids, len(xt), "train_trial_ids"))
    dev_ids = frozenset(_ids(dev_trial_ids, len(xd), "dev_trial_ids"))
    if train_ids & dev_ids:
        raise ValueError("train/dev trial overlap")
    if not isinstance(alphas, (list, tuple)) or not alphas:
        raise ValueError("alphas must be a nonempty fixed list/tuple")
    if any(isinstance(a, (bool, np.bool_)) or not isinstance(a, (int, float, np.integer, np.floating))
           or not np.isfinite(a) or a <= 0 for a in alphas):
        raise ValueError("alphas must be finite positive numbers")
    grid = sorted(set(float(a) for a in alphas))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mean, scale = xt.mean(axis=0), xt.std(axis=0)
            scale[scale == 0] = 1.0
            z = (xt - mean) / scale
            intercept = float(yt.mean())
            gram, rhs = z.T @ z / len(z), z.T @ (yt - intercept) / len(z)
            candidates = []
            for alpha in grid:
                coefficient = np.linalg.solve(gram + alpha * np.eye(xt.shape[1]), rhs)
                pred = _predict_values(xd, mean, scale, coefficient, intercept)
                loss = float(np.mean((yd - pred) ** 2))
                if not np.isfinite(loss) or not np.isfinite(coefficient).all():
                    raise ValueError("fit arithmetic is not finite")
                candidates.append((loss, alpha, coefficient))
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise ValueError("fit arithmetic failed") from exc
    _, alpha, coefficient = min(candidates, key=lambda item: (item[0], item[1]))
    return CountModel(names, _readonly(mean), _readonly(scale), _readonly(coefficient),
                      intercept, alpha, tuple((a, loss) for loss, a, _ in candidates),
                      train_ids, dev_ids)


def predict_query(model, x_query, *, trial_ids, feature_names):
    """Predict [n_query_bins] counts without fitting or accepting query labels."""
    if not isinstance(model, CountModel):
        raise ValueError("model must be a CountModel returned by fit_baseline")
    x = _matrix(x_query, "x_query")
    names = _features(feature_names, x.shape[1])
    if names != model.feature_names:
        raise ValueError("query feature order differs from fitted feature order")
    query_ids = frozenset(_ids(trial_ids, len(x), "trial_ids"))
    if query_ids & (model.train_trial_ids | model.dev_trial_ids):
        raise ValueError("query trial overlaps train/dev trials")
    return _predict_values(x, model.mean, model.scale, model.coefficient, model.intercept)
