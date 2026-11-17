"""Category-first feature recovery and the current NEURAL-076 interaction.

The public array identities retain the recovered v1 producer format. Numerical
outputs use v2 semantics: undefined correlations remain undefined, not zero.
No function fits a decoder, selects voxels, or reads files.
"""
import hashlib
import numpy as np

PEOPLE = tuple('Subject%d' % i for i in range(1, 6))
ROIS = ('V1', 'V2', 'V3', 'V4', 'LOC', 'FFA', 'PPA', 'LVC', 'HVC', 'VC')
FAMILIES = tuple('cnn%d' % i for i in range(1, 9)) + ('hmax1', 'hmax2', 'hmax3', 'gist', 'sift')
PHASES = ('imagery', 'perception')
UNITS = 1000
VERSION = 'neural076_matched_hierarchy_v1'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def matched_indices(family, width, count=UNITS):
    """Preserve the recovered producer's value-independent unit identities."""
    need(family in FAMILIES and type(width) is int and width >= count >= 2,
         'Complete matched feature support')
    order = sorted(range(width), key=lambda j: (
        hashlib.sha256(f'{VERSION}/{family}/{j}'.encode()).digest(), j))
    return np.array(sorted(order[:count]), dtype=np.int64)


def column_pearson(x, y):
    """Pearson across categories, separately for each matched feature unit.

    Scale before centering to avoid overflow for finite float64 predictions.
    Constant columns return NaN internally and are serialized as null by the
    caller. No held-out unit is deleted or silently assigned a zero score.
    """
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    need(x.shape == y.shape and x.ndim == 2 and x.shape[0] >= 2
         and np.isfinite(x).all() and np.isfinite(y).all(), 'Finite paired matrices')

    def centered(a):
        scale = np.max(np.abs(a), axis=0)
        z = a / np.where(scale == 0, 1, scale)
        z -= z.mean(axis=0)
        norm = np.sqrt(np.sum(z * z, axis=0))
        return z / np.where(norm == 0, 1, norm), norm == 0

    a, ac = centered(x)
    b, bc = centered(y)
    r = np.clip(np.sum(a * b, axis=0), -1, 1)
    r[ac | bc] = np.nan
    return r, ac, bc


def category_means(predictions, labels, classes=50, repeats=None):
    p = np.asarray(predictions, dtype=np.float64)
    y = np.asarray(labels)
    need(p.ndim == 2 and np.isfinite(p).all() and y.shape == (len(p),)
         and y.dtype.kind in 'iu', 'Finite predictions / integer private labels')
    need(set(y.tolist()) == set(range(classes)), 'Complete category support')
    rows = []
    for category in range(classes):
        group = p[y == category]
        if repeats is not None:
            need(len(group) == repeats, 'Complete fixed per-category repeats')
        scale = np.max(np.abs(group), axis=0)
        rows.append((group / np.where(scale == 0, 1, scale)).mean(axis=0) * scale)
    return np.stack(rows)


def feature_score(predictions, labels, bank, repeats):
    bank = np.asarray(bank)
    need(bank.shape == (50, UNITS) and bank.dtype.kind == 'f'
         and np.isfinite(bank).all(), 'Finite complete matched category bank')
    p = category_means(predictions, labels, 50, repeats)
    need(p.shape == bank.shape, 'Matched feature and category geometry')
    r, pc, tc = column_pearson(p, bank)
    undefined = pc | tc
    return {
        'mean_r': None if undefined.any() else float(r.mean()),
        'defined_units': int((~undefined).sum()),
        'constant_prediction_unit_positions': np.flatnonzero(pc).tolist(),
        'constant_target_unit_positions': np.flatnonzero(tc).tolist(),
        'unit_count': UNITS,
    }


def strict_mean(values):
    """No renormalization over a favorable defined subset."""
    return None if any(v is None for v in values) else float(np.mean(values))


def linear_contrast(terms):
    return None if any(v is None for _, v in terms) else float(sum(w * v for w, v in terms))


def contrasts(scores):
    """Current primary plus preserved, explicitly secondary legacy contrast."""
    need(set(scores) == set(PHASES), 'Both conditions required')
    for phase in PHASES:
        need(set(scores[phase]) == set(ROIS), 'All ten ROIs required')
        for roi in ROIS:
            row = scores[phase][roi]
            need(set(row) == set(FAMILIES), 'All thirteen families required')
            need(all(v is None or (type(v) in (int, float) and np.isfinite(v)
                     and -1 <= v <= 1) for v in row.values()), 'Signed r or explicit undefined')
    result = {}
    for phase in PHASES:
        s = scores[phase]
        result[phase + '_cnn7_minus_cnn1_HVC_minus_LVC'] = linear_contrast([
            (1, s['HVC']['cnn7']), (-1, s['HVC']['cnn1']),
            (-1, s['LVC']['cnn7']), (1, s['LVC']['cnn1'])])
        result[phase + '_legacy_cnn5to8_minus_cnn1to4_HVC_minus_LVC'] = linear_contrast([
            (roi_sign * layer_sign / 4, s[roi]['cnn%d' % i])
            for roi, roi_sign in [('HVC', 1), ('LVC', -1)]
            for i in range(1, 9) for layer_sign in [1 if i >= 5 else -1]])
    for roi in ROIS:
        for family in FAMILIES:
            result[f'{roi}/{family}/imagery_minus_perception'] = linear_contrast([
                (1, scores['imagery'][roi][family]), (-1, scores['perception'][roi][family])])
    return result


def participant_summary(values):
    """Five participant values and their equal-weight mean; no inferential claim."""
    need(len(values) == 5 and all(v is None or (type(v) in (int, float)
         and np.isfinite(v)) for v in values), 'All five participant values required')
    return {'per_person': dict(zip(PEOPLE, values)), 'mean': strict_mean(values),
            'independent_participants': 5,
            'undefined_participants': [p for p, v in zip(PEOPLE, values) if v is None]}
