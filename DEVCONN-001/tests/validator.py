"""DEVCONN source-bound artifacts: immutable IO, one accepted-clean replay.

Adapted from qualified PR198 validator 1a5f9627ff890735c767e33cb0c5e6fcd5b88244fb33007a44c17204240179f4.
No source reconstruction or oracle import. Trusted setup binds all private code
and source/document pins; undefined endpoints remain valid complete outputs.
"""
import hashlib
import math
import re
import types

import numpy as np

from io_contract import finite_tree, need, number

SOURCE_SHA = '0fb419ee0dbea59376f5b0dc1e91d26502e8203d6e7b02334b979e6a1d9f66e3'
METHOD_SHA = 'e8ba3df50c7cc4bf8b83e2db559c0f1e515f10bf4c45498da84076306e883f6e'
SCHEMA_SHA = '3463740e8c55a9f549590fee013aa29d30480eb63e9984acafd2a41c1a1531b4'
KERNEL_SHA = '2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638'
SUBJECT_IDS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
N_CHILDREN, N_ADULTS, N_ROIS, N_DRAWS = 122, 33, 264, 1000
METRICS = ('short_range', 'long_range', 'segregation')
ASSOCIATIONS = ('raw', 'motion_adjusted')
FILES = ('signal_evidence.npz', 'connectivity_metrics.csv', 'age_effects.json', 'run_metadata.json', 'findings.md')
FISHER_LIMIT = math.atanh(.999)
_KERNEL = None
_BOUND_SHA = None


def bind_reporting_kernel(raw):
    global _KERNEL, _BOUND_SHA
    need(type(KERNEL_SHA) is str and re.fullmatch('[0-9a-f]{64}', KERNEL_SHA), 'unfrozen_kernel')
    need(type(raw) is bytes and len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == KERNEL_SHA, 'private_kernel_identity')
    module = types.ModuleType('_devconn_artifact_reporting')
    exec(compile(raw, '<SHA-bound DEVCONN reporting kernel>', 'exec'), module.__dict__)
    _KERNEL, _BOUND_SHA = module, KERNEL_SHA


def pins():
    result = dict(source_manifest_sha256=SOURCE_SHA, method_sha256=METHOD_SHA,
                  output_schema_sha256=SCHEMA_SHA, reporting_kernel_sha256=KERNEL_SHA)
    need(all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) for value in result.values()), 'unfrozen_private_pins')
    return result


def fields(obj, names):
    need(type(obj) is dict and set(names) <= set(obj), 'required_object_fields')
    return {name: obj[name] for name in names}


def scalar_equal(actual, expected, atol=0., rtol=0.):
    if expected is None: need(actual is None, 'required_null')
    elif type(expected) is bool: need(type(actual) is bool and actual == expected, 'exact_boolean')
    elif type(expected) is int: need(type(actual) is int and actual == expected, 'exact_integer')
    elif type(expected) is float:
        value = number(actual, json_mode=True)
        need(math.isfinite(expected) and abs(value - expected) <= atol + rtol * abs(expected), 'numeric_tolerance')
    elif type(expected) is str: need(type(actual) is str and actual == expected, 'exact_string')
    elif type(expected) is list:
        need(type(actual) is list and len(actual) == len(expected), 'ordered_list')
        for a, b in zip(actual, expected): scalar_equal(a, b, atol, rtol)
    elif type(expected) is dict:
        fields(actual, expected)
        for key, value in expected.items(): scalar_equal(actual[key], value, atol, rtol)
    else: raise ValueError('invalid_canonical_type')


def keyed(rows, names):
    need(type(rows) is list, 'keyed_records_list'); result = {}
    for row in rows:
        values = fields(row, names); key = []
        for name, value in values.items():
            if name == 'frame_index': need(type(value) is int and value >= 0, 'record_integer_key')
            else: need(type(value) is str and value, 'record_string_key')
            key.append(value)
        key = tuple(key); need(key not in result, 'duplicate_record_key'); result[key] = row
    return result


def paired_records(actual, expected, keys):
    a, b = keyed(actual, keys), keyed(expected, keys)
    need(set(a) == set(b), 'record_membership')
    return ((a[key], b[key]) for key in b)


def compare_records(actual, expected, keys, required, atol=0., rtol=0.):
    for a, b in paired_records(actual, expected, keys):
        scalar_equal(fields(a, required), fields(b, required), atol, rtol)


def integer_set(actual, expected):
    need(type(actual) is list and all(type(x) is int and x >= 0 for x in actual)
         and len(actual) == len(set(actual)) and set(actual) == set(expected), 'integer_set')


def text_array(value, shape):
    # Shape before expansion: S0/U0 can otherwise hold arbitrarily many logical elements.
    need(isinstance(value, np.ndarray) and value.shape == shape and value.dtype.kind in 'US', 'string_array')
    if value.dtype.kind == 'S':
        try: result = np.char.decode(value, 'utf-8')
        except UnicodeDecodeError: raise ValueError('array_utf8') from None
    else: result = value
    need(all(type(x) is str and x and '\0' not in x for x in result.ravel().tolist()), 'literal_string')
    return result


def axis_order(value, expected):
    values = text_array(value, (len(expected),)).tolist()
    need(len(set(values)) == len(values) and set(values) == set(expected), 'axis_membership')
    return [values.index(key) for key in expected]


def numeric_array(value, shape):
    need(isinstance(value, np.ndarray) and value.dtype.kind in 'iuf' and value.shape == shape, 'real_array_shape_type')
    result = np.ascontiguousarray(value, dtype=np.float64)
    need(np.isfinite(result).all(), 'finite_array'); return result


def integer_array(value, shape, minimum, maximum):
    array = numeric_array(value, shape)
    need(np.all(array == np.floor(array)) and np.all((array >= minimum) & (array <= maximum)), 'integral_array_domain')
    return array.astype(np.int64)


def bool_array(value, shape):
    need(isinstance(value, np.ndarray) and value.dtype.kind == 'b' and value.shape == shape, 'boolean_array')
    return value


def close_array(actual, expected, atol, rtol):
    expected = np.asarray(expected, dtype=np.float64)
    need(actual.shape == expected.shape and np.isfinite(expected).all(), 'canonical_shape_finite')
    with np.errstate(over='ignore', invalid='ignore'):
        same = np.abs(actual - expected) <= atol + rtol * np.abs(expected)
    need(np.all(same), 'numeric_array_tolerance')


def canonical_primitives(arrays, canonical):
    required = ('subject_ids', 'roi_ids', 'frame_subject_ids', 'frame_indices', 'raw_roi',
                'cleaned_roi', 'canonical_active')
    fields(arrays, required)
    for value in arrays.values():
        need(isinstance(value, np.ndarray) and value.ndim <= 32 and value.dtype.kind in 'biufUS'
             and not value.dtype.hasobject and value.dtype.fields is None, 'array_storage_type')
        if value.dtype.kind == 'f': need(np.isfinite(value).all(), 'nonfinite_array')
    so = axis_order(arrays['subject_ids'], SUBJECT_IDS)
    ro = axis_order(arrays['roi_ids'], canonical['roi_ids'])
    keys = [(sid, i) for sid in SUBJECT_IDS for i in range(len(canonical['persons'][sid]['frame_indices']))]
    n = len(keys)
    subjects = text_array(arrays['frame_subject_ids'], (n,)).tolist()
    frames = integer_array(arrays['frame_indices'], (n,), 0, n - 1)
    observed = list(zip(subjects, map(int, frames)))
    need(len(set(observed)) == n and set(observed) == set(keys), 'frame_membership')
    positions = {key: i for i, key in enumerate(observed)}; order = [positions[key] for key in keys]
    raw = numeric_array(arrays['raw_roi'], (n, N_ROIS))[order][:, ro]
    clean = numeric_array(arrays['cleaned_roi'], (n, N_ROIS))[order][:, ro]
    mask = bool_array(arrays['canonical_active'], (len(SUBJECT_IDS), N_ROIS))[so][:, ro]
    accepted, reference, activity = {}, {}, {}; cursor = 0
    for i, sid in enumerate(SUBJECT_IDS):
        person = canonical['persons'][sid]; length = len(person['frame_indices'])
        sl = slice(cursor, cursor + length); cursor += length
        need(np.array_equal(person['frame_indices'], np.arange(length)), 'canonical_frame_axis')
        close_array(raw[sl], person['raw_roi'], 1e-5, 1e-6)
        need(np.array_equal(mask[i], person['canonical_active']), 'canonical_activity')
        accepted[sid], reference[sid], activity[sid] = clean[sl], person['cleaned_roi'], person['canonical_active']
    return accepted, reference, activity


def validate_bootstrap(arrays, replay):
    expected = replay['bootstrap']; children = expected['subject_ids']
    need(text_array(arrays.get('bootstrap_child_ids'), (N_CHILDREN,)).tolist() == children,
         'fixed_bootstrap_child_order')
    draw_ids = integer_array(arrays.get('bootstrap_draw_ids'), (N_DRAWS,), 0, N_DRAWS - 1)
    need(len(set(map(int, draw_ids))) == N_DRAWS, 'draw_membership')
    order = np.argsort(draw_ids)
    mo = axis_order(arrays.get('bootstrap_metric_ids'), METRICS)
    ao = axis_order(arrays.get('bootstrap_association_ids'), ASSOCIATIONS)
    indices = integer_array(arrays.get('bootstrap_indices'), (N_DRAWS, N_CHILDREN), 0, N_CHILDREN - 1)[order]
    need(np.array_equal(indices, expected['indices']), 'bootstrap_rng_slots')
    shape = (N_DRAWS, len(METRICS), len(ASSOCIATIONS))
    own = numeric_array(arrays.get('bootstrap_r'), shape)[order][:, mo][:, :, ao]
    need(np.all(np.abs(own) <= 1.), 'bootstrap_correlation_domain')
    defined = bool_array(arrays.get('bootstrap_defined'), shape)[order][:, mo][:, :, ao]
    statuses = text_array(arrays.get('bootstrap_status'), shape)[order][:, mo][:, :, ao]
    need(np.array_equal(defined, expected['defined']) and np.array_equal(statuses, expected['status']), 'bootstrap_support')
    need(np.all(own[~defined] == 0.), 'bootstrap_null_sentinel')
    close_array(own[defined], expected['r'][defined], 1e-6, 1e-6)
    for suffix, key in (('motion_nuisance_rank', 'motion_nuisance_rank'), ('motion_df', 'motion_df')):
        values = integer_array(arrays.get('bootstrap_' + suffix), (N_DRAWS,), 0, N_CHILDREN)[order]
        need(np.array_equal(values, expected[key]), 'bootstrap_rank_or_df')


HEADER_FIELDS = ('shape', 'selected_affine', 'storage_dtype', 'spatial_units', 'temporal_units',
                 'zooms', 'raw_toffset', 'raw_scl_slope', 'raw_scl_inter', 'effective_slope', 'effective_intercept')


def compare_header(actual, expected):
    a, b = fields(actual, HEADER_FIELDS), fields(expected, HEADER_FIELDS)
    need(type(a['storage_dtype']) is str, 'header_dtype_string')
    try: own, ref = np.dtype(a['storage_dtype']), np.dtype(b['storage_dtype'])
    except (TypeError, ValueError): raise ValueError('header_dtype') from None
    need(own.kind in 'iuf' and own.fields is None and not own.hasobject and own == ref, 'header_dtype')
    a, b = dict(a), dict(b); del a['storage_dtype']; del b['storage_dtype']
    scalar_equal(a, b, 1e-10, 1e-9)


def validate_metadata(actual, canonical):
    scalar_equal(actual, dict(schema_version='devconn-metadata-v2', task_id='DEVCONN-001',
                            dataset_id='ds000228', status='complete', **pins()))
    need(type(actual.get('analysis_scope')) is str and actual['analysis_scope'].strip(), 'analysis_scope')
    need(type(actual.get('warnings')) is list and all(type(x) is str for x in actual['warnings']), 'warnings')
    versions = actual.get('software_versions')
    need(type(versions) is dict and versions and all(type(k) is str and k and type(v) is str and v.strip()
         for k, v in versions.items()), 'software_strings')
    compare_records(actual.get('source_files'), canonical['source_files'], ('path',),
                    ('path', 'role', 'subject_id', 'size_bytes', 'sha256'))
    for a, b in paired_records(actual.get('cohort'), canonical['cohort'], ('subject_id',)):
        names = ('subject_id', 'age', 'group', 'mean_fd', 'mean_fd_observed_count')
        scalar_equal(fields(a, names), fields(b, names), 1e-10, 1e-9)
        integer_set(a.get('mean_fd_missing_frame_indices'), b['mean_fd_missing_frame_indices'])
    for a, b in paired_records(actual.get('roi_definitions'), canonical['roi_definitions'], ('roi_id',)):
        scalar_equal(a.get('roi_id'), b['roi_id'])
        scalar_equal(a.get('center_mm'), list(map(float, b['center_mm'])), 1e-10, 1e-9)
        scalar_equal(a.get('radius_mm'), float(b['radius_mm']), 1e-10, 1e-9)
    actual_obs, ref_obs = actual.get('source_observed'), canonical['source_observed']
    fields(actual_obs, ('participants_column_names', 'coordinates', 'persons', 'frame_alignment'))
    scalar_equal(actual_obs['participants_column_names'], ref_obs['participants_column_names'])
    scalar_equal(fields(actual_obs['coordinates'], ('path', 'sha256', 'column_names')),
                 fields(ref_obs['coordinates'], ('path', 'sha256', 'column_names')))
    need(type(actual_obs['frame_alignment']) is str and actual_obs['frame_alignment'].strip(), 'frame_alignment')
    person_fields = ('subject_id', 'bold_path', 'confounds_path', 'frame_count', 'confound_column_names',
        'selected_confound_columns', 'excluded_confound_columns', 'mean_fd_sum', 'mean_fd_observed_count',
        'mean_fd_zero_filled_sum', 'mean_fd_denominator')
    for a, b in paired_records(actual_obs['persons'], ref_obs['persons'], ('subject_id',)):
        scalar_equal(fields(a, person_fields), fields(b, person_fields), 1e-10, 1e-9)
        integer_set(a.get('mean_fd_missing_frame_indices'), b['mean_fd_missing_frame_indices'])
        compare_header(a.get('bold_header'), b['bold_header'])
        for key in ('missing_selected_entries', 'mean_fd_missing_entries'):
            compare_records(a.get(key), b[key], ('frame_index', 'column_name'),
                ('frame_index', 'column_name', 'original_token', 'applied_value'))
        compare_records(a.get('roi_supports'), b['roi_supports'], ('roi_id',), ('roi_id', 'n_voxels', 'support_sha256'))
    actual_obs, ref_obs = actual.get('analysis_observed'), canonical['analysis_observed']
    fields(actual_obs, ('persons', 'distance_bins'))
    scalar_equal(fields(actual_obs['distance_bins'], ('q1_mm', 'q2_mm', 'n_pairs', 'n_short_edges', 'n_long_edges', 'membership_sha256')),
                 fields(ref_obs['distance_bins'], ('q1_mm', 'q2_mm', 'n_pairs', 'n_short_edges', 'n_long_edges', 'membership_sha256')), 1e-10, 1e-9)
    for a, b in paired_records(actual_obs['persons'], ref_obs['persons'], ('subject_id',)):
        scalar_equal(fields(a, ('subject_id', 'cleaning_rank', 'n_active_rois')), fields(b, ('subject_id', 'cleaning_rank', 'n_active_rois')))
        compare_records(a.get('roi_activity'), b['roi_activity'], ('roi_id',),
            ('roi_id', 'raw_centered_l2', 'residual_centered_l2', 'activity_threshold', 'active'), 1e-10, 1e-6)


def fisher_domain(value, multiple=1.):
    bound = multiple * FISHER_LIMIT
    need(abs(value) <= bound + 1e-6 + 1e-6 * bound, 'fisher_z_domain')


def csv_integer(value):
    # Scientific notation is valid CSV numeric serialization, but counts are integral.
    x = number(value); need(x.is_integer() and x >= 0, 'csv_integer'); return int(x)


def validate_table(rows, replay):
    for actual, expected in paired_records(rows, replay['participant_rows'], ('subject_id',)):
        scalar_equal(actual.get('group'), expected['group'])
        for key in ('age', 'mean_fd'):
            value = number(actual.get(key)); scalar_equal(value, float(expected[key]), 1e-10, 1e-9)
            if key == 'mean_fd': need(value >= 0, 'fd_domain')
        for key in ('n_active_rois', 'short_range_n_nominal_edges', 'short_range_n_used_edges',
                    'long_range_n_nominal_edges', 'long_range_n_used_edges'):
            scalar_equal(csv_integer(actual.get(key)), expected[key])
        for metric in METRICS:
            scalar_equal(actual.get(metric + '_status'), expected[metric + '_status'])
            if expected[metric] is None:
                need(type(actual.get(metric)) is str and actual[metric] == '', 'csv_null')
            else:
                value = number(actual.get(metric)); fisher_domain(value, 2. if metric == 'segregation' else 1.)
                scalar_equal(value, float(expected[metric]), 1e-6, 1e-6)


def validate_results(actual, replay):
    fixed = dict(schema_version='devconn-results-v2', task_id='DEVCONN-001', status='complete',
                 **{k: v for k, v in pins().items() if k != 'reporting_kernel_sha256'})
    scalar_equal(actual, fixed)
    expected = replay['age_effects']
    for key in ('children_age_spearman', 'group_means'):
        need(type(actual.get(key)) is dict and set(actual[key]) == set(METRICS), 'metric_membership')
    for metric in METRICS:
        item = actual['children_age_spearman'][metric]
        fields(item, expected['children_age_spearman'][metric])
        for name in ('r', 'motion_adjusted_rank_r'):
            if item[name] is not None: need(-1 <= number(item[name], json_mode=True) <= 1, 'correlation_domain')
        for name in ('p', 'motion_adjusted_rank_p'):
            if item[name] is not None: need(0 <= number(item[name], json_mode=True) <= 1, 'p_domain')
        for name in ('raw_bootstrap', 'motion_adjusted_bootstrap'):
            ci = fields(item[name], ('ci95', 'n_expected', 'n_defined', 'status'))['ci95']
            if ci is not None:
                need(type(ci) is list and len(ci) == 2, 'ci_shape')
                lo, hi = [number(x, json_mode=True) for x in ci]
                need(-1 <= lo <= hi <= 1, 'ci_domain')
        groups = actual['group_means'][metric]
        need(type(groups) is dict and set(groups) == {'child', 'adult'}, 'group_mean_membership')
        for group in groups.values():
            value = fields(group, ('mean', 'n_expected', 'n_defined', 'status'))['mean']
            if value is not None: fisher_domain(number(value, json_mode=True), 2. if metric == 'segregation' else 1.)
    fields(actual.get('motion_control'), ('segregation_low_motion_restriction',))
    wanted = dict(expected)
    wanted['motion_control'] = dict(expected['motion_control'])
    for key, restricted in (('segregation_child_vs_adult', False), ('segregation_low_motion_restriction', True)):
        record = actual['motion_control'][key] if restricted else actual.get(key)
        ref = expected['motion_control'][key] if restricted else expected[key]
        fields(record, ref)
        for group in ('child', 'adult'):
            value = fields(record[group], ('mean', 'n_expected', 'n_defined', 'status'))['mean']
            if value is not None: fisher_domain(number(value, json_mode=True), 2.)
        if record['difference'] is not None: fisher_domain(number(record['difference'], json_mode=True), 4.)
        if record['p'] is not None: need(0 <= number(record['p'], json_mode=True) <= 1, 'welch_p_domain')
        if record['df'] is not None: need(number(record['df'], json_mode=True) > 0, 'welch_df_domain')
        if restricted:
            need(number(record['fd_thresh'], json_mode=True) == .2, 'fd_threshold')
            normalized = dict(ref)
            for axis in ('child_ids', 'adult_ids'):
                value = record[axis]
                need(type(value) is list and all(type(x) is str for x in value) and
                     len(value) == len(set(value)) and set(value) == set(ref[axis]), 'restriction_membership')
                normalized[axis] = value
            wanted['motion_control'][key] = normalized
    scalar_equal(actual, wanted, 1e-6, 1e-6)


def verify_artifacts(actual, canonical):
    """Pure complete source-bound validation. One own-clean kernel replay, no IO."""
    expected_pins = pins()
    need(_KERNEL is not None and _BOUND_SHA == KERNEL_SHA, 'kernel_not_bound')
    need(type(canonical) is dict and canonical.get('status') == 'complete', 'canonical_complete_required')
    scalar_equal(canonical.get('pins'), expected_pins)
    ids = canonical.get('roi_ids')
    need(type(ids) is list and len(ids) == N_ROIS and len(set(ids)) == N_ROIS and
         all(type(x) is str and x for x in ids), 'canonical_roi_identity')
    need(canonical.get('subject_ids') == list(SUBJECT_IDS) and set(canonical['persons']) == set(SUBJECT_IDS)
         and set(canonical['covariates']) == set(SUBJECT_IDS), 'canonical_subject_identity')
    fields(actual, FILES)
    for name in ('age_effects.json', 'run_metadata.json'): finite_tree(actual[name])
    need(type(actual['findings.md']) is str and actual['findings.md'].strip(), 'findings')
    accepted, reference, active = canonical_primitives(actual['signal_evidence.npz'], canonical)
    replay = _KERNEL.analyze(accepted, reference, active, canonical['covariates'], list(SUBJECT_IDS),
        canonical['coordinates'], ids, expected_children=N_CHILDREN, expected_adults=N_ADULTS, expected_rois=N_ROIS)
    validate_bootstrap(actual['signal_evidence.npz'], replay)
    validate_table(actual['connectivity_metrics.csv'], replay)
    validate_results(actual['age_effects.json'], replay)
    validate_metadata(actual['run_metadata.json'], canonical)
    return dict(status='ok', n_subjects=len(SUBJECT_IDS), n_children=N_CHILDREN, n_adults=N_ADULTS,
                n_bootstrap_draws=N_DRAWS)


def validate_output_directory(output, canonical):
    from io_contract import output_inventory, read_output
    before = output_inventory(output)
    result = verify_artifacts(read_output(output), canonical)
    need(before == output_inventory(output), 'output_changed_during_validation')
    return result
