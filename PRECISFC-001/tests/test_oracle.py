"""Synthetic mechanics only: these tests never open original MSC signal data."""
import copy
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import nibabel as nib
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('precisfc_oracle', ROOT/'solution'/'compute.py')
oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
METHOD = json.loads((ROOT/'environment'/'method_contract.json').read_text())


@pytest.mark.parametrize('x,status', [([], 'insufficient_frames'), ([2], 'insufficient_frames'),
    ([0,0,0], 'constant'), ([.1]*100, 'constant'), ([-2,-2], 'constant'),
    ([1,1+np.finfo(float).eps,1], 'numerically_constant'), ([1,2,3], 'ok'),
    ([1e-250,2e-250,3e-250], 'ok'), ([1e200,2e200,3e200], 'ok')])
def test_stable_classification(x, status):
    result = oracle.stable_vector(x)
    assert result['status'] == status
    if status == 'insufficient_frames':
        assert all(result[k] is None for k in ('raw_l2','centered_l2','zero_bound'))
    elif status == 'constant':
        assert result['centered_l2'] == 0
    elif status == 'ok':
        np.testing.assert_allclose(np.dot(result['unit'], result['unit']), 1, atol=1e-15)


def test_constant_decimal_diagnostic_is_exactly_zero():
    result = oracle.stable_vector(np.repeat(.1, 101))
    assert result['centered_l2'] == 0
    assert result['raw_l2'] == .1*np.sqrt(101)
    assert result['zero_bound'] == .1*(10*101*np.finfo(float).eps*np.sqrt(101))


@pytest.mark.parametrize('x', [[1,np.nan], [1,np.inf], [[1,2]], [1e308,-1e308,1e308,-1e308]])
def test_vector_failure_not_exclusion(x):
    with pytest.raises(ValueError):
        oracle.stable_vector(x)


@pytest.mark.parametrize('a,b,status', [([], [], 'insufficient_common_edges'),
    ([0], [1], 'insufficient_common_edges'), ([1,1], [2,3], 'constant_edge_vector'),
    ([1,1+np.finfo(float).eps,1], [1,2,3], 'numerically_constant_edge_vector'),
    ([1,2,3], [3,2,1], 'ok')])
def test_pair_undefined_precedence(a,b,status):
    _, _, value, actual = oracle.pair_measure(a,b)
    assert actual == status
    assert (value is not None) == (status == 'ok')
    if status == 'ok':
        assert value == pytest.approx(-1)


@pytest.mark.parametrize('value,expected', [(1+5e-13,1), (-1-5e-13,-1), (.1,.1)])
def test_pearson_roundoff(value, expected):
    assert float(oracle.clamp_pearson(value)) == expected


@pytest.mark.parametrize('value', [1.00001, -1.00001, np.nan, np.inf])
def test_impossible_pearson_fails(value):
    with pytest.raises(ValueError):
        oracle.clamp_pearson(value)


def test_membership_closed_boundary_and_c_order():
    geometry = oracle.sphere_geometry([[1,1,1]], np.eye(4), (3,3,3), np.eye(4), radius=1)
    expected = np.asarray([[0,1,1],[1,0,1],[1,1,0],[1,1,1],[1,1,2],[1,2,1],[2,1,1]])
    np.testing.assert_array_equal(geometry['ijk'], expected)
    assert geometry['boundary'][0] == 0
    np.testing.assert_array_equal(geometry['offsets'], [0,7])


def test_point_direction_not_inverse_or_extra_axis_flip():
    matrix = np.eye(4); matrix[:3,3] = [1,2,3]
    g = oracle.sphere_geometry([[0,0,0]], np.eye(4), (4,5,6), matrix, radius=.1)
    np.testing.assert_array_equal(g['centres'], [[1,2,3]])
    np.testing.assert_array_equal(g['ijk'], [[1,2,3]])


def test_overlap_preserved_but_union_unique():
    g = oracle.sphere_geometry([[1,1,1],[1,1,1]], np.eye(4), (3,3,3), np.eye(4), radius=1)
    assert len(g['ijk']) == 14 and len(g['union']) == 7
    np.testing.assert_array_equal(g['union'][g['membership_to_union']], g['ijk'])


def test_empty_sphere_fails():
    with pytest.raises(ValueError, match='Empty'):
        oracle.sphere_geometry([[50,50,50]], np.eye(4), (3,3,3), np.eye(4))


@pytest.mark.parametrize('text', ['1\n0\n2\n', '1\n0\nnan\n', '1\n0\n', '1 0\n0 1\n'])
def test_nonbinary_or_wrong_mask_rejected(tmp_path, text):
    path = tmp_path/'mask.txt'; path.write_text(text)
    with pytest.raises(ValueError):
        oracle.load_mask(path, 3)


def test_source_mask_numeric_binary(tmp_path):
    path = tmp_path/'mask.txt'; path.write_text('1.0\n0.0\n1\n')
    np.testing.assert_array_equal(oracle.load_mask(path, 3), [True,False,True])


def test_original_float32_means_and_peak_receipt(tmp_path):
    values = np.arange(3*3*3*4, dtype=np.float32).reshape(3,3,3,4)
    path = tmp_path/'toy.nii.gz'; nib.save(nib.Nifti1Image(values, np.eye(4)), path)
    geometry = oracle.sphere_geometry([[1,1,1]], np.eye(4), (3,3,3), np.eye(4), radius=1)
    means, peak, selected = oracle.source_means(path, geometry, values.shape)
    direct = values[tuple(geometry['ijk'].T)].T
    assert selected.dtype == np.float32
    np.testing.assert_array_equal(selected, direct)
    np.testing.assert_array_equal(means[:,0], np.mean(direct, axis=1, dtype=np.float64))
    assert peak[0] == np.max(np.abs(direct))


def test_nonfinite_outside_roi_still_fails(tmp_path):
    values = np.ones((3,3,3,4), dtype=np.float32); values[0,0,0,0] = np.nan
    path = tmp_path/'toy.nii.gz'; nib.save(nib.Nifti1Image(values, np.eye(4)), path)
    geometry = oracle.sphere_geometry([[1,1,1]], np.eye(4), (3,3,3), np.eye(4), radius=.1)
    with pytest.raises(ValueError, match='Nonfinite original'):
        oracle.source_means(path, geometry, values.shape)


def test_both_arms_independently_recomputed():
    means = np.random.default_rng(4).normal(size=(3,8,4))
    masks = np.tile([True,False,True,False,True,False,True,False], (3,1))
    keys = [('S',t) for t in ('func01','func02','func03')]
    result, rows, private = oracle.derive_connectomes(means,masks,keys,['all_frames','censored'])
    for run in range(3):
        for arm, values in enumerate((means[run], means[run,masks[run]])):
            expected = np.corrcoef(values.T)[np.triu_indices(4,1)]
            np.testing.assert_allclose(result['raw_r'][run,arm], expected, atol=1e-15)
    assert not np.allclose(result['raw_r'][:,0], result['raw_r'][:,1])
    assert len(rows) == 24 and np.all(private['roi_status'] == 'ok')


def test_common_support_intersects_all_runs_both_arms():
    means = np.random.default_rng(0).normal(size=(3,6,3)); means[2,::2,1] = .1
    masks = np.tile([True,False], (3,3))
    result, rows, _ = oracle.derive_connectomes(means,masks,[('S',str(i)) for i in range(3)],['all_frames','censored'])
    np.testing.assert_array_equal(result['common_roi'], [True,False,True])
    assert np.isnan(result['raw_r'][:,:,~result['edge_valid']]).all()
    assert np.isfinite(result['raw_r'][:,:,result['edge_valid']]).all()


def test_empty_support_and_qc_propagate_without_available_averaging():
    means = np.ones((3,6,3)); masks = np.ones((3,6), dtype=bool)
    keys = [('S',t) for t in METHOD['source']['sessions']]
    arrays, rows, _ = oracle.derive_connectomes(means,masks,keys,['all_frames','censored'])
    _, pairs, people, result = oracle.summaries(arrays,masks,keys,METHOD,rows,'resource_pilot')
    assert all(p['status'] == 'insufficient_common_edges' and p['pair_r'] is None for p in pairs)
    assert people[0]['censored_status'] == 'incomplete_pairs'
    assert result['group_mean_reliability']['all_six_censored']['status'] == 'incomplete_subjects'
    assert result['group_mean_reliability']['conditional_qc_censored']['status'] == 'empty_qc_subset'


def test_duration_predicate_uses_exact_integer_boundary():
    means = np.ones((3,300,3)); masks = np.zeros((3,300), dtype=bool)
    masks[0,:272] = 1; masks[1,:273] = 1; masks[2,:300] = 1
    keys = [('S',t) for t in METHOD['source']['sessions']]
    arrays, rows, _ = oracle.derive_connectomes(means,masks,keys,['all_frames','censored'])
    qc, _, people, _ = oracle.summaries(arrays,masks,keys,METHOD,rows,'resource_pilot')
    assert [r['duration_qc_pass'] for r in qc] == [False,True,True]
    assert not people[0]['qc_pass']


@pytest.mark.parametrize('n_common', [0,1,2])
def test_zero_one_two_common_rois(n_common):
    means = np.ones((3,6,3))
    means[:,:,:n_common] = np.random.default_rng(13).normal(size=(3,6,n_common))
    masks = np.ones((3,6),dtype=bool)
    keys = [('S',t) for t in METHOD['source']['sessions']]
    arrays, rows, _ = oracle.derive_connectomes(means,masks,keys,['all_frames','censored'])
    assert np.sum(arrays['common_roi']) == n_common
    assert np.sum(arrays['edge_valid']) == n_common*(n_common-1)//2
    _, pairs, _, _ = oracle.summaries(arrays,masks,keys,METHOD,rows,'resource_pilot')
    assert all(p['status'] == 'insufficient_common_edges' for p in pairs)


@pytest.mark.parametrize('placement', ['equal','output_under_source','source_under_output','private_under_output','equal_outputs'])
def test_evidence_paths_disjoint(tmp_path, placement):
    source, output, private = (tmp_path/name for name in ('source','output','private'))
    source.mkdir()
    if placement == 'equal': output = source
    elif placement == 'output_under_source': output = source/'out'
    elif placement == 'source_under_output': output = tmp_path
    elif placement == 'private_under_output': private = output/'private'
    elif placement == 'equal_outputs': private = output
    with pytest.raises(ValueError):
        oracle.prepare_destinations(source,output,private)


def test_symlink_ancestor_refused(tmp_path):
    actual = tmp_path/'actual'; actual.mkdir(); link = tmp_path/'link'; link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlink'):
        oracle.prepare_destinations(tmp_path/'source',link/'out',tmp_path/'private')


@pytest.mark.parametrize('placement', ['output_under_source','private_under_source','equal_outputs'])
def test_parent_traversal_normalized_before_overlap_check(tmp_path,placement):
    source = tmp_path/'source'; source.mkdir()
    output, private = tmp_path/'out',tmp_path/'private'
    if placement == 'output_under_source':
        output = tmp_path/'alias'/'..'/'source'/'output'
    elif placement == 'private_under_source':
        private = tmp_path/'alias'/'..'/'source'/'private'
    else:
        private = tmp_path/'alias'/'..'/'out'
    with pytest.raises(ValueError, match='disjoint'):
        oracle.prepare_destinations(source,output,private)
    assert not any(source.iterdir())
    assert not (tmp_path/'alias').exists()


def test_existing_evidence_preserved(tmp_path):
    output = tmp_path/'output'; output.mkdir(); evidence = output/'keep'; evidence.write_bytes(b'original')
    with pytest.raises(ValueError, match='existing'):
        oracle.prepare_destinations(tmp_path/'source',output,tmp_path/'private')
    assert evidence.read_bytes() == b'original'
    assert not (tmp_path/'private').exists()


def test_local_and_harbor_stager_layouts(tmp_path):
    local = tmp_path/'task'/'environment'/'stage_data.py'; local.parent.mkdir(parents=True); local.write_text('')
    assert oracle.stage_helper_path(tmp_path/'task'/'solution'/'compute.py') == local
    assert oracle.stage_helper_path('/solution/compute.py') == Path('/opt/source/stage_data.py')


def test_failure_cli_is_nonzero_and_writes_findings(tmp_path):
    output, private = tmp_path/'out', tmp_path/'private'
    command = [sys.executable, str(ROOT/'solution'/'compute.py'), '--data-dir', str(tmp_path/'missing-source'),
        '--method-contract', str(tmp_path/'missing-method'), '--output-dir', str(output), '--private-dir', str(private)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    assert result.returncode == 1
    assert json.loads((output/'reliability_stats.json').read_text())['status'] == 'failed_precondition'
    assert json.loads((output/'failure.json').read_text())['reason']
    assert (output/'findings.md').read_text().strip()


def test_actual_solve_sh_entrypoint_missing_inputs(tmp_path):
    output, private = tmp_path/'out',tmp_path/'private'
    environment = dict(os.environ, SOURCE_DIR=str(tmp_path/'absent-source'),
        METHOD_CONTRACT=str(tmp_path/'absent-method'),OUTPUT_DIR=str(output),PRIVATE_DIR=str(private))
    result = subprocess.run([str(ROOT/'solution'/'solve.sh')],env=environment,text=True,capture_output=True,timeout=30)
    assert result.returncode == 1
    assert json.loads((output/'failure.json').read_text())['status'] == 'failed_precondition'
    assert (output/'findings.md').is_file()


def test_method_symlink_and_wrong_pin(tmp_path):
    method = tmp_path/'method.json'; method.write_text('{}')
    with pytest.raises(ValueError, match='SHA256'):
        oracle.load_inputs(tmp_path/'source', method)
    link = tmp_path/'link'; link.symlink_to(method)
    with pytest.raises(ValueError, match='Symlink'):
        oracle.load_inputs(tmp_path/'source', link)


def toy_inputs(tmp_path, monkeypatch):
    method = copy.deepcopy(METHOD)
    method['geometry']['mni_to_world_matrix'] = np.eye(4).tolist()
    atlas = tmp_path/'atlas.csv'
    with atlas.open('w') as stream:
        writer = csv.writer(stream); writer.writerow(['ROI','X','Y','Z'])
        writer.writerows((i,0,0,0) for i in range(1,265))
    transform = tmp_path/'transform'; transform.write_text('t4\n1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n')
    records = {}; files = []
    for subject in method['source']['subjects']:
        for session in method['source']['sessions']:
            for role in ('bold','tmask'):
                item = dict(subject=subject,session=session,role=role,path=subject+session+role,size_bytes=1,
                    sha256='0'*64,published_md5='0'*32,git_blob_sha1='0'*40,version_id='toy',etag='toy')
                records[subject,session,role] = item; files.append(item)
    inputs = dict(root=tmp_path,method=method,records=records,manifest={'files':files},
                  auxiliary=dict(atlas_coordinates=atlas,point_transform=transform))
    monkeypatch.setattr(oracle,'load_inputs',lambda *args: inputs)
    monkeypatch.setattr(oracle,'inspect_header',lambda p,e,s,t: dict(subject_id=s,session_id=t))
    geometry = dict(centres=np.zeros((264,3)), offsets=np.arange(265),ijk=np.zeros((264,3),dtype=int),
        union=np.zeros((1,3),dtype=int),membership_to_union=np.zeros(264,dtype=int),boundary=np.ones(264))
    monkeypatch.setattr(oracle,'sphere_geometry',lambda *args: geometry)
    monkeypatch.setattr(oracle,'load_mask',lambda *args: np.ones(818,dtype=bool))
    means = np.tile(np.arange(818,dtype=np.float64)[:,None],(1,264))
    monkeypatch.setattr(oracle,'source_means',lambda *args: (means,np.repeat(817.,264),means[:,:1].astype(np.float32)))
    return inputs


def test_complete_synthetic_pilot_nine_artifacts_and_private(tmp_path, monkeypatch):
    toy_inputs(tmp_path,monkeypatch)
    output, private = tmp_path/'out', tmp_path/'private'; output.mkdir(); private.mkdir()
    result = oracle.run(tmp_path/'source',tmp_path/'method',output,private,'MSC01')
    assert result['status'] == 'resource_pilot' and result['n_runs'] == 3
    assert {p.name for p in output.iterdir()} == set(METHOD['serialization']['required_files'])
    with np.load(output/'connectivity_arrays.npz',allow_pickle=False) as arrays:
        assert set(arrays.files) == set(METHOD['outputs']['connectivity_arrays.npz']['arrays'])
        assert arrays['roi_means'].shape == (3,818,264)
    with np.load(private/'analysis_arrays.npz',allow_pickle=False) as arrays:
        assert arrays['source_voxels_MSC01_func01'].dtype == np.float32
    metadata = json.loads((output/'run_metadata.json').read_text())
    assert metadata['source_observed']['n_runs'] == 18 and len(metadata['source_observed']['headers']) == 18


def test_private_failure_never_publishes_complete_status(tmp_path,monkeypatch):
    toy_inputs(tmp_path,monkeypatch)
    original = oracle.save_npz
    def fail_private(path, arrays):
        if Path(path).name == 'analysis_arrays.npz':
            raise OSError('fixture private write failure')
        original(path,arrays)
    monkeypatch.setattr(oracle,'save_npz',fail_private)
    output, private = tmp_path/'out',tmp_path/'private'
    assert oracle.main(['--data-dir',str(tmp_path/'source'),'--output-dir',str(output),'--private-dir',str(private),
                        '--pilot-subject','MSC01']) == 1
    assert json.loads((output/'run_metadata.json').read_text())['status'] == 'failed_precondition'
    assert json.loads((output/'reliability_stats.json').read_text())['status'] == 'failed_precondition'
