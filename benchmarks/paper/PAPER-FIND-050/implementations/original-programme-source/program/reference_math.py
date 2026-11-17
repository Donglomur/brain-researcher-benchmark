"""Prospective FIND050 controls. No data access, fit, or execution on import.

All fits take an already admitted development-only float64 matrix. These
benchmark-authored equations preserve the declared source-family conventions;
they do not execute or establish numerical parity with the original author code.
"""
import json
import math
import numpy as np

PROFILE = 'critical_init_float64_five_frame_controls_v1'
SCHEMA = 'critical_init_forecast_reference_state_v1'
HORIZON = 5
SOURCE_RANK = 1000
SOURCE_BLOCK = 10000
EPS = 0.001
LAMBDAS = {'calcium': 0.01, 'ephys': 0.1}
METHODS = ('dmd', 'persistence', 'diagonal_ar')
ARRAY_KEYS = ('basis', 'transition', 'ar_slope', 'ar_intercept')
STATE_METADATA_CAP = 262144
META_KEYS = frozenset(('schema', 'profile', 'n_neurons', 'development_frames',
                       'horizon', 'modality', 'rank', 'basis_metadata',
                       'block_metadata', 'ar_pair_count'))


class ReferenceUnavailable(ValueError):
    """Mandatory control could not be defined; never a reduced-rank fallback."""


def need(ok, reason):
    if not ok:
        raise ReferenceUnavailable(reason)


def array(value, dimensions, name):
    need(type(value) is np.ndarray and value.dtype == np.dtype('float64') and
         value.ndim == dimensions and all(x > 0 for x in value.shape),
         name + ': exact nonempty float64 array')
    need(bool(np.isfinite(value).all()), name + ': finite full support')
    return value


def _guard(lhs, rhs, n, d, label):
    """Prespecified numerical consistency, not an empirical score tolerance."""
    lhs, rhs = np.asarray(lhs, dtype=np.float64), np.asarray(rhs, dtype=np.float64)
    need(lhs.shape == rhs.shape and np.isfinite(lhs).all() and
         np.isfinite(rhs).all(), label + ': finite matched operands')
    residual = float(np.linalg.norm(lhs - rhs))
    scale = max(float(np.linalg.norm(rhs)), 1.0)
    tolerance = 64.0 * np.finfo(np.float64).eps * max(n, d) * scale
    need(math.isfinite(residual) and math.isfinite(tolerance) and residual <= tolerance,
         label + ': declared float64 correspondence failed')
    return {'frobenius_residual': residual, 'bound': tolerance,
            'rule': '64*eps_float64*max(N,D)*max(frobenius(rhs),1)'}


def fit_normalization(raw_development):
    """All development neurons survive, including constant channels."""
    r = array(raw_development, 2, 'development')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        mean = np.mean(r, axis=1, dtype=np.float64)
        centered = r - mean[:, None]
        scale = EPS + np.sqrt(np.mean(centered * centered, axis=1, dtype=np.float64))
        z = centered / scale[:, None]
    array(z, 2, 'normalized development')
    need(np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all(),
         'finite development normalization')
    return {'mean': mean, 'scale': scale, 'development': z}


def normalize_current(current, mean, scale):
    x = array(current, 1, 'current frame')
    mean = array(mean, 1, 'development mean')
    scale = array(scale, 1, 'development scale')
    need(x.shape == mean.shape == scale.shape and (scale > 0).all(),
         'exact normalization support')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        result = (x - mean) / scale
    return array(result, 1, 'normalized current frame')


def source_block_plan(development_frames):
    need(type(development_frames) is int and development_frames > HORIZON,
         'development has positive lagged support')
    d = development_frames
    blocks = max(1, (d - HORIZON) // SOURCE_BLOCK)
    length = min(SOURCE_BLOCK, d - HORIZON)
    need(length > 50, 'original dynamics has no contributing block')
    rows = [{'x_start': j * length, 'x_stop': j * length + length - HORIZON,
             'y_start': j * length + HORIZON, 'y_stop': j * length + length,
             'source_weight': length, 'pair_count': length - HORIZON}
            for j in range(blocks)]
    need(all(0 <= r['x_start'] < r['x_stop'] <= d and
             0 <= r['y_start'] < r['y_stop'] <= d for r in rows),
         'literal source intervals within development')
    return {'horizon': HORIZON, 'initial_block': SOURCE_BLOCK,
            'effective_block': length, 'blocks': rows,
            'pair_count': sum(r['pair_count'] for r in rows),
            'all_permitted_pair_count': d - HORIZON,
            'omitted_pair_count': d - HORIZON - sum(r['pair_count'] for r in rows),
            'weight_sum': length * blocks,
            'normalization': 'sum((X@X.T)/D*L)*D/sum(L)'}


def _source_projection(z, rank):
    """Source algebra kernel. Only engineering controls may select small rank."""
    z = array(z, 2, 'standardized development')
    n, d = z.shape
    need(type(rank) is int and 1 <= rank <= n, 'explicit complete selected rank')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        if rank == n:
            basis = np.eye(n, dtype=np.float64)
            return basis, z, {'branch': 'full_observation_coordinates',
                              'rank': rank, 'source_unused_gram_omitted': True,
                              'correspondence': None, 'orthogonality': None}
        if n < d:
            covariance = (z @ z.T) / d
            _, vectors = np.linalg.eigh(covariance @ covariance.T)
            basis = np.ascontiguousarray(vectors[:, -rank:], dtype=np.float64)
            coordinates = basis.T @ z
            branch = 'neuron_covariance_squared_eigenbasis'
            correspondence = None
        else:
            need(d >= rank, 'source dual branch cannot supply declared rank')
            covariance = (z.T @ z) / d
            _, vectors = np.linalg.eigh(covariance.T @ covariance)
            q = vectors[:, -rank:]
            zq = z @ q
            singular = np.sqrt(np.sum(zq * zq, axis=0, dtype=np.float64))
            need(np.isfinite(singular).all() and (singular > 0).all(),
                 'source dual selected direction has zero or undefined norm')
            basis = np.ascontiguousarray(zq / singular[None, :], dtype=np.float64)
            # This is the literal source training expression. The extension to
            # unseen current vectors must agree before it is used for prediction.
            coordinates = singular[:, None] * q.T
            correspondence = _guard(basis.T @ z, coordinates, n, d,
                                     'dual training coordinate correspondence')
            branch = 'time_covariance_squared_dual_basis'
        orthogonality = _guard(basis.T @ basis, np.eye(rank, dtype=np.float64),
                               n, d, 'source observation basis orthogonality')
    array(basis, 2, 'source observation basis')
    array(coordinates, 2, 'source projected training coordinates')
    need(basis.shape == (n, rank) and coordinates.shape == (rank, d),
         'complete source projection dimensions')
    return basis, coordinates, {'branch': branch, 'rank': rank,
                               'source_unused_gram_omitted': False,
                               'correspondence': correspondence,
                               'orthogonality': orthogonality}


def source_dynamics(projected, regularization):
    p = array(projected, 2, 'source projected development')
    need(type(regularization) is float and regularization in LAMBDAS.values(),
         'fixed source modality regularization')
    k, d = p.shape
    plan = source_block_plan(d)
    xx = np.zeros((k, k), dtype=np.float64)
    xy = np.zeros((k, k), dtype=np.float64)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        for row in plan['blocks']:
            x = p[:, row['x_start']:row['x_stop']]
            y = p[:, row['y_start']:row['y_stop']]
            # Deliberately preserve original operation order and its L weight.
            xx += (x @ x.T) / d * row['source_weight']
            xy += (x @ y.T) / d * row['source_weight']
        xx *= d / plan['weight_sum']
        xy *= d / plan['weight_sum']
        transition = np.linalg.solve(xx + regularization * np.eye(k), xy).T
    array(transition, 2, 'source transition')
    return transition, plan


def diagonal_ar(z):
    z = array(z, 2, 'AR standardized development')
    need(z.shape[1] > HORIZON, 'all lagged development pairs exist')
    x, y = z[:, :-HORIZON], z[:, HORIZON:]
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        mx, my = x.mean(axis=1), y.mean(axis=1)
        xc, yc = x - mx[:, None], y - my[:, None]
        sxx = np.sum(xc * xc, axis=1, dtype=np.float64)
        sxy = np.sum(xc * yc, axis=1, dtype=np.float64)
        ridge = 1e-6 * np.maximum(sxx, 1.0)
        slope = sxy / (sxx + ridge)
        intercept = my - slope * mx
    array(slope, 1, 'AR slope'); array(intercept, 1, 'AR intercept')
    return slope, intercept


def fit_all(standardized_development, modality):
    """Return all mandatory controls; any failure leaves the whole call failed.

    Caller owns input custody, development-only normalization, numerical/runtime
    qualification and memory admission. This function never accesses a target.
    """
    z = array(standardized_development, 2, 'permitted standardized development')
    need(type(modality) is str and modality in LAMBDAS, 'fixed declared modality')
    n, d = z.shape
    rank = min(SOURCE_RANK, n)
    try:
        basis, projected, basis_metadata = _source_projection(z, rank)
        transition, block_metadata = source_dynamics(projected, LAMBDAS[modality])
        slope, intercept = diagonal_ar(z)
    except (np.linalg.LinAlgError, FloatingPointError) as exc:
        raise ReferenceUnavailable('mandatory float64 reference arithmetic failed') from exc
    state = {'schema': SCHEMA, 'profile': PROFILE, 'n_neurons': n,
             'development_frames': d, 'horizon': HORIZON, 'modality': modality,
             'rank': rank, 'basis_metadata': basis_metadata,
             'block_metadata': block_metadata, 'ar_pair_count': d - HORIZON,
             'basis': basis, 'transition': transition,
             'ar_slope': slope, 'ar_intercept': intercept}
    validate_state(state)
    return state


def validate_state(state):
    need(type(state) is dict and set(state) == META_KEYS | set(ARRAY_KEYS),
         'exact trusted reference state keys')
    need(state['schema'] == SCHEMA and state['profile'] == PROFILE and
         state['horizon'] == HORIZON and state['modality'] in LAMBDAS,
         'exact prospective reference profile')
    n, d, k = state['n_neurons'], state['development_frames'], state['rank']
    need(type(n) is int and n > 0 and type(d) is int and d > HORIZON and
         type(k) is int and k == min(SOURCE_RANK, n),
         'production full rank and dimensions')
    need(state['ar_pair_count'] == d-HORIZON and
         state['block_metadata'] == source_block_plan(d),
         'exact declared complete development pairing')
    b = state['basis_metadata']
    need(type(b) is dict and set(b) == {'branch', 'rank', 'source_unused_gram_omitted',
                                      'correspondence', 'orthogonality'} and type(b['rank']) is int and b['rank'] == k,
         'complete source basis provenance')
    expected = ('full_observation_coordinates' if k == n else
                'neuron_covariance_squared_eigenbasis' if n < d else
                'time_covariance_squared_dual_basis')
    need(b['branch'] == expected and b['source_unused_gram_omitted'] is (k == n),
         'source branch fixed by complete dimensions')
    for name, shape in [('basis',(n,k)),('transition',(k,k)),
                        ('ar_slope',(n,)),('ar_intercept',(n,))]:
        value = array(state[name], len(shape), 'reference ' + name)
        need(value.shape == shape, 'exact ' + name + ' support')
    return state


def predict_all(state, standardized_current):
    """Pure current-frame reference prediction; state is already authenticated."""
    # Shape/type validation here does not replace parent's immutable state pin.
    n, k = state['n_neurons'], state['rank']
    z = array(standardized_current, 1, 'current standardized full vector')
    need(z.shape == (n,) and state['basis'].shape == (n,k) and
         state['transition'].shape == (k,k) and state['ar_slope'].shape == (n,) and
         state['ar_intercept'].shape == (n,), 'current/reference dimensions')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            predicted = {'dmd': state['basis'] @ (state['transition'] @ (state['basis'].T @ z)),
                         'persistence': z.copy(),
                         'diagonal_ar': state['ar_slope'] * z + state['ar_intercept']}
    except FloatingPointError as exc:
        raise ReferenceUnavailable('mandatory full-support prediction failed') from exc
    for name in METHODS:
        value = array(predicted[name], 1, name + ' prediction')
        need(value.shape == (n,), name + ': no neuron support reduction')
    return predicted


def state_to_npz_members(state):
    """Numeric NPZ members; caller exclusively writes its trusted artifact.

    No object arrays/pickle. Metadata has a fixed small UTF8 representation;
    parent binds file pins, archive/header extents and loads allow_pickle=False.
    """
    validate_state(state)
    meta = {key: state[key] for key in META_KEYS}
    raw = (json.dumps(meta, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    need(len(raw) <= STATE_METADATA_CAP, 'bounded complete state metadata')
    return {**{key: state[key] for key in ARRAY_KEYS},
            'metadata_utf8': np.frombuffer(raw, dtype=np.uint8).copy()}


def state_from_npz_members(members):
    """Only operator-owned, authenticated, bounded, allow_pickle=False members."""
    need(type(members) is dict and set(members) == set(ARRAY_KEYS) | {'metadata_utf8'},
         'exact trusted NPZ members')
    raw = members['metadata_utf8']
    need(type(raw) is np.ndarray and raw.dtype == np.dtype('uint8') and
         raw.ndim == 1 and 0 < raw.size <= STATE_METADATA_CAP, 'bounded plain metadata bytes')
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate state metadata key')
            value[key] = item
        return value
    def nonfinite(_):
        raise ReferenceUnavailable('nonfinite state metadata')
    meta = json.loads(raw.tobytes().decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=nonfinite)
    need(type(meta) is dict and set(meta) == META_KEYS, 'exact state metadata keys')
    return validate_state({**meta, **{key: members[key] for key in ARRAY_KEYS}})


def state_shape_requirements(n_neurons, development_frames):
    """Exact retained numeric state components, not a peak-RSS estimate."""
    need(type(n_neurons) is int and n_neurons > 0 and
         type(development_frames) is int and development_frames > HORIZON,
         'positive full reference dimensions')
    n, d = n_neurons, development_frames
    k = min(SOURCE_RANK, n)
    source_block_plan(d)
    need(not (n > SOURCE_RANK and n >= d and d < k),
         'declared dual rank support')
    shapes = {'basis': (n,k), 'transition': (k,k),
              'ar_slope': (n,), 'ar_intercept': (n,)}
    sizes = {key: 8*math.prod(shape) for key,shape in shapes.items()}
    return {'array_shapes': shapes, 'numeric_bytes': sizes,
            'numeric_bytes_total': sum(sizes.values()),
            'metadata_bytes_cap': STATE_METADATA_CAP,
            'npz_container_and_header_bytes_included': False,
            'fit_workspace_or_peak_RAM_qualified': False,
            'source_gram_dimension_if_projected': min(n,d) if k<n else None}
