"""Declared native-grid/float representation semantics for predictor ownership.

Behavior is on exact 200-Hz integer ticks. Imaging retains native samples;
only timestamps within 1 ns of a 100-ms boundary snap to that boundary.
This numerical convention neither resamples signals nor certifies real clocks.
"""
import numpy as np
from source_binding import require

TIME_TOLERANCE_S = 1e-9


def time_and_bins(times, *, behavior=False):
    t = np.asarray(times, dtype=float)
    require(t.ndim == 1 and np.isfinite(t).all() and np.all(np.abs(t) < 2**40), "predictor_time_domain")
    if behavior:
        ticks = np.rint(t / .005)
        require(np.all(np.abs(t - ticks * .005) <= TIME_TOLERANCE_S), "predictor_behavior_tick_grid")
        ticks = ticks.astype(np.int64)
        return ticks * .005, ticks // 20
    scaled = t / .1
    nearest = np.rint(scaled)
    snapped = np.abs(t - nearest * .1) <= TIME_TOLERANCE_S
    bins = np.floor(scaled).astype(np.int64)
    bins[snapped] = nearest[snapped].astype(np.int64)
    result = t.copy()
    result[snapped] = nearest[snapped] * .1
    return result, bins


def planned_mask(times, duration, *, behavior=False):
    require(type(duration) in (int, float) and duration in (1., 2.), "predictor_planned_duration")
    t, bins = time_and_bins(times, behavior=behavior)
    mask = np.logical_and(bins >= 0, bins < int(duration * 10))
    return t, bins, mask
