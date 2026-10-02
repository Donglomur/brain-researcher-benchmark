"""Public GRADIENT mathematics; no source access or grader/reference imports.

Canonical input arithmetic shares NumPy/SciPy with verification as disclosed.
The oracle uses a symmetric eigensolve in the stationary-orthogonal subspace;
certificates, not a secret eigenvector array, establish spectral equivalence.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import linalg, signal

NETWORKS = ('Vis', 'SomMot', 'DorsAttn', 'SalVentAttn', 'Limbic', 'Cont', 'Default')
CONFIGS = ('nobp_all', 'bp_all', 'nobp_firstHalf', 'nobp_secondHalf')
CONFOUNDS = ('trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z',
             'framewise_displacement', 'a_comp_cor_00', 'a_comp_cor_01',
             'a_comp_cor_02', 'a_comp_cor_03', 'a_comp_cor_04', 'a_comp_cor_05',
             'csf', 'white_matter')
N_FRAMES, N_PARCELS, N_COMPONENTS = 168, 400, 10
EPS = np.finfo(np.float64).eps
GAP = 4e-8


class PreconditionError(ValueError):
    pass


def require(condition, message):
    if not bool(condition):
        raise PreconditionError(message)


def real_array(value, ndim=None, finite=True):
    array = np.asarray(value)
    require(array.dtype.kind in 'fiu' and array.dtype.kind != 'b', 'real nonBoolean array')
    if ndim is not None:
        require(array.ndim == ndim, 'array dimensionality')
    array = np.asarray(array, dtype=np.float64)
    if finite:
        require(np.isfinite(array).all(), 'finite arithmetic inputs')
    return array


def centered(vector):
    x = real_array(vector, 1)
    require(x.size > 0, 'nonempty vector')
    if np.max(x) == np.min(x):
        return np.zeros_like(x)
    result = x - math.fsum(float(v) for v in x) / len(x)
    require(np.isfinite(result).all(), 'finite centered vector')
    return result


def norm(vector):
    x = real_array(vector, 1)
    if not x.size:
        return 0.
    scale = float(np.max(np.abs(x)))
    if scale == 0:
        return 0.
    result = scale * math.sqrt(math.fsum(float(v) ** 2 for v in x / scale))
    require(math.isfinite(result), 'finite norm')
    return result


def pearson(left, right):
    a, b = centered(left), centered(right)
    require(a.shape == b.shape and len(a) >= 2, 'paired Pearson support')
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return None
    value = math.fsum(float(x) * float(y) for x, y in zip(a / na, b / nb))
    require(abs(value) <= 1 + 1e-12, 'Pearson outside roundoff envelope')
    return min(1., max(-1., value))


def detrend(matrix):
    x = real_array(matrix, 2).copy()
    require(x.shape[0] >= 2, 'detrend frame support')
    constants = np.all(x == x[0], axis=0)
    x -= np.mean(x, axis=0)
    time = np.arange(len(x), dtype=np.float64)
    time -= np.mean(time)
    time /= np.sqrt(np.sum(time ** 2))
    x -= time[:, None] * (time @ x)[None, :]
    x[:, constants] = 0.
    require(np.isfinite(x).all(), 'finite detrending')
    return x


def preprocess(raw, confounds, geometry):
    raw = real_array(raw, 2, finite=False)
    confounds = real_array(confounds, 2)
    geometry = np.asarray(geometry)
    require(geometry.dtype == np.bool_ and geometry.shape == (raw.shape[1],), 'geometry mask')
    require(len(raw) == len(confounds) and len(raw) > 33, 'cleaning frame support')
    require(np.isfinite(raw[:, geometry]).all() and np.isnan(raw[:, ~geometry]).all(), 'raw geometry nulls')
    c = detrend(confounds)
    c -= np.mean(c, axis=0)
    sd = np.std(c, axis=0, ddof=0)
    sd[sd < EPS] = 1.
    c /= sd
    q, r, _ = linalg.qr(c, mode='economic', pivoting=True)
    q = q[:, np.abs(np.diag(r)) > 100 * EPS]
    y = detrend(raw[:, geometry])
    y -= q @ (q.T @ y)
    sos = signal.butter(5, [.01, .1], btype='bandpass', fs=.5, output='sos')
    bp = signal.sosfiltfilt(sos, y, axis=0, padtype='odd', padlen=33)
    clean = np.full((2,) + raw.shape, np.nan, dtype=np.float64)
    clean[0][:, geometry], clean[1][:, geometry] = y, bp
    raw_sd = np.full(raw.shape[1], np.nan)
    clean_norm = np.full((2, raw.shape[1]), np.nan)
    threshold = np.full(raw.shape[1], np.nan)
    active = np.zeros((2, raw.shape[1]), dtype=bool)
    for parcel in np.flatnonzero(geometry):
        raw_sd[parcel] = norm(centered(raw[:, parcel])) / math.sqrt(len(raw) - 1)
        threshold[parcel] = 1e-12 * math.sqrt(len(raw)) * max(1., raw_sd[parcel])
        for arm in range(2):
            clean_norm[arm, parcel] = norm(centered(clean[arm, :, parcel]))
            active[arm, parcel] = clean_norm[arm, parcel] > threshold[parcel]
    fc = np.stack([canonical_fc(clean[a], active[a]) for a in range(2)])
    return dict(cleaned_series=clean, raw_sample_sd=raw_sd, clean_centered_l2=clean_norm,
                activity_threshold=threshold, person_parcel_active=active,
                nuisance_rank=q.shape[1], fc=fc)


def canonical_fc(clean, active):
    clean = real_array(clean, 2, finite=False)
    active = np.asarray(active, dtype=bool)
    count = int(active.sum())
    out = np.full((clean.shape[1], clean.shape[1]), np.nan)
    if count:
        part = np.atleast_2d(np.corrcoef(clean[:, active].T))
        require(part.shape == (count, count) and np.isfinite(part).all(), 'finite active FC')
        part = np.triu(part, 1) + np.triu(part, 1).T + np.eye(count)
        out[np.ix_(active, active)] = part
    return out


def mean_fc(fcs, active):
    fcs, active = np.asarray(fcs), np.asarray(active, dtype=bool)
    good = np.all(active, axis=0)
    out = np.full(fcs.shape[1:], np.nan)
    if good.any():
        part = np.mean(fcs[:, good][:, :, good], axis=0, dtype=np.float64)
        part = np.triu(part, 1) + np.triu(part, 1).T + np.eye(int(good.sum()))
        out[np.ix_(good, good)] = part
    return out, good


def operator(fc, parcel_ids, keep=40):
    fc = real_array(fc, 2)
    parcel_ids = np.asarray(parcel_ids)
    n = len(fc)
    require(fc.shape == (n, n) and parcel_ids.shape == (n,) and len(set(parcel_ids)) == n, 'operator axes')
    require(1 <= keep <= n and np.array_equal(fc, fc.T), 'symmetric FC/retention')
    sparse = np.zeros_like(fc)
    for row in range(n):
        chosen = np.lexsort((parcel_ids, -fc[row]))[:keep]
        sparse[row, chosen] = fc[row, chosen]
    lengths = np.linalg.norm(sparse, axis=1)
    require(np.isfinite(lengths).all() and np.all(lengths > 0), 'positive sparse profile norm')
    profiles = sparse / lengths[:, None]
    cosine = np.clip(profiles @ profiles.T, -1., 1.)
    w = 1. - np.arccos(cosine) / np.pi
    w = np.triu(w, 1) + np.triu(w, 1).T + np.eye(n)
    degrees = np.sum(w, axis=1)
    require(np.all(degrees > 0) and np.isfinite(degrees).all(), 'positive kernel degrees')
    anisotropic = w / (np.sqrt(degrees)[:, None] * np.sqrt(degrees)[None, :])
    d = np.sum(anisotropic, axis=1)
    require(np.all(d > 0) and np.isfinite(d).all(), 'positive anisotropic degrees')
    s = anisotropic / (np.sqrt(d)[:, None] * np.sqrt(d)[None, :])
    s = np.triu(s) + np.triu(s, 1).T
    stationary = np.sqrt(d) / np.sqrt(np.sum(d))
    require(np.isfinite(s).all(), 'finite symmetric operator')
    return s, stationary


def embedding(fc, parcel_ids, components=10, keep=40):
    n = len(parcel_ids)
    result = dict(operator_valid=False, embedding_valid=False, principal_valid=False,
                  retained_span_valid=False, plane_valid=False,
                  eigenvalues=np.full(components + 1, np.nan),
                  eigenvectors=np.full((n, components), np.nan),
                  raw_diffusion=np.full((n, components), np.nan),
                  embedding_status='inactive_parcel', principal_status='embedding_undefined',
                  retained_span_status='embedding_undefined', principal_gap=None,
                  retained_boundary_gap=None)
    if not np.isfinite(fc).all():
        return result
    require(n > components + 1, 'spectral dimension')
    s, u0 = operator(fc, parcel_ids, keep)
    complement = linalg.qr(u0[:, None], mode='full')[0][:, 1:]
    reduced = complement.T @ s @ complement
    reduced = np.triu(reduced) + np.triu(reduced, 1).T
    values, vectors = linalg.eigh(reduced, driver='evd')
    order = np.argsort(values)[::-1][:components + 1]
    values = values[order]
    u = complement @ vectors[:, order[:components]]
    require(np.isfinite(values).all() and np.isfinite(u).all(), 'finite symmetric eigensystem')
    require(np.max(np.linalg.norm(s @ u - u * values[:components], axis=0)) <= 1e-8,
            'oracle spectral residual certificate')
    require(np.max(np.abs(u.T @ u - np.eye(components))) <= 1e-7 and
            np.max(np.abs(u0 @ u)) <= 1e-8, 'oracle spectral orthogonality certificate')
    result.update(operator_valid=True, eigenvalues=values, eigenvectors=u,
                  principal_gap=float(values[0] - values[1]),
                  retained_boundary_gap=float(values[components - 1] - values[components]))
    if 1. - values[0] <= GAP:
        result['embedding_status'] = 'multiscale_singular'
        return result
    g = (u / u0[:, None]) * (values[:components] / (1. - values[:components]))
    for k in range(components):
        anchor = np.lexsort((parcel_ids, -np.abs(g[:, k])))[0]
        if g[anchor, k] < 0:
            g[:, k] *= -1
            u[:, k] *= -1
    require(np.isfinite(g).all(), 'finite multiscale coordinates')
    principal = values[0] - values[1] > GAP and norm(centered(g[:, 0])) > 0
    retained = values[components - 1] - values[components] > GAP
    result.update(embedding_valid=True, principal_valid=bool(principal),
                  retained_span_valid=bool(retained), plane_valid=bool(values[1] - values[2] > GAP),
                  eigenvectors=u, raw_diffusion=g, embedding_status='ok',
                  principal_status=('ok' if principal else 'principal_degenerate' if
                                    values[0] - values[1] <= GAP else 'constant_coordinate'),
                  retained_span_status='ok' if retained else 'retained_boundary_degenerate')
    return result


def align(subjects, reference, max_iterations=10):
    data, ref = real_array(subjects, 3), real_array(reference, 2).copy()
    require(data.shape[1:] == ref.shape, 'GPA coordinate shapes')
    old_distance = math.inf
    rotations, history, distances = [], [ref.copy()], []
    termination = 'iteration_cap'
    for _ in range(max_iterations):
        rs = []
        for subject in data:
            left, _, right = linalg.svd(subject.T @ ref, full_matrices=False, lapack_driver='gesvd')
            rs.append(left @ right)
        rs = np.stack(rs)
        aligned = np.matmul(data, rs)
        new_ref = np.mean(aligned, axis=0, dtype=np.float64)
        distance = float(np.sum((ref - new_ref) ** 2, dtype=np.float64))
        require(math.isfinite(distance), 'finite GPA distance')
        rotations.append(rs)
        history.append(new_ref.copy())
        distances.append(distance)
        ref = new_ref
        if math.isfinite(old_distance) and abs(distance - old_distance) < 1e-5:
            termination = 'converged'
            break
        old_distance = distance
    return dict(gpa_n_iterations=len(distances), gpa_rotations=np.stack(rotations),
                gpa_reference_history=np.stack(history), gpa_distances=np.array(distances),
                aligned_gradients=aligned, termination=termination)


def complete_mean(values):
    valid = [v for v in values if v is not None]
    return dict(value=(math.fsum(valid) / len(values) if len(valid) == len(values) and values else None),
                status='ok' if len(valid) == len(values) and values else 'incomplete_support',
                n_expected=len(values), n_defined=len(valid))


def population_variance(matrix):
    x = real_array(matrix, 2)
    require(len(x) > 0, 'variance support')
    result = np.var(x, axis=0, ddof=0)
    result[np.all(x == x[0], axis=0)] = 0.
    require(np.isfinite(result).all(), 'finite population variance')
    return result


def display(coordinates, networks, principal_valid, plane_valid, orient_all=False):
    coordinates = real_array(coordinates, 2, finite=False)
    nets = np.asarray(networks)
    require(set(nets) == set(NETWORKS), 'all seven source networks')
    good = np.isfinite(coordinates).all(axis=0)
    constant_g1 = bool(good[0] and norm(centered(coordinates[:, 0])) == 0)
    signs = np.zeros(coordinates.shape[1], dtype=np.int64)
    out = coordinates.copy()
    for k in np.flatnonzero(good):
        signs[k] = 1
        if (k == 0 or orient_all) and np.mean(out[nets == 'Default', k]) < np.mean(out[nets == 'Vis', k]):
            signs[k] = -1
            out[:, k] *= -1
    # Keep the entire plane for its rotation-invariant B/W before masking an
    # unresolved individual g1 axis; that axis's network endpoint remains null.
    bw, bw_status = None, 'plane_degenerate'
    if plane_valid and good[:2].all():
        centres = np.stack([np.mean(out[nets == name, :2], axis=0) for name in NETWORKS])
        between = float(np.sum(population_variance(centres)))
        within = float(np.mean([np.sum(population_variance(out[nets == name, :2])) for name in NETWORKS]))
        require(math.isfinite(between) and math.isfinite(within), 'finite B/W components')
        bw, bw_status = (between / within, 'ok') if within > 0 else (None, 'zero_within')
    if not principal_valid or constant_g1:
        good[0], signs[0] = False, 0
        out[:, 0] = np.nan
    means = np.full((len(NETWORKS), coordinates.shape[1]), np.nan)
    for i, name in enumerate(NETWORKS):
        means[i, good] = np.mean(out[nets == name][:, good], axis=0, dtype=np.float64)
    apex = NETWORKS[int(np.argmax(means[:, 0]))] if good[0] else None
    bottom = NETWORKS[int(np.argmin(means[:, 0]))] if good[0] else None
    return dict(coordinates=out, valid=good, signs=signs, means=means,
                apex_network=apex, bottom_network=bottom, between_within=bw,
                between_within_status=bw_status, constant_g1=constant_g1)


def pair_consistency(ids, embeddings, alignment, reference_principal):
    pairs, values, valid = [], [], []
    for i, j in itertools.combinations(range(len(ids)), 2):
        raw = pearson(embeddings[i]['raw_diffusion'][:, 0], embeddings[j]['raw_diffusion'][:, 0]) if (
            embeddings[i]['principal_valid'] and embeddings[j]['principal_valid']) else None
        aligned = pearson(alignment['aligned_gradients'][i, :, 0], alignment['aligned_gradients'][j, :, 0]) if (
            alignment is not None and reference_principal) else None
        pairs.append([ids[i], ids[j]])
        values.append([np.nan if raw is None else raw, np.nan if aligned is None else aligned])
        valid.append([raw is not None, aligned is not None])
    return np.asarray(pairs), np.asarray(values), np.asarray(valid, dtype=bool)
