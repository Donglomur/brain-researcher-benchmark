"""The single public age-blind KMeans recipe; no seed or partition search."""
import warnings

import numpy as np
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits

PARAMETERS = dict(n_clusters=7, init='k-means++', n_init=10, max_iter=300,
                  tol=1e-4, verbose=0, random_state=0, copy_x=True, algorithm='lloyd')


def fit_partition(group_features, group_valid):
    values = np.array(group_features, dtype=np.float64, order='C', copy=True)
    mask = np.asarray(group_valid, dtype=bool)
    if values.ndim != 2 or values.shape[0] != values.shape[1] or mask.shape != values.shape:
        raise ValueError('Partition input axes are invalid')
    if not mask.all():
        return dict(status='incomplete_group_connectome', labels=None, n_clusters_occupied=None,
                    centers=None, inertia=None, n_iter=None, warnings=[])
    if not np.isfinite(values).all() or not np.array_equal(values, values.T) or np.any(np.diag(values) != 0):
        raise ValueError('Complete partition input must be finite, symmetric, zero-diagonal')
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model = KMeans(**PARAMETERS)
        model.fit(values, sample_weight=None)
    occupied = len(set(model.labels_.tolist()))
    if not np.isfinite(model.cluster_centers_).all() or not np.isfinite(model.inertia_):
        raise ArithmeticError('Nonfinite KMeans result')
    return dict(status='ok' if occupied == 7 else 'fewer_than_seven_occupied_clusters',
                labels=model.labels_.astype(np.int64), n_clusters_occupied=occupied,
                centers=model.cluster_centers_.copy(), inertia=float(model.inertia_),
                n_iter=int(model.n_iter_), warnings=[f'{w.category.__name__}: {w.message}' for w in caught])
