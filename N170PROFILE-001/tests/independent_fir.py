"""Independent analytic .1--30 Hz FIR operator; no MNE dependency.

This is the prospective MNE-1.12.1-inspired numerical operator documented in
filter_source_plan.md, not a source reader or a boundary-policy implementation.
Two independently sized, symmetric Hamming lowpasses are centered and
subtracted. Execution uses a single full FFT convolution and explicit slicing,
not MNE overlap-add, scipy.firwin, or a forward/backward filter.

Caller-owned segments must be nonempty finite channel-by-time arrays. Short
segments retain the full kernel and n-1 reflected samples per end; they are not
discarded, replaced, or silently lengthened to match the filter. This operator
does not choose segments, events, channels, units, source support, or tolerances.
"""

import numpy as np
from scipy.signal import fftconvolve


class FIRInputError(ValueError):
    """Invalid or numerically nonfinite FIR input/output."""


def _sampling_frequency(fs):
    if isinstance(fs, (bool, np.bool_)) or not isinstance(
        fs, (int, float, np.integer, np.floating)
    ):
        raise FIRInputError("fs must be a finite real scalar greater than 60 Hz")
    try:
        value = float(fs)
    except (ValueError, OverflowError) as exc:
        raise FIRInputError("fs cannot be represented as float64") from exc
    if not np.isfinite(value) or value <= 60.0:
        raise FIRInputError("fs must be a finite real scalar greater than 60 Hz")
    return value


def _contains_boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_boolean(item) for item in value)
    return isinstance(value, np.ndarray) and value.dtype.kind == "b"


def _channel_matrix(values):
    if np.ma.isMaskedArray(values):
        raise FIRInputError("masked sample arrays are not supported")
    if _contains_boolean(values):
        raise FIRInputError("Boolean samples are not real-valued EEG samples")
    try:
        original = np.asarray(values)
        if original.ndim != 2 or original.dtype.kind not in "iuf":
            raise FIRInputError("expected a two-dimensional real channel-by-time array")
        if original.shape[0] < 1 or original.shape[1] < 1:
            raise FIRInputError("at least one channel and one time sample are required")
        with np.errstate(over="raise", invalid="raise"):
            result = np.array(original, dtype=np.float64, order="C", copy=True)
    except (TypeError, ValueError, OverflowError, FloatingPointError) as exc:
        raise FIRInputError("expected a nonempty finite real channel-by-time array") from exc
    if not np.isfinite(result).all():
        raise FIRInputError("all channel-by-time samples must be finite")
    return result


def _lowpass(length, cutoff):
    """Analytic normalized lowpass, cutoff expressed as fraction of Nyquist."""
    positions = np.arange(length, dtype=np.float64)
    centered = positions - (length - 1) / 2.0
    window = 0.54 - 0.46 * np.cos(2.0 * np.pi * positions / (length - 1))
    taps = cutoff * np.sinc(cutoff * centered) * window
    gain = np.sum(taps, dtype=np.float64)
    if not np.isfinite(gain) or gain == 0.0:
        raise FIRInputError("lowpass DC normalization is nonfinite or zero")
    taps /= gain
    if not np.isfinite(taps).all():
        raise FIRInputError("nonfinite analytic lowpass coefficients")
    return taps


def kernel(fs):
    """Return the analytic odd-length float64 .1--30 Hz bandpass FIR.

    Auto transitions are .1 Hz below and min(7.5, fs/2-30) Hz above.
    Full length uses ceil(duration*fs), then the next odd integer. Component
    lengths use nearest-integer (ties-to-even) rounding of the normalized
    transition expression, then the next odd integer. The two are not
    interchangeable at component-length rounding boundaries.
    """
    fs = _sampling_frequency(fs)
    lower_width = min(max(0.25 * 0.1, 2.0), 0.1)
    upper_width = min(max(0.25 * 30.0, 2.0), fs / 2.0 - 30.0)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            duration = 3.3 / min(lower_width, upper_width)
            samples = duration * fs
            if not np.isfinite(samples):
                raise FIRInputError("filter length is not finitely representable")
            length = max(int(np.ceil(samples)), 1)
            length += (length - 1) % 2
            # Normalize each physical breakpoint before differencing, as in
            # the declared numerical reference; do not substitute width/fs.
            normalized = np.asarray(
                [0.1 - lower_width, 0.1, 30.0, 30.0 + upper_width],
                dtype=np.float64,
            ) / (fs / 2.0)
            result = np.zeros(length, dtype=np.float64)
            # The upper lowpass is inserted first, then the lower is removed.
            for left, right, sign in (
                (normalized[2], normalized[3], 1.0),
                (normalized[0], normalized[1], -1.0),
            ):
                transition = (right - left) / 2.0
                component_length = int(round(3.3 / transition))
                component_length += 1 - component_length % 2
                if component_length > length or component_length < 3:
                    raise FIRInputError("component length is incompatible with full FIR")
                coefficients = _lowpass(component_length, (right + left) / 2.0)
                start = (length - component_length) // 2
                result[start:start + component_length] += sign * coefficients
        except (OverflowError, FloatingPointError, ZeroDivisionError) as exc:
            raise FIRInputError("nonfinite filter design arithmetic") from exc
    if not np.isfinite(result).all():
        raise FIRInputError("nonfinite bandpass coefficients")
    return result


def filter_segment(channels_by_time, fs):
    """Filter all rows of one explicit finite segment, returning a fresh array.

    n=1 is valid and has no reflected samples. Otherwise e=min(N,n)-1;
    reflections are odd about each endpoint, with neither endpoint repeated.
    Full convolution is sliced at e+(N-1)//2 for exactly n samples. No source
    eligibility or minimum-duration decision is made here.
    """
    data = _channel_matrix(channels_by_time)
    coefficients = kernel(fs)
    n_times = data.shape[1]
    edge = min(len(coefficients), n_times) - 1
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            if edge:
                left = 2.0 * data[:, :1] - data[:, edge:0:-1]
                right = 2.0 * data[:, -1:] - data[:, -2:-edge-2:-1]
                padded = np.concatenate((left, data, right), axis=1)
            else:
                padded = data
            if not np.isfinite(padded).all():
                raise FIRInputError("nonfinite endpoint reflection")
            convolved = fftconvolve(
                padded, coefficients[np.newaxis, :], mode="full", axes=-1
            )
            if not np.isfinite(convolved).all():
                raise FIRInputError("nonfinite full convolution")
            start = edge + (len(coefficients) - 1) // 2
            result = np.array(
                convolved[:, start:start + n_times],
                dtype=np.float64, order="C", copy=True,
            )
    except (OverflowError, FloatingPointError) as exc:
        raise FIRInputError("nonfinite reflection or convolution arithmetic") from exc
    if result.shape != data.shape or not np.isfinite(result).all():
        raise FIRInputError("filtered result has invalid shape or nonfinite values")
    return result
