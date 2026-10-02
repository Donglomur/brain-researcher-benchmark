"""Declared ERPLAB-inspired N170 measurement adaptation; not a software port.

Implemented from the parent-approved mathematical specification, without copying
ERPLAB code. The three declared departures are: a selected-peak voltage < 0
requirement; earliest deepest-peak ties instead of an all-equal median-position
branch; and inclusive half-height equality instead of an equality-to-null check.
This module does not claim MATLAB/version equivalence or biological onset.

The caller supplies its already epoch-baselined face-minus-car waveform. Exactly
one additional measurement-time baseline is removed here. Units are milliseconds
and microvolts. The module does not reconstruct source trials, decide source
support, or apply any activity threshold or source-relative fidelity rule.
"""

import numpy as np
from scipy.stats import t as student_t


class MeasurementError(ValueError):
    """Malformed input or nonrepresentable finite arithmetic, not missing data."""


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise MeasurementError(name + ": real non-Boolean number required")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise MeasurementError(name + ": finite float64 required") from exc
    if not np.isfinite(result):
        raise MeasurementError(name + ": finite float64 required")
    return result


def _has_boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_boolean(item) for item in value)
    return False


def _vector(value, name):
    if _has_boolean(value):
        raise MeasurementError(name + ": Boolean entries forbidden")
    try:
        original = np.asarray(value)
        if original.ndim != 1 or original.dtype.kind not in "iuf":
            raise MeasurementError(name + ": one-dimensional real array required")
        with np.errstate(over="raise", invalid="raise"):
            result = np.array(original, dtype=np.float64, order="C", copy=True)
    except (TypeError, ValueError, OverflowError, FloatingPointError) as exc:
        raise MeasurementError(name + ": one-dimensional finite real array required") from exc
    if result.size == 0 or not np.isfinite(result).all():
        raise MeasurementError(name + ": nonempty finite array required")
    return result


def _mean(values, name):
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = float(np.mean(values, dtype=np.float64))
    except FloatingPointError as exc:
        raise MeasurementError(name + ": finite mean overflow") from exc
    if not np.isfinite(result):
        raise MeasurementError(name + ": nonfinite mean")
    return result


def _window(times, requested, name):
    if not isinstance(requested, (list, tuple, np.ndarray)):
        raise MeasurementError(name + ": two ordered finite endpoints required")
    if isinstance(requested, np.ndarray) and requested.ndim != 1:
        raise MeasurementError(name + ": one-dimensional window required")
    if len(requested) != 2:
        raise MeasurementError(name + ": two ordered finite endpoints required")
    lo, hi = (_scalar(requested[i], name) for i in range(2))
    if lo > hi:
        raise MeasurementError(name + ": reversed endpoints")
    try:
        with np.errstate(over="raise", invalid="raise"):
            # argmin returns the first sample when distances are exactly equal.
            first = int(np.argmin(np.abs(times - lo)))
            last = int(np.argmin(np.abs(times - hi)))
    except FloatingPointError as exc:
        raise MeasurementError(name + ": distance overflow") from exc
    if first > last:
        raise MeasurementError(name + ": reversed snapped endpoints")
    return {
        "requested_ms": [lo, hi],
        "sample_indices": [first, last],
        "sample_times_ms": [float(times[first]), float(times[last])],
        "n_samples": last - first + 1,
    }


def measure_waveform(
    times_ms,
    waveform_uv,
    *,
    baseline_window_ms=(-200.0, 0.0),
    amplitude_window_ms=(110.0, 150.0),
    onset_window_ms=(10.0, 150.0),
    onset_supported=True,
):
    """Measure one defined difference waveform, or a declared missing condition.

    None means the caller knows a required condition is missing; it is not a
    substitute for malformed/nonfinite waveforms. Windows snap independently
    to nearest samples, inclusive at both ends. Requested endpoints can lie
    just outside the sampled grid (e.g. a rounded -200-ms epoch boundary).
    The snapped onset interval MUST have three actual samples beyond each end.
    Padding only qualifies local peaks; onset search never enters padding.

    onset_supported is an exact Python bool supplied by the source-support
    contract. False preserves amplitude/baseline but bypasses every onset-only
    calculation, returning numerical_zero_difference. Missing conditions retain
    their missing_condition statuses regardless of this flag.

    Every strictly local minimum is a negative-polarity candidate, irrespective
    of its absolute voltage. Apply the <0 support guard only AFTER selecting
    the deepest local candidate or, if there is none, the in-window minimum.
    """
    if type(onset_supported) is not bool:
        raise MeasurementError("onset_supported: Boolean required")
    times = _vector(times_ms, "times_ms")
    if not np.all(times[1:] > times[:-1]):
        raise MeasurementError("times_ms: strictly increasing samples required")
    windows = {
        "baseline": _window(times, baseline_window_ms, "baseline_window_ms"),
        "amplitude": _window(times, amplitude_window_ms, "amplitude_window_ms"),
        "onset": _window(times, onset_window_ms, "onset_window_ms"),
    }
    start, stop = windows["onset"]["sample_indices"]
    if start < 3 or stop + 3 >= len(times):
        raise MeasurementError("onset_window_ms: full three-sample padding required")
    result = {
        "amplitude_uv": None,
        "amplitude_status": "missing_condition",
        "onset_ms": None,
        "onset_status": "missing_condition",
        "measurement_baseline_uv": None,
        "windows": windows,
        "local_peak_indices": [],
        "peak_selection": None,
        "peak_index": None,
        "peak_time_ms": None,
        "peak_uv": None,
        "half_height_uv": None,
        "crossing_index": None,
    }
    if waveform_uv is None:
        return result
    wave = _vector(waveform_uv, "waveform_uv")
    if wave.shape != times.shape:
        raise MeasurementError("waveform_uv: shape must match time samples")
    blo, bhi = windows["baseline"]["sample_indices"]
    baseline = _mean(wave[blo : bhi + 1], "measurement baseline")
    try:
        with np.errstate(over="raise", invalid="raise"):
            wave -= baseline
    except FloatingPointError as exc:
        raise MeasurementError("measurement baseline subtraction overflow") from exc
    if not np.isfinite(wave).all():
        raise MeasurementError("measurement baseline subtraction nonfinite")
    alo, ahi = windows["amplitude"]["sample_indices"]
    result.update(
        amplitude_uv=_mean(wave[alo : ahi + 1], "sampled amplitude"),
        amplitude_status="ok",
        measurement_baseline_uv=baseline,
    )
    if not onset_supported:
        result["onset_status"] = "numerical_zero_difference"
        return result
    candidates = []
    for index in range(start, stop + 1):
        value = wave[index]
        if value < wave[index - 1] and value < wave[index + 1]:
            left = _mean(wave[index - 3 : index], "left peak neighborhood")
            right = _mean(wave[index + 1 : index + 4], "right peak neighborhood")
            if value < left and value < right:
                candidates.append(index)
    if candidates:
        peak = min(candidates, key=lambda index: (wave[index], index))
        selection = "deepest_local_peak"
    else:
        peak = start + int(np.argmin(wave[start : stop + 1]))
        selection = "in_window_global_minimum"
    peak_uv = float(wave[peak])
    result.update(
        local_peak_indices=candidates,
        peak_selection=selection,
        peak_index=peak,
        peak_time_ms=float(times[peak]),
        peak_uv=peak_uv,
    )
    if peak_uv >= 0:
        result["onset_status"] = "no_negative_peak"
        return result
    half = peak_uv * 0.5
    if half == 0:
        raise MeasurementError("half-height underflow")
    result["half_height_uv"] = half
    for index in range(peak, start - 1, -1):
        if wave[index] >= half:
            result.update(
                onset_ms=float(times[index]),
                onset_status="ok",
                crossing_index=index,
            )
            return result
    result["onset_status"] = "no_in_window_half_height_sample"
    return result


def aggregate_complete(values, *, expected_n=37):
    """Mean and two-sided t(n-1) CI only for all expected participant slots.

    All scalar inputs must be finite or explicit None. No available-case
    estimate, epsilon variance gate, winsorization or sign restriction is used.
    The default fixed cohort is 37; expected_n is explicit for manufactured
    cases and callers must retain the task's full cohort in production.
    """
    if isinstance(expected_n, (bool, np.bool_)) or not isinstance(
        expected_n, (int, np.integer)
    ) or expected_n < 2:
        raise MeasurementError("expected_n: integer at least two required")
    if not isinstance(values, (list, tuple, np.ndarray)):
        raise MeasurementError("values: one participant slot per expected person required")
    if isinstance(values, np.ndarray) and values.ndim != 1:
        raise MeasurementError("values: one-dimensional participant vector required")
    if len(values) != expected_n:
        raise MeasurementError("values: exact complete cohort slot count required")
    parsed = [None if value is None else _scalar(value, "participant value") for value in values]
    missing = [index for index, value in enumerate(parsed) if value is None]
    result = {
        "status": "incomplete_support" if missing else "ok",
        "n_expected": int(expected_n),
        "n_defined": int(expected_n - len(missing)),
        "n_missing": len(missing),
        "missing_indices": missing,
        "mean": None,
        "sample_sd": None,
        "standard_error": None,
        "df": None,
        "ci95": None,
        "interval_kind": "unavailable",
    }
    if missing:
        return result
    data = np.asarray(parsed, dtype=np.float64)
    if np.all(data == data[0]):
        mean = float(data[0])
        sd = se = 0.0
        interval = [mean, mean]
        kind = "constant_point"
    else:
        mean = _mean(data, "group mean")
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                centered = data - mean
                scale = float(np.max(np.abs(centered)))
                sd = float(scale * np.sqrt(np.sum((centered / scale) ** 2) / (expected_n - 1)))
                se = float(sd / np.sqrt(expected_n))
                critical = float(student_t.ppf(0.975, expected_n - 1))
                margin = critical * se
                interval = [mean - margin, mean + margin]
        except (FloatingPointError, ZeroDivisionError) as exc:
            raise MeasurementError("group interval arithmetic overflow or degeneracy") from exc
        if not np.isfinite([sd, se, critical, margin, *interval]).all():
            raise MeasurementError("group interval arithmetic nonfinite")
        if scale == 0 or sd == 0 or se == 0 or margin == 0:
            raise MeasurementError("nonconstant group interval arithmetic underflow")
        kind = "student_t"
    result.update(
        mean=mean,
        sample_sd=sd,
        standard_error=se,
        df=int(expected_n - 1),
        ci95=interval,
        interval_kind=kind,
    )
    return result
