"""Explicit map quantities; choosing a primary metric is a separate selected contract."""
from .contracts import require


def map_quantities(prediction, target):
    import numpy as np
    p = np.asarray(prediction, dtype=float)
    y = np.asarray(target, dtype=float)
    require(p.ndim == y.ndim == 1 and p.shape == y.shape and len(p) > 1, 'Map geometry mismatch')
    require(np.isfinite(p).all() and np.isfinite(y).all(), 'Nonfinite map')
    error = p - y
    pc, yc = p - p.mean(), y - y.mean()
    denom = float(np.linalg.norm(pc) * np.linalg.norm(yc))
    correlation = None if denom == 0 else float(np.dot(pc, yc) / denom)
    if correlation is not None:
        require(abs(correlation) <= 1 + 1e-10, 'Correlation outside numerical domain')
        correlation = max(-1.0, min(1.0, correlation))
    result = {'map_correlation': correlation,
            'correlation_status': 'undefined_constant_map' if correlation is None else 'defined',
            'mean_squared_error': float(np.mean(error * error)),
            'mean_absolute_error': float(np.mean(np.abs(error))),
            'mean_bias': float(np.mean(error)),
            'prediction_mean': float(p.mean()), 'target_mean': float(y.mean())}
    require(all(np.isfinite(v) for k, v in result.items() if k != 'correlation_status' and v is not None),
            'Nonfinite score arithmetic')
    return result


def tuning_loss(predictions, targets, metric):
    require(len(predictions) == len(targets) and len(targets) > 0, 'Incomplete validation pairing')
    values = [map_quantities(p, y) for p, y in zip(predictions, targets)]
    require(metric in ('mean_squared_error', 'map_correlation'), 'Unknown tuning metric')
    require(all(v[metric] is not None for v in values), 'Undefined validation metric; do not drop a condition')
    sign = -1 if metric == 'map_correlation' else 1
    return sign * sum(v[metric] for v in values) / len(values)
