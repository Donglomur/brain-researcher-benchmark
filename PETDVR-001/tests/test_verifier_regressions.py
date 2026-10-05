"""Synthetic full-grid mechanics only; never an original-data reference bank."""
import copy
import csv
import json
from pathlib import Path
import numpy as np
import pytest
import build_reference as b
import proof_of_work as q

ROOT=Path(__file__).resolve().parents[1]

def fixture_payload():
    contract=json.loads((ROOT/'environment/method_contract.json').read_text())
    frames=[]
    for scan_index,(subject,session) in enumerate(b.SCANS):
        for i in range(6):
            row=dict(subject=subject,session=session,frame_index=i,frame_start_s=i*600.,frame_end_s=(i+1)*600.,
                     frame_duration_s=600.,frame_mid_s=(i+.5)*600.,reference=0. if i==0 else 1+i*.4)
            for target_index,target in enumerate(b.TARGETS):
                row[target]=(i+1)**.7+.1*target_index+.03*scan_index
            if i==0:row['highbinding']=0.
            frames.append(row)
    tables=b.analyze_frames(frames)
    meta=dict(status='ok',task_id='PETDVR-001',pipeline_id=b.PIPELINE,source_manifest_sha256=b.MANIFEST_SHA,
              method_contract_sha256=b.METHOD_SHA,source_sha256={'synthetic-fixture':'0'*64},method_contract=contract,
              source_observed={'scans':[dict(subject=s,session=e,n_frames=6) for s,e in b.SCANS]},software_versions={'fixture':'mechanics only'})
    return dict(pipeline_id=b.PIPELINE,provenance='synthetic-mechanics-not-production',tables=tables,summary=b.summaries(tables['window_fits.csv']),metadata=meta)

def write_payload(path,payload):
    path.mkdir(parents=True,exist_ok=True)
    for name,rows in payload['tables'].items():
        with (path/name).open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=payload['metadata']['method_contract']['outputs'][name])
            writer.writeheader();writer.writerows(rows)
    (path/'summary.json').write_text(json.dumps(payload['summary'],allow_nan=False))
    (path/'run_metadata.json').write_text(json.dumps(payload['metadata'],allow_nan=False))
    (path/'findings.md').write_text('Measured numerical sensitivity, without a required direction.')
    return path

@pytest.fixture
def output(tmp_path):
    reference=fixture_payload()
    return write_payload(tmp_path/'output',reference),reference

def test_synthetic_all_scans_targets_windows_and_undefined(output):
    path,ref=output
    assert len(ref['tables']['window_fits.csv'])==280
    assert len(ref['summary']['paired_changes'])==140 and len(ref['summary']['group_windows'])==70
    assert any(row['fit_status']=='insufficient_frames' for row in ref['tables']['window_fits.csv'])
    q.validate_output_directory(path,ref)

@pytest.mark.parametrize('value',[1,'1','1.0','1e0',' 1 '])
def test_integer_format(value):assert q.integer(value)==1

@pytest.mark.parametrize('value',[True,False,'true','inf','NaN','1.1','frame1',''])
def test_bad_integer(value):
    with pytest.raises(AssertionError):q.integer(value)

@pytest.mark.parametrize('value',[True,False,float('inf'),'nan',None,{},[]])
def test_bad_numeric(value):
    with pytest.raises(AssertionError):q.number(value)

@pytest.mark.parametrize('value,expected',[('true',True),('FALSE',False),('1.0',True),('0e0',False),(True,True)])
def test_boolean_notation(value,expected):assert q.boolean(value) is expected

@pytest.mark.parametrize('value',[2,-1,'yes','NaN',''])
def test_bad_boolean(value):
    with pytest.raises(AssertionError):q.boolean(value)

def test_original_frame_integral_includes_zero_negative_history():
    assert b.integral([2.,0.,-1.],[1.,2.,4.])==[1.,2.,0.]

def test_no_zero_origin_trapezoid_substitution():
    values=[2.,4.];duration=[1.,3.]
    assert b.integral(values,duration)==[1.,8.]
    assert b.integral(values,duration)[1]!=1.+.5*(2+4)*2

@pytest.mark.parametrize('x,y,status',[
    ([],[],'insufficient_frames'),([1],[1],'insufficient_frames'),([1,2],[2,3],'insufficient_frames'),
    ([1,1,1],[1,2,3],'rank_deficient_under_public_rule'),
    ([1,2,3],[3,5,7],'ok'),([1,2,3],[5,3,1],'ok'),([1,2,3],[0,0,0],'ok')])
def test_ols_explicit_outcomes(x,y,status):
    row,pred=b.fit_line(x,y)
    assert row['fit_status']==status
    assert len(pred)==(len(x) if status=='ok' else 0)
    if status!='ok':assert row['logan_slope'] is None and row['sse_min2'] is None

def test_constant_y_slope_zero_not_rejected():
    row,pred=b.fit_line([1,2,3],[5,5,5])
    assert row['logan_slope']==0 and row['r_squared'] is None and row['r_squared_status']=='constant_y'

def test_exact_constant_decimal_moments():
    row,_=b.fit_line([1,2,3],[.1,.1,.1])
    assert row['Syy_min2']==0 and row['r_squared_status']=='constant_y' and row['logan_slope']==0
    row,_=b.fit_line([.1,.1,.1],[1,2,3])
    assert row['Sxx_min2']==0 and row['fit_status']=='rank_deficient_under_public_rule'
    ratio=b.ratio_statistics([.1,.1,.1],[.1,.1,.1])
    assert ratio['ratio_population_sd']==0 and ratio['ratio_cv']==0
    assert ratio['ratio_trend_status']=='insufficient_distinct_times'

def test_rank_threshold_is_not_exact_mathematical_rank():
    row,_=b.fit_line([1,1+1e-13,1+2e-13],[1,2,3])
    assert row['Sxx_min2']>0 and row['fit_status']=='rank_deficient_under_public_rule'

@pytest.mark.parametrize('times,values,cv,trend',[
    ([],[],'no_valid_ratio','no_valid_ratio'),([1],[0.],'zero_mean','insufficient_distinct_times'),
    ([1],[2.],'ok','insufficient_distinct_times'),([1,2],[-1.,1.],'zero_mean','ok'),
    ([1,1],[1.,2.],'ok','insufficient_distinct_times'),([1,2],[-2.,-1.],'ok','ok')])
def test_ratio_support_signed_and_zero_mean(times,values,cv,trend):
    row=b.ratio_statistics(times,values)
    assert row['ratio_cv_status']==cv and row['ratio_trend_status']==trend
    if row['ratio_cv'] is not None:assert row['ratio_cv']>=0

def test_member_rows_survive_undefined_fit(output):
    _,ref=output
    fits=q.keyed(ref['tables']['window_fits.csv'],q.KEYS['window_fits.csv'])
    points=q.keyed(ref['tables']['fit_points.csv'],q.KEYS['fit_points.csv'])
    for key,fit in fits.items():
        rows=[p for p in points if p[:-1]==key]
        assert len(rows)==fit['n_window']
        if fit['fit_status']!='ok':
            assert all(not points[p]['in_fit'] and points[p]['predicted_y_min'] is None for p in rows)

def test_metadata_versions_and_unknown_optional_extras(output):
    path,ref=output;data=copy.deepcopy(ref)
    data['metadata']['software_versions']={'alternative':'honest actual implementation'}
    data['metadata']['source_observed']['scans'].reverse()
    data['metadata']['source_observed']['extra']='ungraded'
    data['metadata']['source_observed']['scans'][0]['extra']='ungraded'
    data['summary']['optional_reference_multilinear']=999
    data['summary']['paired_changes'].reverse();data['summary']['group_windows'].reverse()
    for row in data['summary']['group_windows']:
        row['defined_scans'].reverse();row['represented_subjects'].reverse();row['defined_pair_subjects'].reverse()
    write_payload(path,data);q.validate_output_directory(path,ref)

@pytest.mark.parametrize('name',list(q.KEYS))
@pytest.mark.parametrize('kind',['drop','duplicate','wrong_identity'])
def test_complete_tables_no_fractional_coverage(output,name,kind):
    path,ref=output;data=copy.deepcopy(ref);rows=data['tables'][name]
    if kind=='drop':rows.pop()
    elif kind=='duplicate':rows.append(dict(rows[0]))
    else:rows[0]['subject']='sub-99'
    write_payload(path,data)
    with pytest.raises(AssertionError):q.validate_output_directory(path,ref)

@pytest.mark.parametrize('kind',['fabricated_source','bad_integral','clipped_ratio','wrong_slope','zero_undefined','tiny_rank','wrong_status','wrong_residual'])
def test_source_numeric_and_undefined_negatives(output,kind):
    path,ref=output;data=copy.deepcopy(ref)
    if kind=='fabricated_source':data['tables']['source_frames.csv'][0]['reference']=3.
    elif kind=='bad_integral':data['tables']['graph_points.csv'][0]['integral_reference_bq_min_per_ml']=100.
    elif kind=='clipped_ratio':next(r for r in data['tables']['graph_points.csv'] if r['ratio_status']=='ok')['target_over_reference']=1.
    elif kind=='wrong_slope':next(r for r in data['tables']['window_fits.csv'] if r['fit_status']=='ok')['logan_slope']+=1
    elif kind=='zero_undefined':next(r for r in data['tables']['window_fits.csv'] if r['fit_status']!='ok')['logan_slope']=0.
    elif kind=='tiny_rank':next(r for r in data['tables']['window_fits.csv'] if r['rank_threshold_min2'] is not None)['rank_threshold_min2']*=2
    elif kind=='wrong_status':data['tables']['window_fits.csv'][0]['fit_status']='rank_deficient_under_public_rule'
    else:next(r for r in data['tables']['fit_points.csv'] if r['in_fit'])['residual_y_min']+=1
    write_payload(path,data)
    with pytest.raises(AssertionError):q.validate_output_directory(path,ref)

@pytest.mark.parametrize('kind',['source_extra','method_extra','manifest','missing_observation','empty_versions','summary_count','summary_mean','pair_sign'])
def test_metadata_and_summary_negatives(output,kind):
    path,ref=output;data=copy.deepcopy(ref)
    if kind=='source_extra':data['metadata']['source_sha256']['fabricated']='a'*64
    elif kind=='method_extra':data['metadata']['method_contract']['secret_filter']='yes'
    elif kind=='manifest':data['metadata']['source_manifest_sha256']='0'*64
    elif kind=='missing_observation':del data['metadata']['source_observed']['scans'][0]['n_frames']
    elif kind=='empty_versions':data['metadata']['software_versions']={}
    elif kind=='summary_count':data['summary']['n_subjects']=4
    elif kind=='summary_mean':next(r for r in data['summary']['group_windows'] if r['mean_logan_slope'] is not None)['mean_logan_slope']+=1
    else:next(r for r in data['summary']['paired_changes'] if r['pair_status']=='ok')['rescan_minus_baseline']+=1
    write_payload(path,data)
    with pytest.raises(AssertionError):q.validate_output_directory(path,ref)

def test_old_bank_and_fake_fixture_provenance_rejected(tmp_path):
    old=tmp_path/'old.npz';np.savez(old,ref_ids=['x'],ref_values=[3])
    with pytest.raises(AssertionError,match='Obsolete'):q.load_reference(old)
    fake=tmp_path/'fixture.npz';np.savez(fake,reference_json=json.dumps(fixture_payload()))
    with pytest.raises(AssertionError,match='provenance'):q.load_reference(fake)

def test_source_and_method_pin_bytes():
    assert b.sha(ROOT/'environment/method_contract.json')==b.METHOD_SHA==q.METHOD_SHA
    assert b.sha(ROOT/'environment/source_manifest.json')==b.MANIFEST_SHA==q.MANIFEST_SHA

def test_wrong_manifest_stops_before_any_tac(tmp_path):
    (tmp_path/'source_manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):b.load_source(tmp_path,ROOT/'environment/method_contract.json')

def test_offline_python3_and_independent_builder():
    shell=(ROOT/'tests/test.sh').read_text();source=(ROOT/'tests/build_reference.py').read_text()
    assert 'python3 -m pytest' in shell
    assert not any(token in shell for token in ('pip install','apt-get','curl','$HOME'))
    assert 'solution.compute' not in source and 'check_independent' not in source

@pytest.mark.parametrize('collection,field',[('paired_changes','rescan_minus_baseline'),('group_windows','mean_logan_slope'),('group_windows','mean_rescan_minus_baseline')])
def test_required_undefined_summary_field_cannot_be_omitted(output,collection,field):
    path,ref=output;data=copy.deepcopy(ref)
    row=next(r for r in data['summary'][collection] if r[field] is None)
    del row[field]
    write_payload(path,data)
    with pytest.raises(AssertionError,match='missing required'):q.validate_output_directory(path,ref)
