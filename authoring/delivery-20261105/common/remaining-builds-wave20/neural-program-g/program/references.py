"""Concrete operator references; imports numerical libraries only on invocation.

Caches contain deterministic per-channel signal features, never fitted state.
No candidate receives this module, cache or model. Model pickles may be loaded
only inside the isolated reference realm after external exact-byte admission.
"""
from pathlib import Path
import math
from .common import VIEWS, need
from .science import signal_features, contextual_array, training_sequence_statistics, sequence_posterior

RF1 = dict(n_estimators=100, criterion='gini', max_depth=None,
 min_samples_split=2, min_samples_leaf=5, min_weight_fraction_leaf=0.,
 max_features=1., max_leaf_nodes=None, min_impurity_decrease=0., bootstrap=True,
 oob_score=False, n_jobs=2, random_state=241, verbose=0, warm_start=False,
 class_weight='balanced', ccp_alpha=0., max_samples=None, monotonic_cst=None)
GRID = [(1, 0), (1, .5), (1, 1), (5, 0), (5, .5), (5, 1)]


def checked_array(path, dtype, shape):
    import numpy as np
    a = np.load(path, allow_pickle=False, mmap_mode='r')
    need(a.dtype.str == dtype and tuple(a.shape) == tuple(shape) and a.flags.c_contiguous, 'Exact declared array')
    need(np.isfinite(a).all(), 'Finite full-clock array')
    return a


def cache_night(row, root, output):
    """One producer per original night, complete all channels; no labels read."""
    import numpy as np
    root, output = Path(root), Path(output)
    need(not output.exists(), 'Fresh complete cache directory'); output.mkdir()
    e = row['epochs']
    for c in range(3):
        raw = checked_array(root / f'channel-{c}.npy', '<f8', (e * 3000,))
        base = signal_features(raw.reshape(e, 3000))
        # Separate physical channels keep inference controls and cache access exact.
        np.save(output / f'context-{c}.npy', contextual_array(base).astype('<f8'), allow_pickle=False)
    clock = checked_array(root / 'clock.npy', '<f8', (e, 4))[:, 1:]
    np.save(output / 'context-clock.npy', contextual_array(clock).astype('<f8'), allow_pickle=False)


def feature_night(row, root, family, shifted=False, cache=None):
    import numpy as np
    root = Path(root); e = row['epochs']; view = row['view']
    clock = checked_array(root / 'clock.npy', '<f8', (e, 4))[:, 1:]
    blocks = []
    for c in VIEWS[view]:
        if cache is None:
            raw = checked_array(root / f'channel-{c}.npy', '<f8', (e * 3000,))
            base = signal_features(raw.reshape(e, 3000)); context = None
        else:
            context = checked_array(Path(cache) / f'context-{c}.npy', '<f8', (e, 18))
            base = context[:, :6]
        if shifted and c in (0, 1):
            need(e >= 2, 'Whole-night shift support'); base = np.roll(base, max(1, e // 3), axis=0)
            context = None  # Edge-truncated context must be recomputed after shift.
        blocks.append((base, context))
    clock_context = None if cache is None else checked_array(Path(cache) / 'context-clock.npy', '<f8', (e, 9))
    blocks.append((clock, clock_context))
    if family != 'R2': return np.column_stack([base for base, _ in blocks])
    contexts = [(contextual_array(base) if context is None else context, base.shape[1]) for base, context in blocks]
    # Preserve exact original-all / means-all / std-all column order while
    # reusing unshifted channel/clock contexts. No across-night operation.
    return np.column_stack([c[:, part * width:(part + 1) * width] for part in range(3) for c, width in contexts])


def labels(root, epochs, association_control=False):
    import numpy as np
    root = Path(root)
    y = checked_array(root / 'stages.npy', '|i1', (epochs,))
    m = checked_array(root / 'mask.npy', '|b1', (epochs,))
    need(np.isin(y, [-1, 0, 1, 2, 3, 4]).all() and np.array_equal(m, y >= 0), 'Exact full training-label mask')
    if association_control:
        y = np.roll(y, max(1, epochs // 3))
        m = np.roll(m, max(1, epochs // 3))
    return y, m


def clock_keys(clock, max_elapsed):
    import numpy as np
    # Clock contains elapsed hours and wall-clock sin/cos, no date or light cue.
    angles = np.mod(np.arctan2(clock[:, 1], clock[:, 2]), 2 * np.pi)
    # EDF start clocks have integer-second resolution, and epochs start on
    # exact30s offsets. Recover that declared resolution before binning so
    # floating sin/cos roundoff cannot turn midnight into the23:30 bin.
    seconds = np.rint(angles / (2 * np.pi) * 86400).astype(int) % 86400
    wall = seconds // 1800
    elapsed = np.clip(np.floor(clock[:, 0]).astype(int), 0, max_elapsed)
    return elapsed, wall


def fit(nights, family, view, parameter=None, association_control=False):
    """Training support supplied only by trusted staging, never caller labels."""
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    need(family in ('R0', 'R1', 'R2') and view in VIEWS, 'Declared reference family/view')
    need(not association_control or (family == 'R2' and view in ('C', 'EC')), 'Only declared association controls')
    xx, yy, sequences = [], [], []
    maximum_training_elapsed = 0
    for row in nights:
        item = {**row, 'view': view}
        x = feature_night(item, row['root'], family, cache=row.get('cache'))
        if family == 'R0': maximum_training_elapsed = max(maximum_training_elapsed, int(np.floor(x[:, 0]).max()))
        y, m = labels(row['root'], row['epochs'], association_control)
        xx.append(x[m]); yy.append(y[m]); sequences.append(y)
    x, y = np.concatenate(xx), np.concatenate(yy)
    need(len(y), 'Whole training support cannot be empty')
    prior, transition = training_sequence_statistics(sequences)
    if family == 'R0':
        need(view == 'C' and parameter in (1, 10, 100), 'Frozen R0 grid')
        max_elapsed = maximum_training_elapsed
        counts = np.zeros((max_elapsed + 1, 48, 5), dtype=np.float64)
        elapsed, wall = clock_keys(x, max_elapsed)
        np.add.at(counts, (elapsed, wall, y), 1)
        posterior = (counts + parameter * prior) / (counts.sum(axis=2, keepdims=True) + parameter)
        state = {'posterior': posterior, 'max_elapsed': max_elapsed, 'alpha': parameter, 'counts': counts}
    else:
        params = dict(RF1)
        if family == 'R2':
            need(parameter in (1, 5), 'Declared R2 leaf grid')
            params.update(n_estimators=300, max_features='sqrt', max_leaf_nodes=4096,
                          class_weight=None, min_samples_leaf=parameter)
        model = RandomForestClassifier(**params).fit(x, y)
        state = {'estimator': model}
    return {'family': family, 'view': view, 'prior': prior, 'transition': transition,
            'association_control': association_control, 'parameter': parameter, 'state': state}


def predict(model, row, shifted=False, power=None, alpha=None):
    import numpy as np
    family, view = model['family'], model['view']
    need(not shifted or view in ('EC', 'EOC'), 'Declared signal shift only')
    x = feature_night({**row, 'view': view}, row['root'], family, shifted, row.get('cache'))
    if family == 'R0':
        elapsed, wall = clock_keys(x, model['state']['max_elapsed'])
        if alpha is None:
            p = model['state']['posterior'][elapsed, wall]
        else:
            need(alpha in (1, 10, 100), 'Declared R0 validation alpha')
            counts = model['state']['counts'][elapsed, wall]
            p = (counts + alpha * model['prior']) / (counts.sum(axis=1, keepdims=True) + alpha)
    else:
        estimator = model['state']['estimator']; p = np.zeros((len(x), 5), dtype=np.float64)
        p[:, estimator.classes_.astype(int)] = estimator.predict_proba(x)
        if family == 'R2':
            need(power in (0, .5, 1), 'Frozen R2 transition choice')
            p = sequence_posterior(p, model['prior'], model['transition'], power)
    need(p.shape == (row['epochs'], 5) and np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
         and np.all(np.abs(p.sum(axis=1) - 1) <= 1e-6), 'Unrepaired complete reference probabilities')
    return p.astype('<f8')


def choose(scores, family):
    """Independent validation evaluator supplies complete equal-person scores."""
    grid = [1, 10, 100] if family == 'R0' else GRID
    need(len(scores) == len(grid) and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in scores), 'Complete validation grid')
    return grid[max(range(len(grid)), key=lambda i: (scores[i], -i))]
