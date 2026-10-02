"""Prospective MAPREL oracle math; no IO, fetches, source access or import actions.

Spin conventions intentionally follow neuromaps0.0.7 at ffcc2e0f657943ce00a1b6a968396f32250e495c,
nulls/spins.py:_gen_rotation/gen_spinsamples. NumPy2.2.6/SciPy1.17.0 QR,
cKDTree ties and linear_sum_assignment ties are public computational choices,
not a claim of an independent spin algorithm or a unique scientific optimum.
Source parsing will be independent of the grader. Parent-approved recipe;
public IO/source pins remain separate, before original values.
"""
import math
import numbers
import warnings

import numpy as np
from scipy import optimize, spatial

METHODS = ('original', 'vasa', 'hungarian')
MAX_ATTEMPTS = 500
SOURCE_ATOL, SOURCE_RTOL, RELATIVE_TOL = 1e-6, 1e-6, 1e-6


def need(condition, message):
    if not condition:
        raise ValueError(message)


def real_array(value, ndim=None):
    raw = np.asarray(value)
    need(raw.dtype.kind in 'iuf' and raw.dtype.kind != 'b', 'real non-Boolean array')
    if isinstance(value, (list, tuple)):
        need(not any(isinstance(x, (bool, np.bool_)) for x in np.asarray(value, dtype=object).flat),
             'mixed Boolean array')
    out = np.asarray(raw, dtype=np.float64)
    need((ndim is None or out.ndim == ndim) and np.isfinite(out).all(), 'finite real shape')
    return out


def integers(value, ndim=1):
    array = real_array(value, ndim)
    need(np.all(array == np.floor(array)) and np.all(np.abs(array) <= 2**53), 'exact integer values')
    return array.astype(np.int64)


def configuration(method, seed, count):
    need(type(method) is str and method in METHODS, 'declared spin method')
    need(isinstance(seed, numbers.Integral) and not isinstance(seed, (bool, np.bool_))
         and 0 <= int(seed) <= 2**32-1, 'uint32 integer seed')
    need(isinstance(count, numbers.Integral) and not isinstance(count, (bool, np.bool_))
         and 100 <= int(count) <= 4096, '100..4096 integer rotations')
    return method, int(seed), int(count)


def geometry(centroids, hemisphere, parcel_ids):
    xyz, hemi, ids = real_array(centroids, 2), integers(hemisphere), integers(parcel_ids)
    need(xyz.shape == (len(ids), 3) and hemi.shape == ids.shape and len(ids) >= 2, 'geometry axes')
    need(len(np.unique(ids)) == len(ids) and np.all(ids > 0), 'unique positive literal parcel IDs')
    need(set(hemi.tolist()) == {0, 1}, 'both cortical hemispheres')
    need(np.all(np.any(xyz != 0, axis=1)), 'nonzero centroids')
    order = np.argsort(ids, kind='stable')
    return np.ascontiguousarray(xyz[order]), hemi[order], ids[order]


def rotation_pair(rng):
    """One coupled hemisphere pair; RNG is a single private legacy RandomState."""
    need(isinstance(rng, np.random.RandomState), 'legacy RandomState required')
    q, upper = np.linalg.qr(rng.normal(size=(3, 3)))
    q = q @ np.diag(np.sign(np.diag(upper)))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    need(np.isfinite(q).all(), 'finite rotation')
    reflect = np.diag([-1, 1, 1])
    return q, reflect @ q @ reflect


def assign(coordinates, rotation, method):
    """Destination rows query rotated source rows; no inversion of assignment."""
    need(method in METHODS, 'spin method')
    coor, q = real_array(coordinates, 2), real_array(rotation, 2)
    need(coor.shape[1:] == (3,) and len(coor) > 0 and q.shape == (3, 3), 'assignment shapes')
    rotated = coor @ q
    if method == 'original':
        costs, columns = spatial.cKDTree(rotated).query(coor, 1)
    else:
        distances = spatial.distance_matrix(coor, rotated)
        if method == 'hungarian':
            rows, columns = optimize.linear_sum_assignment(distances)
            need(np.array_equal(rows, np.arange(len(coor))), 'complete Hungarian rows')
            costs = distances[rows, columns]
        else:
            columns = np.zeros(len(coor), dtype=np.int64)
            costs = np.zeros(len(coor), dtype=np.float64)
            for _ in range(len(coor)):
                row = distances.min(axis=1).argmax()
                columns[row] = distances[row].argmin()
                costs[row] = distances[row, columns[row]]
                distances[row] = -np.inf
                distances[:, columns[row]] = np.inf
    need(np.isfinite(costs).all(), 'finite assignment cost')
    return np.asarray(columns, dtype=np.int64), np.asarray(costs, dtype=np.float64)


def _columns(xyz, hemi, ids, method, seed, count):
    """Pure kernel; caller validates public count. Small tests may use count<100."""
    rng = np.random.RandomState(seed)
    index = np.arange(len(ids), dtype=np.int64)
    indices = np.zeros((len(ids), count), dtype=np.int64)
    costs = np.zeros((len(ids), count), dtype=np.float64)
    attempts = np.zeros(count, dtype=np.int64)
    retained_duplicate = np.zeros(count, dtype=bool)
    warned = False
    for col in range(count):
        duplicate, attempted = True, 0
        while duplicate and attempted < MAX_ATTEMPTS:
            attempted += 1
            sample = np.zeros(len(ids), dtype=np.int64)
            for h, rotation in enumerate(rotation_pair(rng)):
                mask = hemi == h
                assigned, distance = assign(xyz[mask], rotation, method)
                sample[mask] = index[mask][assigned]
                costs[mask, col] = distance
            duplicate = bool(np.any(np.all(sample[:, None] == indices[:, :col], axis=0))
                             or np.array_equal(sample, index))
        # Match upstream warning condition even if candidate500 happens to be unique.
        if attempted == MAX_ATTEMPTS and not warned:
            warnings.warn('Duplicate rotations used; inspect retained mapping diagnostics.',
                          UserWarning, stacklevel=2)
            warned = True
        indices[:, col] = sample
        attempts[col] = attempted
        retained_duplicate[col] = duplicate
    return dict(parcel_ids=ids.copy(), rotation_ids=np.arange(count, dtype=np.int64),
                centroids=xyz.copy(), hemisphere=hemi.copy(), spin_parcel_ids=ids[indices],
                attempts=attempts, retained_duplicate=retained_duplicate, assignment_cost=costs)


def generate_spins(centroids, hemisphere, parcel_ids, *, method='original', seed=0, count=1000):
    method, seed, count = configuration(method, seed, count)
    xyz, hemi, ids = geometry(centroids, hemisphere, parcel_ids)
    return _columns(xyz, hemi, ids, method, seed, count)


def stable_l2(vector):
    vector = np.asarray(vector, dtype=np.float64)
    maximum = float(np.max(np.abs(vector))) if vector.size else 0.
    if maximum == 0:
        return 0.
    return maximum * math.sqrt(math.fsum((float(v)/maximum)**2 for v in vector))


def centered(vector, scale=None):
    vector = real_array(vector, 1)
    need(len(vector) >= 2, 'at least two parcels')
    if np.all(vector == vector[0]):
        return np.zeros_like(vector)
    if scale is None:
        scale = float(np.max(np.abs(vector)))
    need(math.isfinite(scale) and scale > 0, 'positive centering scale')
    scaled = vector / scale
    mean = math.fsum(float(v) for v in scaled) / len(scaled)
    return scaled - mean


def active(vector):
    return stable_l2(centered(vector)) > 0


def pearson(left, right):
    left, right = real_array(left, 1), real_array(right, 1)
    need(left.shape == right.shape, 'paired map axes')
    x, y = centered(left), centered(right)
    nx, ny = stable_l2(x), stable_l2(y)
    if nx == 0 or ny == 0:
        return None
    value = math.fsum(float(a)*float(b) for a, b in zip(x, y)) / (nx*ny)
    need(math.isfinite(value) and abs(value) <= 1 + 1e-12, 'finite Pearson domain')
    return max(-1., min(1., value))


def relative_fidelity(submitted, canonical):
    submitted, canonical = real_array(submitted, 1), real_array(canonical, 1)
    need(submitted.shape == canonical.shape, 'map shape')
    scale = float(max(np.max(np.abs(submitted)), np.max(np.abs(canonical))))
    if not active(canonical):
        return 0.  # Canonical inactivity remains authoritative, regardless of accepted jitter.
    x, y = centered(submitted, scale), centered(canonical, scale)
    return stable_l2(x-y) / stable_l2(y)


def join_maps(parcel_ids, gradient, thickness, spin_parcel_ids):
    ids, spins = integers(parcel_ids), integers(spin_parcel_ids, 2)
    a, b = real_array(gradient, 1), real_array(thickness, 1)
    need(len(np.unique(ids)) == len(ids) and len(ids) >= 2 and np.all(ids > 0), 'literal parcel identity')
    need(a.shape == b.shape == ids.shape and spins.shape[0] == len(ids), 'map/spin axes')
    positions = {int(pid): i for i, pid in enumerate(ids)}
    need(all(int(pid) in positions for pid in spins.flat), 'spin source membership')
    lookup = np.array([positions[int(pid)] for pid in spins.flat], dtype=np.int64).reshape(spins.shape)
    # Canonical parcel order makes fsum replay insensitive to file row permutations.
    order = np.argsort(ids, kind='stable')
    return a[order], b[order], a[lookup[order]]


def source_fidelity(accepted_gradient, accepted_thickness, canonical_gradient,
                    canonical_thickness, parcel_ids, spin_parcel_ids):
    a, b, rotated = join_maps(parcel_ids, accepted_gradient, accepted_thickness, spin_parcel_ids)
    sa, sb, srotated = join_maps(parcel_ids, canonical_gradient, canonical_thickness, spin_parcel_ids)
    for actual, source in ((a, sa), (b, sb)):
        need(np.all(np.abs(actual-source) <= SOURCE_ATOL+SOURCE_RTOL*np.abs(source)), 'signed source fidelity')
        need(relative_fidelity(actual, source) <= RELATIVE_TOL, 'centered source fidelity')
    null_active = np.array([active(srotated[:, k]) for k in range(srotated.shape[1])], dtype=bool)
    for k in np.flatnonzero(null_active):
        need(relative_fidelity(rotated[:, k], srotated[:, k]) <= RELATIVE_TOL, 'remapped source fidelity')
    return dict(gradient=active(sa), thickness=active(sb), null_gradient=null_active)


def status(a_active, b_active):
    return ('ok' if a_active and b_active else 'inactive_gradient' if b_active
            else 'inactive_thickness' if a_active else 'inactive_both')


def derive(gradient, thickness, parcel_ids, spin_parcel_ids, rotation_ids, support):
    """One accepted-map replay; support was computed from canonical source maps."""
    a, b, rotated = join_maps(parcel_ids, gradient, thickness, spin_parcel_ids)
    rotations = integers(rotation_ids)
    need(len(rotations) == rotated.shape[1] and set(rotations.tolist()) == set(range(len(rotations))),
         'complete unique rotation IDs')
    need(type(support) is dict and set(support) == {'gradient', 'thickness', 'null_gradient'}, 'support fields')
    need(type(support['gradient']) is bool and type(support['thickness']) is bool, 'Boolean observed support')
    mask = np.asarray(support['null_gradient'])
    need(mask.dtype.kind == 'b' and mask.shape == rotations.shape, 'Boolean complete null support')
    observed_status = status(support['gradient'], support['thickness'])
    observed = pearson(a, b) if observed_status == 'ok' else None
    need(observed_status != 'ok' or observed is not None, 'accepted observed map inactive')
    records = []
    for position in np.argsort(rotations):
        state = status(bool(mask[position]), support['thickness'])
        value = pearson(rotated[:, position], b) if state == 'ok' else None
        need(state != 'ok' or value is not None, 'accepted remapped map inactive')
        records.append(dict(rotation_id=int(rotations[position]), status=state, r=value))
    defined = [row['r'] for row in records if row['r'] is not None]
    complete = observed is not None and len(defined) == len(records)
    exceedances = sum(abs(value) >= abs(observed) for value in defined) if complete else None
    numerator = exceedances+1 if complete else None
    denominator = len(records)+1
    return dict(observed_status=observed_status, pearson_r=observed, null_distribution=records,
                n_null_expected=len(records), n_null_defined=len(defined), n_exceedances=exceedances,
                p_spin_numerator=numerator, p_spin_denominator=denominator,
                inference_status='ok' if complete else 'incomplete_support',
                p_spin=numerator/denominator if complete else None,
                significant_after_spatial_null=(20*numerator < denominator) if complete else None)
