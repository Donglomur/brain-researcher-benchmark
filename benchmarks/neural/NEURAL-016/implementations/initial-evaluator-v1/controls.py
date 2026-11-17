"""Bounded engineering utilities; no dataset/model access or inferential claims."""
from __future__ import annotations

import numpy as np
from evaluator import ContractError, require


def joint_linguistic_circular_shift(times, linguistic_features, shift_steps: int,
                                   minimum_displacement_seconds: float):
    """Shift all linguistic columns together on one uniformly sampled block.

    A circular shift preserves *circular* discrete autocorrelation and the joint
    linguistic feature geometry. It does not establish a conditional null given
    acoustics/visual covariates. Irregular word-event tables are rejected: shifting
    their row indices does not preserve physical-time autocorrelation. Apply
    separately to each frozen continuous block, then refit the complete frozen
    recipe; never move information across train/test partitions.
    """
    t = np.asarray(times, dtype=float)
    x = np.asarray(linguistic_features, dtype=float)
    require(t.ndim == 1 and len(t) >= 3, "uniform time block needs at least three points")
    require(x.ndim == 2 and x.shape[0] == len(t) and x.shape[1] > 0, "linguistic features must be samples by columns")
    require(bool(np.isfinite(t).all()) and bool(np.isfinite(x).all()), "nonfinite control input")
    spacing = np.diff(t)
    require(bool(np.all(spacing > 0)), "time must increase")
    require(bool(np.allclose(spacing, spacing[0], rtol=1e-7, atol=1e-10)), "irregular event times cannot use time-preserving shift")
    require(isinstance(shift_steps, int) and not isinstance(shift_steps, bool), "shift_steps must be an integer")
    require(0 < shift_steps < len(t), "shift must be nonidentity and inside block")
    require(isinstance(minimum_displacement_seconds, (int, float)) and not isinstance(minimum_displacement_seconds, bool)
            and np.isfinite(minimum_displacement_seconds) and minimum_displacement_seconds > 0,
            "minimum displacement must be finite and positive")
    distance = min(shift_steps, len(t) - shift_steps) * spacing[0]
    require(distance >= minimum_displacement_seconds, "circular displacement is below temporal guard")
    shifted = np.roll(x, shift_steps, axis=0)
    require(not bool(np.array_equal(shifted, x)), "degenerate shift leaves every linguistic feature unchanged")
    return shifted
