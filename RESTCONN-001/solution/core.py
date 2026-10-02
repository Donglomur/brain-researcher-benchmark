"""Prospective RESTCONN oracle arithmetic; import-safe, no source/grader I/O.

Joint-map least squares uses SciPy gelsd. Cleaning is the public explicit
Nilearn-0.13.1-inspired recipe, including (Q @ Q.T) @ Y. It is not an
unconditional equivalence claim for Nilearn's API: near-dependent nuisance
columns can amplify layout-dependent normalization roundoff into different
retained QR directions. The frozen operational threshold is not ideal rank.
Circular evidence is implemented here independently of the verifier.
"""
from __future__ import annotations
import math
import numpy as np
from scipy import linalg, signal

PARTICIPANT = '0010064'
TARGETS = ('R DMN', 'Cereb')
CONFOUND_SET = frozenset(('motion-pitch', 'motion-roll', 'motion-yaw', 'motion-x',
    'motion-y', 'motion-z', 'compcor1', 'compcor2', 'compcor3', 'compcor4',
    'compcor5', 'csf', 'wm'))
EPS = np.finfo(np.float64).eps


class PreconditionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreconditionError(message)


def real_array(values, shape=None):
    def reject_bool(v):
        if isinstance(v, (bool, np.bool_)):
            raise PreconditionError('Boolean is not a scientific number')
        if isinstance(v, (list, tuple)):
            for item in v: reject_bool(item)
    reject_bool(values)
    a = np.asarray(values)
    require(a.dtype.kind in 'iuf' and np.isfinite(a).all(), 'finite real scientific array')
    require(shape is None or a.shape == shape, 'scientific array shape')
    return np.array(a, dtype=np.float64, copy=True, order='C')


def extract_coefficients(maps, bold):
    m, y = real_array(maps), real_array(bold)
    require(m.ndim == 4 and m.shape[-1] == 39, 'all 39 spatial maps required')
    require(y.ndim == 4 and y.shape[:3] == m.shape[:3] and y.shape[-1] > 33,
            'matching full grid and complete frames >33')
    a = np.ascontiguousarray(m.reshape((-1, 39), order='C'))
    b = np.ascontiguousarray(y.reshape((-1, y.shape[-1]), order='C'))
    coef, _, rank, singular = linalg.lstsq(a, b, cond=EPS, lapack_driver='gelsd',
        overwrite_a=False, overwrite_b=False, check_finite=True)
    require(np.isfinite(coef).all() and np.isfinite(singular).all(), 'finite minimum-norm map fit')
    return coef.T.copy(), int(rank), singular


def detrend(a):
    x = a.copy()
    x -= x.mean(axis=0)
    trend = np.arange(len(x), dtype=np.float64)
    trend -= trend.mean()
    length = np.sqrt((trend ** 2).sum())
    if length >= EPS: trend /= length
    x -= np.dot(trend, x) * trend[:, None]
    return x


def scaled_center(values):
    x = real_array(values)
    require(x.ndim == 1 and len(x) >= 2, 'complete time vector')
    if x.max() == x.min():
        return np.zeros_like(x), 0.
    scale = float(np.max(np.abs(x)))
    u = x / scale
    return u - math.fsum(map(float, u)) / len(u), scale


def stable_norm(values):
    a = real_array(values)
    require(a.ndim == 1 and len(a) > 0, 'norm vector')
    scale = float(np.max(np.abs(a)))
    result = 0. if scale == 0 else scale * math.sqrt(math.fsum(float(v / scale) ** 2 for v in a))
    require(math.isfinite(result), 'finite stable norm')
    return result


def centered_norm(values):
    c, scale = scaled_center(values)
    result = scale * stable_norm(c)
    require(math.isfinite(result), 'finite centered norm')
    return result


def clean_coefficients(raw_coefficients, confounds):
    raw, c = real_array(raw_coefficients), real_array(confounds)
    require(raw.ndim == c.ndim == 2 and len(raw) == len(c) > 33 and
            raw.shape[1] == 39 and c.shape[1] == 13, 'complete 39 maps and 13 nuisance columns')
    y, c = detrend(raw), detrend(c)
    sos = signal.butter(5, [.01, .1], btype='bandpass', fs=.5, output='sos')
    y = signal.sosfiltfilt(sos, y, axis=0, padtype='odd', padlen=33)
    c = signal.sosfiltfilt(sos, c, axis=0, padtype='odd', padlen=33)
    c -= c.mean(axis=0)
    sd = c.std(axis=0, ddof=0)
    sd[sd < EPS] = 1.
    c /= sd
    q, r, pivots = linalg.qr(c, mode='economic', pivoting=True)
    retained = np.abs(np.diag(r)) > 100 * EPS
    q = q[:, retained]
    residual = y - (q @ q.T) @ y
    residual -= residual.mean(axis=0)
    sample_sd = residual.std(axis=0, ddof=1)
    divisor = sample_sd.copy()
    divisor[divisor < EPS] = 1.
    z = residual / divisor
    raw_sd = np.array([centered_norm(raw[:, i]) / math.sqrt(len(raw) - 1) for i in range(39)])
    norms = np.array([centered_norm(residual[:, i]) for i in range(39)])
    thresholds = 1e-12 * math.sqrt(len(raw)) * np.maximum(1., raw_sd)
    active = norms > thresholds
    z[:, ~active] = 0.
    require(all(np.isfinite(a).all() for a in (z, raw_sd, norms, thresholds)), 'finite cleanup/support')
    return dict(cleaned=z, confound_rank=int(retained.sum()), raw_sample_sd=raw_sd,
        residual_centered_l2=norms, activity_threshold=thresholds, active=active,
        residual_before_zscore=residual, filtered_coefficients=y, standardized_confounds=c,
        nuisance_q=q, nuisance_pivots=pivots, nuisance_qr_diagonal=np.abs(np.diag(r)), sos=sos)


def circular_evidence(cleaned, active):
    y = real_array(cleaned)
    a = np.asarray(active)
    require(y.ndim == 2 and y.shape[1] == 2 and len(y) > 1, 'two full target vectors')
    require(a.shape == (2,) and a.dtype.kind == 'b', 'two Boolean canonical activity flags')
    n = len(y)
    shifts = list(range(1, n))
    inactive = [TARGETS[i] for i in range(2) if not a[i]]
    status = 'inactive_target' if inactive else 'ok'
    inference = dict(method='circular_shift_all', shifted_region=TARGETS[0],
        shift_direction='positive_np_roll', shifts=shifts, null_r=[None] * (n - 1),
        exceeds=[None] * (n - 1), n_exceedances=None, numerator=None,
        denominator=n, alpha=.05, p_value=None, significant=None,
        inactive_regions=inactive, status=status)
    result = dict(subject=PARTICIPANT, region_a=TARGETS[0], region_b=TARGETS[1],
        n_timepoints=n, status=status, r=None, p_value=None, significant=None, inference=inference)
    if inactive: return result
    x, _ = scaled_center(y[:, 0])
    z, _ = scaled_center(y[:, 1])
    denominator = stable_norm(x) * stable_norm(z)
    require(denominator > 0 and math.isfinite(denominator), 'active vectors need nonzero norms')
    def dot(k):
        return math.fsum(float(x[(t - k) % n]) * float(z[t]) for t in range(n))
    def ratio(value):
        r = value / denominator
        require(math.isfinite(r) and abs(r) <= 1 + 1e-12, 'correlation roundoff domain')
        return max(-1., min(1., r))
    observed = dot(0)
    dots = [dot(k) for k in shifts]
    exceeds = [abs(v) >= abs(observed) for v in dots]
    count = sum(exceeds)
    p = (1 + count) / n
    significant = 20 * (1 + count) < n
    inference.update(null_r=[ratio(v) for v in dots], exceeds=exceeds, n_exceedances=count,
        numerator=1 + count, p_value=p, significant=significant)
    result.update(r=ratio(observed), p_value=p, significant=significant)
    return result
