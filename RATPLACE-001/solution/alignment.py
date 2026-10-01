"""Elapsed-time alignment: never snap spikes across removed running samples."""
import numpy as np

def sample_indices(timestamps, spikes, included, dt):
    t = np.asarray(timestamps, float)
    st = np.asarray(spikes, float)
    indices = np.searchsorted(t, st, side="right") - 1
    safe = np.clip(indices, 0, len(t)-1)
    keep = (indices >= 0) & (st < t[safe] + dt) & np.asarray(included, bool)[safe]
    return safe[keep]

def shifted_spikes(spikes, epochs, rng, min_shift):
    shifted = []
    st = np.asarray(spikes, float)
    for start, stop in epochs:
        duration = stop-start
        if duration <= 2*min_shift:
            raise ValueError("epoch too short for the declared minimum time shift")
        current = st[(st >= start) & (st < stop)]
        shift = rng.uniform(min_shift, duration-min_shift)
        shifted.extend(start + (current-start+shift) % duration)
    return np.asarray(shifted)
