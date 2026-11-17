"""Small source-grounded FUS conventions, not a MAT loader or clock alignment.

These functions have no I/O. They do not infer acquisition duration, rollover,
latency, trial membership, exposure, calibration or canonical input eligibility.
"""
import re

_BEHAVIOR = re.compile(r"(-?)([0-9]{2,3}):([0-9]{2}):([0-9]{2}),([0-9]{3})", re.ASCII)
_SUMMARY = re.compile(r"(-?)([0-9]{2,3}):([0-9]{2}):([0-9]{2})\.([0-9]{3})", re.ASCII)
_RT_GRID_DEGREES = {1: 225, 2: 270, 3: 315, 4: 180, 6: 0, 7: 135, 8: 90, 9: 45}


def _clock_ms(value, pattern):
    if value is None or value == "":
        return None
    if type(value) is not str:
        raise ValueError("clock must be a documented string or explicit missing value")
    match = pattern.fullmatch(value)
    if match is None:
        raise ValueError("unsupported clock syntax; no coercion or rollover inference")
    sign, hours, minutes, seconds, fraction = match.groups()
    h, m, s, ms = map(int, (hours, minutes, seconds, fraction))
    if m > 59 or s > 59:
        raise ValueError("minute/second outside documented clock range")
    magnitude = ((h * 60 + m) * 60 + s) * 1000 + ms
    return -magnitude if sign else magnitude


def parse_behavior_clock_ms(value):
    """Interpret HH:MM:SS,FFF or HHH:MM:SS,FFF as exact integer milliseconds.

    A leading minus applies to the whole magnitude. This is an explicit signed
    representation, not a claim of bitwise equivalence to MATLAB parseTime's
    negative-hour edge behavior. Empty/None stays missing; dates are not inferred.
    """
    return _clock_ms(value, _BEHAVIOR)


def parse_rt_summary_clock_ms(value):
    """Interpret only summaryResults.txt column 3, acq_timestamp: HH:MM:SS.FFF.

    The first two log columns use HH-MM-SS.FFF and are explicitly refused here.
    Native time_acq is passed to MATLAB datestr by the released simulation. Its
    physical timestamp event remains unknown; this function does not decode it.
    """
    return _clock_ms(value, _SUMMARY)


def rt_grid_label_to_degrees(label):
    """Map the released eight-target RT 3x3 grid convention to angular degrees.

    Label 5 denotes the center, not a ninth direction. Two-target labels use a
    different convention and must never enter this function. A real adapter must
    first validate eight-target mode and join the stored labels to targetPos.
    """
    if type(label) is not int or label not in _RT_GRID_DEGREES:
        raise ValueError("expected an eight-target RT grid label excluding center 5")
    return _RT_GRID_DEGREES[label]
