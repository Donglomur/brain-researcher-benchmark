"""Manufactured primitives/receipts only; no reader, oracle, sources or bank.

The small fixture changes cohort/ROI sizes explicitly in this test module only.
It retains the real bound kernel and all 1000 bootstrap slots. Narrow receipt
tests use the cached genuine replay; full validation itself is never memoized.
"""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

HERE = Path(__file__).parent
for name in ('io_contract', 'validator'):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
V, IO = sys.modules['validator'], sys.modules['io_contract']


def header(n):
    return dict(shape=[3, 4, 5, n], selected_affine=np.eye(4).tolist(), storage_dtype='<f4',
        spatial_units='unknown', temporal_units='unknown', zooms=[4., 4., 4., 1.], raw_toffset=0.,
        raw_scl_slope='NaN', raw_scl_inter='NaN', effective_slope=1., effective_intercept=0.)


def make_reference(ids):
    rois = ['1', '02', '3', '04', '5', '6']
    coordinates = np.column_stack(([0., 1., 3., 7., 15., 31.], np.zeros(6), np.zeros(6)))
    ref = dict(status='complete', subject_ids=ids, roi_ids=rois, coordinates=coordinates,
        pins=V.pins(), persons={}, covariates={}, cohort=[], source_files=[],
        roi_definitions=[dict(roi_id=r, center_mm=list(map(int, xyz)), radius_mm=5)
                         for r, xyz in zip(rois, coordinates)],
        source_observed=dict(participants_column_names=['participant_id', 'Age', 'Child_Adult'],
            coordinates=dict(path='atlas/fabricated.csv', sha256='4' * 64, column_names=['ROI', 'X', 'Y', 'Z']),
            persons=[], frame_alignment='Original rows, no measured stimulus alignment'),
        analysis_observed=dict(persons=[], distance_bins=dict(q1_mm=4., q2_mm=15., n_pairs=15,
            n_short_edges=5, n_long_edges=5, membership_sha256='7' * 64)))
    rng = np.random.default_rng(19344)
    for i, sid in enumerate(ids):
        n = 36 + i % 3
        clean = rng.normal(size=(n, 6)) + rng.normal(size=(n, 1)) * (.1 + i / 8)
        clean -= clean.mean(axis=0)
        raw = rng.normal(size=(n, 6))
        ref['persons'][sid] = dict(raw_roi=raw, cleaned_roi=clean,
            canonical_active=np.ones(6, bool), frame_indices=np.arange(n))
        cov = dict(age=float(5 + i * 3 % 11), group='child' if i < 6 else 'adult',
                   mean_fd=[.19, .2, .21, .01, .15, .24, .1, .2, .05][i])
        ref['covariates'][sid] = cov
        ref['cohort'].append(dict(subject_id=sid, **cov, mean_fd_observed_count=n - 2,
                                   mean_fd_missing_frame_indices=[0, 2]))
        for role in ('bold', 'confounds'):
            ref['source_files'].append(dict(path=sid + '.' + role, role=role, subject_id=sid,
                                           size_bytes=100, sha256='5' * 64))
        missing = [dict(frame_index=j, column_name='framewise_displacement',
                        original_token='n/a' if j == 0 else '', applied_value=0.) for j in (0, 2)]
        ref['source_observed']['persons'].append(dict(subject_id=sid, bold_path=sid + '.bold',
            confounds_path=sid + '.confounds', bold_header=header(n), frame_count=n,
            confound_column_names=['motion', 'framewise_displacement', 'unused'],
            selected_confound_columns=['motion'], excluded_confound_columns=['framewise_displacement', 'unused'],
            missing_selected_entries=[], mean_fd_sum=float(cov['mean_fd'] * n),
            mean_fd_observed_count=n - 2, mean_fd_missing_entries=missing,
            mean_fd_missing_frame_indices=[0, 2], mean_fd_zero_filled_sum=float(cov['mean_fd'] * n),
            mean_fd_denominator=n, roi_supports=[dict(roi_id=r, n_voxels=2, support_sha256='6' * 64) for r in rois]))
        ref['analysis_observed']['persons'].append(dict(subject_id=sid, cleaning_rank=3, n_active_rois=6,
            roi_activity=[dict(roi_id=r, raw_centered_l2=5., residual_centered_l2=2.,
                               activity_threshold=5e-12, active=True) for r in rois]))
    return ref


def replay(ref, arrays):
    accepted, source, active = V.canonical_primitives(arrays, ref)
    return V._KERNEL.analyze(accepted, source, active, ref['covariates'], ref['subject_ids'],
        ref['coordinates'], ref['roi_ids'], expected_children=6, expected_adults=3, expected_rois=6)


def refresh(actual, ref):
    result = replay(ref, actual['signal_evidence.npz']); b = result['bootstrap']
    actual['signal_evidence.npz'].update(bootstrap_child_ids=np.asarray(b['subject_ids']),
        bootstrap_draw_ids=np.arange(1000), bootstrap_metric_ids=np.asarray(b['metric_ids']),
        bootstrap_association_ids=np.asarray(b['association_ids']), bootstrap_indices=b['indices'].copy(),
        bootstrap_r=b['r'].copy(), bootstrap_defined=b['defined'].copy(), bootstrap_status=b['status'].copy(),
        bootstrap_motion_nuisance_rank=b['motion_nuisance_rank'].copy(), bootstrap_motion_df=b['motion_df'].copy())
    actual['connectivity_metrics.csv'] = [{k: '' if v is None else str(v) for k, v in row.items()}
                                         for row in result['participant_rows']]
    actual['age_effects.json'] = dict(schema_version='devconn-results-v2', task_id='DEVCONN-001', status='complete',
        **{k: v for k, v in ref['pins'].items() if k != 'reporting_kernel_sha256'}, **copy.deepcopy(result['age_effects']))
    return result


def make_output(ref):
    ids, people = ref['subject_ids'], ref['persons']
    arrays = dict(subject_ids=np.asarray(ids), roi_ids=np.asarray(ref['roi_ids']),
        frame_subject_ids=np.concatenate([np.repeat(sid, len(people[sid]['frame_indices'])) for sid in ids]),
        frame_indices=np.concatenate([people[sid]['frame_indices'] for sid in ids]),
        raw_roi=np.concatenate([people[sid]['raw_roi'] for sid in ids]),
        cleaned_roi=np.concatenate([people[sid]['cleaned_roi'] for sid in ids]),
        canonical_active=np.stack([people[sid]['canonical_active'] for sid in ids]))
    metadata = dict(schema_version='devconn-metadata-v2', task_id='DEVCONN-001', dataset_id='ds000228',
        status='complete', **ref['pins'], analysis_scope='Fabricated conditional method test',
        software_versions={'python': 'fixture', 'numpy': 'fixture'}, warnings=[],
        **{k: copy.deepcopy(ref[k]) for k in ('cohort', 'source_files', 'roi_definitions', 'source_observed', 'analysis_observed')})
    actual = {'signal_evidence.npz': arrays, 'run_metadata.json': metadata, 'findings.md': 'No direction is required.'}
    return actual, refresh(actual, ref)


@pytest.fixture(scope='module')
def base():
    ids = [f'sub-pixar{i:03d}' for i in range(1, 10)]
    with pytest.MonkeyPatch.context() as mp:
        for key, value in (('SUBJECT_IDS', tuple(ids)), ('N_CHILDREN', 6), ('N_ADULTS', 3), ('N_ROIS', 6)):
            mp.setattr(V, key, value)
        V.bind_reporting_kernel((HERE / 'reporting_kernel.py').read_bytes())
        ref = make_reference(ids); actual, result = make_output(ref)
        yield ref, actual, result


@pytest.fixture
def fabricated(base):
    return copy.deepcopy(base)


def test_genuine_full_1000_slots_no_mutation(fabricated):
    ref, actual, _ = fabricated; saved = copy.deepcopy(actual)
    assert V.verify_artifacts(actual, ref) == dict(status='ok', n_subjects=9, n_children=6, n_adults=3, n_bootstrap_draws=1000)
    for key, value in saved['signal_evidence.npz'].items():
        assert np.array_equal(actual['signal_evidence.npz'][key], value)
    for key in V.FILES[1:]: assert actual[key] == saved[key]


def test_manufactured_receipts_do_not_alias_expected_results(fabricated):
    _, actual, expected = fabricated
    preserved = copy.deepcopy(expected['age_effects'])
    actual['age_effects.json']['children_age_spearman']['short_range']['n_expected'] = True
    actual['age_effects.json']['motion_control']['segregation_low_motion_restriction']['child_ids'].clear()
    assert expected['age_effects'] == preserved


def test_all_coherent_axes_and_keyed_metadata_permutations(fabricated):
    ref, actual, _ = fabricated; a = actual['signal_evidence.npz']
    frame = np.arange(len(a['frame_indices']))[::-1]; ro = np.arange(6)[::-1]; so = np.arange(9)[::-1]
    for key in ('frame_subject_ids', 'frame_indices'): a[key] = a[key][frame]
    for key in ('raw_roi', 'cleaned_roi'): a[key] = a[key][frame][:, ro]
    a['canonical_active'] = a['canonical_active'][so][:, ro]
    a['subject_ids'] = a['subject_ids'][so]; a['roi_ids'] = a['roi_ids'][ro]
    draw = np.arange(1000)[::-1]; metric = [2, 0, 1]; arm = [1, 0]
    for key in ('bootstrap_draw_ids', 'bootstrap_indices', 'bootstrap_motion_nuisance_rank', 'bootstrap_motion_df'):
        a[key] = a[key][draw]
    for key in ('bootstrap_r', 'bootstrap_defined', 'bootstrap_status'): a[key] = a[key][draw][:, metric][:, :, arm]
    a['bootstrap_metric_ids'] = a['bootstrap_metric_ids'][metric]
    a['bootstrap_association_ids'] = a['bootstrap_association_ids'][arm]
    actual['connectivity_metrics.csv'].reverse(); m = actual['run_metadata.json']
    for key in ('cohort', 'source_files', 'roi_definitions'): m[key].reverse()
    for row in m['cohort']: row['mean_fd_missing_frame_indices'].reverse()
    m['source_observed']['persons'].reverse(); m['analysis_observed']['persons'].reverse()
    for row in m['source_observed']['persons']:
        row['roi_supports'].reverse(); row['mean_fd_missing_entries'].reverse(); row['mean_fd_missing_frame_indices'].reverse()
    for row in m['analysis_observed']['persons']: row['roi_activity'].reverse()
    restriction = actual['age_effects.json']['motion_control']['segregation_low_motion_restriction']
    restriction['child_ids'].reverse(); restriction['adult_ids'].reverse()
    assert V.verify_artifacts(actual, ref)['status'] == 'ok'


def test_safe_representations_extras_and_coordinate_numeric_spellings(fabricated):
    ref, actual, _ = fabricated; a = actual['signal_evidence.npz']
    for key in ('subject_ids', 'roi_ids', 'frame_subject_ids', 'bootstrap_child_ids', 'bootstrap_metric_ids', 'bootstrap_association_ids'):
        a[key] = a[key].astype('S32')
    for key in ('frame_indices', 'bootstrap_draw_ids', 'bootstrap_indices', 'bootstrap_motion_nuisance_rank', 'bootstrap_motion_df'):
        a[key] = a[key].astype(float)
    a['extra'] = np.zeros((1,) * 32); a['zero_width_extra'] = np.ndarray((2, 3), dtype='S0', buffer=b'')
    m = actual['run_metadata.json']; m['extra'] = {'description': 'not a prose fingerprint'}
    for row in m['source_observed']['persons']: row['bold_header']['storage_dtype'] = 'float32'
    for row in m['roi_definitions']: row['center_mm'] = list(map(float, row['center_mm']))
    for row in actual['connectivity_metrics.csv']: row['extra'] = 'free text'
    assert V.verify_artifacts(actual, ref)['status'] == 'ok'


def test_own_clean_replay_then_six_decimal_derived_receipts(fabricated):
    ref, actual, _ = fabricated
    # Admitted affine perturbation preserves source eligibility, not literal source bytes.
    actual['signal_evidence.npz']['cleaned_roi'] *= 1 + 2e-8
    actual['signal_evidence.npz']['cleaned_roi'] += 1e-9
    refresh(actual, ref)
    for row in actual['connectivity_metrics.csv']:
        for key in V.METRICS:
            if row[key] != '': row[key] = format(float(row[key]), '.6f')
    def rounded(value):
        if type(value) is float: return round(value, 6)
        if type(value) is list: return [rounded(x) for x in value]
        if type(value) is dict: return {k: rounded(x) for k, x in value.items()}
        return value
    actual['age_effects.json'] = rounded(actual['age_effects.json'])
    assert V.verify_artifacts(actual, ref)['status'] == 'ok'


def test_accepted_tie_break_replayed_without_canonical_rank_target(fabricated):
    ref, _, _ = fabricated
    # These two fabricated subjects share length36 and an exactly tied source metric.
    first, other = ref['subject_ids'][0], ref['subject_ids'][3]
    ref['persons'][other]['cleaned_roi'] = ref['persons'][first]['cleaned_roi'].copy()
    actual, source_replay = make_output(ref)
    a = actual['signal_evidence.npz']
    row = np.flatnonzero(a['frame_subject_ids'] == other)[0]
    a['cleaned_roi'][row, 0] += 5e-8
    own = refresh(actual, ref)
    assert any(own['age_effects']['children_age_spearman'][m]['r'] !=
               source_replay['age_effects']['children_age_spearman'][m]['r'] for m in V.METRICS)
    assert V.verify_artifacts(actual, ref)['status'] == 'ok'
    actual['age_effects.json']['children_age_spearman'] = source_replay['age_effects']['children_age_spearman']
    with pytest.raises(ValueError, match='numeric_tolerance'):
        V.validate_results(actual['age_effects.json'], own)


class NoList(np.ndarray):
    def tolist(self): raise AssertionError('malformed axis expanded')


@pytest.mark.parametrize('axis', ['subject_ids', 'roi_ids', 'frame_subject_ids', 'bootstrap_child_ids',
    'bootstrap_metric_ids', 'bootstrap_association_ids', 'bootstrap_status'])
@pytest.mark.parametrize('dtype', ['S0', 'U0'])
def test_shape_before_text_expansion(fabricated, axis, dtype):
    ref, actual, result = fabricated
    a = actual['signal_evidence.npz']; a[axis] = np.ndarray((1,), dtype=dtype, buffer=b'').view(NoList)
    with pytest.raises(ValueError, match='string_array'):
        if axis.startswith('bootstrap'): V.validate_bootstrap(a, result)
        else: V.canonical_primitives(a, ref)


@pytest.mark.parametrize('kind', ['raw', 'clean', 'active', 'duplicate_frame', 'frame_bool', 'subject_alias', 'roi_alias', 'nonfinite'])
def test_source_primitive_binding(fabricated, kind):
    ref, actual, _ = fabricated; a = actual['signal_evidence.npz']
    if kind == 'raw': a['raw_roi'][0, 0] += 1
    elif kind == 'clean': a['cleaned_roi'][0, 0] += 1
    elif kind == 'active': a['canonical_active'][0, 0] = False
    elif kind == 'duplicate_frame': a['frame_indices'][1] = a['frame_indices'][0]
    elif kind == 'frame_bool': a['frame_indices'] = a['frame_indices'].astype(bool)
    elif kind == 'subject_alias': a['subject_ids'][0] = '001'
    elif kind == 'roi_alias': a['roi_ids'][1] = '2'
    else: a['cleaned_roi'][0, 0] = np.nan
    with pytest.raises(ValueError): V.verify_artifacts(actual, ref)


@pytest.mark.parametrize('kind', ['children_order', 'rng_slots', 'drop_draw', 'duplicate_draw', 'status',
    'defined', 'r_domain', 'r_value', 'rank', 'df', 'integer_bool'])
def test_bootstrap_binding_without_replaying_cached_reference(fabricated, kind):
    _, actual, result = fabricated; a = actual['signal_evidence.npz']
    if kind == 'children_order':
        a['bootstrap_child_ids'] = a['bootstrap_child_ids'][::-1]
        a['bootstrap_indices'] = 5 - a['bootstrap_indices']
    elif kind == 'rng_slots': a['bootstrap_indices'] = a['bootstrap_indices'][:, ::-1]
    elif kind == 'drop_draw': a['bootstrap_r'] = a['bootstrap_r'][:-1]
    elif kind == 'duplicate_draw': a['bootstrap_draw_ids'][1] = 0
    elif kind == 'status': a['bootstrap_status'][0, 0, 0] = 'invented'
    elif kind == 'defined': a['bootstrap_defined'][0, 0, 0] ^= True
    elif kind in ('r_domain', 'r_value'):
        index = tuple(np.argwhere(a['bootstrap_defined'])[0])
        a['bootstrap_r'][index] = 1.0000001 if kind == 'r_domain' else (0. if abs(a['bootstrap_r'][index]) > .1 else .5)
    elif kind == 'rank': a['bootstrap_motion_nuisance_rank'][0] += 1
    elif kind == 'df': a['bootstrap_motion_df'][0] += 1
    else: a['bootstrap_indices'] = a['bootstrap_indices'].astype(bool)
    with pytest.raises(ValueError): V.validate_bootstrap(a, result)


@pytest.mark.parametrize('kind', ['fd', 'age', 'group', 'metric', 'status', 'count', 'null_token', 'missing', 'duplicate'])
def test_csv_receipt_binding(fabricated, kind):
    _, actual, result = fabricated; rows = actual['connectivity_metrics.csv']; row = rows[0]
    if kind in ('fd', 'age'): key = 'mean_fd' if kind == 'fd' else 'age'; row[key] = str(float(row[key]) + .01)
    elif kind == 'group': row['group'] = 'adult'
    elif kind == 'metric': row['short_range'] = str(float(row['short_range']) + .01)
    elif kind == 'status': row['short_range_status'] = 'empty_edge_family'
    elif kind == 'count': row['short_range_n_used_edges'] = '1.5'
    elif kind == 'null_token': row['short_range'] = 'NaN'
    elif kind == 'missing': rows.pop()
    else: rows[-1] = copy.deepcopy(row)
    with pytest.raises(ValueError): V.validate_table(rows, result)


def test_fisher_receipts_above_one_and_fractional_welch_df(fabricated):
    _, actual, result = fabricated
    result['participant_rows'][0]['short_range'] = 2.5
    actual['connectivity_metrics.csv'][0]['short_range'] = '2.5'
    V.validate_table(actual['connectivity_metrics.csv'], result)
    welch = result['age_effects']['segregation_child_vs_adult']
    assert welch['status'] == 'ok' and type(welch['df']) is float
    V.validate_results(actual['age_effects.json'], result)


@pytest.mark.parametrize('kind', ['p_domain', 'r_domain', 'count_bool', 'count_float', 'null', 'ci', 'threshold', 'restricted_members', 'welch_p'])
def test_json_domains_and_types(fabricated, kind):
    _, actual, result = fabricated; obj = actual['age_effects.json']; item = obj['children_age_spearman']['short_range']
    if kind == 'p_domain': item['p'] = 1.0000001
    elif kind == 'r_domain': item['r'] = -1.0000001
    elif kind == 'count_bool': item['n_expected'] = True
    elif kind == 'count_float': item['df'] = float(item['df'])
    elif kind == 'null': item['r'] = None
    elif kind == 'ci': item['raw_bootstrap']['ci95'] = [.5, -.5]
    elif kind == 'threshold': obj['motion_control']['segregation_low_motion_restriction']['fd_thresh'] += 1e-9
    elif kind == 'restricted_members': obj['motion_control']['segregation_low_motion_restriction']['child_ids'] = []
    else: obj['segregation_child_vs_adult']['p'] = -1e-9
    with pytest.raises(ValueError): V.validate_results(obj, result)


@pytest.mark.parametrize('kind', ['source_hash', 'source_missing', 'support_hash', 'support_count', 'mask', 'rank',
    'header', 'dtype', 'missing_token', 'fd_denominator', 'missing_index_bool', 'column_order', 'coordinate', 'bins', 'frame_alignment'])
def test_source_metadata_binding(fabricated, kind):
    ref, actual, _ = fabricated; m = actual['run_metadata.json']; person = m['source_observed']['persons'][0]
    if kind == 'source_hash': m['source_files'][0]['sha256'] = '0' * 64
    elif kind == 'source_missing': m['source_files'].pop()
    elif kind == 'support_hash': person['roi_supports'][0]['support_sha256'] = '0' * 64
    elif kind == 'support_count': person['roi_supports'][0]['n_voxels'] = 2.
    elif kind == 'mask': m['analysis_observed']['persons'][0]['roi_activity'][0]['active'] = 1
    elif kind == 'rank': m['analysis_observed']['persons'][0]['cleaning_rank'] += 1
    elif kind == 'header': person['bold_header']['raw_toffset'] = 1.
    elif kind == 'dtype': person['bold_header']['storage_dtype'] = 'float64'
    elif kind == 'missing_token': person['mean_fd_missing_entries'][0]['original_token'] = 'NA'
    elif kind == 'fd_denominator': person['mean_fd_denominator'] -= 1
    elif kind == 'missing_index_bool': person['mean_fd_missing_frame_indices'][0] = False
    elif kind == 'column_order': person['confound_column_names'].reverse()
    elif kind == 'coordinate': m['roi_definitions'][0]['center_mm'][0] += .01
    elif kind == 'bins': m['analysis_observed']['distance_bins']['q1_mm'] += 1e-7
    else: del m['source_observed']['frame_alignment']
    with pytest.raises(ValueError): V.validate_metadata(m, ref)


def test_canonical_inactive_jitter_keeps_complete_null_slots(fabricated):
    ref, _, _ = fabricated
    for sid, p in ref['persons'].items():
        p['cleaned_roi'][:] = 0.; p['canonical_active'][:] = False
    for row in ref['analysis_observed']['persons']:
        row['n_active_rois'] = 0
        for roi in row['roi_activity']: roi.update(active=False, residual_centered_l2=0.)
    actual, result = make_output(ref)
    actual['signal_evidence.npz']['cleaned_roi'][:] = np.linspace(-1e-9, 1e-9, len(actual['signal_evidence.npz']['frame_indices']))[:, None]
    assert not result['bootstrap']['defined'].any()
    assert V.verify_artifacts(actual, ref)['status'] == 'ok'
    actual['signal_evidence.npz']['bootstrap_r'][0, 0, 0] = 1e-12
    with pytest.raises(ValueError, match='null_sentinel'): V.validate_bootstrap(actual['signal_evidence.npz'], result)


def test_pointwise_close_erased_small_active_direction_is_rejected(fabricated):
    ref, _, _ = fabricated
    for p in ref['persons'].values(): p['cleaned_roi'] *= 1e-12
    actual, _ = make_output(ref); actual['signal_evidence.npz']['cleaned_roi'][:] = 0.
    with pytest.raises(ValueError, match='clean_centered_fidelity'): V.verify_artifacts(actual, ref)


@pytest.mark.parametrize('mode', ['pin', 'pilot', 'unbound', 'kernel_bytes'])
def test_authority_fails_closed(fabricated, monkeypatch, mode):
    ref, actual, _ = fabricated
    if mode == 'pin': monkeypatch.setattr(V, 'METHOD_SHA', None)
    elif mode == 'pilot': ref['status'] = 'resource_pilot'
    elif mode == 'unbound': monkeypatch.setattr(V, '_BOUND_SHA', '0' * 64)
    else:
        with pytest.raises(ValueError, match='private_kernel_identity'): V.bind_reporting_kernel(b'raise RuntimeError()')
        return
    with pytest.raises(ValueError): V.verify_artifacts(actual, ref)


def save_output(actual, path):
    path.mkdir()
    np.savez_compressed(path / V.FILES[0], **actual[V.FILES[0]])
    with (path / V.FILES[1]).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=IO.CSV_COLUMNS); writer.writeheader(); writer.writerows(actual[V.FILES[1]])
    for name in V.FILES[2:4]: (path / name).write_text(json.dumps(actual[name], allow_nan=False))
    (path / V.FILES[4]).write_text(actual[V.FILES[4]])


def test_disk_composition_and_late_failure_marker(fabricated, tmp_path, monkeypatch):
    ref, actual, _ = fabricated; path = tmp_path / 'output'; save_output(actual, path)
    assert V.validate_output_directory(path, ref)['status'] == 'ok'
    original = V.verify_artifacts
    def injected(*args):
        result = original(*args); (path / 'failure_report.json').symlink_to(path / 'absent'); return result
    monkeypatch.setattr(V, 'verify_artifacts', injected)
    with pytest.raises(ValueError, match='failed_run_marker'): V.validate_output_directory(path, ref)
