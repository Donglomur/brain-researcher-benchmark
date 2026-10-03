"""Fabricated source bases and output receipts; no original scientific inputs."""
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

HERE=Path(__file__).parent
for name in ('io_contract','verify_artifacts'):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
V=sys.modules['verify_artifacts']


def header(shape):
    return dict(shape=shape,selected_affine=np.eye(4).tolist(),storage_dtype='<f4',spatial_units='mm',temporal_units='sec',
        zooms=[1.,1.,1.,2.][:len(shape)],raw_toffset=0.,raw_scl_slope='NaN',raw_scl_inter='NaN',
        effective_slope=1.,effective_intercept=0.)


@pytest.fixture
def fabricated(monkeypatch):
    ids=[f'sub-pixar{i:03d}' for i in range(1,10)]
    monkeypatch.setattr(V,'SUBJECT_IDS',tuple(ids)); monkeypatch.setattr(V,'N_CHILDREN',6); monkeypatch.setattr(V,'N_ADULTS',3)
    for name,value in (('SOURCE_SHA','1'*64),('METHOD_SHA','2'*64),('SCHEMA_SHA','3'*64)):
        monkeypatch.setattr(V,name,value)
    kernel=(HERE/'reporting_kernel.py').read_bytes()
    monkeypatch.setattr(V,'KERNEL_SHA',hashlib.sha256(kernel).hexdigest()); V.bind_reporting_kernel(kernel)
    rng=np.random.default_rng(8342)
    canonical=dict(status='complete',subject_ids=ids,roi_ids=list(V.ROI_IDS),pipeline_ids=list(V.PIPELINE_IDS),
        pins=V.pins(),persons={},covariates={},cohort=[],source_files=[],roi_definitions=[],
        source_observed=dict(participants_column_names=['participant_id','Age','Child_Adult'],persons=[],
            frame_alignment='Original released rows, no measured movie-onset claim',
            template=dict(path='template.nii.gz',sha256='4'*64,header=header([3,4,5]),
                          normalization=dict(dtype='float32',operator='divide_by_global_maximum',maximum=20.))),
        analysis_observed=dict(persons=[],child_motion_nuisance_rank=2))
    for index,sid in enumerate(ids):
        n=16+index%3
        clean=rng.normal(size=(n,2,12)); clean-=clean.mean(axis=0)
        raw=rng.normal(size=(n,12)); gs=rng.normal(size=n)
        canonical['persons'][sid]=dict(raw_roi=raw,global_signal=gs,cleaned_roi=clean,
            canonical_active=np.ones((2,12),dtype=bool),frame_indices=np.arange(n))
        cov=dict(age=float(5+(index*3)%11),group='child' if index<6 else 'adult',mean_fd=.1+((index*7)%13)/100.)
        canonical['covariates'][sid]=cov
        canonical['cohort'].append(dict(subject_id=sid,**cov,mean_fd_observed_count=n-1,mean_fd_missing_frame_indices=[0]))
        for role in ('bold','confounds'):
            canonical['source_files'].append(dict(path=sid+'.'+role,role=role,subject_id=sid,size_bytes=100,sha256='5'*64))
        canonical['source_observed']['persons'].append(dict(subject_id=sid,bold_path=sid+'.bold',confounds_path=sid+'.confounds',
            bold_header=header([3,4,5,n]),frame_count=n,confound_column_names=['fd','motion','unused'],
            selected_confound_columns=['motion','fd'],excluded_confound_columns=['unused'],
            missing_selected_entries=[dict(frame_index=0,column_name='fd',original_token='n/a',applied_value=0.)],
            mean_fd_sum=float(cov['mean_fd']*(n-1)),mean_fd_observed_count=n-1,
            roi_supports=[dict(roi_id=rid,n_voxels=2,support_sha256='6'*64) for rid in V.ROI_IDS],
            global_support=dict(n_voxels=20,support_sha256='7'*64)))
        canonical['analysis_observed']['persons'].append(dict(subject_id=sid,pipelines=[
            dict(pipeline_id=arm,cleaning_rank=3,n_active_rois=12,roi_activity=[dict(roi_id=rid,raw_centered_l2=5.,
                residual_centered_l2=2.,activity_threshold=5e-12,active=True) for rid in V.ROI_IDS]) for arm in V.PIPELINE_IDS]))
    for rid in V.ROI_IDS:
        canonical['roi_definitions'].append(dict(roi_id=rid,network='ToM' if rid in V.ROI_IDS[:6] else 'pain',center_mm=[0,1,2],radius_mm=9.))
    return canonical,output_for(canonical)


def replay(canonical,arrays):
    accepted,reference,active=V.canonical_primitives(arrays,canonical)
    return V._KERNEL.analyze(accepted,reference,active,canonical['covariates'],canonical['subject_ids'],
                             expected_children=V.N_CHILDREN,expected_adults=V.N_ADULTS)


def refresh_receipts(actual,canonical):
    result=replay(canonical,actual['signal_evidence.npz'])
    actual['network_connectivity.csv']=[{key:('' if value is None else str(value)) for key,value in row.items()}
                                      for row in result['participant_rows']]
    actual['age_effects.json']=dict(schema_version='socialbrain-results-v2',task_id='SOCIALBRAIN-001',status='complete',
        **{k:v for k,v in canonical['pins'].items() if k!='reporting_kernel_sha256'},**result['age_effects'])
    actual['run_metadata.json']['analysis_observed']['child_motion_nuisance_rank']=result['analysis_observed']['child_motion_nuisance_rank']


def output_for(canonical):
    ids=canonical['subject_ids']; people=canonical['persons']
    arrays=dict(subject_ids=np.asarray(ids),roi_ids=np.asarray(V.ROI_IDS),pipeline_ids=np.asarray(V.PIPELINE_IDS),
        frame_subject_ids=np.concatenate([np.repeat(sid,len(people[sid]['frame_indices'])) for sid in ids]),
        frame_indices=np.concatenate([people[sid]['frame_indices'] for sid in ids]),
        raw_roi=np.concatenate([people[sid]['raw_roi'] for sid in ids]),
        global_signal=np.concatenate([people[sid]['global_signal'] for sid in ids]),
        cleaned_roi=np.concatenate([people[sid]['cleaned_roi'] for sid in ids]),
        canonical_active=np.stack([people[sid]['canonical_active'] for sid in ids]))
    metadata=dict(schema_version='socialbrain-metadata-v2',task_id='SOCIALBRAIN-001',dataset_id='ds000228',status='complete',
        **canonical['pins'],analysis_scope='Fabricated method-control fixture',warnings=[],
        software_versions={key:'actual-fixture-version' for key in ('python','numpy','scipy','nibabel','nilearn','scikit_learn')},
        **{key:copy.deepcopy(canonical[key]) for key in ('cohort','roi_definitions','source_files','source_observed','analysis_observed')})
    actual={'signal_evidence.npz':arrays,'run_metadata.json':metadata,'findings.md':'Either sign and either pipeline ordering are allowed.'}
    refresh_receipts(actual,canonical); return actual


def test_complete_genuine_and_no_input_mutation(fabricated):
    canonical,actual=fabricated; saved=copy.deepcopy(actual)
    assert V.verify_artifacts(actual,canonical)==dict(status='ok',n_subjects=9,n_children=6,n_adults=3)
    for key,array in saved['signal_evidence.npz'].items(): assert np.array_equal(array,actual['signal_evidence.npz'][key])
    for key in ('network_connectivity.csv','age_effects.json','run_metadata.json','findings.md'): assert actual[key]==saved[key]


def test_coherent_every_axis_and_keyed_record_permutation(fabricated):
    canonical,actual=fabricated; a=actual['signal_evidence.npz']; n=len(a['frame_indices'])
    frame=np.arange(n)[::-1]; roi=np.arange(12)[::-1]; arm=[1,0]; subject=np.arange(9)[::-1]
    for key in ('frame_indices','frame_subject_ids','global_signal'): a[key]=a[key][frame]
    a['raw_roi']=a['raw_roi'][frame][:,roi]; a['cleaned_roi']=a['cleaned_roi'][frame][:,arm][:,:,roi]
    a['canonical_active']=a['canonical_active'][subject][:,arm][:,:,roi]
    a['roi_ids']=a['roi_ids'][roi]; a['pipeline_ids']=a['pipeline_ids'][arm]; a['subject_ids']=a['subject_ids'][subject]
    actual['network_connectivity.csv'].reverse(); m=actual['run_metadata.json']
    for key in ('cohort','source_files','roi_definitions'): m[key].reverse()
    m['source_observed']['persons'].reverse(); m['analysis_observed']['persons'].reverse()
    for person in m['source_observed']['persons']: person['roi_supports'].reverse()
    for person in m['analysis_observed']['persons']:
        person['pipelines'].reverse()
        for pipeline in person['pipelines']: pipeline['roi_activity'].reverse()
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


def test_value_integral_axes_byte_strings_and_dtype_aliases(fabricated):
    canonical,actual=fabricated; a=actual['signal_evidence.npz']; a['frame_indices']=a['frame_indices'].astype(float)
    for key in ('subject_ids','roi_ids','pipeline_ids','frame_subject_ids'): a[key]=a[key].astype('S32')
    m=actual['run_metadata.json']; m['source_observed']['template']['header']['storage_dtype']='float32'
    for person in m['source_observed']['persons']: person['bold_header']['storage_dtype']='float32'
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


class NoListConversion(np.ndarray):
    def tolist(self):
        raise AssertionError('malformed axis reached Python-list allocation')


@pytest.mark.parametrize('axis',['subject_ids','roi_ids','pipeline_ids','frame_subject_ids'])
@pytest.mark.parametrize('dtype',['S0','U0'])
def test_required_string_shape_checked_before_conversion(fabricated,axis,dtype):
    canonical,actual=fabricated
    # Tiny logical shape exercises the same guard without a huge allocation.
    value=np.ndarray((1,),dtype=np.dtype(dtype),buffer=b'').view(NoListConversion)
    assert value.dtype.itemsize==0
    actual['signal_evidence.npz'][axis]=value
    with pytest.raises(ValueError,match='string_axis'):
        V.verify_artifacts(actual,canonical)


@pytest.mark.parametrize('dtype',['S0','U0'])
def test_zero_width_optional_arrays_remain_permitted(fabricated,dtype):
    canonical,actual=fabricated
    actual['signal_evidence.npz']['optional']=np.ndarray((2,3),dtype=np.dtype(dtype),buffer=b'').view(NoListConversion)
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


def test_roi_coordinates_allow_json_numeric_float_spelling(fabricated):
    canonical,actual=fabricated
    for row in actual['run_metadata.json']['roi_definitions']:
        row['center_mm']=[float(value) for value in row['center_mm']]
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


@pytest.mark.parametrize('sign',[-1.,1.])
def test_csv_metric_domain_is_strict_even_within_receipt_tolerance(fabricated,sign):
    canonical,actual=fabricated
    expected=replay(canonical,actual['signal_evidence.npz'])
    expected['participant_rows'][0]['within_tom']=sign*.999999
    actual['network_connectivity.csv'][0]['within_tom']=str(sign*(1.+5e-7))
    with pytest.raises(ValueError,match='metric_domain'):
        V.validate_table(actual['network_connectivity.csv'],expected)


def test_own_series_change_and_six_decimal_receipts_are_valid(fabricated):
    canonical,actual=fabricated; a=actual['signal_evidence.npz']
    a['cleaned_roi']=a['cleaned_roi']*(1+2e-8)+1e-9; refresh_receipts(actual,canonical)
    for row in actual['network_connectivity.csv']:
        for key in V.METRICS: row[key]=format(float(row[key]),'.6f')
    def rounded(value):
        if type(value) is float: return round(value,6)
        if type(value) is list: return [rounded(x) for x in value]
        if type(value) is dict: return {k:rounded(v) for k,v in value.items()}
        return value
    actual['age_effects.json']=rounded(actual['age_effects.json'])
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


def test_bounded_harmless_extras_and_free_prose(fabricated):
    canonical,actual=fabricated; actual['signal_evidence.npz']['optional']=np.ones((1,)*32)
    actual['run_metadata.json']['free']=dict(note='any wording',numbers=[1.,2.])
    actual['run_metadata.json']['software_versions']['numpy']='different-compatible-version'
    actual['run_metadata.json']['source_observed']['frame_alignment']='Released row ordering, no measured onset'
    actual['age_effects.json']['note']='No chosen direction'
    for row in actual['network_connectivity.csv']: row['harmless']='annotation'
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


@pytest.mark.parametrize('mode',['subject_duplicate','roi_label','pipeline_label','frame_duplicate','frame_fractional','frame_bool',
    'raw_bool','raw_offset','gs_offset','clean_offset','active_integer','active_flip','nonfinite_extra','object_extra'])
def test_primitive_binding_mutations(fabricated,mode):
    canonical,actual=fabricated; a=actual['signal_evidence.npz']
    if mode=='subject_duplicate': a['subject_ids'][1]=a['subject_ids'][0]
    elif mode=='roi_label': a['roi_ids'][0]='wrong'
    elif mode=='pipeline_label': a['pipeline_ids'][0]='other'
    elif mode=='frame_duplicate': a['frame_indices'][1]=a['frame_indices'][0]
    elif mode=='frame_fractional': a['frame_indices']=a['frame_indices'].astype(float); a['frame_indices'][0]=.5
    elif mode=='frame_bool': a['frame_indices']=a['frame_indices'].astype(bool)
    elif mode=='raw_bool': a['raw_roi']=a['raw_roi'].astype(bool)
    elif mode=='raw_offset': a['raw_roi'][0,0]+=.1
    elif mode=='gs_offset': a['global_signal'][0]+=.1
    elif mode=='clean_offset': a['cleaned_roi'][0,0,0]+=.1
    elif mode=='active_integer': a['canonical_active']=a['canonical_active'].astype(int)
    elif mode=='active_flip': a['canonical_active'][0,0,0]=False
    elif mode=='nonfinite_extra': a['extra']=np.array([np.nan])
    else: a['extra']=np.array([object()],dtype=object)
    with pytest.raises(ValueError): V.verify_artifacts(actual,canonical)


@pytest.mark.parametrize('mode',['csv_bool','csv_metric','csv_fd','csv_null','csv_duplicate','json_bool','json_integer_float',
    'r_domain','p_domain','adult_domain','status','source_pin','count','extra_metric','missing_field'])
def test_downstream_receipts_are_typed_and_own_replayed(fabricated,mode):
    canonical,actual=fabricated; row=actual['network_connectivity.csv'][0]; result=actual['age_effects.json']
    if mode=='csv_bool': row['within_tom']=True
    elif mode=='csv_metric': row['within_tom']=str(-1. if float(row['within_tom'])>0 else 1.)
    elif mode=='csv_fd': row['mean_fd']='999'
    elif mode=='csv_null': row['within_tom']=''
    elif mode=='csv_duplicate': actual['network_connectivity.csv'][1]=copy.deepcopy(row)
    elif mode=='json_bool': result['within_tom']['r']=True
    elif mode=='json_integer_float': result['within_tom']['n_defined']=float(result['within_tom']['n_defined'])
    elif mode=='r_domain': result['within_tom']['r']=1.00000001
    elif mode=='p_domain': result['within_tom']['p']=-1e-9
    elif mode=='adult_domain': result['adult_means']['within_tom']=1.00000001
    elif mode=='status': result['within_tom']['status']='made_up'
    elif mode=='source_pin': result['source_manifest_sha256']='0'*64
    elif mode=='count': result['within_tom']['n_defined']-=1
    elif mode=='extra_metric': result['adult_means']['new']=0.
    else: del result['within_tom']['p']
    with pytest.raises(ValueError): V.verify_artifacts(actual,canonical)


@pytest.mark.parametrize('mode',['header_dtype','header_affine','ordered_headers','source_hash','source_duplicate','cohort_count_bool',
    'missing_token','support_hash','activity_bool','cleaning_rank','warnings','extra_inf','normalization_dtype','empty_scope'])
def test_source_metadata_fields_and_semantic_dtype_scope(fabricated,mode):
    canonical,actual=fabricated; m=actual['run_metadata.json']; p=m['source_observed']['persons'][0]
    if mode=='header_dtype': p['bold_header']['storage_dtype']='>f4'
    elif mode=='header_affine': p['bold_header']['selected_affine'][0][3]+=1.
    elif mode=='ordered_headers': p['confound_column_names'].reverse()
    elif mode=='source_hash': m['source_files'][0]['sha256']='0'*64
    elif mode=='source_duplicate': m['source_files'][1]=copy.deepcopy(m['source_files'][0])
    elif mode=='cohort_count_bool': m['cohort'][0]['mean_fd_observed_count']=True
    elif mode=='missing_token': p['missing_selected_entries'][0]['original_token']=''
    elif mode=='support_hash': p['roi_supports'][0]['support_sha256']='0'*64
    elif mode=='activity_bool': m['analysis_observed']['persons'][0]['pipelines'][0]['roi_activity'][0]['active']=1
    elif mode=='cleaning_rank': m['analysis_observed']['persons'][0]['pipelines'][0]['cleaning_rank']+=1
    elif mode=='warnings': m['warnings']=[dict(message='not string')]
    elif mode=='extra_inf': m['extra']={'x':float('inf')}
    elif mode=='normalization_dtype': m['source_observed']['template']['normalization']['dtype']='f4'
    else: m['analysis_scope']=''
    with pytest.raises(ValueError): V.verify_artifacts(actual,canonical)


def test_nulls_keep_every_subject_and_inactive_jitter_ignored(fabricated):
    canonical,_=fabricated; sid=canonical['subject_ids'][0]
    canonical['persons'][sid]['canonical_active'][0,0]=False
    canonical['persons'][sid]['cleaned_roi'][:,0,0]=0
    pipeline=canonical['analysis_observed']['persons'][0]['pipelines'][0]
    pipeline['roi_activity'][0]['active']=False; pipeline['n_active_rois']=11
    actual=output_for(canonical); a=actual['signal_evidence.npz']; n=len(canonical['persons'][sid]['frame_indices'])
    a['cleaned_roi'][:n,0,0]=np.linspace(-5e-8,5e-8,n); refresh_receipts(actual,canonical)
    assert actual['network_connectivity.csv'][0]['within_tom']==''
    assert actual['age_effects.json']['within_tom']['status']=='incomplete_subject_support'
    assert V.verify_artifacts(actual,canonical)['status']=='ok'


@pytest.mark.parametrize('mode',['kernel_unbound','pin_unfrozen','pilot','partial_ids','wrong_source_pin'])
def test_private_authority_cannot_be_supplied_by_artifacts(fabricated,monkeypatch,mode):
    canonical,actual=fabricated
    if mode=='kernel_unbound': monkeypatch.setattr(V,'_KERNEL',None)
    elif mode=='pin_unfrozen': monkeypatch.setattr(V,'SOURCE_SHA',None)
    elif mode=='pilot': canonical['status']='resource_pilot'
    elif mode=='partial_ids': canonical['subject_ids']=canonical['subject_ids'][:-1]
    else: canonical['pins']['source_manifest_sha256']='0'*64
    with pytest.raises(ValueError): V.verify_artifacts(actual,canonical)


def test_wrong_kernel_bytes_fail_before_execution(fabricated):
    with pytest.raises(ValueError,match='private_kernel_identity'):
        V.bind_reporting_kernel(b'raise RuntimeError("must not execute")')


def write_artifacts(root,actual):
    root.mkdir()
    np.savez_compressed(root/'signal_evidence.npz',**actual['signal_evidence.npz'])
    with (root/'network_connectivity.csv').open('x',newline='') as stream:
        rows=actual['network_connectivity.csv']; writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    for name in ('age_effects.json','run_metadata.json'):
        (root/name).write_text(json.dumps(actual[name],allow_nan=False))
    (root/'findings.md').write_text(actual['findings.md'])


def test_complete_file_parser_to_pure_validator_integration(fabricated,tmp_path):
    canonical,actual=fabricated; root=tmp_path/'output'; write_artifacts(root,actual)
    assert V.validate_output_directory(root,canonical)['status']=='ok'


def test_failure_marker_after_scientific_replay_still_rejects(fabricated,tmp_path,monkeypatch):
    canonical,actual=fabricated; root=tmp_path/'output'; write_artifacts(root,actual)
    original=V._KERNEL.analyze
    def analyze(*args,**kwargs):
        result=original(*args,**kwargs); (root/'failure_report.json').write_text('{}'); return result
    monkeypatch.setattr(V._KERNEL,'analyze',analyze)
    with pytest.raises(ValueError,match='failed_run_marker'): V.validate_output_directory(root,canonical)
