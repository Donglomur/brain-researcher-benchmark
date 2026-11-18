"""Independent finite-projection reference for one calcium/joint-angle pair.

Derived from the pinned Kaufman MATLAB functions, without production helpers.
This module has not been executed during construction. It provides a mathematical
float64 reference, not an assertion of native MATLAB/imgaussfilt numeric parity.

Caller owns source identity, original trial eligibility, ROI/24-column lineage,
and the FIRST ELIGIBLE maxCams shared camera step. That step is never replaced by
this trial's median. No fitting, inverse kinematics, or scientific score occurs.
"""
from __future__ import annotations

from bisect import bisect_left
import math

import numpy as np


# Explicit projection guard, not a MATLAB scientific parameter. The authenticated
# trial's kernels are 29 neural taps and 19 joint taps. Larger reference workloads
# require a separately reviewed resource bound rather than unbounded allocation.
MAX_GAUSSIAN_TAPS = 4095


class ReferenceRefusal(ValueError):
    """Input is outside this finite, in-support float64 projection's contract."""


def _real_array(value, name):
    try:
        a = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ReferenceRefusal(name + ": real numeric array required") from exc
    if a.dtype.kind not in "fiu" or a.dtype.itemsize > 8:
        raise ReferenceRefusal(name + ": real numeric dtype of at most 64 bits required")
    if a.dtype.kind in "iu" and a.size:
        if int(a.min()) < -(2**53) or int(a.max()) > 2**53:
            raise ReferenceRefusal(name + ": integer values exceed exact float64 admission")
    a = np.asarray(a, dtype=np.float64)
    if not np.isfinite(a).all():
        raise ReferenceRefusal(name + ": finite values required; no NaN repair or imputation")
    return a


def _scalar(value, name):
    a = _real_array(value, name)
    if a.size != 1:
        raise ReferenceRefusal(name + ": exactly one numeric value required")
    return float(a.reshape(-1)[0])


def _vector(value, name):
    a = _real_array(value, name)
    if not (a.ndim == 1 or (a.ndim == 2 and 1 in a.shape)) or not a.size:
        raise ReferenceRefusal(name + ": nonempty vector required")
    return a.reshape(-1, order="F")


def _matrix(value, name):
    a = _real_array(value, name)
    if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] < 1:
        raise ReferenceRefusal(name + ": time-by-channel matrix with at least two rows required")
    return a


def _finite(value, name):
    if not math.isfinite(value):
        raise ReferenceRefusal(name + ": derived nonfinite value")
    return value


def _increasing(values, name):
    # Python scalar subtraction exposes overflow without an integer wraparound.
    for i in range(1, len(values)):
        step = float(values[i]) - float(values[i - 1])
        if not math.isfinite(step) or step <= 0:
            raise ReferenceRefusal(name + ": finite strictly increasing values required")


def _gaussian_weights(sd):
    """Odd ceil(8*sd) tap kernel, normalized as explicit Gaussian weights."""
    if not math.isfinite(sd) or sd <= 0:
        raise ReferenceRefusal("Gaussian standard deviation must be finite and positive")
    width = _finite(sd * 8.0, "Gaussian width")
    count = math.ceil(width)
    count += (count + 1) % 2
    if count < 1 or count > MAX_GAUSSIAN_TAPS:
        raise ReferenceRefusal("Gaussian kernel exceeds the explicit reference tap bound")
    radius = count // 2
    weights = []
    for offset in range(-radius, radius + 1):
        scaled = offset / sd
        weights.append(math.exp(-0.5 * scaled * scaled))
    total = math.fsum(weights)
    if not math.isfinite(total) or total <= 0:
        raise ReferenceRefusal("Gaussian normalization is invalid")
    return np.asarray([w / total for w in weights], dtype=np.float64)


def _symmetric_index(index, count):
    """Edge-inclusive reflection: -1->0, -2->1, count->count-1.

    A period of 2*count also handles kernels wider than the data. This is
    symmetric boundary extension, not reflect-without-repeating-the-edge.
    """
    phase = index % (2 * count)
    return phase if phase < count else 2 * count - 1 - phase


def _gaussian_by_weighted_sums(values, sd):
    weights = _gaussian_weights(sd)
    radius = len(weights) // 2
    output = np.empty(values.shape, dtype=np.float64)
    for row in range(values.shape[0]):
        source_rows = [
            _symmetric_index(row + tap - radius, values.shape[0])
            for tap in range(len(weights))
        ]
        for channel in range(values.shape[1]):
            try:
                filtered = math.fsum(
                    float(weights[tap]) * float(values[source_row, channel])
                    for tap, source_row in enumerate(source_rows)
                )
            except (OverflowError, ValueError) as exc:
                raise ReferenceRefusal("Gaussian weighted sum overflowed") from exc
            output[row, channel] = _finite(filtered, "Gaussian weighted sum")
    return output, weights


def _count_overlap(events, frame_times, roi_lags, cycle, sync, lift, grid):
    """Literal source-order per-ROI count-overlap formula, with 1-based indices."""
    nroi = events.shape[1]
    width_in_frames = 10.0 / cycle
    event_relative = _finite(lift - sync, "event minus sync")
    frame_zero = _finite(
        1.0 + (event_relative - float(frame_times[0])) / cycle,
        "event frame coordinate",
    )
    shape = (len(grid), nroi)
    coordinates = np.empty(shape, dtype=np.float64)
    early_indices = np.empty(shape, dtype=np.int64)
    late_indices = np.empty(shape, dtype=np.int64)
    early_weights = np.empty(shape, dtype=np.float64)
    values = np.empty(shape, dtype=np.float64)
    for row, time_ms in enumerate(grid):
        # Keep addition/division/subtraction order from eventLockData.m103-118.
        base = _finite(frame_zero + float(time_ms) / cycle, "grid frame coordinate")
        for roi in range(nroi):
            coordinate = _finite(base - float(roi_lags[roi]) / cycle, "ROI frame coordinate")
            early, late = math.floor(coordinate), math.ceil(coordinate)
            if early < 1 or late > events.shape[0]:
                raise ReferenceRefusal("Padded neural grid requires an out-of-range source frame")
            early_weight = min((late - coordinate) / width_in_frames, 1.0)
            late_weight = 1.0 - early_weight
            # At an integer coordinate early==late and the source assigns the
            # late term weight one. Do not replace this with ordinary interp1.
            summed = (
                float(events[early - 1, roi]) * early_weight
                + float(events[late - 1, roi]) * late_weight
            )
            value = _finite(summed * width_in_frames, "resampled neural value")
            coordinates[row, roi] = coordinate
            early_indices[row, roi], late_indices[row, roi] = early, late
            early_weights[row, roi], values[row, roi] = early_weight, value
    return values, coordinates, early_indices, late_indices, early_weights


def _linear_by_brackets(times, values, grid):
    """Independent bracket search and two-term weighted sum; no extrapolation."""
    x = [float(v) for v in times]
    prepared = np.empty((len(grid), values.shape[1]), dtype=np.float64)
    lower = np.empty(len(grid), dtype=np.int64)
    upper = np.empty(len(grid), dtype=np.int64)
    fractions = np.empty(len(grid), dtype=np.float64)
    for row, query_value in enumerate(grid):
        query = float(query_value)
        if query < x[0] or query > x[-1]:
            raise ReferenceRefusal("Joint preparation requires out-of-support interpolation")
        right = bisect_left(x, query)
        if right < len(x) and x[right] == query:
            prepared[row, :] = values[right, :]
            lower[row] = upper[row] = right
            fractions[row] = 0.0
            continue
        left = right - 1
        span = _finite(x[right] - x[left], "camera interpolation interval")
        fraction = _finite((query - x[left]) / span, "camera interpolation fraction")
        if not 0.0 <= fraction <= 1.0:
            raise ReferenceRefusal("Invalid in-support camera interpolation fraction")
        for channel in range(values.shape[1]):
            try:
                value = math.fsum((
                    (1.0 - fraction) * float(values[left, channel]),
                    fraction * float(values[right, channel]),
                ))
            except (OverflowError, ValueError) as exc:
                raise ReferenceRefusal("Joint interpolation overflowed") from exc
            prepared[row, channel] = _finite(value, "interpolated joint value")
        lower[row], upper[row], fractions[row] = left, right, fraction
    return prepared, lower, upper, fractions


def reference_pair(
    events, joint_angles, camera_times, frame_times, roi_lags,
    cycle_ms, sync_ms, lift_ms, shared_camera_step_ms,
) -> dict[str, np.ndarray]:
    """Return seven source-route stages plus independent coordinate diagnostics.

    Inputs are one eligible trial in MATLAB time-by-channel orientation. Clocks
    and lags may be 1-D or MATLAB row/column vectors. Scalars are numeric singleton
    values. This finite-only projection refuses NaN/Inf, missing support and
    invalid shapes; it does not reproduce MATLAB's NaN propagation, skipped
    trials, default interp1 out-of-support NaNs, or inverse-kinematics fallback.

    All565 authenticated session-local ROI columns can be passed; arbitrary
    positive nroi also supports separately selected generated controls. Exactly
    24 stored joint-angle columns are required. No input array is modified.
    """
    neural = _matrix(events, "events")
    angles = _matrix(joint_angles, "joint_angles")
    cameras = _vector(camera_times, "camera_times")
    frames = _vector(frame_times, "frame_times")
    lags = _vector(roi_lags, "roi_lags")
    cycle = _scalar(cycle_ms, "cycle_ms")
    sync = _scalar(sync_ms, "sync_ms")
    lift = _scalar(lift_ms, "lift_ms")
    shared_step = _scalar(shared_camera_step_ms, "shared_camera_step_ms")
    if cycle < 10.0:
        raise ReferenceRefusal("Original frame cycle must support the source 10 ms grid")
    if shared_step <= 0.0:
        raise ReferenceRefusal("Shared first-eligible camera step must be positive")
    if neural.shape != (len(frames), len(lags)):
        raise ReferenceRefusal("Event rows/frame clock or event columns/ROI lags mismatch")
    if angles.shape != (len(cameras), 24):
        raise ReferenceRefusal("Exactly 24 joint columns and matching camera rows are required")
    _increasing(frames, "frame_times")
    _increasing(cameras, "camera_times")

    padded_grid = np.asarray(list(range(-270, 871, 10)), dtype=np.float64)
    prepared_grid = np.asarray(list(range(-200, 801, 10)), dtype=np.float64)
    evaluation_grid = np.asarray(list(range(-100, 401, 10)), dtype=np.float64)
    padded, coordinates, early, late, early_weights = _count_overlap(
        neural, frames, lags, cycle, sync, lift, padded_grid,
    )
    smoothed_padded, neural_kernel = _gaussian_by_weighted_sums(padded, 35.0 / 10.0)
    neural_prepared = smoothed_padded[7:108, :].copy()  # MATLAB rows8:108.

    joint_sd = _finite(15.0 / shared_step, "joint Gaussian standard deviation")
    joint_smoothed, joint_kernel = _gaussian_by_weighted_sums(angles, joint_sd)
    camera_relative = np.asarray([
        _finite((float(t) + sync) - lift, "event-relative camera time")
        for t in cameras
    ], dtype=np.float64)
    _increasing(camera_relative, "event-relative camera times")
    joint_prepared, lower, upper, fractions = _linear_by_brackets(
        camera_relative, joint_smoothed, prepared_grid,
    )
    return {
        "neural_padded": padded,
        "neural_smoothed_padded": smoothed_padded,
        "neural_prepared": neural_prepared,
        "joint_smoothed_full": joint_smoothed,
        "joint_prepared": joint_prepared,
        "neural_eval": neural_prepared[10:61, :].copy(),
        "joint_eval": joint_prepared[10:61, :].copy(),
        "padded_times_ms": padded_grid,
        "prepared_times_ms": prepared_grid,
        "evaluation_times_ms": evaluation_grid,
        "neural_frame_coordinates_one_based": coordinates,
        "neural_early_frames_one_based": early,
        "neural_late_frames_one_based": late,
        "neural_early_weights": early_weights,
        "camera_event_times_ms": camera_relative,
        "joint_interpolation_lower_zero_based": lower,
        "joint_interpolation_upper_zero_based": upper,
        "joint_interpolation_fractions": fractions,
        "neural_gaussian_weights": neural_kernel,
        "joint_gaussian_weights": joint_kernel,
    }
