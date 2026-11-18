"""Frozen generated-control predecessor, not an available scientific operator.

The fit_target_scale body below is retained verbatim from models.py SHA256
114f941268ff51ddb7a4acfe29ddd1826b843f2af842ba3469badf7d2e1f4cec,
lines358..374. It preserves the original rounding-defect counterexample after
that module is repaired. The small support definitions only satisfy its API.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class TargetScale:
    mean: object
    sigma: object

def need(condition, message):
    if not condition:
        raise ValueError(message)

def reserve_array(owner, shape, *, itemsize=8, copies=1):
    size = 1
    for width in shape:
        size *= width
    owner.reserve("retained_bytes", size * itemsize * copies)

def fit_target_scale(raw_targets, weights, owner):
    import numpy as np
    need(raw_targets.ndim == 2 and raw_targets.shape[1] == 127 * 150 and
         raw_targets.shape[0] == len(weights), "Complete target fit basis")
    reserve_array(owner, tuple(map(int, raw_targets.shape)), copies=3)
    reserve_array(owner, (127 * 150,), copies=3)
    mean = weights @ raw_targets
    centered = raw_targets - mean
    sigma = np.sqrt(weights @ (centered ** 2))
    constant = np.all(raw_targets == raw_targets[0], axis=0)
    need(not constant.any() and np.isfinite(mean).all() and np.isfinite(sigma).all() and
         np.all(sigma > 0), "Undefined or constant target coordinate makes full case unavailable")
    mean.setflags(write=False)
    sigma.setflags(write=False)
    standardized = centered / sigma
    need(np.isfinite(standardized).all(), "Finite full standardized target matrix")
    return TargetScale(mean, sigma), standardized
