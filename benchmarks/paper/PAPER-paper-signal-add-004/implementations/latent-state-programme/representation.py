"""Prospective real-training-only representation and raw-run phase controls.

These functions define future authorized preprocessing. They do not read files,
import NumPy/SciPy at module import, or claim native preprocessing equivalence.
"""
from core import HMM, CONTROLS, need, seed_for, validate_runs


def _np():
    import numpy
    return numpy


def embedded(x, lags):
    np = _np()
    x = np.asarray(x, dtype='float64')
    need(x.ndim == 2 and len(x) > lags and np.isfinite(x).all(), 'Finite full original run')
    need(type(lags) is int and lags > 0 and lags % 2 == 1, 'Odd within-run lag support')
    return np.lib.stride_tricks.sliding_window_view(x, lags, axis=0).reshape(len(x)-lags+1, -1).copy()


def ae(x):
    np = _np()
    from scipy.signal import hilbert
    x = np.asarray(x, dtype='float64')
    need(x.ndim == 2 and x.shape[1] == 38 and len(x) >= 5 and np.isfinite(x).all(),
         'Complete finite 38-parcel run')
    envelope = np.abs(hilbert(x, axis=0))
    return np.stack([np.convolve(envelope[:, c], np.ones(5)/5, mode='valid')
                     for c in range(38)], axis=1)


def features(x, branch):
    need(branch in HMM, 'One of the four held-person HMM branches')
    if branch == 'elekta_ae':
        return ae(x)
    need(x.shape[1] == (1 if branch == 'ctf_bursts' else 38), 'Full original channels')
    return embedded(x, 21 if branch == 'ctf_bursts' else 15)


def fit(rows, branch, fold):
    """Fit once on unrandomized training people; no query argument exists."""
    np = _np()
    validate_runs(rows, branch, fold, 'train')
    need(all(set(r) == {'person', 'run', 'observations'} for r in rows), 'Training-only run view')
    xs = [features(r['observations'], branch) for r in rows]
    x = np.concatenate(xs, axis=0)
    need(np.isfinite(x).all() and len(x) > 1, 'Finite complete training features')
    anchor = x[0].copy()
    offset = (x-anchor).mean(axis=0)
    residual = (x-anchor)-offset
    need(np.all(x.max(axis=0) > x.min(axis=0)), 'No constant training dimension')
    bound = np.max(np.abs(residual), axis=0)
    scale = bound*np.sqrt(np.mean((residual/bound)**2, axis=0))
    z = residual/scale
    need(np.isfinite(z).all(), 'Representable real-training moments')
    if branch == 'elekta_ae':
        projection = np.eye(38)
    else:
        _, singular, v = np.linalg.svd(z, full_matrices=False)
        d = HMM[branch][0]
        need(len(singular) >= d and singular[0] > 0 and singular[d-1]/singular[0] > 1e-10,
             'Full fixed prospective rank; no dimension dropping')
        projection = v[:d].T
        for i in range(d):
            if projection[np.argmax(np.abs(projection[:, i])), i] < 0:
                projection[:, i] *= -1
    return {'profile': 'osl_real_training_representation_v1', 'branch': branch, 'fold': fold,
            'training_runs': [(r['person'], r['run']) for r in rows],
            'anchor': anchor, 'offset': offset, 'scale': scale, 'projection': projection}


def apply(x, state):
    np = _np()
    need(state['profile'] == 'osl_real_training_representation_v1', 'Explicit prospective profile')
    f = features(x, state['branch'])
    y = (((f-state['anchor'])-state['offset'])/state['scale']) @ state['projection']
    need(y.shape[1] == HMM[state['branch']][0] and np.isfinite(y).all(),
         'Full finite frozen represented support')
    return y


def randomize(x, seed, control):
    np = _np()
    need(control in CONTROLS, 'Fixed three control families')
    x = np.asarray(x, dtype='float64')
    need(x.ndim == 2 and len(x) >= 3 and np.isfinite(x).all(), 'Finite raw training run')
    if control == 'real':
        return x.copy()
    spectrum = np.fft.rfft(x, axis=0)
    count = len(spectrum)-1-(len(x) % 2 == 0)
    columns = 1 if control == 'common_phase' else x.shape[1]
    rng = np.random.Generator(np.random.PCG64(seed))
    angles = rng.uniform(-np.pi, np.pi, size=(count, columns))
    spectrum[1:1+count] *= np.exp(1j*angles)
    return np.fft.irfft(spectrum, n=len(x), axis=0)


def training_control(rows, state, control):
    branch, fold = state['branch'], state['fold']
    validate_runs(rows, branch, fold, 'train')
    need([(r['person'], r['run']) for r in rows] == state['training_runs'], 'Frozen training support')
    return [{'person': r['person'], 'run': r['run'],
             'observations': apply(randomize(r['observations'], seed_for(
                 'raw_surrogate', branch, fold, control, r['person'], r['run']), control), state)}
            for r in rows]


def query(rows, state):
    """Trusted operator only. It never fits or accepts a control selector."""
    validate_runs(rows, state['branch'], state['fold'], 'query')
    return [{'person': r['person'], 'run': r['run'], 'observations': apply(r['observations'], state)}
            for r in rows]
