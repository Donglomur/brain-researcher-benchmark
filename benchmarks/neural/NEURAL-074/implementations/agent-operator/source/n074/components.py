"""Prospective shared profiles and nonnegative participant spatial loadings.

This is a new explicit implementation, not a claim of literal HBM invocation parity.
"""
from dataclasses import dataclass
from .contracts import require


@dataclass(frozen=True)
class Components:
    profiles: object
    spatial_template: object
    objective: float
    iterations: int
    converged: bool


def fit_components(responses, config):
    """Minimize squared reconstruction plus L1 spatial penalty.

    Y has training-person × training-contrast × space shape. V is shared
    contrast × component; U is person × space × component, constrained U>=0.
    Each V column has norm <=1. All alignment is jointly fit on this Y only.
    """
    import numpy as np
    config.validate()
    y = np.asarray(responses, dtype=float)
    require(y.ndim == 3 and min(y.shape) > 0 and np.isfinite(y).all(), 'Invalid training response tensor')
    require(config.rank <= min(y.shape[1:]), 'Component rank exceeds training support')
    left, _, _ = np.linalg.svd(y.mean(axis=0), full_matrices=False)
    v = left[:, :config.rank].copy()
    # Resolve SVD signs using training values only, before the nonnegative fit.
    for k in range(config.rank):
        index = int(np.argmax(np.abs(v[:, k])))
        if v[index, k] < 0:
            v[:, k] *= -1
    u = np.maximum(np.einsum('scp,ck->spk', y, v), 0.0)
    def objective():
        error = np.einsum('ck,spk->scp', v, u) - y
        return float(np.sum(error * error) + config.component_penalty * np.sum(u))
    previous = objective()
    converged = False
    iteration = 0
    for iteration in range(1, config.max_iterations + 1):
        gram_v = v.T @ v
        lu = 2.0 * float(np.linalg.norm(gram_v, 2))
        require(lu > 0 and np.isfinite(lu), 'Degenerate component profile step')
        gradient_u = 2.0 * (u @ gram_v - np.einsum('scp,ck->spk', y, v))
        u = np.maximum(0.0, u - gradient_u / lu - config.component_penalty / lu)
        gram_u = np.einsum('spk,spl->kl', u, u)
        lv = 2.0 * float(np.linalg.norm(gram_u, 2))
        if lv == 0:
            # A legitimate all-zero spatial solution; keep an explicit fit disposition.
            break
        require(np.isfinite(lv), 'Nonfinite shared-profile step')
        gradient_v = 2.0 * (v @ gram_u - np.einsum('scp,spk->ck', y, u))
        v = v - gradient_v / lv
        v = v / np.maximum(1.0, np.linalg.norm(v, axis=0))[None, :]
        current = objective()
        require(np.isfinite(current), 'Nonfinite component objective')
        # Numerical slack is a fit-check convention, not a scientific threshold.
        require(current <= previous + 1e-9 * max(1.0, abs(previous)), 'Component objective increased')
        if abs(previous - current) <= config.relative_tolerance * max(1.0, abs(previous)):
            previous, converged = current, True
            break
        previous = current
    final = objective()
    require(np.isfinite(u).all() and np.isfinite(v).all(), 'Nonfinite component fit')
    # Mean aggregation matches the equal-person squared-error training target.
    return Components(v, u.mean(axis=0), final, iteration, converged)
