"""Synthetic-only numerical, status and evidence-safety fixtures."""
import copy
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest
from scipy import signal,stats

SPEC=importlib.util.spec_from_file_location('clinconn_oracle',Path(__file__).parents[1]/'solution/compute.py')
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)


def test_frozen_method_pin():
    p=Path(__file__).parents[1]/'environment/method_contract.json'
    assert c.digest(p)==c.METHOD_SHA256
    assert json.loads(p.read_text())['source']['source_manifest_sha256']==c.SOURCE_SHA256


@pytest.mark.parametrize('shape',[(152,),(128,),(152,3)])
def test_decimal_constant_center_exact_zero(shape):
    x=np.full(shape,.1)
    assert np.array_equal(c.centered(x),np.zeros(shape))
    if len(shape)==2:assert np.array_equal(c.detrended(x),np.zeros(shape))


def test_linear_detrend_matches_scipy():
    x=np.random.default_rng(1).normal(size=(128,5))+np.arange(128)[:,None]*.13
    np.testing.assert_allclose(c.detrended(x),signal.detrend(x,axis=0),atol=1e-13,rtol=1e-12)


def test_cleaning_explicit_pipeline_and_constant():
    rng=np.random.default_rng(12);raw=rng.normal(size=(128,5));raw[:,0]=.1;conf=rng.normal(size=(128,13))
    r=c.clean_parcels(raw,conf)
    assert r['parcel_status'][0]=='constant_input'
    assert r['parcel_original_centered_l2'][0]==r['parcel_residual_l2'][0]==0
    assert r['parcel_zero_bound'][0]==10*128*c.EPS*c.TINY
    assert r['nuisance_rank']==13
    np.testing.assert_allclose(r['standardized'][:,1:].mean(axis=0),0,atol=1e-15)
    np.testing.assert_allclose(r['standardized'][:,1:].std(axis=0,ddof=1),1,atol=1e-15)
    np.testing.assert_allclose(r['nuisance_q'].T@r['residual'],0,atol=1e-13)


def test_exact_nuisance_signal_numerical_zero():
    rng=np.random.default_rng(2);conf=rng.normal(size=(152,13));raw=conf[:,:2].copy()
    r=c.clean_parcels(raw,conf)
    assert np.all(r['parcel_status']=='numerical_zero_residual')
    assert np.all(r['standardized']==0)


def test_constant_nuisance_reduces_rank():
    rng=np.random.default_rng(3);conf=rng.normal(size=(128,13));conf[:,0]=.1
    r=c.clean_parcels(rng.normal(size=(128,2)),conf)
    assert r['nuisance_rank']==12


@pytest.mark.parametrize('n',[0,1,33])
def test_filter_too_short(n):
    with pytest.raises(ValueError):c.clean_parcels(np.ones((n,2)),np.ones((n,13)))


@pytest.mark.parametrize('where',['raw','confound'])
def test_clean_nonfinite(where):
    a=np.ones((128,2));b=np.ones((128,13));(a if where=='raw' else b)[2,0]=np.nan
    with pytest.raises(ValueError):c.clean_parcels(a,b)


def test_fd_defined_denominator_and_threshold():
    r=c.fd_summary([np.nan,.1,.3]);assert r['n_fd_defined']==2 and not r['first_fd_defined']
    assert r['mean_fd']==.2 and not r['qc_fd_lt_0_2']
    assert c.fd_summary([0.,.1,.3])['n_fd_defined']==3
    assert c.fd_summary([np.nan,np.nextafter(.2,0)])['qc_fd_lt_0_2']


@pytest.mark.parametrize('fd',[[],[np.nan],[.1,np.nan],[-.1,.1],[np.inf,.1],[np.nan,-.1]])
def test_invalid_fd(fd):
    with pytest.raises(ValueError):c.fd_summary(fd)


def test_ols_signed_crude_coefficient_classical_se():
    group=np.r_[np.zeros(5),np.ones(4)];y=np.array([0,1,2,3,4,0,1,1,2],float)
    r,p=c.ols_effect(y,group)
    expected=y[group==1].mean()-y[group==0].mean();assert r['estimate']==pytest.approx(expected)
    sse=((y[group==0]-y[group==0].mean())**2).sum()+((y[group==1]-y[group==1].mean())**2).sum()
    se=np.sqrt(sse/7*(1/5+1/4))
    assert r['se']==pytest.approx(se) and r['t']<0 and r['df']==7
    assert r['p']==pytest.approx(2*stats.t.sf(abs(expected/se),7))
    np.testing.assert_allclose(r['ci95'],[expected-1.96*se,expected+1.96*se])
    assert p['raw_sse']==pytest.approx(sse)


def test_adjusted_ols_equivalent_lstsq():
    rng=np.random.default_rng(42);group=np.tile([0,1],10);fd=rng.uniform(size=20);y=rng.normal(size=20)
    r,_=c.ols_effect(y,group,fd);x=np.column_stack([np.ones(20),group,fd]);beta=np.linalg.lstsq(x,y,rcond=None)[0]
    assert r['estimate']==pytest.approx(beta[1],abs=1e-14)
    assert r['rank']==3 and r['df']==17


def test_rank_deficient_but_estimable_constant_fd():
    group=np.tile([0,1],6);y=np.arange(12,dtype=float)**2
    a,_=c.ols_effect(y,group);b,_=c.ols_effect(y,group,np.full(12,.1))
    assert b['status']=='ok' and b['rank']==2
    for key in ('estimate','se','t','p','sse'):assert b[key]==pytest.approx(a[key])


def test_rank_deficient_diagnosis_confound():
    group=np.tile([0,1],6);r,_=c.ols_effect(np.arange(12),group,group)
    assert r['status']=='rank_deficient' and r['rank']==2 and r['df']==10
    assert r['estimate'] is r['sse'] is None


def test_numerically_discarded_tiny_nuisance():
    group=np.tile([0,1],6);fd=np.full(12,.1)+np.arange(12)*1e-18;y=np.arange(12,dtype=float)**2
    r,_=c.ols_effect(y,group,fd);assert r['rank']==2 and r['status']=='ok'


def test_constant_response_zero_inference():
    group=np.tile([0,1],6);r,p=c.ols_effect(np.full(12,.1),group)
    assert r['status']=='zero_se' and r['estimate']==r['se']==r['sse']==0
    assert r['ci95']==[0.,0.] and r['t'] is r['p'] is None
    assert 'residual' in p and p['raw_sse']>=0


def test_perfect_nonconstant_fit_keeps_signed_effect():
    group=np.tile([0,1],6);r,_=c.ols_effect(3-2*group,group)
    assert r['status']=='zero_se' and r['estimate']==pytest.approx(-2) and r['se']==0


def test_empty_response_keeps_actual_design_support():
    group=np.tile([0,1],6);r,_=c.ols_effect(None,group,np.arange(12),empty=True)
    assert r['status']=='empty_response_bin' and r['n']==12 and r['rank']==3 and r['df']==9 and r['n_schz']==6
    assert r['estimate'] is r['sse'] is None


@pytest.mark.parametrize('group,status',[(np.zeros(6),'missing_group'),(np.array([0,1]),'insufficient_df'),(np.array([]),'missing_group')])
def test_model_precedence(group,status):
    r,_=c.ols_effect(np.zeros(len(group)),group)
    assert r['status']==status


def test_common_quantile_ties_not_forced_bins():
    d=np.array([1,1,1,1.]);valid=np.array([[1,1,1,0],[1,1,1,1]],bool)
    common,bins,q=c.common_families(d,valid)
    assert common.tolist()==[True,True,True,False] and bins.tolist()==['middle']*3+['excluded_not_common']
    assert q['n_short']==q['n_long']==0


def test_empty_common_family_explicit():
    common,bins,q=c.common_families(np.array([1.,2]),np.zeros((3,2),bool))
    assert not common.any() and (bins=='excluded_not_common').all() and q==dict(q1=None,q2=None,n_short=0,n_middle=0,n_long=0)


@pytest.mark.parametrize('x,y,status',[([1],[2],'insufficient_n'),([.1]*6,list(range(6)),'constant_fd'),(list(range(6)),[.1]*6,'constant_edge')])
def test_pearson_undefined(x,y,status):
    assert c.pearson(x,y)==(status,None)


def test_pearson_signed():
    assert c.pearson(np.arange(10),-np.arange(10))[1]==pytest.approx(-1)


@pytest.mark.parametrize('layout',['source_equals_output','output_under_source','source_under_private','private_under_output','output_symlink_parent','existing_output'])
def test_evidence_safety(tmp_path,layout):
    src=tmp_path/'source';src.mkdir();(src/'keep').write_text('original');out=tmp_path/'output';private=tmp_path/'private'
    if layout=='source_equals_output':out=src
    elif layout=='output_under_source':out=src/'out'
    elif layout=='source_under_private':private=tmp_path
    elif layout=='private_under_output':private=out/'private'
    elif layout=='output_symlink_parent':link=tmp_path/'link';link.symlink_to(src,target_is_directory=True);out=link/'out'
    else:out.mkdir();(out/'keep').write_text('earlier')
    with pytest.raises(ValueError):c.validate_destinations(src,out,private)
    assert (src/'keep').read_text()=='original'


def test_missing_source_has_failure_findings(tmp_path):
    out=tmp_path/'out';private=tmp_path/'private'
    with pytest.raises(FileNotFoundError):c.run(tmp_path/'source',tmp_path/'missing-method',out,private)
    assert json.loads((out/'group_stats.json').read_text())['status']=='failed_precondition'
    assert (out/'findings.md').read_text().strip()
    assert (private/'failure.json').is_file()
    assert json.loads((out/'run_metadata.json').read_text())['reason']


def test_json_empty_fields_not_nan(tmp_path):
    path=tmp_path/'data.json';c.write_json(path,{'x':None,'n':np.int64(3)})
    assert json.loads(path.read_text())=={'x':None,'n':3}
    with pytest.raises(FileExistsError):c.write_json(path,{})


def test_csv_blank_undefined_explicit_bool(tmp_path):
    p=tmp_path/'data.csv';c.write_csv(p,['x','v'],[{'x':None,'v':False}])
    assert p.read_text().splitlines()==['x,v',',false']


@pytest.mark.parametrize('n',[128,152])
def test_explicit_public_sos_matches_known_design(n):
    rng=np.random.default_rng(444);raw=rng.normal(size=(n,3));conf=rng.normal(size=(n,13));actual=c.clean_parcels(raw,conf)
    coefficients=signal.butter(5,[.009,.08],btype='bandpass',fs=.5,output='sos')
    expected=signal.sosfiltfilt(coefficients,signal.detrend(raw,axis=0),axis=0,padtype='odd',padlen=33)
    np.testing.assert_array_equal(actual['sos'],coefficients)
    np.testing.assert_allclose(actual['filtered_parcel'],expected,atol=1e-13,rtol=1e-12)


def test_zero_family_and_pilot_never_fit(monkeypatch):
    atlas=dict(distance=np.array([1.]),edge_i=np.array([0]),edge_j=np.array([1]),parcel_id=np.array(['L:1','R:1']))
    selected=[dict(subject_id='sub-a',group='CONTROL'),dict(subject_id='sub-b',group='SCHZ')]
    subjects=[]
    for row in selected:
        subjects.append(dict(raw_r=np.array([np.nan]),fisher_z=np.array([np.nan]),edge_valid=np.array([False]),fisher_clipped=np.array([False]),
            summary=dict(**row,mean_fd=.1),cleaned=dict(parcel_status=np.array(['constant_input']*2),parcel_original_centered_l2=np.zeros(2),parcel_residual_l2=np.zeros(2),parcel_zero_bound=np.full(2,10*128*c.EPS*c.TINY))))
    _,summaries,_,edge_stats,result,_=c.summarize(atlas,selected,subjects)
    assert result['n_common_edges']==0 and all(row['mean_fc'] is None for row in summaries)
    assert all(row['status']=='excluded_not_common' and row['n']==row['rank']==row['df']==0 for row in edge_stats)
    assert all(row['status']=='empty_response_bin' and row['n']==2 for row in result['short_range_effects'].values())
    monkeypatch.setattr(c,'ols_effect',lambda *a,**k:pytest.fail('Pilot must not fit group models'))
    *_,pilot,_=c.summarize(atlas,selected[:1],subjects[:1],pilot=True)
    assert pilot['status']=='resource_pilot' and pilot['short_range_effects']=={}


def test_existing_output_failure_never_overwrites(tmp_path):
    out=tmp_path/'out';out.mkdir();(out/'group_stats.json').write_text('preserve')
    with pytest.raises(ValueError):c.run(tmp_path/'source',tmp_path/'missing-method',out,tmp_path/'private')
    assert (out/'group_stats.json').read_text()=='preserve' and not (tmp_path/'private').exists()


def test_empty_exception_still_has_reason(tmp_path,monkeypatch):
    def fail(*args):raise ValueError()
    monkeypatch.setattr(c,'load_inputs',fail)
    out=tmp_path/'out'
    with pytest.raises(ValueError):c.run(tmp_path/'source',tmp_path/'method',out,tmp_path/'private')
    assert json.loads((out/'run_metadata.json').read_text())['reason']=='ValueError'
