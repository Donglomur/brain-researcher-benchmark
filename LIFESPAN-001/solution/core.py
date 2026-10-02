"""Frozen source-canonical arithmetic, independent of file IO/grader code.

NumPy corrcoef and sklearn KMeans are intentionally shared public reference
operations. No verifier implementation or historical numerical bank is imported.
"""
import math
import warnings

import numpy as np
from scipy.stats import pearsonr

from partition_contract import fit_partition

ZMAX = float(np.arctanh(0.999))


def finite_real(value, ndim):
    a = np.asarray(value)
    if a.ndim != ndim or a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
        raise ValueError('Finite real array of declared dimensionality required')
    return a


def parcel_means(source, membership):
    """Exact public C-order float64 mean expression; v must be ascending."""
    x = finite_real(source, 2)
    means = np.empty((len(x), len(membership)), dtype=np.float64)
    for i, vertices in enumerate(membership):
        v = np.asarray(vertices)
        if v.ndim != 1 or v.dtype.kind not in 'iu' or len(v) == 0 or np.any(v < 0) or np.any(v >= x.shape[1]) or np.any(np.diff(v) <= 0):
            raise ValueError('Nonempty ascending unique source vertex indices required')
        means[:, i] = np.asarray(x[:, v], dtype=np.float64, order='C').mean(axis=1, dtype=np.float64)
    q = means.astype(np.float32)
    if not np.isfinite(q).all():
        raise ArithmeticError('Nonfinite once-rounded parcel mean')
    return q, means


def individual_connectome(q):
    x = finite_real(q, 2).astype(np.float64)
    if not np.array_equal(x.astype(np.float32).astype(np.float64), x):
        raise ValueError('Canonical means must be exact float32 values or their promotion')
    n_frames, n_rois = x.shape
    edges = np.column_stack(np.triu_indices(n_rois, 1)).astype(np.int64)
    status = (np.full(n_rois, 'insufficient_frames', dtype='U24') if n_frames < 2 else
              np.where(np.all(x == x[0], axis=0), 'constant', 'ok').astype('U24'))
    valid = (status[edges[:, 0]] == 'ok') & (status[edges[:, 1]] == 'ok')
    raw = np.full(len(edges), np.nan)
    caught_messages = []
    if n_frames >= 2:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            full = np.corrcoef(x.T)
        caught_messages = [f'{w.category.__name__}: {w.message}' for w in caught]
        raw[valid] = full[edges[valid, 0], edges[valid, 1]]
    if not np.isfinite(raw[valid]).all():
        raise ArithmeticError('Nonfinite Pearson result for nonconstant source parcels')
    z = np.full(len(edges), np.nan)
    z[valid] = np.arctanh(np.clip(raw[valid], -0.999, 0.999))
    return dict(parcel_status=status, edge_roi_index=edges, edge_valid=valid,
                raw_r=raw, fisher_z=z, warnings=caught_messages)


def group_connectome(z, valid, edges, n_rois, expected_subjects):
    z, valid, edges = np.asarray(z), np.asarray(valid, dtype=bool), np.asarray(edges)
    accumulator = np.zeros(z.shape[1], dtype=np.float64)
    for row in z:
        accumulator += row  # Authenticated manifest order, not sorted filenames.
    pair_valid = np.all(valid, axis=0) & (len(z) == expected_subjects)
    average = accumulator / expected_subjects
    average[~pair_valid] = np.nan
    group = np.full((n_rois, n_rois), np.nan, dtype=np.float64)
    group_mask = np.zeros((n_rois, n_rois), dtype=bool)
    i, j = edges.T
    group[i, j] = average
    group[j, i] = average
    group_mask[i, j] = pair_valid
    group_mask[j, i] = pair_valid
    np.fill_diagonal(group, 0.0)
    np.fill_diagonal(group_mask, True)
    return group, group_mask


def summarize_people(z, valid, edges, statuses, partition, ids, ages):
    labels = partition['labels']
    partition_ok = partition['status'] == 'ok'
    nw = nb = None
    if partition_ok:
        within = labels[edges[:, 0]] == labels[edges[:, 1]]
        nw, nb = int(within.sum()), int((~within).sum())
    rows = []
    for subject, age, values, mask, parcel_status in zip(ids, ages, z, valid, statuses):
        complete = bool(mask.all())
        row = dict(subject_id=subject, age=float(age), n_edges_expected=len(values), n_edges_defined=int(mask.sum()),
                   global_fisher_sum=None, global_connectivity=None,
                   global_status='ok' if complete else 'incomplete_edge_support',
                   n_within_edges=None, n_between_edges=None, within_positive_sum=None, between_positive_sum=None,
                   within_network_connectivity=None, between_network_connectivity=None,
                   system_segregation=None, segregation_status='partition_undefined')
        if np.all(parcel_status == 'insufficient_frames'):
            row['global_status'] = 'insufficient_frames'
        if complete:
            row['global_fisher_sum'] = float(np.sum(values, dtype=np.float64))
            row['global_connectivity'] = row['global_fisher_sum'] / len(values)
        if partition_ok:
            row.update(n_within_edges=nw, n_between_edges=nb)
            if nw == 0 or nb == 0:
                row['segregation_status'] = 'empty_pair_family'
            elif not complete:
                row['segregation_status'] = 'incomplete_edge_support'
            else:
                positive = np.maximum(values, 0)
                ws, bs = float(np.sum(positive[within])), float(np.sum(positive[~within]))
                w, b = ws / nw, bs / nb
                ratio = None if w == 0 else (w - b) / w
                if ratio is not None and not math.isfinite(ratio):
                    raise ArithmeticError('Nonfinite segregation ratio')
                row.update(within_positive_sum=ws, between_positive_sum=bs,
                           within_network_connectivity=w, between_network_connectivity=b,
                           system_segregation=ratio, segregation_status='zero_within_mean' if w == 0 else 'ok')
        rows.append(row)
    return rows


def endpoint(ages, values, ids, expected_ids):
    available = {s: (float(a), v) for s, a, v in zip(ids, ages, values)}
    missing = [s for s in expected_ids if s not in available or available[s][1] is None]
    out = dict(status='incomplete_subject_support', n_expected=len(expected_ids),
               n_defined=len(expected_ids) - len(missing), undefined_subject_ids=missing,
               pearson_r=None, p=None, ci95=None)
    if missing:
        return out, []
    age = np.array([available[s][0] for s in expected_ids], dtype=np.float64)
    val = np.array([available[s][1] for s in expected_ids], dtype=np.float64)
    if not np.isfinite(age).all() or not np.isfinite(val).all():
        raise ArithmeticError('Nonfinite age-endpoint inputs')
    if np.all(age == age[0]):
        out['status'] = 'constant_age'
        return out, []
    if np.all(val == val[0]):
        out['status'] = 'constant_summary'
        return out, []
    if len(age) <= 3:
        raise ValueError('Defined Fisher interval needs more than three people')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = pearsonr(age, val)
    r, p = float(result.statistic), float(result.pvalue)
    interval = np.tanh(np.arctanh(np.clip(r, -0.999999, 0.999999)) +
                       np.array([-1.0, 1.0]) * 1.96 / np.sqrt(len(age) - 3))
    if not np.isfinite([r, p, *interval]).all():
        raise ArithmeticError('Nonfinite Pearson endpoint')
    out.update(status='ok', pearson_r=r, p=p, ci95=interval.tolist())
    return out, [f'{w.category.__name__}: {w.message}' for w in caught]


def analyze(q, ages, subject_ids, *, expected_subject_ids=None, method_sha256='', pilot=False):
    q = finite_real(q, 3)
    age = finite_real(ages, 1).astype(np.float64)
    ids = list(subject_ids)
    expected = ids if expected_subject_ids is None else list(expected_subject_ids)
    if len(q) != len(ids) or len(age) != len(ids) or len(set(ids)) != len(ids) or not ids:
        raise ValueError('Subject axes invalid')
    if any(s not in expected for s in ids) or np.any(age < 0) or not np.array_equal(age, age.astype(np.float32).astype(float)):
        raise ValueError('Canonical subject/age identities invalid')
    if not pilot and ids != expected:
        raise ValueError('Full canonical cohort order required')
    people = [individual_connectome(person) for person in q]
    edges = people[0]['edge_roi_index']
    statuses = np.stack([p['parcel_status'] for p in people])
    valid = np.stack([p['edge_valid'] for p in people])
    raw = np.stack([p['raw_r'] for p in people])
    z = np.stack([p['fisher_z'] for p in people])
    group, group_valid = group_connectome(z, valid, edges, q.shape[2], len(expected))
    part = fit_partition(group, group_valid)
    warnings_out = [f'{s}: {w}' for s, p in zip(ids, people) for w in p['warnings']] + part['warnings']
    summary = summarize_people(z, valid, edges, statuses, part, ids, age)
    complete_ids = [s for s, m in zip(ids, valid) if m.all()]
    clusters = [] if part['labels'] is None else [dict(network_id=str(int(v)), n_rois=int(np.sum(part['labels'] == v)))
                                                 for v in sorted(set(part['labels'].tolist()))]
    within_count = None
    if part['status'] == 'ok':
        within_count = int(np.sum(part['labels'][edges[:, 0]] == part['labels'][edges[:, 1]]))
    partition_doc = dict(status=part['status'], method_contract_sha256=method_sha256, n_rois=q.shape[2],
                         n_subjects_expected=len(expected), n_subjects_complete_connectome=len(complete_ids),
                         n_clusters_requested=7, n_clusters_occupied=part['n_clusters_occupied'],
                         n_within_edges=within_count, n_between_edges=None if within_count is None else len(edges) - within_count,
                         clusters=clusters, incomplete_subject_ids=[s for s in expected if s not in complete_ids])
    results = dict(status='resource_pilot' if pilot else 'ok', n_subjects=len(ids), age_range=[float(age.min()), float(age.max())])
    for name, field in [('overall_connectivity_vs_age', 'global_connectivity'),
                        ('system_segregation_vs_age', 'system_segregation')]:
        result, diagnostic_warnings = endpoint(age, [r[field] for r in summary], ids, expected)
        results[name] = result
        warnings_out += diagnostic_warnings
    if pilot:
        results['resource_pilot_scope'] = {'processed_subject_ids': ids, 'expected_subjects': len(expected),
                                         'cohort_partition_or_age_inference_computed': False}
    return dict(parcel_status=statuses, edge_roi_index=edges, edge_valid=valid, raw_r=raw, fisher_z=z,
                group_features=group, group_valid=group_valid, partition=partition_doc, fit=part,
                summary=summary, results=results, warnings=warnings_out)
