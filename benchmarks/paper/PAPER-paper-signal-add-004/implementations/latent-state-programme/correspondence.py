"""Separate native comparison views. Literal source arrays are never rewritten."""
from core import need


def match(reference_covariances, candidate_covariances, reference_frame, candidate_frame):
    """Held library RV objective and SciPy assignment, only in equal coordinates.

    No query arrays, outcomes or alternate representation are accepted. Exact
    ties retain the bound SciPy operation's result and are explicitly reported.
    """
    need(reference_frame == candidate_frame and reference_frame,
         'Authenticated identical native prepared coordinates required')
    import numpy as np
    import scipy
    from scipy.optimize import linear_sum_assignment
    a = np.asarray(reference_covariances, dtype='float64')
    b = np.asarray(candidate_covariances, dtype='float64')
    need(a.shape == b.shape and a.ndim == 3 and a.shape[0] in (3, 7, 8)
         and a.shape[1] == a.shape[2] and np.isfinite(a).all() and np.isfinite(b).all(),
         'Complete native covariance stacks')
    k = len(a)
    cost = np.empty((k, k))
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        ag = [x @ x.T for x in a]
        bg = [x @ x.T for x in b]
        for i in range(k):
            for j in range(k):
                numerator = np.trace(ag[i].T @ bg[j])
                denominator = np.sqrt(np.trace(ag[i].T @ ag[i])*np.trace(bg[j].T @ bg[j]))
                need(denominator > 0, 'Defined RV similarity for every state')
                cost[i, j] = -numerator/denominator
    need(np.isfinite(cost).all(), 'Representable complete RV costs')
    row, order = linear_sum_assignment(cost)
    need(np.array_equal(row, np.arange(k)), 'Complete one-to-one assignment')
    optimum = float(cost[row, order].sum())
    # Probe alternatives only to report assignment ambiguity. They never replace
    # the original solver order or optimize any scientific observable.
    alternate_equal_optimum = False
    for i, j in zip(row, order):
        altered = cost.copy()
        altered[i, j] = np.inf
        r, c = linear_sum_assignment(altered)
        if float(altered[r, c].sum()) == optimum:
            alternate_equal_optimum = True
    return {'order': order.tolist(), 'cost': cost.tolist(), 'total_cost': optimum,
            'equal_optimum_detected': alternate_equal_optimum,
            'solver': 'scipy.optimize.linear_sum_assignment', 'scipy_version': scipy.__version__,
            'coordinate_binding': reference_frame,
            'biological_identity_established': False, 'query_used': False}


def permute(value, order, state_axes):
    """Apply one fixed permutation to every declared state axis, on a copy."""
    import numpy as np
    need(type(order) is list and sorted(order) == list(range(len(order))), 'Full permutation')
    x = np.asarray(value)
    need(type(state_axes) in (tuple, list) and len(set(state_axes)) == len(state_axes), 'Unique explicit state axes')
    result = x.copy()
    for axis in state_axes:
        need(type(axis) is int and 0 <= axis < result.ndim and result.shape[axis] == len(order),
             'Every state axis matches complete permutation')
        result = np.take(result, order, axis=axis)
    return result
