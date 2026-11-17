"""Prespecified full-support probability and nested-mouse metrics.

NumPy is supplied by the qualified worker. No empirical I/O occurs here.
"""
import math

VIEWS = ('training_prior', 'context', 'wheel_plus_context',
         'neural_plus_context', 'neural_wheel_plus_context')
CLASS_ORDER = ('left_stronger', 'equal', 'right_stronger')
SUM_TOLERANCE = 1e-8
BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 20261102
STRATA = {'contrast': ('blank_equal', 'nonblank_equal', 'unequal'),
          'engagement': ('source_not_included', 'source_included', 'unknown'),
          'movement': ('no_released_interval_overlap', 'known_nondirectional_overlap',
                       'known_directional_overlap', 'unknown_code_or_unlocatable_interval')}


def need(ok, label):
    if not ok:
        raise ValueError(label)


def extended(value):
    value = float(value)
    if math.isnan(value):
        return {'status': 'undefined', 'value': None}
    if math.isinf(value):
        return {'status': 'positive_infinity' if value > 0 else 'negative_infinity', 'value': None}
    return {'status': 'finite', 'value': value}


def number(record):
    need(type(record) is dict and set(record) == {'status', 'value'}, 'Exact extended number')
    if record['status'] == 'finite':
        need(type(record['value']) in (int, float) and math.isfinite(record['value']), 'Finite scalar')
        return float(record['value'])
    need(record['value'] is None, 'Nonfinite scalar has no JSON number')
    if record['status'] == 'positive_infinity':
        return math.inf
    if record['status'] == 'negative_infinity':
        return -math.inf
    need(record['status'] == 'undefined', 'Known extended scalar status')
    return math.nan


def probabilities(values, np):
    p = np.asarray(values)
    need(p.ndim == 2 and p.shape[1] == 3 and p.shape[0] > 0 and p.dtype.kind == 'f',
         'Nonempty three-column floating probabilities')
    need(bool(np.isfinite(p).all()) and bool(((p >= 0) & (p <= 1)).all()),
         'Finite probabilities in closed unit interval')
    p = np.array(p, dtype=np.float64, order='C', copy=True)
    sums = p.sum(axis=1)
    need(bool((np.abs(sums - 1) <= SUM_TOLERANCE).all()), 'Probability sum within fixed tolerance')
    p /= sums[:, None]
    return p


def align_views(outputs, required_ids, np):
    need(type(outputs) is dict and set(outputs) == set(VIEWS), 'Complete exact five-view panel')
    ids = np.asarray(required_ids)
    need(ids.ndim == 1 and ids.dtype.kind in 'iu' and len(ids) > 0 and
         len(np.unique(ids)) == len(ids), 'Unique required integer source rows')
    expected = [int(x) for x in ids]
    result = {}
    for view in VIEWS:
        row = outputs[view]
        need(type(row) is dict and set(row) == {'row_ids', 'probabilities'}, 'Exact view artifact fields')
        actual = np.asarray(row['row_ids'])
        need(actual.ndim == 1 and actual.dtype.kind in 'iu' and len(actual) == len(ids), 'Integer view row count')
        keys = [int(x) for x in actual]
        need(len(set(keys)) == len(keys) and set(keys) == set(expected), 'No missing, extra or duplicate row')
        p = probabilities(row['probabilities'], np)
        need(len(p) == len(keys), 'One probability vector per row')
        positions = {key: i for i, key in enumerate(keys)}
        result[view] = p[[positions[key] for key in expected]]
    return result


def mean_log_loss(p, y, np):
    need(p.shape == (len(y), 3) and len(y) > 0, 'Full paired loss support')
    chosen = p[np.arange(len(y)), y]
    zero = chosen == 0
    if bool(zero.any()):
        return math.inf
    return float(-np.log(chosen).mean())


def session_metrics(outputs, required_ids, labels, np):
    p_by_view = align_views(outputs, required_ids, np)
    y = np.asarray(labels)
    need(y.ndim == 1 and y.dtype.kind in 'iu' and len(y) == len(required_ids) and
         bool(((y >= 0) & (y <= 2)).all()), 'Exact three-class query target support')
    y = y.astype(np.int64, copy=False)
    counts = np.bincount(y, minlength=3)
    onehot = np.eye(3, dtype=np.float64)[y]
    metrics = {}
    for view in VIEWS:
        p = p_by_view[view]
        predicted = np.argmax(p, axis=1)  # First class in fixed order wins exact ties.
        recalls = [float((predicted[y == k] == k).mean()) if counts[k] else None for k in range(3)]
        metrics[view] = {
            'natural_log_loss': extended(mean_log_loss(p, y, np)),
            'top1_accuracy': float((predicted == y).mean()),
            'multiclass_Brier_mean_sum3': float(np.square(p - onehot).sum(axis=1).mean()),
            'class_recall': recalls,
            'macro_recall': {'status': 'finite', 'value': sum(recalls) / 3} if bool((counts > 0).all())
                else {'status': 'undefined_missing_query_class', 'value': None},
            'zero_true_class_probability_rows': int((p[np.arange(len(y)), y] == 0).sum()),
        }
    effect = number(metrics['wheel_plus_context']['natural_log_loss']) - number(
        metrics['neural_wheel_plus_context']['natural_log_loss'])
    return {'query_rows': len(y), 'class_counts': [int(x) for x in counts], 'views': metrics,
            'primary_wheel_minus_joint_logloss': extended(effect),
            'case_removal_for_probability_or_performance': False}


def descriptive_metrics(outputs, required_ids, labels, strata, np):
    """Post-commit diagnostics only; empty strata remain explicit, never selected."""
    need(set(strata) == set(STRATA), 'Exact descriptive strata')
    aligned = align_views(outputs, required_ids, np)
    result = {}
    for name, categories in STRATA.items():
        codes = np.asarray(strata[name])
        need(codes.shape == (len(required_ids),) and codes.dtype.kind in 'iu' and
             bool(((codes >= 0) & (codes < len(categories))).all()), 'Descriptive code range')
        rows = {}
        for code, label in enumerate(categories):
            mask = codes == code
            count = int(mask.sum())
            if not count:
                rows[label] = {'rows': 0, 'status': 'undefined_empty_stratum', 'metrics': None}
                continue
            subset = {view: {'row_ids': required_ids[mask],
                             'probabilities': aligned[view][mask]} for view in VIEWS}
            rows[label] = {'rows': count, 'status': 'descriptive_only',
                           'metrics': session_metrics(subset, required_ids[mask], labels[mask], np)}
        result[name] = rows
    return result


def aggregate(records, roster, np):
    """All required sessions -> equal sessions/mouse -> equal mice.

    A caller supplies the exact fixed roster. Real-worker admission additionally
    requires all39 source sessions and10 mice; small invented rosters qualify
    the same weighting code without pretending to be empirical cohorts.
    """
    need(type(records) is list and type(roster) is list and len(records) == len(roster) > 0,
         'Complete required cohort only')
    expected = {r['session']: r['mouse'] for r in roster}
    need(len(expected) == len(roster) and all(type(k) is str and type(v) is str for k, v in expected.items()),
         'Unique declared source session/mouse roster')
    actual = {r['session']: r for r in records}
    need(len(actual) == len(records) and set(actual) == set(expected) and
         all(actual[k]['mouse'] == v for k, v in expected.items()), 'No missing/extra session or mouse reassignment')
    mice = sorted(set(expected.values()))
    mouse_rows = []
    for mouse in mice:
        sessions = [r['session'] for r in roster if r['mouse'] == mouse]
        losses = {}
        for view in VIEWS:
            values = [number(actual[key]['metrics']['views'][view]['natural_log_loss']) for key in sessions]
            need(all(not math.isnan(x) and x >= 0 for x in values), 'Valid nonnegative complete session losses')
            losses[view] = extended(sum(values) / len(values))
        effect = number(losses['wheel_plus_context']) - number(losses['neural_wheel_plus_context'])
        mouse_rows.append({'mouse': mouse, 'sessions': sessions, 'session_count': len(sessions),
                           'view_logloss': losses, 'primary_wheel_minus_joint': extended(effect)})
    absolute = {view: extended(sum(number(row['view_logloss'][view]) for row in mouse_rows) / len(mice))
                for view in VIEWS}
    effects = [number(row['primary_wheel_minus_joint']) for row in mouse_rows]
    primary = extended(sum(effects) / len(effects))
    draws = np.empty(0, dtype=np.float64)
    interval = {'status': 'undefined_nonfinite_mouse_effect', 'lower': None, 'upper': None}
    if all(math.isfinite(x) for x in effects):
        rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
        sampled = rng.integers(0, len(mice), size=(BOOTSTRAP_DRAWS, len(mice)), dtype=np.int64)
        draws = np.asarray(effects, dtype=np.float64)[sampled].mean(axis=1)
        limits = np.quantile(draws, [.025, .975], method='linear')
        interval = {'status': 'finite', 'lower': float(limits[0]), 'upper': float(limits[1])}
    return {'required_sessions': len(roster), 'required_mice': len(mice),
            'session_records': records, 'mouse_records': mouse_rows,
            'equal_mouse_view_logloss': absolute, 'primary_wheel_minus_joint': primary,
            'paired_mouse_bootstrap': {'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED,
                'generator': 'NumPy.PCG64', 'percentiles': [.025, .975], 'quantile_method': 'linear',
                'interval': interval, 'draw_values_retained': len(draws)},
            'subset_renormalization': False}, draws
