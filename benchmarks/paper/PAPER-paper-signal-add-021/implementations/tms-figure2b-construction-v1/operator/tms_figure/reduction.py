"""Independent scalar arithmetic for the selected TMS Figure 2B branch.

No data loading, plotting, native libraries, estimator, or production admission.
Axes are deliberately restricted to finite strictly increasing real coordinates.
All arithmetic uses Python binary64; exact MATLAB/native rounding parity is held.
"""
import bisect
import math


def _number(value):
    if type(value) not in (int, float):
        raise ValueError("A nonboolean built-in real scalar is required")
    try:
        return float(value)
    except OverflowError as error:
        raise ValueError("Scalar must be representable as binary64") from error


def mean_db(values):
    """Return (ordinary ordered mean, non-NaN contributor count).

    Omit input NaNs only. Infinities contribute and mixed signs may generate NaN.
    This same omission helper is used for the two nested topography reductions.
    No compensated sum or native summation-order equivalence is claimed.
    """
    total = 0.0
    count = 0
    for value in values:
        value = _number(value)
        if not math.isnan(value):
            total = total + value
            count += 1
    return (total / count if count else float("nan"), count)


def _power10(exponent):
    try:
        return 10.0 ** exponent
    except OverflowError:
        # A binary64 overflow in the literal positive-base power is +infinity.
        return float("inf")


def normalized(pin, pout):
    """Literal (10**(pout/10)-10**(pin/10))/(10**(pin/10)+10**(pout/10)).

    Inputs are the already-computed participant dB means. Do not substitute a
    tanh/logistic identity: it changes literal overflow/underflow outcomes.
    """
    inside = _power10(_number(pin) / 10.0)
    outside = _power10(_number(pout) / 10.0)
    numerator = outside - inside
    denominator = inside + outside
    if denominator == 0.0:
        return float("nan")  # Both nonnegative powers underflowed: literal 0/0.
    return numerator / denominator


def _axis(values):
    coordinates = [_number(value) for value in values]
    if not coordinates or any(not math.isfinite(value) for value in coordinates):
        raise ValueError("A nonempty finite axis is required")
    if any(right <= left for left, right in zip(coordinates, coordinates[1:])):
        raise ValueError("Axis must be strictly increasing")
    return coordinates


def _nearest(coordinates, value):
    if value <= coordinates[0]:
        return 0
    if value >= coordinates[-1]:
        return len(coordinates) - 1
    right = bisect.bisect_left(coordinates, value)
    left = right - 1
    return left if abs(coordinates[left] - value) <= abs(coordinates[right] - value) else right


def nearest_window(axis, lower, upper):
    """Inclusive zero-based range between two separately nearest scalar endpoints.

    Lower-index ties match the selected upstream scalar call on an increasing
    axis. Out-of-range endpoints, including infinities, clamp to the axis ends.
    This is not the upstream two-element-vector range-selection branch.
    """
    coordinates = _axis(axis)
    lower, upper = _number(lower), _number(upper)
    if math.isnan(lower) or math.isnan(upper) or lower > upper:
        raise ValueError("Ordered non-NaN scalar bounds are required")
    first = _nearest(coordinates, lower)
    last = _nearest(coordinates, upper)
    return list(range(first, last + 1))


def window_reduce(values, *, channels, frequency_axis, time_axis,
                  frequency_bounds, time_bounds):
    """Reduce flat channel x frequency x time values, time first, frequency next.

    Flat offset is (channel * number_of_frequencies + frequency) *
    number_of_times + time. Every channel is retained. Only selected values are
    read; the production adapter must authenticate/validate its complete tensor.
    The small general shape accepted here is not production-scope admission.
    """
    if type(channels) is not int or channels < 1:
        raise ValueError("A positive nonboolean channel count is required")
    frequencies, times = _axis(frequency_axis), _axis(time_axis)
    if type(frequency_bounds) not in (list, tuple) or len(frequency_bounds) != 2:
        raise ValueError("Two frequency bounds are required")
    if type(time_bounds) not in (list, tuple) or len(time_bounds) != 2:
        raise ValueError("Two time bounds are required")
    nf, nt = len(frequencies), len(times)
    if len(values) != channels * nf * nt:
        raise ValueError("Exact complete flat tensor length is required")
    frequency_indices = nearest_window(frequencies, *frequency_bounds)
    time_indices = nearest_window(times, *time_bounds)
    topography = []
    time_contributors = []
    frequency_contributors = []
    for channel in range(channels):
        frequency_means = []
        counts = []
        for frequency in frequency_indices:
            offset = (channel * nf + frequency) * nt
            value, count = mean_db(values[offset + time] for time in time_indices)
            frequency_means.append(value)
            counts.append(count)
        value, count = mean_db(frequency_means)
        topography.append(value)
        time_contributors.append(counts)
        frequency_contributors.append(count)
    return {"topography": topography, "time_contributors": time_contributors,
            "frequency_contributors": frequency_contributors,
            "frequency_indices": frequency_indices, "time_indices": time_indices}

