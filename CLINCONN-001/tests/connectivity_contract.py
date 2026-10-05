"""Source-bound CNP receipts and independently implemented public statistics.

No solution imports, effect-direction gates, similarity scores or prose grading.
Synthetic fixtures exercise mechanics; only an original-source bank is evidence.
"""
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

EPS = np.finfo(np.float64).eps
TINY = np.finfo(np.float64).tiny
MODELS = ('all_crude', 'all_fd_adjusted')
ARRAY_FIELDS = ('subject_id parcel_id edge_id parcel_status '
    'parcel_original_centered_l2 parcel_residual_l2 parcel_zero_bound '
    'raw_r fisher_z edge_valid fisher_clipped').split()
TOLS = {
    'raw_r': (1e-7, 1e-6), 'fc': (1e-6, 1e-6),
    'stats': (1e-6, 1e-5), 'source': (1e-10, 1e-8),
    'geometry': (1e-5, 1e-7), 'norm': (1e-10, 1e-7),
    'floor': (0., 1e-7), 'exact': (0., 0.)}
INT_FIELDS = set(('source_participant_row source_rest annotation_index n_vertices '
    'edge_id n_valid_subjects n_frames n_fd_defined n_confound_columns nuisance_rank '
    'n_valid_parcels n_invalid_parcels n_common_edges n_saturated_common_edges '
    'n n_schz n_control rank df').split())
FLAG_FIELDS = set(('available_left available_right available_confounds selected '
    'included common_valid first_fd_defined qc_fd_lt_0_2').split())
TEXT_FIELDS = set(('subject_id group exclusion_reason parcel_id hemisphere '
    'annotation_name parcel_i parcel_j distance_bin model status qcfc_status').split())


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def integer(value):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not an integer')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AssertionError('Invalid integer')
    require(result.is_finite() and result == result.to_integral_value(),
            'Nonfinite or fractional integer')
    return int(result)


def number(value):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not a number')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise AssertionError('Invalid number')
    require(math.isfinite(result), 'Nonfinite number')
    return result


def flag(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    result = integer(value)
    require(result in (0, 1), 'Invalid Boolean flag')
    return bool(result)


def close(actual, expected, kind='stats', label='measurement'):
    a, b = number(actual), number(expected)
    atol, rtol = TOLS[kind]
    require(abs(a-b) <= atol+rtol*abs(b), f'{label} differs from source/declared arithmetic')


def array_close(actual, expected, kind, label, undefined=False):
    a, b = np.asarray(actual), np.asarray(expected)
    require(a.shape == b.shape and a.dtype.kind == 'f', f'Invalid {label} array')
    if undefined:
        require(np.array_equal(np.isnan(a), np.isnan(b)), f'Wrong undefined {label} support')
        keep = np.isfinite(b)
    else:
        keep = np.ones(b.shape, bool)
    require(np.isfinite(a[keep]).all() and not np.isinf(a).any(), f'Nonfinite {label}')
    atol, rtol = TOLS[kind]
    require(np.all(np.abs(a[keep]-b[keep]) <= atol+rtol*np.abs(b[keep])),
            f'{label} differs from original source')


def json_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise AssertionError('Nonfinite JSON literal')
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def csv_load(path, columns):
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
                'Missing/duplicate CSV header')
        require(set(columns) <= set(reader.fieldnames), 'Missing required CSV columns')
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows),
            'Malformed CSV row')
    return rows


def match(actual, expected, label='JSON', kind='stats', closed=False):
    """Type-aware finite recursive comparison; required null keys cannot be omitted."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f'Missing {label} fields')
        if closed:
            require(set(actual) == set(expected), f'Unexpected {label} scientific identity')
        for key, value in expected.items():
            match(actual[key], value, label+'.'+key, kind, closed)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f'Wrong {label} list')
        for a, b in zip(actual, expected):
            match(a, b, label, kind, closed)
    elif expected is None:
        require(actual is None, f'Undefined {label} must be null')
    elif isinstance(expected, bool):
        require(isinstance(actual, bool) and actual == expected, f'Wrong {label} Boolean')
    elif isinstance(expected, int):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and integer(actual) == expected, f'Wrong {label} count')
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool), f'Wrong {label} type')
        close(actual, expected, kind, label)
    else:
        require(isinstance(actual, str) and actual == expected, f'Wrong {label} text')


def keyed(rows, keys):
    result = {}
    for row in rows:
        require(isinstance(row, dict) and set(keys) <= set(row), 'Missing row identity')
        key = tuple(integer(row[k]) if k in INT_FIELDS else row[k] for k in keys)
        require(key not in result, 'Duplicate keyed row')
        result[key] = row
    return result


def field_kind(field):
    if field in ('centroid_x', 'centroid_y', 'centroid_z', 'distance'):
        return 'geometry'
    if field in ('fd_sum', 'mean_fd', 'tr_s'):
        return 'source'
    if field == 'nuisance_rank_threshold':
        return 'floor'
    if field in ('mean_fc', 'short_range_fc', 'long_range_fc'):
        return 'fc'
    return 'stats'


def domains(field, value):
    if value is None:
        return
    if field in ('se', 'sse', 'fd_sum', 'mean_fd', 'distance', 'nuisance_rank_threshold'):
        require(number(value) >= 0, f'Negative {field}')
    if field in ('p', 'fraction_abs_t_gt_2', 'patient_higher_fraction'):
        require(0 <= number(value) <= 1, f'Invalid {field} domain')
    if field in ('qcfc_r', 'r'):
        require(-1 <= number(value) <= 1, f'Invalid {field} domain')
    if field in ('mean_fc', 'short_range_fc', 'long_range_fc'):
        require(abs(number(value)) <= math.atanh(.999)+1e-12, 'Invalid Fisher-z mean domain')


def validate_table(actual, expected, keys):
    a, b = keyed(actual, keys), keyed(expected, keys)
    require(set(a) == set(b), 'Complete source-keyed table required')
    for key, row in b.items():
        require(set(row) <= set(a[key]), 'Missing row fields')
        for field, value in row.items():
            got = a[key][field]
            if value is None:
                require(got == '', 'Undefined CSV measurement must be blank')
            elif field in FLAG_FIELDS:
                require(flag(got) == bool(value), 'Wrong source Boolean category')
            elif field in INT_FIELDS:
                require(integer(got) == value, 'Wrong source identity/count')
            elif field in TEXT_FIELDS:
                require(got == value, 'Wrong source identity/status')
            else:
                domains(field, got)
                close(got, value, field_kind(field), field)


def pearson(x, y, x_status='constant_fd', y_status='constant_edge'):
    x, y = np.asarray(x, float), np.asarray(y, float)
    require(x.ndim == 1 and x.shape == y.shape and np.isfinite(x).all() and np.isfinite(y).all(),
            'Invalid correlation inputs')
    if len(x) < 2:
        return 'insufficient_n', None
    if np.all(x == x[0]):
        return x_status, None
    if np.all(y == y[0]):
        return y_status, None
    a, b = x-x.mean(), y-y.mean()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0:
        return x_status, None
    if nb == 0:
        return y_status, None
    r = float(np.dot(a/na, b/nb))
    require(abs(r) <= 1+1e-12, 'Invalid Pearson overshoot')
    return 'ok', float(np.clip(r, -1, 1))


def empty_effect(n=0, n_schz=0, rank=0, status='excluded_not_common'):
    return dict(status=status, n=int(n), n_schz=int(n_schz), n_control=int(n-n_schz),
                rank=int(rank), df=int(n-rank), estimate=None, se=None,
                ci95=[None, None], t=None, p=None, sse=None)


def ols_many(y, diagnosis, fd=None, empty=False):
    """Batched public classical OLS using a contrast-estimable SVD pseudoinverse."""
    g = np.asarray(diagnosis, float)
    require(g.ndim == 1 and np.isin(g, [0., 1.]).all(), 'Invalid diagnosis coding')
    y = np.asarray(y, float)
    if y.ndim == 1:
        y = y[:, None]
    require(y.ndim == 2 and len(y) == len(g), 'Invalid response shape')
    n, n_out = y.shape
    columns = [np.ones(n), g]
    if fd is not None:
        fd = np.asarray(fd, float)
        require(fd.shape == g.shape and np.isfinite(fd).all(), 'Invalid FD design')
        columns.append(fd)
    x = np.column_stack(columns)
    p = x.shape[1]
    if n:
        u, s, vt = np.linalg.svd(x, full_matrices=False)
        use = s > max(n, p)*EPS*s[0]
        rank = int(use.sum())
        plus = (vt[use].T/s[use]) @ u[:, use].T
        e = np.zeros(p); e[1] = 1
        estimable = np.linalg.norm(e-vt[use].T@(vt[use]@e)) <= 100*max(n, p)*EPS
    else:
        rank, estimable = 0, False
        plus = np.zeros((p, 0))
    base = empty_effect(n, int(g.sum()), rank)
    if empty:
        base['status'] = 'empty_response_bin'
    elif not n or np.all(g == g[0]):
        base['status'] = 'missing_group'
    elif n-rank <= 0:
        base['status'] = 'insufficient_df'
    elif not estimable:
        base['status'] = 'rank_deficient'
    else:
        require(np.isfinite(y).all(), 'Nonfinite modeled response')
        beta = plus@y
        residual = y-x@beta
        constant = np.all(y == y[0], axis=0)
        centered = y-y.mean(axis=0)
        rn = np.linalg.norm(residual, axis=0)
        bound = 10*max(n, p)*EPS*np.maximum(np.linalg.norm(centered, axis=0), TINY)
        zero = constant | (rn <= bound)
        sse = np.einsum('ij,ij->j', residual, residual)
        sse[zero] = 0.
        estimates = beta[1].copy(); estimates[constant] = 0.
        se = np.sqrt(sse/(n-rank)*np.dot(plus[1], plus[1]))
        require(np.isfinite(estimates).all() and np.isfinite(sse).all() and np.isfinite(se).all(),
                'Nonfinite OLS result')
        result = []
        for i in range(n_out):
            row = dict(base)
            est, sigma = float(estimates[i]), float(se[i])
            row.update(status='zero_se' if sigma == 0 else 'ok', estimate=est, se=sigma,
                       ci95=[est-1.96*sigma, est+1.96*sigma], sse=float(sse[i]))
            if sigma:
                statistic = est/sigma
                require(math.isfinite(statistic), 'Nonfinite t statistic')
                row.update(t=statistic, p=float(2*student_t.sf(abs(statistic), n-rank)))
            result.append(row)
        return result
    return [dict(base, ci95=[None, None]) for _ in range(n_out)]


def ols(y, diagnosis, fd=None, empty=False):
    return ols_many(y, diagnosis, fd, empty)[0]


def family(distance, common):
    d, c = np.asarray(distance, float), np.asarray(common, bool)
    require(d.ndim == 1 and d.shape == c.shape and np.isfinite(d).all() and (d >= 0).all(),
            'Invalid edge distances')
    bins = np.full(len(d), 'excluded_not_common', dtype='U19')
    if not c.any():
        return bins, dict(q1=None, q2=None, n_short=0, n_middle=0, n_long=0)
    q1, q2 = np.quantile(d[c], [1/3, 2/3], method='linear')
    bins[c] = 'middle'; bins[c & (d < q1)] = 'short'; bins[c & (d > q2)] = 'long'
    return bins, dict(q1=float(q1), q2=float(q2),
        n_short=int(np.sum(bins == 'short')), n_middle=int(np.sum(bins == 'middle')),
        n_long=int(np.sum(bins == 'long')))


def summarize(ref, values=None, fd_values=None):
    """Recompute source-authoritative support plus full matrix and model summaries."""
    a = ref if values is None else values
    subjects = ref['subject_id'].tolist()
    n = len(subjects)
    source_rows = {r['subject_id']: r for r in ref['connectivity_rows']}
    group = np.array([source_rows[s]['group'] for s in subjects])
    g = (group == 'SCHZ').astype(float)
    source_fd = np.array([source_rows[s]['mean_fd'] for s in subjects], float)
    fd = source_fd if fd_values is None else np.asarray(fd_values, float)
    require(fd.shape == source_fd.shape and np.isfinite(fd).all(), 'Invalid submitted FD axis')
    valid = ref['edge_valid']
    common = valid.all(axis=0)
    edge_rows = sorted(ref['edge_rows'], key=lambda r: r['edge_id'])
    d = np.array([r['distance'] for r in edge_rows], float)
    bins, bin_result = family(d, common)
    matrix = a['fisher_z']
    means = {}
    for name, keep in [('mean_fc', common), ('short_range_fc', bins == 'short'), ('long_range_fc', bins == 'long')]:
        means[name] = matrix[:, keep].mean(axis=1) if keep.any() else None
    subjects_out = []
    for i, sid in enumerate(subjects):
        row = dict(source_rows[sid])
        row.update(n_valid_parcels=int(np.sum(ref['parcel_status'][i] == 'ok')),
                   n_invalid_parcels=int(np.sum(ref['parcel_status'][i] != 'ok')),
                   n_common_edges=int(common.sum()),
                   n_saturated_common_edges=int(np.sum(ref['fisher_clipped'][i, common])))
        for name, y in means.items():
            row[name] = None if y is None else float(y[i])
        subjects_out.append(row)
    edges_out = []
    for i, row in enumerate(edge_rows):
        edges_out.append(dict(row, n_valid_subjects=int(valid[:, i].sum()),
                              common_valid=bool(common[i]), distance_bin=str(bins[i])))
    stats_by_model = {}
    for model in MODELS:
        fits = [empty_effect() for _ in range(len(d))]
        calculated = ols_many(matrix[:, common], g, fd if model == 'all_fd_adjusted' else None)
        for e, result in zip(np.flatnonzero(common), calculated):
            fits[e] = result
        stats_by_model[model] = fits
    qc = [pearson(fd, matrix[:, e]) if common[e] else ('excluded_not_common', None) for e in range(len(d))]
    stats_rows = []
    for e in range(len(d)):
        for model in MODELS:
            row = dict(stats_by_model[model][e])
            interval = row.pop('ci95')
            row.update(edge_id=int(ref['edge_id'][e]), model=model, ci95_low=interval[0],
                       ci95_high=interval[1], qcfc_status=qc[e][0], qcfc_r=qc[e][1])
            stats_rows.append(row)
    primary = {}
    for model in ('all_crude', 'all_fd_adjusted', 'qc_fd_lt_0_2'):
        keep = source_fd < .2 if model == 'qc_fd_lt_0_2' else np.ones(n, bool)
        y = means['short_range_fc']
        primary[model] = ols(np.zeros(int(keep.sum())) if y is None else y[keep],
                             g[keep], fd[keep] if model == 'all_fd_adjusted' else None, empty=y is None)
    thresholds, maps = {}, {}
    for model, fits in stats_by_model.items():
        finite = [e for e in np.flatnonzero(common) if fits[e]['t'] is not None]
        selected = [e for e in finite if abs(fits[e]['t']) > 2]
        positive = sum(fits[e]['t'] > 2 for e in selected)
        thresholds[model] = dict(n_common_edges=int(common.sum()), n_defined_t=len(finite),
            n_undefined_t=int(common.sum())-len(finite), n_abs_t_gt_2=len(selected),
            fraction_abs_t_gt_2=len(selected)/len(finite) if finite else None,
            n_patient_higher=positive, patient_higher_fraction=positive/len(selected) if selected else None)
        usable = [e for e in finite if qc[e][1] is not None]
        status, r = pearson([fits[e]['t'] for e in usable], [qc[e][1] for e in usable],
                            'constant_group_t', 'constant_qcfc')
        maps[model] = dict(status=status, n_edges=len(usable), r=r)
    group_means = {}
    for name, values in dict(means, mean_fd=fd).items():
        group_means[name] = {label: None if values is None or not np.any(group == label)
                            else float(values[group == label].mean()) for label in ('SCHZ', 'CONTROL')}
    result = dict(status='complete', task_id='CLINCONN-001', n_candidates=len(ref['cohort_rows']),
        n_subjects=n, group_counts={label: int(np.sum(group == label)) for label in ('SCHZ', 'CONTROL')},
        n_candidate_edges=len(d), n_common_edges=int(common.sum()), distance_bins=bin_result,
        group_means=group_means, short_range_effects=primary, edgewise_abs_t_gt_2=thresholds,
        group_map_vs_qcfc=maps)
    return dict(edge_rows=edges_out, connectivity_rows=subjects_out, edge_stats=stats_rows, group_stats=result)


def axis_order(actual, expected, label):
    require(actual.ndim == 1 and len(actual) == len(expected), f'Incomplete {label} axis')
    ids = actual.tolist()
    require(len(set(ids)) == len(ids) and set(ids) == set(expected.tolist()), f'Wrong/duplicate {label} axis')
    lookup = {v: i for i, v in enumerate(ids)}
    return np.array([lookup[v] for v in expected.tolist()], dtype=np.int64)


def validate_arrays(path, ref):
    with np.load(path, allow_pickle=False) as archive:
        require(set(ARRAY_FIELDS) <= set(archive.files), 'Missing source array fields')
        raw = {k: np.array(archive[k]) for k in archive.files}
    require(all(v.dtype.kind in 'biufUS' for v in raw.values()), 'Nonprimitive array receipt')
    order = {}
    for name in ('subject_id', 'parcel_id', 'edge_id'):
        require(raw[name].dtype.kind == 'U' if name != 'edge_id' else raw[name].dtype.kind in 'iu',
                'Invalid source axis dtype')
        order[name] = axis_order(raw[name], ref[name], name)
    a = {k: ref[k] for k in ('subject_id', 'parcel_id', 'edge_id')}
    for name in ARRAY_FIELDS[3:]:
        val = raw[name]
        require(val.shape == ref[name].shape, f'Wrong {name} shape')
        cols = order['parcel_id'] if name.startswith('parcel_') else order['edge_id']
        a[name] = val[np.ix_(order['subject_id'], cols)]
    require(a['parcel_status'].dtype.kind == 'U' and np.array_equal(a['parcel_status'], ref['parcel_status']),
            'Wrong source parcel status')
    for name in ('edge_valid', 'fisher_clipped'):
        require(a[name].dtype.kind == 'b' and np.array_equal(a[name], ref[name]), 'Wrong source validity/clipping category')
    for name in ('parcel_original_centered_l2', 'parcel_residual_l2', 'parcel_zero_bound'):
        array_close(a[name], ref[name], 'floor' if name == 'parcel_zero_bound' else 'norm', name)
        require((a[name] >= 0).all(), 'Negative parcel norm/floor')
    for name, kind in [('raw_r', 'raw_r'), ('fisher_z', 'fc')]:
        array_close(a[name], ref[name], kind, name, undefined=True)
        require(np.array_equal(np.isnan(a[name]), ~ref['edge_valid']), 'Wrong undefined edge pattern')
    keep = ref['edge_valid']
    require(np.all(np.abs(a['raw_r'][keep]) <= 1+1e-12), 'Impossible Pearson coefficient')
    limit = math.atanh(.999)
    require(np.all(np.abs(a['fisher_z'][keep]) <= limit+1e-12), 'Impossible clipped Fisher-z')
    # Propagate allowed raw-r serialization error through the nonlinear transform.
    derived = np.arctanh(np.clip(a['raw_r'][keep], -.999, .999))
    source_derived = np.arctanh(np.clip(ref['raw_r'][keep], -.999, .999))
    atol, rtol = TOLS['fc']
    allowance = atol+rtol*np.abs(source_derived)+np.abs(derived-source_derived)
    require(np.all(np.abs(a['fisher_z'][keep]-derived) <= allowance), 'Incoherent Fisher transform')
    return a


def validate_metadata(actual, ref):
    wanted = ref['metadata']
    for name in ('status', 'task_id', 'dataset_id', 'source_manifest_sha256', 'method_contract_sha256'):
        require(actual.get(name) == wanted[name], 'Wrong source/method/status fingerprint')
    for name in ('source_sha256', 'method_contract'):
        match(actual.get(name), wanted[name], name, 'exact', closed=True)
    observed = wanted['source_observed']
    match(actual.get('source_observed'), {k: v for k, v in observed.items() if k != 'subjects'},
          'source_observed', 'source')
    match(actual['source_observed']['atlas'], observed['atlas'], 'observed atlas', 'exact', closed=True)
    match(actual['source_observed']['group_counts'], observed['group_counts'], 'observed group counts', closed=True)
    a = keyed(actual['source_observed'].get('subjects', []), ['subject_id'])
    b = keyed(observed['subjects'], ['subject_id'])
    require(set(a) == set(b), 'Complete measured source metadata required')
    for key in b:
        match(a[key], b[key], 'source subject', 'source')
    software = actual.get('software')
    require(isinstance(software, dict) and software and all(isinstance(k, str) and k.strip()
            and isinstance(v, str) and v.strip() for k, v in software.items()), 'Actual software mapping required')


def validate_group(actual, expected):
    require(isinstance(actual, dict) and set(expected) <= set(actual), 'Missing group statistics fields')
    scalar = {k: v for k, v in expected.items() if not isinstance(v, dict)}
    match(actual, scalar, 'group statistics')
    for key in ('group_counts', 'distance_bins', 'group_means', 'short_range_effects',
                'edgewise_abs_t_gt_2', 'group_map_vs_qcfc'):
        require(set(actual[key]) == set(expected[key]), 'Unexpected statistical model/family')
    match(actual['group_counts'], expected['group_counts'], 'group counts', closed=True)
    match(actual['distance_bins'], expected['distance_bins'], 'distance bins', 'geometry', closed=True)
    for measure, row in expected['group_means'].items():
        match(actual['group_means'][measure], row, 'group means', 'source' if measure == 'mean_fd' else 'fc', closed=True)
        for value in actual['group_means'][measure].values():
            domains(measure, value)
    for name in ('short_range_effects', 'edgewise_abs_t_gt_2', 'group_map_vs_qcfc'):
        for model, row in expected[name].items():
            match(actual[name][model], row, name+'.'+model)
    for name, row in actual['short_range_effects'].items():
        for field in ('se', 'sse', 'p'):
            domains(field, row[field])
    for row in actual['edgewise_abs_t_gt_2'].values():
        for field in ('fraction_abs_t_gt_2', 'patient_higher_fraction'):
            domains(field, row[field])
    for row in actual['group_map_vs_qcfc'].values():
        domains('r', row['r'])


def propagated_arithmetic(actual, source, recalculated, kind, label):
    """Independent within-submission arithmetic at the published output tolerance.

    Source-authoritative undefined quantities remain undefined, but a defined
    source statistic cannot be replaced by an undefined recomputation. There is
    no error-budget widening using distance from the source answer.
    """
    if source is None:
        return
    require(recalculated is not None, f'Submitted precision makes defined {label} undefined')
    close(actual, recalculated, kind, 'submitted '+label)


def validate_submitted_arithmetic(tables, result, ref, values, authoritative):
    submitted = keyed(tables['connectivity_rows'], ['subject_id'])
    fd = np.array([number(submitted[(sid,)]['mean_fd']) for sid in ref['subject_id']])
    recalculated = summarize(ref, values, fd_values=fd)
    for key, source_row in keyed(authoritative['connectivity_rows'], ['subject_id']).items():
        row = submitted[key]
        propagated_arithmetic(row['mean_fd'], source_row['mean_fd'],
            number(row['fd_sum'])/integer(row['n_fd_defined']), 'source', 'submitted FD mean')
    for name, keys, fields in [
            ('connectivity_rows', ['subject_id'], ['mean_fc', 'short_range_fc', 'long_range_fc']),
            ('edge_stats', ['edge_id', 'model'], ['estimate', 'se', 'ci95_low', 'ci95_high', 't', 'p', 'sse', 'qcfc_r'])]:
        actual = keyed(tables[name], keys)
        source = keyed(authoritative[name], keys)
        calc = keyed(recalculated[name], keys)
        for key in source:
            for field in fields:
                if source[key][field] is not None:
                    propagated_arithmetic(actual[key][field], source[key][field], calc[key][field],
                                          field_kind(field), field)
    for measure, row in authoritative['group_stats']['group_means'].items():
        for group, value in row.items():
            propagated_arithmetic(result['group_means'][measure][group], value,
                recalculated['group_stats']['group_means'][measure][group],
                'source' if measure == 'mean_fd' else 'fc', 'group mean')
    for model, row in authoritative['group_stats']['short_range_effects'].items():
        got = result['short_range_effects'][model]
        calc = recalculated['group_stats']['short_range_effects'][model]
        for field in ('estimate', 'se', 't', 'p', 'sse'):
            propagated_arithmetic(got[field], row[field], calc[field], 'stats', 'group '+field)
        for i in range(2):
            propagated_arithmetic(got['ci95'][i], row['ci95'][i], calc['ci95'][i], 'stats', 'group CI')
    for model, row in authoritative['group_stats']['group_map_vs_qcfc'].items():
        propagated_arithmetic(result['group_map_vs_qcfc'][model]['r'], row['r'],
            recalculated['group_stats']['group_map_vs_qcfc'][model]['r'], 'stats', 'group-map correlation')


def validate_output_directory(output, ref):
    output = Path(output)
    definitions = ref['metadata']['method_contract']['outputs']
    for filename, key, keys in [('cohort.csv', 'cohort_rows', ['subject_id']),
            ('parcels.csv', 'parcel_rows', ['parcel_id'])]:
        validate_table(csv_load(output/filename, definitions[filename]['columns']), ref[key], keys)
    values = validate_arrays(output/'subject_edge_fc.npz', ref)
    expected = ref.get('derived') or summarize(ref)
    tables = {}
    for filename, key, keys in [('edges.csv', 'edge_rows', ['edge_id']),
            ('connectivity.csv', 'connectivity_rows', ['subject_id']),
            ('edge_stats.csv', 'edge_stats', ['edge_id', 'model'])]:
        tables[key] = csv_load(output/filename, definitions[filename]['columns'])
        validate_table(tables[key], expected[key], keys)
    result = json_load(output/'group_stats.json')
    validate_group(result, expected['group_stats'])
    validate_submitted_arithmetic(tables, result, ref, values, expected)
    validate_metadata(json_load(output/'run_metadata.json'), ref)
    require((output/'findings.md').read_text().strip(), 'Nonempty findings required')
    return expected['group_stats']
