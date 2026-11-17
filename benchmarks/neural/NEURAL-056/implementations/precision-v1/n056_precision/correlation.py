"""Stable Pearson cells for the unchanged NEURAL-056 encoding endpoint.

Only floating-point arithmetic is revised. No tolerance declares a cell constant,
no cells are dropped, and no reliability correction enters the primary score.
"""
from __future__ import annotations

import numpy as np


def _matrix(value, name):
    value = np.asarray(value)
    if value.ndim != 2 or value.dtype.kind != "f" or value.dtype.itemsize not in (4, 8):
        raise ValueError(f"{name}: a float32/float64 image-by-coordinate matrix is required")
    value = np.asarray(value, dtype=np.float64)
    if not np.isfinite(value).all():
        raise ValueError(f"{name}: finite complete support is required")
    return value


def _center(value):
    """Remove an observed anchor before scaling, retaining small variations.

    Subtracting an observed value preserves nearby float64 differences. Only
    columns spanning opposite extreme signs can overflow that subtraction;
    divide those columns by two first. Power-of-two scaling then bounds the
    differences without the avoidable rounding of division by their maximum.
    """
    with np.errstate(over="ignore", under="ignore", invalid="raise"):
        shifted = value - value[:1]
        overflow = ~np.isfinite(shifted).all(axis=0)
        if overflow.any():
            half = np.ldexp(value[:, overflow], -1)
            shifted[:, overflow] = half - half[:1]
        peak = np.max(np.abs(shifted), axis=0)
        varying = peak != 0
        exponent = np.frexp(peak)[1]
        bounded = np.ldexp(shifted, -exponent)
        bounded -= bounded.mean(axis=0)
    return bounded, varying


def correlation(target, prediction):
    """Return the predecessor matrix API, including its undefined-cell policy.

    Rows are images. Callers preserve all 1,700 response cells: 200 rows for
    outer evaluation and 3,300 for inner development. Constant predictions score
    zero with raw correlation undefined. Any constant target makes the full mean
    undefined, while all cells and their individual values remain in the result.
    """
    target = _matrix(target, "target")
    prediction = _matrix(prediction, "prediction")
    if target.shape != prediction.shape or len(target) < 2 or target.shape[1] == 0:
        raise ValueError("matching nonempty complete image/coordinate support is required")
    a, valid = _center(target)
    b, varying = _center(prediction)
    scores = np.zeros(target.shape[1], dtype=np.float64)
    both = valid & varying
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        a2 = np.sum(a * a, axis=0)
        b2 = np.sum(b * b, axis=0)
        scores[both] = np.sum(a * b, axis=0)[both] / np.sqrt(a2[both] * b2[both])
    scores = np.clip(scores, -1.0, 1.0)
    if not np.isfinite(scores).all():
        raise ValueError("representable correlation required")
    return {
        "raw": [float(v) if valid[i] and varying[i] else None for i, v in enumerate(scores)],
        "score": [float(v) if valid[i] else None for i, v in enumerate(scores)],
        "constant_target": int((~valid).sum()),
        "constant_prediction": int((~varying).sum()),
        "mean": float(scores.mean()) if valid.all() else None,
    }
