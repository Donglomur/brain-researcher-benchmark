"""Prospective N170 accepted-condition authority, in fixed microvolt units.

No source loading, artifact parsing, cached acceptance or import-time I/O.
Production must load this module and its sibling measurement_kernel from the
private pinned verifier directory, never the public editable runtime copy.
The fidelity calculation evaluates the same baseline expression separately;
only the unrebased accepted difference is supplied to measurement replay, so
no already-rebaselined vector is baseline-subtracted again.
"""
import numpy as np

import measurement_kernel as mk

EPS64 = float(np.finfo(np.float64).eps)
RELATIVE_BOUND = 1e-8
ROUNDING_FACTOR = 64.0
CONDITIONS = ("face", "car")


class WaveContractError(ValueError):
    """Malformed, nonrepresentable or source-inconsistent accepted evidence."""


def _need(condition, message):
    if not condition:
        raise WaveContractError(message)


def _maxabs(vector):
    return float(np.max(np.abs(vector)))


def _budget(vector):
    magnitude = _maxabs(vector)
    return RELATIVE_BOUND * magnitude + ROUNDING_FACTOR * EPS64 * max(1.0, magnitude)


def waveform_budget(reference):
    """B(v), with no waveform-dependent relaxation or absolute EEG cutoff."""
    return _budget(mk._vector(reference, "reference waveform"))


def _difference(left, right, label):
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.array(left - right, dtype=np.float64, order="C", copy=True)
    except FloatingPointError as exc:
        raise WaveContractError(label + ": subtraction overflow") from exc
    _need(np.isfinite(result).all(), label + ": nonfinite subtraction")
    return result


def _check(accepted, reference, label):
    error = _maxabs(_difference(accepted, reference, label))
    bound = _budget(reference)
    _need(error <= bound, label + ": source waveform fidelity")
    return {"max_abs_error_uv": error, "bound_uv": bound}


def check_supnorm(accepted, reference):
    """Standalone manufactured/authoring check; exact shape, finite real data."""
    ref = mk._vector(reference, "reference waveform")
    value = mk._vector(accepted, "accepted waveform")
    _need(value.shape == ref.shape, "waveform shape")
    return _check(value, ref, "waveform")


def _rebased(difference, baseline_indices):
    first, last = baseline_indices
    # Deliberately the same contiguous float64 reduction as the held kernel.
    baseline = mk._mean(difference[first:last + 1], "measurement baseline")
    return _difference(difference, baseline, "measurement rebaseline")


def replay_conditions(
    times_ms,
    accepted,
    source,
    *,
    baseline_window_ms=(-200.0, 0.0),
    amplitude_window_ms=(110.0, 150.0),
    onset_window_ms=(10.0, 150.0),
):
    """Validate face/car and derived difference; measure accepted waves once.

    accepted/source are exact {face: vector|None, car: vector|None} mappings.
    None denotes canonical missing-condition support, not an arbitrary skip.
    Artifact adapters translate their already-validated condition masks to None;
    their masked storage sentinels are not measured or treated as real zeros.
    Every present source condition is validated even if the other is missing.
    The source controls only missingness and the public numerical-zero rule,
    never the selected peak, crossing, amplitude or onset of an active wave.
    """
    _need(type(accepted) is dict and set(accepted) == set(CONDITIONS), "accepted condition keys")
    _need(type(source) is dict and set(source) == set(CONDITIONS), "source condition keys")
    times = mk._vector(times_ms, "times_ms")
    options = dict(baseline_window_ms=baseline_window_ms,
                   amplitude_window_ms=amplitude_window_ms,
                   onset_window_ms=onset_window_ms)
    # Validate grid/windows/padding for all cases, including missing conditions.
    missing_measurement = mk.measure_waveform(times, None, **options)
    canonical = {}; supplied = {}; checks = {}
    for condition in CONDITIONS:
        ref = source[condition]; value = accepted[condition]
        if ref is None:
            _need(value is None, condition + ": canonical missing condition")
            canonical[condition] = supplied[condition] = None
            checks[condition] = None
            continue
        _need(value is not None, condition + ": defined condition missing")
        ref = mk._vector(ref, "source " + condition)
        value = mk._vector(value, "accepted " + condition)
        _need(ref.shape == times.shape == value.shape, condition + ": waveform shape")
        checks[condition] = _check(value, ref, condition)
        canonical[condition] = ref; supplied[condition] = value
    if any(canonical[name] is None for name in CONDITIONS):
        return {"measurement": missing_measurement,
                "source_support": {"status": "missing_condition", "onset_supported": False,
                    "source_rebased_difference_max_abs_uv": None, "numerical_zero_limit_uv": None},
                "fidelity": {**checks, "rebased_difference": None}}
    source_difference = _difference(canonical["face"], canonical["car"], "source face-minus-car")
    accepted_difference = _difference(supplied["face"], supplied["car"], "accepted face-minus-car")
    baseline_indices = missing_measurement["windows"]["baseline"]["sample_indices"]
    source_rebased = _rebased(source_difference, baseline_indices)
    accepted_rebased = _rebased(accepted_difference, baseline_indices)
    checks["rebased_difference"] = _check(accepted_rebased, source_rebased, "rebased difference")
    source_magnitude = _maxabs(source_rebased)
    zero_limit = ROUNDING_FACTOR * EPS64 * max(1.0, _maxabs(canonical["face"]), _maxabs(canonical["car"]))
    supported = bool(source_magnitude > zero_limit)
    measurement = mk.measure_waveform(times, accepted_difference, onset_supported=supported, **options)
    return {"measurement": measurement,
            "source_support": {"status": "resolved" if supported else "numerical_zero_difference",
                "onset_supported": supported, "source_rebased_difference_max_abs_uv": source_magnitude,
                "numerical_zero_limit_uv": zero_limit},
            "fidelity": checks}
