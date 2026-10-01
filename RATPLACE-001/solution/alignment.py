"""Elapsed-time alignment: never snap spikes across removed running samples."""
import numpy as np

def running_samples(timestamps, xy, epochs, threshold, dt):
    t=np.asarray(timestamps,float);xy=np.asarray(xy,float)
    valid=np.isfinite(xy).all(axis=1)&(xy>0).all(axis=1)
    included=np.zeros(len(t),bool)
    for start,stop in epochs:
        indices=np.flatnonzero((t>=start)&(t<stop)&valid)
        if not len(indices):continue
        split=np.flatnonzero((np.diff(indices)>1)|(np.diff(t[indices])>1.5*dt))+1
        for segment in np.split(indices,split):
            if len(segment)<2:continue
            velocity=np.gradient(xy[segment],t[segment],axis=0)
            speed=np.sqrt((velocity**2).sum(axis=1))
            width=min(5,len(segment));kernel=np.ones(width)/width
            smoothed=np.convolve(speed,kernel,mode="same")
            included[segment]=smoothed>threshold
    return included

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
