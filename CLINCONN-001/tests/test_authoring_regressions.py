"""Small synthetic mechanism fixtures, never original-source evidence or a bank."""
import copy
import csv
import json
from pathlib import Path
import numpy as np
import pytest
import connectivity_contract as q
import proof_of_work as pw

TASK = Path(__file__).resolve().parents[1]


def toy_reference():
    method = json.loads((TASK/'environment/method_contract.json').read_text())
    subjects = np.array([f'sub-{i}' for i in range(6)])
    parcel_ids = np.array(['L:1', 'L:2', 'R:1', 'R:2'])
    group = ['CONTROL']*3+['SCHZ']*3
    fd = [.05, .1, .25, .1, .15, .35]
    raw = np.random.default_rng(8).uniform(-.6, .6, (6, 6))
    centers = [0., 1., 3., 7.]
    ref = dict(subject_id=subjects, parcel_id=parcel_ids, edge_id=np.arange(6),
        parcel_status=np.full((6, 4), 'ok', dtype='U24'),
        parcel_original_centered_l2=np.full((6, 4), 5.), parcel_residual_l2=np.ones((6, 4)),
        parcel_zero_bound=np.full((6, 4), 10*40*q.EPS*5), raw_r=raw,
        fisher_z=np.arctanh(raw), edge_valid=np.ones((6, 6), bool), fisher_clipped=np.zeros((6, 6), bool))
    ref['cohort_rows'] = [dict(source_participant_row=i, subject_id=sid, group=group[i], source_rest=1,
        available_left=True, available_right=True, available_confounds=True, selected=True, exclusion_reason='selected')
        for i, sid in enumerate(subjects)]
    ref['parcel_rows'] = [dict(parcel_id=pid, hemisphere=pid[0], annotation_index=int(pid[2:]),
        annotation_name='fixture_'+pid, n_vertices=3, included=True, exclusion_reason='included',
        centroid_x=centers[i], centroid_y=0., centroid_z=0.) for i, pid in enumerate(parcel_ids)]
    ii, jj = np.triu_indices(4, 1)
    ref['edge_rows'] = [dict(edge_id=e, parcel_i=parcel_ids[i], parcel_j=parcel_ids[j],
        distance=centers[j]-centers[i], n_valid_subjects=6, common_valid=True, distance_bin='middle')
        for e, (i, j) in enumerate(zip(ii, jj))]
    ref['connectivity_rows'] = [dict(subject_id=sid, group=group[i], n_frames=40, tr_s=2.,
        fd_sum=fd[i]*39, n_fd_defined=39, first_fd_defined=False, mean_fd=fd[i], qc_fd_lt_0_2=fd[i]<.2,
        n_confound_columns=13, nuisance_rank=2, nuisance_rank_threshold=100*q.EPS,
        n_valid_parcels=4, n_invalid_parcels=0, n_common_edges=6, n_saturated_common_edges=0,
        mean_fc=0., short_range_fc=0., long_range_fc=0.) for i, sid in enumerate(subjects)]
    ref['metadata'] = dict(status='complete', task_id='CLINCONN-001', dataset_id='ds000030',
        source_manifest_sha256='fixture-not-source', method_contract_sha256=pw.METHOD_SHA256,
        source_sha256={'synthetic_fixture': '0'*64}, method_contract=method,
        source_observed=dict(n_source_participants=6, n_candidates=6, n_selected=6, n_unavailable=0,
            group_counts={'SCHZ': 3, 'CONTROL': 3}, atlas={'synthetic_fixture': True},
            subjects=[dict(subject_id=sid, n_frames=40, n_vertices_left=6, n_vertices_right=6,
                n_confounds_rows=40, tr_s=2., surface_dtype_left='float32', surface_dtype_right='float32') for sid in subjects]),
        software={'fixture': 'synthetic-mechanics-only'})
    return ref


def write_submission(path, ref):
    path.mkdir(exist_ok=True)
    derived = q.summarize(ref)
    for filename, rows in [('cohort.csv', ref['cohort_rows']), ('parcels.csv', ref['parcel_rows']),
            ('edges.csv', derived['edge_rows']), ('connectivity.csv', derived['connectivity_rows']),
            ('edge_stats.csv', derived['edge_stats'])]:
        with (path/filename).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=ref['metadata']['method_contract']['outputs'][filename]['columns'])
            writer.writeheader(); writer.writerows(rows)
    np.savez_compressed(path/'subject_edge_fc.npz', **{k: ref[k] for k in q.ARRAY_FIELDS})
    (path/'group_stats.json').write_text(json.dumps(derived['group_stats'], allow_nan=False))
    (path/'run_metadata.json').write_text(json.dumps(ref['metadata'], allow_nan=False))
    (path/'findings.md').write_text('A synthetic parser fixture; not a scientific result.\n')


@pytest.mark.parametrize('text,wanted', [('1e2', 100), ('-1.0', -1), ('9007199254740993', 9007199254740993)])
def test_exact_integral_notation(text, wanted):
    assert q.integer(text) == wanted


@pytest.mark.parametrize('bad', [True, 'NaN', 'Infinity', '.25', '', None])
def test_reject_nonintegral(bad):
    with pytest.raises(AssertionError): q.integer(bad)


@pytest.mark.parametrize('bad', [True, 'NaN', 'Infinity', '-Infinity', '', None])
def test_reject_nonfinite_numeric(bad):
    with pytest.raises(AssertionError): q.number(bad)


@pytest.mark.parametrize('value', [True, 'true', 'TRUE', '1e0'])
def test_boolean_serializations(value):
    assert q.flag(value)


@pytest.mark.parametrize('bad', ['truthy', '2', '-1', '', None])
def test_invalid_flags(bad):
    with pytest.raises(AssertionError): q.flag(bad)


@pytest.mark.parametrize('actual,expected', [(True, 1), (1, True), ('1', 1), ({}, {'x': None})])
def test_json_type_and_missing_null(actual, expected):
    with pytest.raises(AssertionError): q.match(actual, expected)


def test_rank_two_constant_fd_is_estimable():
    g = np.array([0, 0, 0, 1, 1, 1.])
    y = np.array([.1, .4, .2, -.1, -.2, -.15])
    plain = q.ols(y, g); redundant = q.ols(y, g, np.full(6, .2))
    assert redundant['rank'] == 2 and redundant['status'] == 'ok'
    assert redundant['estimate'] < 0
    for key in ('estimate', 'se', 't', 'p', 'sse'): assert redundant[key] == pytest.approx(plain[key], abs=1e-12)


@pytest.mark.parametrize('level', [.1, -.2, 0., 1e-100])
def test_exact_constant_response(level):
    result = q.ols(np.full(6, level), [0, 0, 0, 1, 1, 1], [.1, .2, .3, .2, .3, .4])
    assert result['status'] == 'zero_se'
    assert result['estimate'] == result['se'] == result['sse'] == 0
    assert result['ci95'] == [0., 0.] and result['t'] is result['p'] is None


def test_perfect_group_fit_zero_se_not_infinite():
    result = q.ols([.1, .1, .1, .4, .4, .4], [0, 0, 0, 1, 1, 1])
    assert result['status'] == 'zero_se' and result['estimate'] == pytest.approx(.3)
    assert result['t'] is None and result['p'] is None


def test_nonestimable_diagnosis_fd_collinear():
    result = q.ols([.1, .2, .3, .4], [0, 0, 1, 1], [0, 0, 1, 1])
    assert result['rank'] == 2 and result['status'] == 'rank_deficient'
    assert result['estimate'] is result['sse'] is None


@pytest.mark.parametrize('g,status', [([], 'missing_group'), ([0], 'missing_group'), ([0, 1], 'insufficient_df')])
def test_ols_small_support(g, status):
    result = q.ols(np.zeros(len(g)), g)
    assert result['status'] == status and result['n'] == len(g)


def test_empty_bin_keeps_cohort_rank():
    result = q.ols(np.zeros(6), [0, 0, 0, 1, 1, 1], np.full(6, .2), empty=True)
    assert result['status'] == 'empty_response_bin' and result['rank'] == 2
    assert result['n'] == 6 and result['df'] == 4 and result['estimate'] is None


def test_quantile_ties_not_forced_terciles():
    bins, stats = q.family([1., 1., 1., 1., 2., 2.], np.ones(6, bool))
    assert stats['n_short'] == 0 and stats['q1'] == 1
    assert np.sum(bins == 'middle') == 4


def test_empty_common_family():
    bins, stats = q.family([1., 2.], [False, False])
    assert bins.tolist() == ['excluded_not_common']*2
    assert stats == dict(q1=None, q2=None, n_short=0, n_middle=0, n_long=0)


@pytest.mark.parametrize('x,y,status', [([], [], 'insufficient_n'), ([.1]*3, [1,2,3], 'constant_fd'),
    ([1,2,3], [.1]*3, 'constant_edge')])
def test_defined_correlation_support(x, y, status):
    assert q.pearson(x, y) == (status, None)


def test_synthetic_complete_parser_positive(tmp_path):
    ref = toy_reference(); write_submission(tmp_path, ref)
    assert q.validate_output_directory(tmp_path, ref)['n_subjects'] == 6


def test_complete_accounting_no_common_edges(tmp_path):
    ref = toy_reference()
    ref['parcel_status'][:] = 'constant_input'; ref['edge_valid'][:] = False
    ref['raw_r'][:] = np.nan; ref['fisher_z'][:] = np.nan
    write_submission(tmp_path, ref)
    result = q.validate_output_directory(tmp_path, ref)
    assert result['n_common_edges'] == 0 and result['distance_bins']['q1'] is None
    assert result['short_range_effects']['all_crude']['status'] == 'empty_response_bin'


def test_consistent_npz_axis_order_and_integer_width(tmp_path):
    ref = toy_reference(); values = {}
    for k in q.ARRAY_FIELDS:
        val = ref[k]
        if val.ndim == 1: values[k] = val[::-1]
        else: values[k] = val[::-1, ::-1]
    values['edge_id'] = values['edge_id'].astype(np.uint32)
    np.savez(tmp_path/'a.npz', **values)
    q.validate_arrays(tmp_path/'a.npz', ref)


@pytest.mark.parametrize('mode', ['affine', 'sign', 'wrong_z', 'valid_nan', 'false_valid', 'wrong_clip', 'negative_norm', 'wrong_id', 'bool_id', 'dup_id'])
def test_source_array_forgeries(tmp_path, mode):
    ref = toy_reference(); values = {k: v.copy() for k, v in ref.items() if k in q.ARRAY_FIELDS}
    if mode == 'affine':
        values['raw_r'] += .01; values['fisher_z'] = np.arctanh(values['raw_r'])
    elif mode == 'sign':
        values['raw_r'] *= -1; values['fisher_z'] *= -1
    elif mode == 'wrong_z': values['fisher_z'] = values['raw_r'].copy()
    elif mode == 'valid_nan': values['raw_r'][0,0] = np.nan
    elif mode == 'false_valid': values['edge_valid'][0,0] = False
    elif mode == 'wrong_clip': values['fisher_clipped'][0,0] = True
    elif mode == 'negative_norm': values['parcel_residual_l2'][0,0] = -1
    elif mode == 'wrong_id': values['subject_id'][0] = 'alien'
    elif mode == 'bool_id': values['edge_id'] = values['edge_id'].astype(bool)
    elif mode == 'dup_id': values['parcel_id'][0] = values['parcel_id'][1]
    np.savez(tmp_path/'bad.npz', **values)
    with pytest.raises(AssertionError): q.validate_arrays(tmp_path/'bad.npz', ref)


def test_fisher_endpoint_rounding_source_flag_preserved(tmp_path):
    ref = toy_reference(); ref['raw_r'][0,0] = .99900000001
    ref['fisher_z'][0,0] = np.arctanh(.999); ref['fisher_clipped'][0,0] = True
    values = {k: v.copy() for k, v in ref.items() if k in q.ARRAY_FIELDS}
    values['raw_r'][0,0] = .999
    np.savez(tmp_path/'valid.npz', **values)
    q.validate_arrays(tmp_path/'valid.npz', ref)


def test_actual_software_and_free_prose(tmp_path):
    ref = toy_reference(); write_submission(tmp_path, ref)
    meta = copy.deepcopy(ref['metadata']); meta['software'] = {'independent package': 'real-version'}
    meta['description'] = 'Additional harmless detail.'
    (tmp_path/'run_metadata.json').write_text(json.dumps(meta))
    (tmp_path/'findings.md').write_text('No required scientific direction.\n')
    q.validate_output_directory(tmp_path, ref)


@pytest.mark.parametrize('mode', ['extra_source', 'method_boolean', 'missing_status', 'failed_status'])
def test_metadata_identity_mutations(mode):
    ref = toy_reference(); meta = copy.deepcopy(ref['metadata'])
    if mode == 'extra_source': meta['source_sha256']['fictional'] = 'a'*64
    elif mode == 'method_boolean': meta['method_contract']['schema_version'] = True
    elif mode == 'missing_status': del meta['status']
    else: meta['status'] = 'failed_precondition'
    with pytest.raises(AssertionError): q.validate_metadata(meta, ref)


def test_temporary_historical_scalar_bank_rejected(tmp_path):
    np.savez(tmp_path/'old.npz', ref_ids=np.array(['1']), ref_stats=np.array('{}'))
    with pytest.raises(AssertionError, match='Obsolete'): pw.load_reference(tmp_path/'old.npz')


def test_offline_python3_entrypoint():
    text = (TASK/'tests/test.sh').read_text()
    assert 'python3 -m pytest' in text and 'pip install' not in text and 'uvx' not in text


def test_group_quantile_uses_geometry_tolerance_once():
    wanted = q.summarize(toy_reference())['group_stats']
    wanted['distance_bins']['q1'] = 1e-7
    actual = copy.deepcopy(wanted); actual['distance_bins']['q1'] += 5e-6
    q.validate_group(actual, wanted)


@pytest.mark.parametrize('measure,shift', [('mean_fd', 1e-7), ('mean_fc', 3e-6)])
def test_group_mean_uses_its_public_tolerance(measure, shift):
    wanted = q.summarize(toy_reference())['group_stats']; actual = copy.deepcopy(wanted)
    actual['group_means'][measure]['SCHZ'] += shift
    with pytest.raises(AssertionError): q.validate_group(actual, wanted)


def test_atlas_metadata_closed_but_descriptions_allowed():
    ref = toy_reference(); meta = copy.deepcopy(ref['metadata'])
    meta['source_observed']['extra_description'] = 'harmless'
    q.validate_metadata(meta, ref)
    meta['source_observed']['atlas']['invented_transform'] = True
    with pytest.raises(AssertionError): q.validate_metadata(meta, ref)


def test_submitted_arrays_recomputed(monkeypatch, tmp_path):
    ref = toy_reference(); write_submission(tmp_path, ref)
    original = q.summarize; seen = []
    def observed(reference, values=None, fd_values=None):
        if values is not None:
            seen.append((values['fisher_z'].copy(), fd_values.copy()))
        return original(reference, values, fd_values)
    monkeypatch.setattr(q, 'summarize', observed)
    q.validate_output_directory(tmp_path, ref)
    assert len(seen) == 1 and np.array_equal(seen[0][0], ref['fisher_z'])


def test_qc_membership_uses_source_not_rounded_fd():
    ref = toy_reference(); ref['connectivity_rows'][4]['mean_fd'] = .199999999999
    ref['connectivity_rows'][4]['fd_sum'] = .199999999999*39
    fd = np.array([r['mean_fd'] for r in ref['connectivity_rows']]); fd[4] = .2
    a = q.summarize(ref); b = q.summarize(ref, ref, fd_values=fd)
    assert a['group_stats']['short_range_effects']['qc_fd_lt_0_2']['n'] == b['group_stats']['short_range_effects']['qc_fd_lt_0_2']['n']


def test_source_close_but_internally_wrong_mean_rejected(tmp_path):
    ref = toy_reference(); write_submission(tmp_path, ref)
    arrays = {k: v.copy() for k, v in ref.items() if k in q.ARRAY_FIELDS}
    arrays['fisher_z'] += .9e-6
    np.savez(tmp_path/'subject_edge_fc.npz', **arrays)
    columns = ref['metadata']['method_contract']['outputs']['connectivity.csv']['columns']
    rows = q.csv_load(tmp_path/'connectivity.csv', columns)
    for row in rows:
        row['mean_fc'] = str(float(row['mean_fc'])-.9e-6)
    with (tmp_path/'connectivity.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    # Both components independently fit their source tolerances. Their joint
    # arithmetic differs by1.8e-6 and must not pass via a source-distance budget.
    with pytest.raises(AssertionError, match='submitted mean_fc'):
        q.validate_output_directory(tmp_path, ref)


def test_six_decimal_summary_with_float32_matrix_positive(tmp_path):
    ref = toy_reference(); write_submission(tmp_path, ref)
    arrays = {k: v.astype(np.float32) if k in ('raw_r', 'fisher_z') else v
              for k, v in ref.items() if k in q.ARRAY_FIELDS}
    np.savez(tmp_path/'subject_edge_fc.npz', **arrays)
    columns = ref['metadata']['method_contract']['outputs']['connectivity.csv']['columns']
    rows = q.csv_load(tmp_path/'connectivity.csv', columns)
    for row in rows:
        for field in ('mean_fc', 'short_range_fc', 'long_range_fc'):
            row[field] = f'{float(row[field]):.6f}'
    with (tmp_path/'connectivity.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    q.validate_output_directory(tmp_path, ref)
