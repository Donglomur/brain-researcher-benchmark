"""GCaMP8 prepared-rate metrics; no model, preprocessing, or cohort selection.

Pearson uses the prepared rates directly. The secondary error/bias diagnostics
apply the additional Gaussian filter used in the pinned author demos. The caller
owns and freezes evaluation support; a candidate cannot mask its own errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import scipy
from scipy.ndimage import gaussian_filter1d


def _condition(sampling_rate_hz, smoothing_seconds):
    for name, value in (("sampling_rate_hz", sampling_rate_hz),
                        ("smoothing_seconds", smoothing_seconds)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite positive number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")
    sigma = float(sampling_rate_hz * smoothing_seconds)
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("finite positive smoothing width in samples required")
    return {"sampling_rate_hz": float(sampling_rate_hz),
            "smoothing_seconds": float(smoothing_seconds),
            "secondary_sigma_samples": sigma,
            "secondary_filter": {"mode": "reflect", "truncate": 4.0},
            "primary_extra_smoothing": False,
            "lag_search": False, "prediction_clipping": False}


def _inputs(prediction, target, valid_mask):
    prediction, target, mask = map(np.asarray, (prediction, target, valid_mask))
    if any(x.ndim != 1 for x in (prediction, target, mask)):
        raise ValueError("one complete prepared-rate vector and mask required")
    if prediction.shape != target.shape or mask.shape != target.shape:
        raise ValueError("prediction, target, and fixed mask must have equal shape")
    if mask.dtype != np.dtype(bool):
        raise ValueError("evaluator mask must be boolean, not inferred from predictions")
    if any(x.dtype.kind not in "iuf" for x in (prediction, target)):
        raise ValueError("real numeric rate vectors required")
    prediction = prediction[mask].astype(np.float64, copy=False)
    target = target[mask].astype(np.float64, copy=False)
    if not np.isfinite(prediction).all() or not np.isfinite(target).all():
        raise ValueError("nonfinite rate on fixed evaluation support")
    if (target < 0).any():
        raise ValueError("prepared ground-truth rates must be nonnegative")
    return prediction, target, mask


def score_rates(prediction, target, *, valid_mask, sampling_rate_hz, smoothing_seconds):
    """Score one neuron/condition on the caller's immutable support.

    Inputs are already aligned, sampled, and target-smoothed. This function does
    not generate target rates from spikes. As in the source demo, masking occurs
    before diagnostic smoothing; internal gaps are therefore compressed. Supply
    the exact source-prepared vector, not a new concatenation of recordings.
    """
    condition = _condition(sampling_rate_hz, smoothing_seconds)
    pred, truth, mask = _inputs(prediction, target, valid_mask)
    result = {
        "schema": "gcamp8-author-rate-metrics/v1",
        "libraries": {"numpy": np.__version__, "scipy": scipy.__version__},
        "condition": condition,
        "samples_total": int(mask.size), "samples_scored": int(pred.size),
        "support_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
        "pearson": None, "pearson_reason": None,
        "smoothed_normalized_absolute_error": None,
        "smoothed_normalized_bias": None, "normalization_reason": None,
    }
    if pred.size == 0:
        result.update(pearson_reason="no_valid_samples", normalization_reason="no_valid_samples")
        return result
    if pred.size < 2:
        result["pearson_reason"] = "fewer_than_two_samples"
    elif np.ptp(truth) == 0:
        result["pearson_reason"] = "constant_target"
    elif np.ptp(pred) == 0:
        result["pearson_reason"] = "constant_prediction"
    else:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result["pearson"] = float(np.corrcoef(truth, pred)[0, 1])
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        sigma = condition["secondary_sigma_samples"]
        truth_smooth = gaussian_filter1d(truth, sigma=sigma, mode="reflect", truncate=4.0)
        pred_smooth = gaussian_filter1d(pred, sigma=sigma, mode="reflect", truncate=4.0)
        signal = float(np.sum(truth_smooth))
        if signal == 0:
            result["normalization_reason"] = "zero_target_sum"
        else:
            difference = pred_smooth - truth_smooth
            result["smoothed_normalized_absolute_error"] = float(np.sum(np.abs(difference)) / signal)
            result["smoothed_normalized_bias"] = float(np.sum(difference) / signal)
    for key in ("pearson", "smoothed_normalized_absolute_error", "smoothed_normalized_bias"):
        if result[key] is not None and not math.isfinite(result[key]):
            raise ValueError("nonfinite computed metric")
    if result["pearson"] is not None and not -1 <= result["pearson"] <= 1:
        raise ValueError("Pearson correlation outside its range")
    return result


def compare_rates(candidate, author, target, *, valid_mask, sampling_rate_hz, smoothing_seconds):
    """Descriptive paired scores; no paper win or inference from one neuron."""
    kwargs = dict(valid_mask=valid_mask, sampling_rate_hz=sampling_rate_hz,
                  smoothing_seconds=smoothing_seconds)
    candidate_score = score_rates(candidate, target, **kwargs)
    author_score = score_rates(author, target, **kwargs)
    delta = {}
    for metric in ("pearson", "smoothed_normalized_absolute_error", "smoothed_normalized_bias"):
        c, a = candidate_score[metric], author_score[metric]
        delta[metric] = None if c is None or a is None else c - a
        if delta[metric] is not None and not math.isfinite(delta[metric]):
            raise ValueError("nonfinite paired metric difference: " + metric)
    return {"schema": "gcamp8-paired-rate-metrics/v1", "candidate": candidate_score,
            "author": author_score, "candidate_minus_author": delta}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Evaluator NPZ with prediction, target, valid_mask; optional author")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sampling-rate-hz", type=float, required=True)
    parser.add_argument("--smoothing-seconds", type=float, required=True)
    args = parser.parse_args()
    with np.load(args.input, allow_pickle=False) as packet:
        names = set(packet.files)
        if len(packet.files) != len(names):
            parser.error("duplicate NPZ members")
        if names not in ({"prediction", "target", "valid_mask"},
                         {"prediction", "author", "target", "valid_mask"}):
            parser.error("unexpected NPZ members")
        kwargs = dict(valid_mask=packet["valid_mask"], sampling_rate_hz=args.sampling_rate_hz,
                      smoothing_seconds=args.smoothing_seconds)
        if "author" in names:
            result = compare_rates(packet["prediction"], packet["author"], packet["target"], **kwargs)
        else:
            result = score_rates(packet["prediction"], packet["target"], **kwargs)
    # Refuse to replace a previous score, including the input file itself.
    with args.output.open("x") as output:
        output.write(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
