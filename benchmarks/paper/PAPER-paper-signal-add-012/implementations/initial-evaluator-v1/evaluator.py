# SPDX-License-Identifier: GPL-3.0-only
"""Source-as-written ISD kernel and prospective complete-cohort paired contrasts.

This does not reproduce empirical results or resolve the author's unspecified BCT
version. See scientific_holds in every report and the accompanying provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import shortest_path
from scipy.stats import t

TASK_ID = 'PAPER-paper-signal-add-012'
THRESHOLDS = np.arange(1, 101, dtype=float) / 100
COHORTS = {
    'Dataset-3': (14, ('baseline', 'light', 'deep', 'recovery'), 448),
    'Dataset-4-main': (17, ('baseline', 'light', 'surgical'), 240),
    'Dataset-4-supplement': (6, (), 240),  # Two conditions not independently resolved.
    'Dataset-5': (33, ('N1', 'N2', 'N3', 'awake'), None),
}
HOLDS = [
    'No authentic MAT payload, condition-axis binding, or participant roster verified.',
    'Author BCT revision unspecified; retained correlation self-loops may differ from paper intent.',
    'No MATLAB/native numerical parity, empirical reference, tolerance, or protected grading target established.',
    'Prospective complete-cohort state contrast and length/motion policy require scientific approval before empirical use.',
    'Full Dataset-3/4/5 state coverage is not implemented: one declared pair per cohort, Dataset-4 withheld and unequal Dataset-5 stages rejected.',
    'Dataset-4 subcohort overlap unresolved; cohorts must not be pooled as independent participants.',
    'No temporal transition/ETC claim: responsiveness annotations and transition timing unavailable.',
    'Rights, candidate access parity, protected references, baseline replay and scientific qualification remain open.',
]


def _matrix(value, name):
    a = np.asarray(value, dtype=float)
    if a.ndim != 2 or min(a.shape) < 2 or not np.isfinite(a).all():
        raise ValueError(f'{name}: finite 2D array with dimensions >=2 required')
    return a


def correlation_matrix(value):
    """Pearson correlation of columns (time x ROI); reject undefined constant ROIs."""
    a = _matrix(value, 'time series')
    with np.errstate(over='ignore', invalid='ignore'):
        centered = a - a.mean(axis=0)
        norm = np.linalg.norm(centered, axis=0)
    if not np.isfinite(centered).all() or not np.isfinite(norm).all():
        raise ValueError('correlation normalization overflow; rescale audited inputs explicitly')
    if np.any(norm == 0):
        raise ValueError('constant or numerically unresolved ROI has undefined Pearson correlation')
    z = centered / norm
    c = np.clip(z.T @ z, -1.0, 1.0)
    if not np.isfinite(c).all():
        raise ValueError('nonfinite Pearson correlation')
    # corr has an exact unit diagonal; rounding there must not add edges at t=1.
    np.fill_diagonal(c, 1.0)
    return c


def _fc(value, name):
    a = _matrix(value, name)
    if a.shape[0] != a.shape[1] or not np.array_equal(a, a.T):
        raise ValueError(f'{name}: square symmetric correlation matrix required')
    if np.any(np.abs(a) > 1) or not np.array_equal(np.diag(a), np.ones(len(a))):
        raise ValueError(f'{name}: correlations in [-1,1] and exact unit diagonal required')
    return a


def binary_global_efficiency(adjacency):
    """BCT charpath defaults: omit diagonal, retain unreachable pairs as zero inverse."""
    a = np.asarray(adjacency, dtype=bool)
    n = len(a)
    distances = shortest_path(a, directed=False, unweighted=True)
    off = distances[~np.eye(n, dtype=bool)]
    return float(np.sum(np.divide(1.0, off, out=np.zeros_like(off), where=np.isfinite(off))) / (n * (n - 1)))


def bct_clustering_with_diagonal(adjacency):
    """Literal BCT clustering_coef_bu neighborhood rule, including input self-loops.

    This intentionally is not standard loop-free clustering. It can exceed one.
    """
    a = np.asarray(adjacency, dtype=bool)
    values = np.zeros(len(a), dtype=float)
    for u in range(len(a)):
        neighbors = np.flatnonzero(a[u])
        k = len(neighbors)
        if k >= 2:
            values[u] = np.count_nonzero(a[np.ix_(neighbors, neighbors)]) / (k * (k - 1))
    return values


def isd_from_fc(no_gsr, gsr):
    a, b = _fc(no_gsr, 'noGSR FC'), _fc(gsr, 'GSR FC')
    if a.shape != b.shape:
        raise ValueError('GSR/noGSR ROI shapes differ')
    efficiency = np.array([binary_global_efficiency(a > x) for x in THRESHOLDS])
    clustering = np.array([bct_clustering_with_diagonal(b > x).mean() for x in THRESHOLDS])
    integration, segregation = float(efficiency.mean()), float(clustering.mean())
    upper = np.triu_indices(len(a), 1)
    return {
        'integration': integration, 'segregation': segregation, 'isd': integration - segregation,
        'thresholds': THRESHOLDS.tolist(), 'multilevel_efficiency': efficiency.tolist(),
        'multilevel_clustering': clustering.tolist(),
        'mean_correlation_no_gsr': float(a[upper].mean()),
        'mean_absolute_correlation_no_gsr': float(np.abs(a[upper]).mean()),
        'mean_correlation_gsr': float(b[upper].mean()),
        'diagonal_policy': 'retained_as_in_author_main',
    }


def paired_timeseries(no_gsr, gsr):
    a, b = _matrix(no_gsr, 'noGSR'), _matrix(gsr, 'GSR')
    if a.shape != b.shape:
        raise ValueError('paired preprocessing variants must have identical time/ROI dimensions')
    result = isd_from_fc(correlation_matrix(a), correlation_matrix(b))
    result.update(n_timepoints=len(a), n_rois=a.shape[1],
                  global_signal_sd_no_gsr=float(a.mean(axis=1).std(ddof=1)),
                  mean_roi_sd_no_gsr=float(a.std(axis=0, ddof=1).mean()))
    return result


def phase_randomized_pair(no_gsr, gsr, seed):
    """Prospective null preserving each ROI's discrete circular autocorrelation.

    Independent phases across ROIs destroy between-ROI timing; identical phases
    across preprocessing variants preserve their paired spectral relationship.
    DC and the real Nyquist bin (even length) are unchanged.
    """
    a, b = _matrix(no_gsr, 'noGSR'), _matrix(gsr, 'GSR')
    if a.shape != b.shape:
        raise ValueError('surrogate requires aligned paired matrices')
    rng = np.random.default_rng(seed)
    fa, fb = np.fft.rfft(a, axis=0), np.fft.rfft(b, axis=0)
    phases = np.exp(1j * rng.uniform(0, 2 * np.pi, size=fa.shape))
    phases[0] = 1
    if len(a) % 2 == 0:
        phases[-1] = 1
    return (np.fft.irfft(fa * phases, n=len(a), axis=0),
            np.fft.irfft(fb * phases, n=len(a), axis=0))


def paired_effect(before, after):
    """Prospective equal-participant mean(after-before) with Student-t 95% CI."""
    a, b = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
    if a.ndim != 1 or b.shape != a.shape or len(a) < 2 or not np.isfinite([a, b]).all():
        raise ValueError('at least two complete finite participant pairs required')
    d = b - a
    mean, sd = float(d.mean()), float(d.std(ddof=1))
    se = sd / math.sqrt(len(d))
    radius = float(t.ppf(.975, len(d) - 1) * se)
    return {'n_participants': len(d), 'mean_difference_after_minus_before': mean,
            'sd_difference': sd, 'standard_error': se, 'ci95': [mean - radius, mean + radius],
            'interval_recipe': 'paired_student_t_95_percent', 'participant_differences': d.tolist()}


def _identifiers(value, name):
    a = np.asarray(value)
    if a.ndim != 1 or a.dtype.kind not in 'USiu' or len(set(a.tolist())) != len(a):
        raise ValueError(f'{name}: unique 1D string/integer IDs required')
    return a


def _load_pair(record, root, length, roi_count):
    path = (root / record['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('input path must stay within manifest directory')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record['sha256']:
        raise ValueError('input sha256 mismatch')
    with np.load(path, allow_pickle=False) as z:
        a, b = _matrix(z['no_gsr'], 'noGSR'), _matrix(z['gsr'], 'GSR')
        if a.shape != b.shape or a.shape != (length, roi_count):
            raise ValueError('complete observation length/ROI shape mismatch; no truncation or masking')
        for axis, name in [(0, 'sample_ids'), (1, 'roi_ids')]:
            left = _identifiers(z['no_gsr_' + name], name)
            right = _identifiers(z['gsr_' + name], name)
            if len(left) != a.shape[axis] or not np.array_equal(left, right):
                raise ValueError(f'GSR/noGSR {name} differ')
        # Return IDs too: all state recordings must use the same ROI ordering.
        roi_ids = np.array(z['no_gsr_roi_ids'])
    fd = float(record['mean_framewise_displacement_mm'])
    if not math.isfinite(fd) or fd < 0:
        raise ValueError('finite nonnegative mean framewise displacement required')
    return a, b, roi_ids, fd


def evaluate_manifest(manifest, root):
    """Evaluate an explicit, full-cohort, paired-state normalized NPZ boundary.

    The boundary is prospective. MAT variable and condition maps remain unverified.
    Dataset4 is not admitted until its supplement labels/overlap are resolved.
    """
    if manifest['schema_version'] != 1 or manifest['task_id'] != TASK_ID:
        raise ValueError('wrong schema/task')
    cohort = manifest['cohort']
    if cohort not in ('Dataset-3', 'Dataset-5'):
        raise ValueError('only Dataset-3/5 admitted; Dataset-4 condition/overlap holds retained')
    population, conditions, native_length = COHORTS[cohort]
    engineering = manifest.get('engineering_control', False)
    if type(engineering) is not bool:
        raise ValueError('engineering_control must be Boolean')
    roster = _identifiers(manifest['participant_ids'], 'participant_ids').tolist()
    if len(roster) < 2 or (not engineering and len(roster) != population):
        raise ValueError('complete declared cohort population required')
    if not isinstance(manifest['roster_source'], str) or not manifest['roster_source'].strip():
        raise ValueError('roster_source provenance required')
    before, after = manifest['contrast']['before'], manifest['contrast']['after']
    if before == after or before not in conditions or after not in conditions:
        raise ValueError('unknown or identical condition contrast')
    tr = float(manifest['tr_seconds'])
    if not math.isfinite(tr) or tr <= 0:
        raise ValueError('explicit positive TR required')
    length = manifest['n_timepoints']
    rois = manifest['n_rois']
    if type(length) is not int or length < 3 or type(rois) is not int or rois < 2:
        raise ValueError('integer time/ROI dimensions required')
    if not engineering and (rois != 450 or (native_length is not None and length != native_length)):
        raise ValueError('source population dimensions cannot be reduced')
    if manifest['length_policy'] != 'require_equal_no_truncation':
        raise ValueError('only exact matched lengths admitted; Dataset-5 unequal stages remain a hold')
    if manifest['motion_policy'] != 'report_all_no_exclusion':
        raise ValueError('prospective policy reports motion; automatic exclusion is not allowed')
    if not isinstance(manifest['normalization_provenance'], str) or not manifest['normalization_provenance'].strip():
        raise ValueError('normalization_provenance required')
    null_count, null_seed = manifest['surrogate_count'], manifest['surrogate_seed']
    if type(null_count) is not int or null_count < 2 or type(null_seed) is not int or null_seed < 0:
        raise ValueError('at least two phase surrogates and a nonnegative integer seed required')
    records = manifest['recordings']
    expected = {(p, c) for p in roster for c in (before, after)}
    actual = [(r['participant_id'], r['condition']) for r in records]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError('exactly both states for every declared participant required')
    rows, scores, roi_identity = [], {}, None
    for record_index, record in enumerate(sorted(records, key=lambda r: (str(r['participant_id']), r['condition']))):
        if record['tr_seconds'] != tr:
            raise ValueError('TR differs across cohort/state')
        a, b, ids, fd = _load_pair(record, root, length, rois)
        if roi_identity is not None and not np.array_equal(ids, roi_identity):
            raise ValueError('ROI identities/order differs across states or participants')
        roi_identity = ids
        score = paired_timeseries(a, b)
        score['mean_framewise_displacement_mm'] = fd
        nulls = []
        for j in range(null_count):
            sa, sb = phase_randomized_pair(a, b, np.random.SeedSequence([null_seed, record_index, j]))
            nulls.append(paired_timeseries(sa, sb)['isd'])
        score['surrogate_mean_isd'] = float(np.mean(nulls))
        score['surrogate_sd_isd'] = float(np.std(nulls, ddof=1))
        score['isd_minus_surrogate_mean'] = score['isd'] - score['surrogate_mean_isd']
        scores[(record['participant_id'], record['condition'])] = score
        rows.append({'participant_id': record['participant_id'], 'condition': record['condition'],
                     'input_sha256': record['sha256'], **score})
    endpoints = ('integration', 'segregation', 'isd', 'mean_correlation_no_gsr',
                 'mean_absolute_correlation_no_gsr', 'mean_correlation_gsr',
                 'global_signal_sd_no_gsr', 'mean_roi_sd_no_gsr', 'mean_framewise_displacement_mm',
                 'surrogate_mean_isd', 'isd_minus_surrogate_mean')
    effects = {key: paired_effect([scores[(p, before)][key] for p in roster],
                                  [scores[(p, after)][key] for p in roster]) for key in endpoints}
    return {'task_id': TASK_ID, 'status': 'engineering_control_only' if engineering else 'unqualified_source_metrics',
            'scientifically_qualified': False, 'recipe': 'source_as_written_isd_paired_v1',
            'cohort': cohort, 'contrast': manifest['contrast'], 'participant_order': roster,
            'primary_endpoint': 'isd', 'contrasts': effects, 'recordings': rows,
            'scientific_holds': HOLDS,
            'source_revision': 'fba91ec089cb5d582c183bbdc6599c706a38f437',
            'prospective_bct_revision': 'b7f59ebcf0b4f4979ab3914e30c61eaf345b11d5',
            'input_provenance': {key: manifest[key] for key in ('roster_source', 'normalization_provenance',
                'tr_seconds', 'n_timepoints', 'n_rois', 'surrogate_count', 'surrogate_seed')},
            'prospective_policies': {
                'aggregation': 'equal participants; after minus before; no cross-cohort pooling',
                'uncertainty': 'Student-t interval on paired participant differences, not timepoints',
                'length': manifest['length_policy'], 'motion': manifest['motion_policy']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = evaluate_manifest(manifest, args.manifest.parent)
    report['manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
