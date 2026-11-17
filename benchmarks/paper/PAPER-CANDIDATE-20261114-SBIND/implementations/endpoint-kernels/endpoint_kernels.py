"""Owner-side SBIND endpoint arithmetic; no data selection or model execution.

Rows are (sample_id, values) pairs. The independently frozen support is the
complete ordered list of samples admitted to this particular metric. Labels
and predictions must join it exactly, even when supplied in a different order.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from collections.abc import Sequence


class MetricError(ValueError):
    """Malformed, incomplete, or unrepresentable metric operands."""


@dataclass(frozen=True)
class MetricResult:
    metric: str
    n_samples: int
    support_sha256: str
    output_ids: tuple[str, ...]
    values: tuple[float, ...]
    # The denominator of each F1 output is not n_samples. Preserve TP, FP, FN.
    confusion: tuple[tuple[int, int, int], ...] = ()


def _sequence(value, name):
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise MetricError(f"{name} must be a sequence")
    return value


def _identities(values, name):
    result = tuple(_sequence(values, name))
    if not result or any(type(x) is not str or not x for x in result):
        raise MetricError(f"{name} must contain nonempty string identities")
    if len(set(result)) != len(result):
        raise MetricError(f"{name} contains duplicate identities")
    return result


def _join(support, targets, predictions):
    support = _identities(support, "support")
    joined = []
    for name, rows in (("targets", targets), ("predictions", predictions)):
        index = {}
        for row in _sequence(rows, name):
            row = _sequence(row, name + " row")
            if len(row) != 2 or type(row[0]) is not str or not row[0]:
                raise MetricError(f"{name} row requires an identity and values")
            if row[0] in index:
                raise MetricError(f"duplicate {name} identity")
            index[row[0]] = row[1]
        if set(index) != set(support):
            raise MetricError(f"{name} does not exactly cover the frozen support")
        joined.append(tuple(index[key] for key in support))
    digest = hashlib.sha256(json.dumps(support, ensure_ascii=True,
                                     separators=(",", ":")).encode("ascii")).hexdigest()
    return support, digest, joined[0], joined[1]


def _number(value):
    if type(value) not in (int, float):
        raise MetricError("continuous values and class scores must be real numbers")
    try:
        value = float(value)
    except OverflowError as exc:
        raise MetricError("numeric value exceeds binary64") from exc
    if not math.isfinite(value):
        raise MetricError("nonfinite metric operand")
    return value


def _vector(values, width, *, binary=False):
    values = _sequence(values, "values")
    if len(values) != width:
        raise MetricError("wrong output width")
    if binary:
        if any(type(v) not in (int, bool) or v not in (0, 1) for v in values):
            raise MetricError("binary targets must be literal 0/1 integers or booleans")
        return tuple(int(v) for v in values)
    return tuple(_number(v) for v in values)


def _mse(support, targets, predictions, output_ids, selected):
    support, digest, truth, pred = _join(support, targets, predictions)
    n = len(support)
    scale = math.sqrt(n)
    totals, corrections = [0.0] * len(selected), [0.0] * len(selected)
    for raw_t, raw_p in zip(truth, pred):
        # Validate all original pixels, but materialize only one pair of rows.
        t, p = _vector(raw_t, len(output_ids)), _vector(raw_p, len(output_ids))
        for i, column in enumerate(selected):
            # Divide before squaring to avoid a sum overflow when the mean is
            # representable. Nonrepresentable subtraction is refused explicitly.
            residual = t[column] - p[column]
            scaled = residual / scale
            term = scaled * scaled
            if not math.isfinite(term):
                raise MetricError("squared error exceeds binary64")
            total = totals[i] + term
            if not math.isfinite(total):
                raise MetricError("mean squared error exceeds binary64")
            corrections[i] += ((totals[i] - total) + term if totals[i] >= term
                               else (term - total) + totals[i])
            totals[i] = total
    results = tuple(total + correction for total, correction in zip(totals, corrections))
    if any(not math.isfinite(value) for value in results):
        raise MetricError("mean squared error exceeds binary64")
    return MetricResult("MSE", n, digest, tuple(output_ids[i] for i in selected),
                        results)


def wfci1_behavior_mse(support, targets, predictions, *, channel_ids):
    """Fourteen per-channel MSEs in the owner's frozen normalization units."""
    channels = _identities(channel_ids, "channel_ids")
    if len(channels) != 14:
        raise MetricError("WFCI1 requires all fourteen behavior channels")
    return _mse(support, targets, predictions, channels, tuple(range(14)))


def neural_mse(support, targets, predictions, *, brain_pixel_indices):
    """Per-pixel MSE for an explicit frozen mask; all 16384 pixels required.

    Flatten (1,128,128) fields in channel/row/column order. No inferred brain
    mask, zero-pixel exclusion, variance normalization or pixel averaging.
    """
    pixels = tuple(_sequence(brain_pixel_indices, "brain_pixel_indices"))
    if (not pixels or any(type(x) is not int or not 0 <= x < 16384 for x in pixels)
            or len(set(pixels)) != len(pixels)):
        raise MetricError("brain mask requires distinct in-range pixel indices")
    return _mse(support, targets, predictions,
                tuple(f"pixel:{i}" for i in range(16384)), pixels)


def _argmax(scores, n_classes):
    scores = _vector(scores, n_classes)
    # np.argmax uses the first maximum, including exact ties.
    return max(range(n_classes), key=scores.__getitem__)


def wfci2_behavior_f1(support, targets, predictions, *, channel_ids):
    """Four binary positive-class F1s from class scores, not thresholded labels.

    Prediction values have shape (4,2), class order (0,1). Zero denominator
    yields 0, matching the pinned author's zero_division=0 convention.
    """
    channels = _identities(channel_ids, "channel_ids")
    if len(channels) != 4:
        raise MetricError("WFCI2 requires all four binary behavior channels")
    support, digest, truth, pred = _join(support, targets, predictions)
    counts = [[0, 0, 0] for _ in channels]
    for t, p in zip(truth, pred):
        t = _vector(t, 4, binary=True)
        p = _sequence(p, "channel scores")
        if len(p) != 4:
            raise MetricError("WFCI2 requires scores for all four channels")
        for i in range(4):
            label = _argmax(p[i], 2)
            counts[i][0] += int(t[i] == 1 and label == 1)
            counts[i][1] += int(t[i] == 0 and label == 1)
            counts[i][2] += int(t[i] == 1 and label == 0)
    values = tuple(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
                   for tp, fp, fn in counts)
    return MetricResult("binary_F1", len(support), digest, channels, values,
                        tuple(tuple(row) for row in counts))


def fus_trial_accuracy(support, targets, predictions, *, directions):
    """Count successful trials once, using final-state class scores.

    Target values: (final_observation_offset, class_index).
    Prediction values: (final_observation_offset, class_scores).
    Original trials contain 30 frames, so the final offset must be 29. This
    checks declarations, not that a model actually used only allowed history.
    The owner must authenticate class-index mapping and successful trial census.
    """
    if type(directions) is not int or directions not in (2, 8):
        raise MetricError("the original fUS tasks have two or eight directions")
    support, digest, truth, pred = _join(support, targets, predictions)
    correct = 0
    for t, p in zip(truth, pred):
        t, p = _sequence(t, "trial target"), _sequence(p, "trial prediction")
        if len(t) != 2 or len(p) != 2:
            raise MetricError("trial operands require final offset and value")
        if type(t[0]) is not int or type(p[0]) is not int or t[0] != 29 or p[0] != 29:
            raise MetricError("fUS direction must use the final state of a 30-frame trial")
        if type(t[1]) is not int or not 0 <= t[1] < directions:
            raise MetricError("invalid fUS class index")
        correct += int(t[1] == _argmax(p[1], directions))
    return MetricResult("trial_accuracy", len(support), digest,
                        (f"fUS_{directions}_direction",), (correct / len(support),))
