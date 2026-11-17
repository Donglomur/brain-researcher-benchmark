"""Actual full-rank and rank-matched ridge consumers; not executed during construction."""
from dataclasses import dataclass
from .contracts import require, positive


@dataclass(frozen=True)
class Ridge:
    coefficients: object
    feature_mean: object
    target_mean: object

    def predict(self, features):
        import numpy as np
        x = np.asarray(features, dtype=float)
        require(x.ndim == 2 and x.shape[1] == self.coefficients.shape[0], 'Prediction feature geometry mismatch')
        require(np.isfinite(x).all(), 'Nonfinite prediction features')
        out = (x - self.feature_mean) @ self.coefficients + self.target_mean
        require(np.isfinite(out).all(), 'Nonfinite ridge prediction')
        return out


def fit_ridge(features, targets, penalty, rank=None):
    import numpy as np
    positive(penalty, 'ridge penalty')
    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    require(x.ndim == y.ndim == 2 and x.shape[0] == y.shape[0] and x.shape[0] > 1,
            'Ridge expects aligned nontrivial training rows')
    require(np.isfinite(x).all() and np.isfinite(y).all(), 'Nonfinite training values')
    xm, ym = x.mean(axis=0), y.mean(axis=0)
    xc, yc = x - xm, y - ym
    gram = xc.T @ xc + penalty * np.eye(x.shape[1])
    full = np.linalg.solve(gram, xc.T @ yc)
    if rank is None:
        coefficients = full
    else:
        require(type(rank) is int and 0 < rank <= min(full.shape), 'Requested rank is not supported')
        # Whiten by the ridge quadratic form. Truncation here solves the
        # penalized reduced-rank objective; truncating raw B is not equivalent.
        chol = np.linalg.cholesky(gram)
        weighted = chol.T @ full
        u, singular, vt = np.linalg.svd(weighted, full_matrices=False)
        low = (u[:, :rank] * singular[:rank]) @ vt[:rank, :]
        coefficients = np.linalg.solve(chol.T, low)
    require(np.isfinite(coefficients).all(), 'Nonfinite fitted coefficients')
    return Ridge(coefficients, xm, ym)
