"""Stable complete-basis weighted TRAIN moments for the NEURAL-080 readout.

An additive numerical repair candidate. The preserved generalization operator
still uses its pinned predecessor; selecting this kernel requires selecting it
for BOTH reference construction and scorer scale reconstruction. No study input
is opened at import. Generated controls do not qualify authentic EEG or fits.
"""
from dataclasses import dataclass

TARGET_WIDTH = 127 * 150


@dataclass(frozen=True)
class TargetScale:
    mean: object
    sigma: object


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def fit_target_scale(raw_targets, weights, owner):
    """Return mean, population sigma, and same-basis standardized TRAIN values.

    Each coordinate is anchored at an observed TRAIN value, then divided by its
    maximum TRAIN deviation before evaluating weighted moments. This avoids
    squaring dimensional tiny/large deviations and computing variance around a
    rounded large-offset mean. All 19,050 coordinates must remain nonconstant.

    The stored mean is necessarily one representable float64 value. As in the
    predecessor's interface, standardized values use that stored mean; their
    weighted mean can be nonzero at machine precision. prepare_ridge's explicit
    target intercept handles it. Do not silently assume a zero intercept.
    """
    import numpy as np

    _need(type(raw_targets) is np.ndarray and raw_targets.ndim == 2 and
          raw_targets.shape[1] == TARGET_WIDTH and raw_targets.shape[0] >= 2 and
          raw_targets.dtype == np.dtype('float64'),
          'Complete float64 TRAIN matrix with 127 channels by 150 bins required')
    _need(type(weights) is np.ndarray and weights.shape == (raw_targets.shape[0],) and
          weights.dtype == np.dtype('float64'), 'Aligned float64 TRAIN weights required')
    # The source Owner counts cumulative logical payload allocation, not peak
    # resident memory. Charge conservative temporaries before their allocation.
    owner.reserve('retained_bytes', raw_targets.nbytes * 6 + TARGET_WIDTH * 8 * 9 +
                  weights.nbytes * 3 + raw_targets.size + weights.size)
    _need(np.isfinite(raw_targets).all() and np.isfinite(weights).all() and
          np.all(weights > 0), 'Finite complete TRAIN values and positive weights required')
    total = weights.sum()
    _need(np.isfinite(total) and abs(float(total) - 1.0) <= 32 * np.finfo(np.float64).eps,
          'Source family/person weights must already be normalized')
    # Remove accumulated roundoff in the sum; do not accept arbitrary weights.
    normalized_weights = weights / total
    anchor = raw_targets[0]
    with np.errstate(over='ignore', invalid='ignore', under='ignore', divide='ignore'):
        shifted = raw_targets - anchor
        _need(np.isfinite(shifted).all(), 'TRAIN deviations are not representable')
        spread = np.max(np.abs(shifted), axis=0)
        _need(np.all(spread > 0), 'Constant target coordinate makes the complete case unavailable')
        shifted /= spread
        centered_mean = normalized_weights @ shifted
        centered = shifted - centered_mean
        variance = normalized_weights @ (centered * centered)
        sigma = spread * np.sqrt(variance)
        mean = anchor + spread * centered_mean
        _need(np.isfinite(mean).all() and np.isfinite(sigma).all() and np.all(sigma > 0),
              'Every TRAIN target mean and positive sigma must be representable')
        standardized = (raw_targets - mean) / sigma
    _need(np.isfinite(standardized).all(), 'Finite full standardized target matrix required')
    mean.setflags(write=False)
    sigma.setflags(write=False)
    return TargetScale(mean, sigma), standardized
