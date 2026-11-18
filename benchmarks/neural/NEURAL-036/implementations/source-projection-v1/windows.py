"""Literal NEURAL-036 operator projection; no file I/O or scientific fitting.

Input clocks must already be seconds in the same verified time frame. This
function cannot establish clock provenance or the physical meaning of a proxy.
The full-session source may already contain noncausal preprocessing.
"""
import numpy as np


def _array(value, dimensions, name):
    if type(value) is not np.ndarray or value.ndim != dimensions:
        raise ValueError(name + " geometry")
    if value.dtype.kind not in "fiu" or not np.isfinite(value).all():
        raise ValueError(name + " must contain finite real numbers")
    if value.dtype.kind == "f" and value.dtype.itemsize > 8:
        raise ValueError(name + " extended-precision dtype is not admitted")


def project(x, t, behavior, clock):
    """Return all five original blocks and private target/persistence arrays.

    This is operator-only preparation. Never deliver this complete dictionary to
    a participant: use views.project_view to select the permitted role and arm.
    Array validation adds fail-closed geometry checks; the grid expressions and
    right-sided predecessor lookup preserve the pinned historical implementation.
    """
    _array(x, 2, "neural")
    _array(t, 1, "neural clock")
    _array(behavior, 1, "behavior proxy")
    _array(clock, 1, "behavior clock")
    if (not len(t) or not len(clock) or x.shape[1] < 1 or
            len(t) != len(x) or len(clock) != len(behavior)):
        raise ValueError("nonempty aligned source geometry required")
    if not ((t[1:] > t[:-1]).all() and (clock[1:] > clock[:-1]).all()
            and np.isin(behavior, (0, 1)).all()):
        raise ValueError("strictly ordered clocks and binary proxy required")

    base = np.arange(5, dtype=float)[:, None] * 60
    past = base + 10.05 + np.arange(300)[None, :] * .1
    shifted = base + .05 + np.arange(300)[None, :] * .1
    future = base + 50.05 + np.arange(100)[None, :] * .1

    def neural(grid):
        index = np.searchsorted(t, grid, side="right") - 1
        if index.min() < 0 or grid.max() > t[-1]:
            raise ValueError("no neural extrapolation")
        return x[index].astype("<f8", copy=False)

    def state(grid):
        index = np.searchsorted(clock, grid, side="right") - 1
        if index.min() < 0 or grid.max() > clock[-1]:
            raise ValueError("no behavior extrapolation")
        return behavior[index].astype("<f8", copy=False)

    history = state(past)
    return {"neural": neural(past), "shifted": neural(shifted),
            "history": history, "target": state(future).mean(axis=1),
            "persistence": history.mean(axis=1)}
