"""Public MOVIESYNC equations; no source I/O or verifier imports."""
from __future__ import annotations
import math
import numpy as np
from scipy import linalg, signal

IDS = tuple(f'sub-pixar{i:03d}' for i in (*range(1, 32), *range(123, 132)))
VISUAL = ('Vis', 'Striate', 'Occ post')
CONFOUNDS = ('trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z',
             'framewise_displacement', 'a_comp_cor_00', 'a_comp_cor_01',
             'a_comp_cor_02', 'a_comp_cor_03', 'a_comp_cor_04', 'a_comp_cor_05',
             'csf', 'white_matter')
EPS = np.finfo(np.float64).eps
N_FRAMES = 168
ACTIVE_BOUND = 1e-12 * math.sqrt(N_FRAMES)


class PreconditionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreconditionError(message)


def real_array(value, shape=None):
    raw = np.asarray(value)
    require(raw.dtype.kind in 'iuf' and raw.dtype.kind != 'b', 'real numeric array')
    x = np.asarray(raw, dtype=np.float64)
    require(np.isfinite(x).all(), 'finite scientific array')
    if shape is not None:
        require(x.shape == shape, f'array shape must be {shape}')
    return x


def extract_coefficients(maps, bold):
    m = real_array(maps)
    y = real_array(bold)
    require(m.ndim == 4 and m.shape[-1] == 39, '39 spatial maps')
    require(y.shape == m.shape[:3] + (N_FRAMES,), 'matching BOLD grid and168frames')
    design = np.ascontiguousarray(m.reshape((-1, 39), order='C'))
    observations = np.ascontiguousarray(y.reshape((-1, N_FRAMES), order='C'))
    coef, _, rank, singular = linalg.lstsq(
        design, observations, cond=EPS, lapack_driver='gelsd',
        overwrite_a=False, overwrite_b=False, check_finite=True)
    require(np.isfinite(coef).all() and np.isfinite(singular).all(), 'finite map fit')
    return coef.T.copy(), int(rank), singular


def clean_coefficients(coefficients, confounds):
    x = real_array(coefficients, (N_FRAMES, 39))
    c = real_array(confounds, (N_FRAMES, len(CONFOUNDS)))
    sos = signal.butter(5, [0.01, 0.1], btype='bandpass', fs=0.5, output='sos')
    filtered = signal.sosfiltfilt(sos, x, axis=0, padtype='odd', padlen=33)
    filtered_c = signal.sosfiltfilt(sos, c, axis=0, padtype='odd', padlen=33)
    centered_c = filtered_c - filtered_c.mean(axis=0)
    scales = centered_c.std(axis=0, ddof=0)
    scales[scales < EPS] = 1.0
    standardized_c = centered_c / scales
    q, r, pivots = linalg.qr(standardized_c, mode='economic', pivoting=True)
    diagonal = np.abs(np.diag(r))
    q = q[:, diagonal > 100 * EPS]
    residual = filtered - q @ (q.T @ filtered)
    centered = residual - residual.mean(axis=0)
    sd = centered.std(axis=0, ddof=1)
    divisors = np.where(sd < EPS, 1.0, sd)
    cleaned = centered / divisors
    require(np.isfinite(cleaned).all(), 'finite standardized residuals')
    private = dict(filtered_coefficients=filtered, filtered_confounds=filtered_c,
                   standardized_confounds=standardized_c, nuisance_q=q,
                   nuisance_qr_diagonal=diagonal, nuisance_pivots=pivots,
                   residual_coefficients=residual, sample_sd=sd, sos=sos)
    return cleaned, int(q.shape[1]), private


def center(x):
    x = real_array(x)
    require(x.ndim == 1 and len(x) > 0, 'one complete time vector')
    if np.all(x == x[0]):
        return np.zeros_like(x)
    return x - math.fsum(map(float, x)) / len(x)


def norm(x):
    x = real_array(x)
    scale = float(np.max(np.abs(x)))
    return 0. if scale == 0 else scale * math.sqrt(math.fsum(float(v / scale)**2 for v in x))


def support(series):
    x = real_array(series)
    require(x.ndim == 3 and x.shape[1:] == (N_FRAMES, 3) and x.shape[0] >= 2,
            'person by168frames by3visual series')
    norms = np.empty((len(x), 3))
    templates = np.empty_like(x)
    for i in range(len(x)):
        for k in range(3):
            norms[i, k] = norm(center(x[i, :, k]))
            for t in range(N_FRAMES):
                templates[i, t, k] = math.fsum(float(x[j, t, k]) for j in range(len(x)) if j != i) / (len(x) - 1)
    template_norms = np.asarray([[norm(center(templates[i, :, k])) for k in range(3)] for i in range(len(x))])
    return norms > ACTIVE_BOUND, template_norms > ACTIVE_BOUND, templates, norms, template_norms


def correlation(a, b):
    a = center(a)
    b = center(b)
    na, nb = norm(a), norm(b)
    require(na > 0 and nb > 0, 'active vector has nonzero centered norm')
    value = math.fsum(float(av / na) * float(bv / nb) for av, bv in zip(a, b))
    require(math.isfinite(value) and abs(value) <= 1 + 1e-12, 'correlation numerical domain')
    return max(-1., min(1., value))


def aggregate(values, expected):
    require(len(values) == expected, 'complete aggregate membership')
    defined = [float(v) for v in values if v is not None]
    require(all(math.isfinite(v) for v in defined), 'finite defined correlations')
    complete = len(defined) == expected
    return dict(value=math.fsum(defined) / expected if complete else None,
                status='ok' if complete else 'incomplete_support',
                n_expected=expected, n_defined=len(defined))


def derive(series, participant_ids, visual_ids, map_labels, *, estimator='pairwise',
           person_active=None, template_active=None):
    x = real_array(series)
    ids = list(participant_ids)
    vi = [int(v) for v in visual_ids]
    require(len(ids) == len(set(ids)) == x.shape[0] and len(ids) >= 2, 'unique person axes')
    require(len(vi) == len(set(vi)) == 3 and len(map_labels) == 39, 'visual map axes')
    require(estimator in ('pairwise', 'loo', 'leave-one-out'), 'declared estimator')
    pa, ta, templates, norms, tnorms = support(x)
    if person_active is not None:
        require(np.asarray(person_active).dtype == bool and np.shape(person_active) == pa.shape, 'Boolean person support')
        pa = np.asarray(person_active)
    if template_active is not None:
        require(np.asarray(template_active).dtype == bool and np.shape(template_active) == ta.shape, 'Boolean template support')
        ta = np.asarray(template_active)
    n = len(ids)
    pair_values = [[[None for _ in range(n)] for _ in range(n)] for _ in vi]
    pairs = []
    for k, mid in enumerate(vi):
        for i in range(n):
            for j in range(i + 1, n):
                value = correlation(x[i, :, k], x[j, :, k]) if pa[i, k] and pa[j, k] else None
                pair_values[k][i][j] = pair_values[k][j][i] = value
                pairs.append(dict(participant_a=ids[i], participant_b=ids[j], map_id=mid,
                                  map_label=map_labels[mid], r=value,
                                  status='ok' if value is not None else 'inactive_person'))
    rows = []
    person_values = {'pairwise': [[] for _ in ids], 'loo': [[] for _ in ids]}
    region_values = {'pairwise': [[] for _ in vi], 'loo': [[] for _ in vi]}
    for i, pid in enumerate(ids):
        for k, mid in enumerate(vi):
            pv = aggregate([pair_values[k][i][j] for j in range(n) if j != i], n - 1)
            status = 'inactive_target' if not pa[i, k] else ('inactive_template' if not ta[i, k] else 'ok')
            lv = correlation(x[i, :, k], templates[i, :, k]) if status == 'ok' else None
            rows.append(dict(participant_id=pid, map_id=mid, map_label=map_labels[mid],
                             isc_pairwise=pv['value'], pairwise_status='ok' if pv['status'] == 'ok' else 'incomplete_pair_support',
                             pairwise_n_expected=n - 1, pairwise_n_defined=pv['n_defined'],
                             isc_loo=lv, loo_status=status, loo_n_expected=n - 1, loo_n_defined=n - 1,
                             loo_n_active_contributors=int(np.count_nonzero(np.delete(pa[:, k], i)))))
            person_values['pairwise'][i].append(pv['value'])
            person_values['loo'][i].append(lv)
            region_values['loo'][k].append(lv)
    people = [dict(participant_id=pid, **{key: aggregate(person_values[key][i], 3) for key in person_values})
              for i, pid in enumerate(ids)]
    regions = []
    for k, mid in enumerate(vi):
        values = [pair_values[k][i][j] for i in range(n) for j in range(i + 1, n)]
        regions.append(dict(map_id=mid, map_label=map_labels[mid],
                            pairwise=aggregate(values, n * (n - 1) // 2),
                            loo=aggregate(region_values['loo'][k], n)))
    estimators = {key: aggregate([row[key]['value'] for row in people], n) for key in person_values}
    chosen = 'loo' if estimator == 'leave-one-out' else estimator
    results = dict(schema_version='moviesync-results-v2', status='ok', isc_estimator=estimator,
                   visual_isc=estimators[chosen]['value'], visual_isc_status=estimators[chosen]['status'],
                   n_subjects=n, n_timepoints=N_FRAMES, reference_zero=0., estimators=estimators,
                   per_region=regions, per_subject=people)
    return dict(pairs=pairs, rows=rows, results=results, person_active=pa,
                template_active=ta, templates=templates, person_norms=norms, template_norms=tnorms)
