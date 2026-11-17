"""Frozen NEURAL-026 prospective controlled reconstruction; no I/O on import.

fit_predict is supplied method source, not executed during construction.
All learned transforms use training trials only. The shifted arm refits its
entire neural residualization/PCA/decoder pipeline after a whole-trial shift.
"""
import numpy as np

MICE = ('cfa17', 'cfa19', 'cfa20', 'cfa22', 'cfa24')
AREAS = ('M1', 'S1')
ARMS = ('nuisance', 'neural', 'shifted')
TIME_MS = np.arange(-100., 401., 10.)
N_ROIS = 128
N_FOLDS = 5
N_JOINTS = 24
N_NUISANCE = 141
ALPHA = 1.0  # mean squared loss + alpha * squared coefficient norm


def need(test, message):
    if not test:
        raise ValueError(message)


def case_ids():
    return [f'{mouse}_{area}_fold{fold}' for mouse in MICE for area in AREAS
            for fold in range(N_FOLDS)]


def validate_design(design):
    """Enforce the full pooled-once estimand before any private-reference read."""
    need(type(design) is dict and design.get('schema') == 'neural026_design_v1'
         and type(design.get('cases')) is list and len(design['cases']) == 50,
         'Exact fifty-case operator design')
    need([c.get('case_id') for c in design['cases']] == case_ids(), 'Fixed case order')
    for row in design['cases']:
        cid = row['case_id']
        mouse, area, foldtext = cid.split('_')
        fold = int(foldtext[4:])
        need(row.get('mouse') == mouse and row.get('area') == area
             and type(row.get('fold')) is int and row['fold'] == fold, 'Case identity matches biological unit/fold')
        for side in ('train_id', 'query_id'):
            ids = row.get(side)
            need(type(ids) is list and 4 <= len(ids) <= 4096
                 and all(type(i) is int and 0 < i < 2**63 for i in ids)
                 and ids == sorted(set(ids)), 'Positive sorted unique bounded trial IDs')
        need(not set(row['train_id']) & set(row['query_id']), 'Whole-trial separation')
        counts = row.get('matched_counts')
        need(type(counts) is dict and set(counts) == {'1','2'}
             and all(type(x) is int and x >= 10 for x in counts.values())
             and 20 <= sum(counts.values()) <= 4096, 'Exact matched target support')
    for mouse in MICE:
        area_counts = []
        for area in AREAS:
            rows = [r for r in design['cases'] if r['mouse'] == mouse and r['area'] == area]
            queries = [t for r in rows for t in r['query_id']]
            need(len(queries) == len(set(queries)), 'Query trials appear in exactly one fold')
            universe = set(queries); counts = rows[0]['matched_counts']
            need(len(universe) == sum(counts.values()), 'Matched complete source support')
            for r in rows:
                need(r['matched_counts'] == counts
                     and set(r['train_id']) == universe - set(r['query_id']),
                     'Each training set is the complement of its query fold')
            area_counts.append(counts)
        need(area_counts[0] == area_counts[1], 'M1/S1 matched counts per target within mouse')


def nuisance(target, duration_ms, centroid):
    """Only LR, event clock, retrospective duration, and centroid/velocity.

    centroid: trial x 51 x 6, xyz position then xyz velocity. No individual
    marker coordinates, joint angles, aperture, or query-label masks enter.
    """
    target = np.asarray(target)
    duration_ms = np.asarray(duration_ms)
    c = np.asarray(centroid, dtype=float)
    n = len(target)
    need(target.shape == duration_ms.shape == (n,) and n > 0
         and target.dtype.kind in 'iu' and np.isin(target, [1, 2]).all(), 'LR 1/2 only')
    need(c.shape == (n, 51, 6) and np.isfinite(c).all()
         and np.isfinite(duration_ms).all() and (duration_ms > 0).all(),
         'Finite complete coarse motion and positive lift-to-grab interval')
    time = np.broadcast_to(TIME_MS, (n, 51))
    phase = np.clip(time / duration_ms[:, None], 0., 1.)
    p = np.stack((phase, phase**2, phase**3, (time < 0).astype(float),
                  (time > duration_ms[:, None]).astype(float),
                  np.broadcast_to(duration_ms[:, None] / 1000., (n, 51))), axis=2)
    clock = np.eye(51)[np.broadcast_to(np.arange(51), (n, 51))]
    blocks = [clock * (target == k)[:, None, None] for k in (1, 2)]
    blocks += [p * (target == k)[:, None, None] for k in (1, 2)]
    blocks += [c, np.stack([c[:, :, i] * c[:, :, j]
                            for i in range(6) for j in range(i, 6)], axis=2)]
    out = np.concatenate(blocks, axis=2)
    need(out.shape == (n, 51, N_NUISANCE) and np.isfinite(out).all(), 'Fixed nuisance basis')
    return out


def training_shift(target):
    """Nonidentity whole-trial cyclic shift within training LR strata only."""
    target = np.asarray(target)
    need(target.ndim == 1 and target.dtype.kind in 'iu' and np.isin(target, [1, 2]).all(),
         'Training target vector')
    mapping = np.arange(len(target))
    for k in (1, 2):
        ids = np.flatnonzero(target == k)
        need(len(ids) >= 2, 'Each training target needs at least two trials; no identity fallback')
        mapping[ids] = np.roll(ids, len(ids) // 2)
    need((mapping != np.arange(len(target))).all(), 'Every training trial shifts')
    return mapping


def validate_packet(v):
    expected = {'train_x', 'train_z', 'train_y', 'train_id', 'train_target',
                'query_x', 'query_z', 'query_id', 'query_target'}
    need(set(v) == expected, 'Exact public packet; no query labels')
    for side in ('train', 'query'):
        x, z, ids, target = (v[side + '_' + k] for k in ('x', 'z', 'id', 'target'))
        n = len(ids)
        need(ids.ndim == target.ndim == 1 and ids.dtype.kind in 'iu'
             and target.dtype.kind in 'iu' and n == len(target) and 4 <= n <= 4096
             and (ids > 0).all() and (np.diff(ids.astype(np.int64)) > 0).all(),
             'Chronological distinct whole trial IDs')
        need(x.shape == (n, 51, N_ROIS) and z.shape == (n, 51, N_NUISANCE)
             and np.isfinite(x).all() and np.isfinite(z).all()
             and np.isin(target, [1, 2]).all(), 'Exact finite public covariates')
        need(all(np.count_nonzero(target == k) >= 2 for k in (1, 2)), 'Both target strata supported')
    y = v['train_y']
    need(y.shape == (len(v['train_id']), 51, N_JOINTS) and np.isfinite(y).all(), 'Training angles')
    need(not np.intersect1d(v['train_id'], v['query_id']).size, 'Whole-trial train/query separation')


def _ridge(train_x, train_y, query_x):
    """Deterministic centered/scaled ridge; coefficients penalized, intercept not."""
    mx = train_x.mean(axis=0)
    sx = train_x.std(axis=0)
    sx[sx == 0] = 1.
    my = train_y.mean(axis=0)
    a, b = (train_x - mx) / sx, train_y - my
    coef = np.linalg.solve(a.T @ a + len(a) * ALPHA * np.eye(a.shape[1]), a.T @ b)
    return a @ coef + my, ((query_x - mx) / sx) @ coef + my


def _neural_arm(x, qx, z, qz, y_residual, ridge=_ridge):
    fitted_x, predicted_x = ridge(z, x, qz)
    residual, query_residual = x - fitted_x, qx - predicted_x
    mean, scale = residual.mean(axis=0), residual.std(axis=0)
    scale[scale == 0] = 1.
    a, q = (residual - mean) / scale, (query_residual - mean) / scale
    _, s, vt = np.linalg.svd(a, full_matrices=False)
    energy = s * s
    if float(energy.sum()) == 0.:
        return np.zeros((len(q), N_JOINTS))
    count = int(np.searchsorted(np.cumsum(energy) / energy.sum(), .9)) + 1
    basis = vt[:count].T
    return ridge(a @ basis, y_residual, q @ basis)[1]


def fit_predict(packet, ridge=_ridge, neural_arm=_neural_arm):
    """One supplied method. No folds are combined, no query outcome is accepted."""
    validate_packet(packet)
    z = packet['train_z'].reshape(-1, N_NUISANCE)
    qz = packet['query_z'].reshape(-1, N_NUISANCE)
    y = packet['train_y'].reshape(-1, N_JOINTS)
    x = packet['train_x'].reshape(-1, N_ROIS)
    qx = packet['query_x'].reshape(-1, N_ROIS)
    base_train, base_query = ridge(z, y, qz)
    residual = y - base_train
    shifted_x = packet['train_x'][training_shift(packet['train_target'])].reshape(-1, N_ROIS)
    out = {'trial_id': packet['query_id'].copy(), 'nuisance': base_query}
    for arm, tx in (('neural', x), ('shifted', shifted_x)):
        out[arm] = base_query + neural_arm(tx, qx, z, qz, residual, ridge=ridge)
    for arm in ARMS:
        out[arm] = out[arm].reshape(len(packet['query_id']), 51, N_JOINTS)
        need(np.isfinite(out[arm]).all(), 'Finite complete predictions')
    return out
