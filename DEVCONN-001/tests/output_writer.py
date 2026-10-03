"""Five DEVCONN artifacts from source-bound primitives; no import-time I/O.

Adapted from the qualified PR198 writer. The caller supplies an authenticated
source reference and SHA-bound reporting kernel. This module does not load data,
accept numerical endpoint receipts as inputs, or import an editable public kernel.
Only accepted cleaned series (default: source reconstruction) drive one replay.
"""
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import stat

import numpy as np

FILES = ('signal_evidence.npz', 'connectivity_metrics.csv', 'age_effects.json',
         'run_metadata.json', 'findings.md')
IDS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
COLUMNS = ('subject_id', 'age', 'group', 'mean_fd', 'n_active_rois',
           'short_range', 'long_range', 'segregation',
           'short_range_status', 'long_range_status', 'segregation_status',
           'short_range_n_nominal_edges', 'short_range_n_used_edges',
           'long_range_n_nominal_edges', 'long_range_n_used_edges')
PIN_NAMES = ('source_manifest_sha256', 'method_sha256', 'output_schema_sha256', 'reporting_kernel_sha256')
CAPS = dict(zip(FILES, (256 * 1024**2, 1024**2, 1024**2, 32 * 1024**2, 1024**2)))
TOTAL_CAP = 512 * 1024**2
NPZ_EXPANDED_CAP = 512 * 1024**2


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def fresh_output(value, protected=()):
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and not any(x in ('.', '..') for x in raw.split('/')), 'absolute_output_without_traversal_required')
    output = Path(raw)
    for node in (*reversed(output.parents), output):
        if os.path.lexists(node):
            need(stat.S_ISDIR(node.lstat().st_mode), 'output_symlink_or_nondirectory')
    for item in (*protected, Path(__file__).absolute().parent):
        item = Path(item).absolute()
        need(output != item and output not in item.parents and item not in output.parents,
             'output_protected_overlap')
    if output.exists():
        need(not any(output.iterdir()), 'fresh_or_empty_output_required')
    else:
        need(output.parent.is_dir(), 'output_parent_required')
        output.mkdir()
    return output


def json_write(path, data):
    payload = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    need(len(payload) <= CAPS.get(path.name, 1024**2), 'json_artifact_cap')
    with path.open('xb') as stream:
        stream.write(payload)


def integer_axis(value, length, label):
    def has_bool(item):
        return isinstance(item, (bool, np.bool_)) or (
            isinstance(item, (list, tuple)) and any(has_bool(x) for x in item))
    need(not has_bool(value), label + '_boolean')
    array = np.asarray(value)
    need(array.shape == (length,) and array.dtype.kind in 'iuf'
         and np.isfinite(array).all(), label + '_type_shape')
    need(np.array_equal(np.sort(array), np.arange(length)), label + '_complete_axis')
    return array.astype(np.int64)


def primitive_inputs(reference, kernel, accepted_clean=None):
    """Normalize coherent frame rows; ROI order is bound to source coordinates."""
    need(reference.get('status') == 'complete', 'complete_reference_required')
    ids = reference['subject_ids']
    need(type(ids) is list and len(ids) == len(IDS)
         and all(type(sid) is str for sid in ids) and set(ids) == set(IDS), 'fixed_cohort_required')
    ids = list(IDS)
    people, covariates = reference['persons'], reference['covariates']
    need(type(people) is dict and type(covariates) is dict
         and set(people) == set(covariates) == set(ids), 'participant_membership')
    rois = reference['roi_ids']
    need(type(rois) is list and len(rois) == 264 and len(set(rois)) == 264
         and all(type(rid) is str and rid and not any(ord(c) < 32 or ord(c) == 127 for c in rid)
                 for rid in rois), 'literal_roi_axis')
    coordinates = kernel.real_array(reference['coordinates'], 2)
    need(coordinates.shape == (264, 3), 'coordinate_shape')
    if accepted_clean is not None:
        need(type(accepted_clean) is dict and set(accepted_clean) == set(ids), 'accepted_participant_membership')
    raw, canonical, accepted, active, frame_axes = {}, {}, {}, {}, {}
    for sid in ids:
        person = people[sid]
        y = kernel.real_array(person['raw_roi'], 2)
        source = kernel.real_array(person['cleaned_roi'], 2)
        need(y.shape == source.shape and y.shape[0] >= 2 and y.shape[1] == 264, 'primitive_shape')
        frames = integer_axis(person['frame_indices'], y.shape[0], 'frame_indices')
        order = np.argsort(frames)
        mask = np.asarray(person['canonical_active'])
        need(mask.dtype.kind == 'b' and mask.shape == (264,), 'active_type_shape')
        value = source if accepted_clean is None else kernel.real_array(accepted_clean[sid], 2)
        need(value.shape == source.shape, 'accepted_clean_shape')
        value, source, mask = kernel.validate_clean_series(value[order], source[order], mask)
        raw[sid], canonical[sid], accepted[sid], active[sid] = y[order], source, value, mask
        frame_axes[sid] = frames[order]
    return ids, rois, coordinates, raw, canonical, accepted, active, frame_axes


def bootstrap_arrays(result, covariates, kernel):
    """Child order and ordered RNG slots are not subject-reorderable axes."""
    boot = result['bootstrap']
    children = sorted(sid for sid in IDS if covariates[sid]['group'] == 'child')
    need(len(children) == 122 and boot['subject_ids'] == children, 'bootstrap_child_order')
    need(type(boot['seed']) is int and boot['seed'] == 11
         and type(boot['n_draws']) is int and boot['n_draws'] == 1000, 'bootstrap_fixed_rng')
    need(boot['metric_ids'] == list(kernel.METRICS) and boot['association_ids'] == list(kernel.ASSOCIATIONS),
         'bootstrap_metric_association_axis')
    indices = np.asarray(boot['indices'])
    need(indices.dtype.kind in 'iu' and indices.shape == (1000, 122)
         and np.array_equal(indices, kernel.bootstrap_indices(122)), 'bootstrap_rng_slots')
    values = kernel.real_array(boot['r'], 3)
    defined = np.asarray(boot['defined'])
    statuses = np.asarray(boot['status'])
    need(values.shape == defined.shape == statuses.shape == (1000, 3, 2)
         and defined.dtype.kind == 'b' and statuses.dtype.kind in 'US'
         and np.all(np.abs(values) <= 1.) and np.all(values[~defined] == 0.)
         and np.all(statuses != ''), 'bootstrap_receipt_shape_or_domain')
    rank, df = np.asarray(boot['motion_nuisance_rank']), np.asarray(boot['motion_df'])
    need(rank.dtype.kind in 'iu' and df.dtype.kind in 'iu' and rank.shape == df.shape == (1000,)
         and np.all((rank == 1) | (rank == 2)) and np.array_equal(df, 122 - rank - 1),
         'bootstrap_rank_df')
    return dict(bootstrap_child_ids=np.asarray(children),
        bootstrap_draw_ids=np.arange(1000, dtype=np.int64),
        bootstrap_metric_ids=np.asarray(boot['metric_ids']),
        bootstrap_association_ids=np.asarray(boot['association_ids']),
        bootstrap_indices=indices.astype(np.int64), bootstrap_r=values,
        bootstrap_defined=defined.copy(), bootstrap_status=statuses.copy(),
        bootstrap_motion_nuisance_rank=rank.astype(np.int64), bootstrap_motion_df=df.astype(np.int64))


def software_versions():
    out = {key: importlib.metadata.version(distribution) for key, distribution in
           [('numpy', 'numpy'), ('scipy', 'scipy'), ('nibabel', 'nibabel'),
            ('nilearn', 'nilearn'), ('scikit_learn', 'scikit-learn'), ('pandas', 'pandas')]}
    return dict(python=platform.python_version(), **out)


def findings(effects):
    lines = ['# Distance-dependent movie connectivity', '',
        'All 155 released participants are retained: 122 children and 33 adults. '
        'Short- and long-distance quantities are signed mean Fisher-z values, not mean correlations. '
        'Distance bins are fixed from all original coordinates. Each person uses the eligible edges '
        'whose two source-defined ROI signals are active; varying coverage limits comparability. '
        'Segregation is short minus long. CSV rounding is never fed back into inference.', '']
    for metric in ('short_range', 'long_range', 'segregation'):
        value = effects['children_age_spearman'][metric]
        lines.append(f"{metric}: child r={value['r']}, p={value['p']} ({value['status']}); "
            f"FD-adjusted r={value['motion_adjusted_rank_r']}, p={value['motion_adjusted_rank_p']} "
            f"({value['motion_adjusted_rank_status']}); raw bootstrap "
            f"{value['raw_bootstrap']['n_defined']}/1000 defined, CI={value['raw_bootstrap']['ci95']}; "
            f"adjusted bootstrap {value['motion_adjusted_bootstrap']['n_defined']}/1000 defined, "
            f"CI={value['motion_adjusted_bootstrap']['ci95']}.")
        means = effects['group_means'][metric]
        lines.append(f"Equal-person child mean={means['child']['mean']}; adult mean={means['adult']['mean']}.")
    for label, record in (
        ('Full cohort', effects['segregation_child_vs_adult']),
        ('FD<0.2 restriction', effects['motion_control']['segregation_low_motion_restriction'])):
        lines.append(f"{label}: child-adult segregation difference={record['difference']}; "
                     f"Welch t={record['t']}, df={record['df']}, p={record['p']} ({record['status']}).")
    lines.extend(['', 'This is a Fair/Power-motivated public movie-data methods application, '
        'not replication of the named resting-state sample, ROI set or developmental finding. '
        'Cross-sectional age associations do not establish within-person development. FD adjustment '
        'and restriction are not causal motion removal or motion matching. Bootstrap intervals are '
        'conditional on the fixed atlas and preprocessing; all 1000 slots are retained, with a null '
        'interval if any required draw is undefined. No effect direction, significance, attenuation, '
        'prose keyword or model difficulty was required.'])
    return '\n'.join(lines) + '\n'


def write_artifacts(reference, output, kernel, *, protected=(), accepted_clean=None):
    """Caller-owned canonical reference + optional coherent accepted signal map.

    Optional arrays use each person's current source frame/ROI axis and must pass
    the same source-close support/fidelity guards. No result receipt is an input.
    Output is fresh/empty, exclusively created, never cleaned up or overwritten.
    """
    directory = fresh_output(output, protected)
    try:
        ids, rois, coordinates, raw, canonical, accepted, active, frames = primitive_inputs(
            reference, kernel, accepted_clean)
        pins = reference['pins']
        need(all(type(pins.get(k)) is str and re.fullmatch('[0-9a-f]{64}', pins[k])
                 for k in PIN_NAMES), 'authority_pins')
        warnings = reference.get('warnings', [])
        need(type(warnings) is list and all(type(x) is str for x in warnings), 'warning_strings')
        result = kernel.analyze(accepted, canonical, active, reference['covariates'],
                                ids, coordinates, rois)
        need([row['subject_id'] for row in result['participant_rows']] == ids, 'result_row_membership')
        bootstrap = bootstrap_arrays(result, reference['covariates'], kernel)
        lengths = [len(frames[sid]) for sid in ids]
        arrays = dict(subject_ids=np.asarray(ids), roi_ids=np.asarray(rois),
            frame_subject_ids=np.concatenate([np.repeat(sid, n) for sid, n in zip(ids, lengths)]),
            frame_indices=np.concatenate([frames[sid] for sid in ids]),
            raw_roi=np.concatenate([raw[sid] for sid in ids]),
            cleaned_roi=np.concatenate([accepted[sid] for sid in ids]),
            canonical_active=np.stack([active[sid] for sid in ids]), **bootstrap)
        need(sum(value.nbytes for value in arrays.values()) <= NPZ_EXPANDED_CAP,
             'expanded_array_cap')
        with (directory / FILES[0]).open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        with (directory / FILES[1]).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(result['participant_rows'])
        shared = {key: pins[key] for key in PIN_NAMES[:3]}
        effects = dict(result['age_effects'], schema_version='devconn-results-v2',
                       task_id='DEVCONN-001', status='complete', **shared)
        json_write(directory / FILES[2], effects)
        metadata = dict(schema_version='devconn-metadata-v2', task_id='DEVCONN-001',
            dataset_id='ds000228', status='complete', **shared,
            reporting_kernel_sha256=pins['reporting_kernel_sha256'],
            analysis_scope='Cross-sectional movie distance-bin connectivity, child age and FD sensitivity',
            cohort=reference['cohort'], roi_definitions=reference['roi_definitions'],
            source_files=reference['source_files'], source_observed=reference['source_observed'],
            analysis_observed=reference['analysis_observed'], software_versions=software_versions(),
            warnings=warnings)
        json_write(directory / FILES[3], metadata)
        with (directory / FILES[4]).open('x', encoding='utf-8') as stream:
            stream.write(findings(effects))
        need(not os.path.lexists(directory / 'failure_report.json'), 'authoritative_failure_marker')
        entries = list(directory.iterdir())
        need({p.name for p in entries} == set(FILES)
             and all(stat.S_ISREG(p.lstat().st_mode) for p in entries), 'late_output_entry')
        sizes = {p.name: p.stat().st_size for p in entries}
        need(all(0 < size <= CAPS[name] for name, size in sizes.items())
             and sum(sizes.values()) <= TOTAL_CAP, 'artifact_size_cap')
        return effects
    except BaseException as exc:
        marker = directory / 'failure_report.json'
        if not os.path.lexists(marker):
            json_write(marker, dict(status='failed_precondition', error_type=type(exc).__name__,
                                    reason='artifact_serialization_failed'))
        raise
