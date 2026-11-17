"""Recovered NEURAL-069 numerical primitives; source hashes in SOURCE_PINS.json.

Function bodies below are verbatim from the historical benchmark implementation.
The public scorer separately names the current ROI-macro endpoint and legacy
family-macro companion; no inference, fitting, or source-data reads occur here.
"""
from __future__ import annotations
import math
from collections import Counter
from fractions import Fraction
from typing import Mapping
import numpy as np

SUBJECTS = tuple(f"sub-{i:02d}" for i in range(1, 11))
FAMILIES = {"V1": ("lV1v", "rV1v", "lV1d", "rV1d"),
            "MT": ("lMT", "rMT"), "STS": ("lSTS", "rSTS")}
ROIS = tuple(roi for rois in FAMILIES.values() for roi in rois)

class MetricInputError(ValueError):
    """Malformed/nonfinite inputs, as distinct from valid undefined metrics."""



def _array(value, *, ndim, name):
    try:
        a = np.asarray(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise MetricInputError(f"{name}: numeric array required") from exc
    if a.ndim != ndim or a.dtype.kind not in "fiu" or a.dtype.kind == "b":
        raise MetricInputError(f"{name}: real numeric {ndim}D array required")
    # Float64 is the declared arithmetic representation. Reject conversion
    # overflow instead of silently reclassifying valid source values as missing.
    with np.errstate(over="ignore", invalid="ignore"):
        a = a.astype(np.float64, copy=False)
    if not np.isfinite(a).all():
        raise MetricInputError(f"{name}: every value must be finite float64")
    return a



def _pair(truth, prediction):
    y = _array(truth, ndim=2, name="truth")
    p = _array(prediction, ndim=2, name="prediction")
    if y.shape != p.shape or y.shape[0] < 2 or y.shape[1] < 1:
        raise MetricInputError("matched nonempty [videos, voxels] arrays required")
    return y, p



def _mean(values):
    """Finite convex average without overflowing an intermediate unscaled sum."""
    values = list(values)
    if not values:
        raise MetricInputError("empty aggregate")
    if all(v == values[0] for v in values):
        return float(values[0])
    try:
        return math.fsum(float(v) / len(values) for v in values)
    except OverflowError:
        # At DBL_MAX, rounding each division can put a finite convex mean a
        # fraction of an ULP over the range. Recover the exact float-input mean.
        return float(sum(Fraction.from_float(float(v)) for v in values) / len(values))



def _metric(values, dispositions, **extra):
    counts = dict(sorted(Counter(dispositions).items()))
    defined = counts.get("defined", 0)
    total = len(dispositions)
    return {
        "status": "defined" if defined == total else "undefined",
        "value": _mean(values) if defined == total else None,
        "support": {"total_voxels": total, "defined_voxels": defined,
                    "dispositions": counts},
        **extra,
    }



def pearson_columns(truth, prediction):
    """Equal-voxel Pearson. Undefined truth is never dropped from the mean.

    Exact constant predictions on nonconstant truth receive zero by prospective
    convention. A safe midpoint is subtracted BEFORE residual scaling, preserving
    representable variation around a large offset. Exact constant checks prevent
    mean-roundoff creating spurious correlations.
    """
    y, p = _pair(truth, prediction)
    yc = np.all(y == y[0:1], axis=0)
    pc = np.all(p == p[0:1], axis=0)
    yy = y - (y.min(axis=0) / 2 + y.max(axis=0) / 2)
    pp = p - (p.min(axis=0) / 2 + p.max(axis=0) / 2)
    sy = np.max(np.abs(yy), axis=0)
    sp = np.max(np.abs(pp), axis=0)
    yy /= np.where(sy == 0, 1.0, sy)
    pp /= np.where(sp == 0, 1.0, sp)
    yy -= yy.mean(axis=0)
    pp -= pp.mean(axis=0)
    vals = []
    dispositions = []
    for j in range(y.shape[1]):
        if yc[j]:
            dispositions.append("constant_truth")
        elif pc[j]:
            vals.append(0.0)
            dispositions.append("defined")
        else:
            # Normalize each norm separately; multiplying the raw norms can
            # underflow even when their quotient is perfectly well-defined.
            yn = math.sqrt(float(np.dot(yy[:, j], yy[:, j])))
            pn = math.sqrt(float(np.dot(pp[:, j], pp[:, j])))
            if yn == 0 or pn == 0:
                dispositions.append("numerical_resolution_failure")
                continue
            r = float(np.dot(yy[:, j] / yn, pp[:, j] / pn))
            if not math.isfinite(r):
                dispositions.append("numerical_overflow")
            else:
                vals.append(min(1.0, max(-1.0, r)))  # roundoff-only range guard
                dispositions.append("defined")
    return _metric(vals, dispositions,
                   constant_prediction_with_nonconstant_truth=int(np.sum(pc & ~yc)))



def _require_keys(value, keys, name):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise MetricInputError(f"{name}: exact keys {list(keys)} required")



def _validate_panel(truth, panels, means, strict):
    if not isinstance(truth, Mapping) or not truth:
        raise MetricInputError("truth must be a nonempty participant mapping")
    if type(strict) is not bool:
        raise MetricInputError("strict must be a boolean")
    if any(not isinstance(s, str) for s in truth):
        raise MetricInputError("participant IDs must be strings")
    subjects = SUBJECTS if strict else tuple(sorted(truth))
    _require_keys(truth, subjects, "truth")
    for name, panel in panels.items():
        _require_keys(panel, subjects, name)
    if means is not None:
        _require_keys(means, subjects, "training_mean")
    videos = None
    # Admit the entire panel before computing any endpoint.
    admitted, predictions, train = {}, {n: {} for n in panels}, {}
    for sid in subjects:
        _require_keys(truth[sid], ROIS, f"truth[{sid}]")
        for n, panel in panels.items():
            _require_keys(panel[sid], ROIS, f"{n}[{sid}]")
            predictions[n][sid] = {}
        if means is not None:
            _require_keys(means[sid], ROIS, f"training_mean[{sid}]")
            train[sid] = {}
        admitted[sid] = {}
        for roi in ROIS:
            y = _array(truth[sid][roi], ndim=2, name=f"truth[{sid}][{roi}]")
            if y.shape[0] < 2 or y.shape[1] < 1:
                raise MetricInputError("empty/one-video ROI")
            videos = y.shape[0] if videos is None else videos
            if y.shape[0] != videos or (strict and videos != 102):
                raise MetricInputError("every ROI must share the full video count")
            admitted[sid][roi] = y
            for n, panel in panels.items():
                _, p = _pair(y, panel[sid][roi])
                predictions[n][sid][roi] = p
            if means is not None:
                m = _array(means[sid][roi], ndim=1, name="training mean")
                if m.shape != (y.shape[1],):
                    raise MetricInputError("training mean shape mismatch")
                train[sid][roi] = m
    return subjects, videos, admitted, predictions, train



def _aggregate(children, weights=None):
    defined = all(x["status"] == "defined" for x in children.values())
    if weights is None:
        value = _mean(x["value"] for x in children.values()) if defined else None
    else:
        total_weight = sum(weights.values())
        value = None
        if defined:
            vals = [c["value"] for c in children.values()]
            if all(v == vals[0] for v in vals):
                value = float(vals[0])
            else:
                try:
                    value = math.fsum(children[k]["value"] * (weights[k] / total_weight)
                                      for k in children)
                except OverflowError:
                    value = float(sum(Fraction.from_float(children[k]["value"]) * weights[k]
                                      for k in children) / total_weight)
    return {"status": "defined" if defined else "undefined",
            "value": value,
            "support": {"total_components": len(children),
                        "defined_components": sum(x["status"] == "defined"
                                                  for x in children.values()),
                        "undefined_component_ids": [k for k, x in children.items()
                                                    if x["status"] != "defined"]}}
