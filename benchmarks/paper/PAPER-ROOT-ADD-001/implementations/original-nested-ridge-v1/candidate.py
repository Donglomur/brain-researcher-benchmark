"""Prespecified sentence-group nested Ridge candidate for selected Figure 3b.

The public entry is predict(train_x, train_y, query_x, context). Alpha selection
uses only outer-training observations. Runtime admission belongs to the harness.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

ALPHAS = (0.001, 0.01, 0.1, 1.0, 10.0)
ORIGINAL_ALPHA = 0.01
TIE_ATOL = 1e-12
INNER_FOLDS = 3


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _matrix(value, columns, name):
    _need(type(value) is np.ndarray, name + " must be an ordinary ndarray")
    _need(value.dtype == np.dtype(np.float64), name + " must be float64")
    _need(value.ndim == 2 and value.shape[0] >= 1 and value.shape[1] == columns,
          name + " has invalid selected-task geometry")
    _need(np.isfinite(value).all(), name + " must be finite")
    return value


def _training_groups(context, rows):
    _need(type(context) is dict and "train_qid" in context and "held_qid" in context,
          "Context must supply train_qid and held_qid")
    supplied = context["train_qid"]
    if isinstance(supplied, (list, tuple)):
        _need(not any(isinstance(q, (bool, np.bool_)) for q in supplied),
              "Boolean training sentence identifiers are invalid")
    raw = np.asarray(supplied)
    _need(raw.ndim == 1 and raw.shape[0] == rows and raw.dtype.kind in "iuf",
          "Training sentence identifiers must be a numeric vector aligned to rows")
    _need(np.isfinite(raw).all() and np.all(raw > -(2**53))
          and np.all(raw < 2**53) and np.all(raw == np.floor(raw)),
          "Training sentence identifiers must be finite exact integers")
    groups = raw.astype(np.float64, copy=False)
    held = context["held_qid"]
    _need(isinstance(held, (int, float, np.integer, np.floating))
          and not isinstance(held, (bool, np.bool_)),
          "Held sentence identifier must be numeric")
    _need(abs(held) < 2**53 and np.isfinite(held) and held == np.floor(held),
          "Held sentence identifier must be a finite exact integer")
    held = float(held)
    _need(not np.any(groups == held), "Outer held sentence appears in training")
    return groups


def _prediction(value, rows):
    _need(type(value) is np.ndarray and value.dtype == np.dtype(np.float64)
          and value.shape in ((rows,), (rows, 1)) and np.isfinite(value).all(),
          "Ridge must return complete finite float64 predictions")
    return value[:, None] if value.ndim == 1 else value


def _pooled_pearson(target, prediction):
    # One correlation over the stitched inner-validation rows, not a fold mean.
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        score = float(np.corrcoef(target[:, 0], prediction[:, 0])[0, 1])
    return score if np.isfinite(score) else None


def _select_alpha(train_x, train_y, train_qid):
    """Internal helper; operands are validated by the public predict entry."""
    unique, inverse = np.unique(train_qid, return_inverse=True)
    if unique.size < INNER_FOLDS:
        return ORIGINAL_ALPHA
    assignment = inverse % INNER_FOLDS
    scores = []
    for alpha in ALPHAS:
        validation = np.empty_like(train_y)
        for fold in range(INNER_FOLDS):
            held = assignment == fold
            estimator = Ridge(alpha=alpha)
            estimator.fit(train_x[~held], train_y[~held])
            validation[held] = _prediction(estimator.predict(train_x[held]),
                                           int(np.count_nonzero(held)))
        scores.append((alpha, _pooled_pearson(train_y, validation)))
    finite = [(alpha, score) for alpha, score in scores if score is not None]
    if not finite:
        return ORIGINAL_ALPHA
    maximum = max(score for _, score in finite)
    tied = [alpha for alpha, score in finite if maximum - score <= TIE_ATOL]
    return ORIGINAL_ALPHA if ORIGINAL_ALPHA in tied else min(tied)


def predict(train_x, train_y, query_x, context):
    """Select alpha on outer TRAIN only, refit TRAIN, then predict outer QUERY.

    Unused provider context fields are ignored. No query targets, files, network
    or persistent learned state are accessed by this programme.
    """
    train_x = _matrix(train_x, 30, "train_x")
    train_y = _matrix(train_y, 1, "train_y")
    query_x = _matrix(query_x, 30, "query_x")
    _need(train_x.shape[0] == train_y.shape[0], "Training rows must align")
    groups = _training_groups(context, train_x.shape[0])
    alpha = _select_alpha(train_x, train_y, groups)
    estimator = Ridge(alpha=alpha)
    estimator.fit(train_x, train_y)
    return _prediction(estimator.predict(query_x), query_x.shape[0])
