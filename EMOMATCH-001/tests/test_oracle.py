"""Manufactured oracle mechanics; never loads original recordings or banks."""
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import gzip
import io
import json
import os
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
from scipy import linalg
import nibabel as nib

SOLUTION=Path(__file__).parents[1]/'solution'
sys.path.insert(0,str(SOLUTION))
spec=importlib.util.spec_from_file_location('core',SOLUTION/'core.py')
c=importlib.util.module_from_spec(spec);sys.modules['core']=c;spec.loader.exec_module(c)
import source_reader as sr
import compute as oracle


@pytest.mark.parametrize('base',[0.,.1,-.1,1e8,-1e8])
@pytest.mark.parametrize('layout',['C','F','slice'])
def test_fsum_normalization_exact_and_near_constant(base,layout):
    a=np.full((135,3),base);a[:,1]+=np.linspace(-1e-7,1e-7,135);a[:,2]+=np.arange(135)%3
    if layout=='F':a=np.asfortranarray(a)
    elif layout=='slice':b=np.repeat(a,2,axis=0);a=b[::2]
    y,mu,sd,denom,constant=c.normalize_roi(a)
    assert constant.tolist()==[True,False,False]
    assert mu[0]==base and sd[0]==0 and np.array_equal(y[:,0],np.zeros(135))
    for col in (1,2):
        expected=math.fsum(float(v) for v in a[:,col])/135
        d=[float(v-expected) for v in a[:,col]]
        expected_sd=math.sqrt(math.fsum(v*v for v in d)/135)
        assert mu[col]==expected and sd[col]==expected_sd and denom[col]==expected_sd+1e-8
        np.testing.assert_array_equal(y[:,col],(a[:,col]-expected)/denom[col])


@pytest.mark.parametrize('bad',[[[True]],[[float('nan')]],[[float('inf')]],[[1+2j]],[['1']],np.empty((0,2))])
def test_invalid_normalization(bad):
    with pytest.raises(c.PreconditionError):c.normalize_roi(bad)


def test_voxel_mean_storage_and_support():
    a=np.arange(2*3*4*5,dtype=np.float32).reshape(2,3,4,5);support=[np.array([0,2,23]),np.array([1])]
    expected=np.array([[np.mean(np.ascontiguousarray(a[:,:,:,t].ravel()[s],dtype=np.float64)) for s in support] for t in range(5)])
    np.testing.assert_array_equal(c.voxel_means(a,support),expected)
    np.testing.assert_array_equal(c.voxel_means(np.asfortranarray(a),support),expected)
    for wrong in [np.array([],dtype=int),np.array([2,1]),np.array([0,24]),np.array([1,1])]:
        with pytest.raises(c.PreconditionError):c.voxel_means(a,[wrong])


def test_nearest_half_snap_and_closed_domain():
    labels=np.arange(3).reshape(3,1,1)
    coords=np.array([[-1e-7,0,0],[-1.01e-7,0,0],[.5-5e-8,0,0],[.5-2e-7,0,0],[2+5e-8,0,0],[2+2e-7,0,0]])
    assert c.nearest_labels(coords,labels).tolist()==[0,0,1,0,2,0]


def test_geometry_digests_and_sphere_boundary():
    b=np.eye(4);b[:3,3]=np.array(c.SPHERES['amy_L'])-np.array([6,0,0])
    labels=np.ones((13,1,1),dtype=np.int16)
    support,meta=c.geometric_supports((13,1,1),b,labels,b,chunk_size=3)
    assert support['amy_L'].tolist()==list(range(13)) and support['1'].tolist()==list(range(13))
    assert len(support)==111 and c.support_digest(support['1'])==hashlib.sha256(b'EMOMATCH_support_v1\n'+np.arange(13,dtype='<i8').tobytes()).hexdigest()
    negzero=b.copy();negzero[3,0]=-0.
    assert c.grid_id((13,1,1),negzero)==meta['grid_id']


def test_duration_imputation_target_pooled_and_preserved():
    rt=np.array([1.,3.,0.,5.]);missing=np.array([False,False,True,False]);before=rt.copy()
    a,b,median=c.duration_models(rt,missing)
    assert median==3 and a.tolist()==[3]*4 and b.tolist()==[1,3,3,5]
    np.testing.assert_array_equal(rt,before)
    with pytest.raises(c.PreconditionError):c.duration_models([0.],[False])
    with pytest.raises(c.PreconditionError):c.duration_models([0.],[True])


def test_confound_accurate_fill_all_missing():
    a=np.array([[1e16,0],[1,0],[-1e16,0],[0,0]],float);mask=np.zeros_like(a,dtype=bool);mask[-1,0]=True;mask[:,1]=True
    actual=c.impute_confounds(a,mask)
    assert actual[-1,0]==1/3 and np.array_equal(actual[:,1],np.zeros(4)) and a[-1,0]==0


def test_design_explicit_columns_no_full_rank():
    times=np.arange(135)*2.;conf=np.zeros((135,13));conf[:,0]=1
    x,names,contrast,presence=c.construct_design([10.,40.],['control','emotion'],[1.,2.],times,conf)
    assert names[:2]==['control','emotion'] and names[-14:]==list(c.CONFOUNDS)+['constant']
    assert np.array_equal(x[:,-1],np.ones(135)) and np.array_equal(x[:,names.index('trans_x')],np.ones(135))
    assert presence=={'control':True,'emotion':True} and contrast[:2].tolist()==[-1,1]
    assert np.linalg.matrix_rank(x)<x.shape[1]
    x2,_,_,presence=c.construct_design([10.],['emotion'],[1.],times,conf)
    assert not presence['control'] and np.array_equal(x2[:,0],np.zeros(135))


def test_svd_minimum_norm_rank_deficiency_and_estimability():
    rng=np.random.default_rng(9);x=rng.normal(size=(30,3));x=np.column_stack([x,x[:,0]])
    y=rng.normal(size=(30,2));con=np.array([1.,0,0,1.])
    fit=c.minimum_norm(x,y,con)
    expected=linalg.lstsq(x,y,cond=max(x.shape)*np.finfo(float).eps,lapack_driver='gelsd')[0]
    np.testing.assert_allclose(fit['beta'],expected,atol=1e-14)
    assert fit['rank']==3 and fit['status']=='ok'
    np.testing.assert_allclose(fit['residual_sse'],np.sum((y-x@fit['beta'])**2,axis=0))
    bad=c.minimum_norm(x,y,[1.,0,0,-1.])
    assert bad['status']=='contrast_nonestimable' and not bad['contrast_defined'].any() and not bad['contrast_estimate'].any()
    absent=c.minimum_norm(x,y,[1.,0,0,-1.],conditions_present=False)
    assert absent['status']=='missing_condition'


def test_svd_strict_singular_cutoff():
    cut=3*np.finfo(float).eps
    fit=c.minimum_norm(np.diag([1.,cut,cut/2]),np.eye(3),[1.,0,0])
    assert fit['rank']==1 and fit['residual_df']==2


@pytest.mark.parametrize('values,status',[([1.,1.,1.],'zero_variance'),([1.,None,3.],'incomplete_support'),([1.,2.,3.],'ok'),([1.],'insufficient_n')])
def test_complete_only_group(values,status):
    out=c.complete_statistic(values,len(values));assert out['status']==status
    if status in ('incomplete_support','insufficient_n'):assert out['mean'] is None and out['t'] is None
    elif status=='zero_variance':assert out['ci95']==[1,1] and out['t'] is None and out['p'] is None
    else:assert out['mean']==2 and out['sample_sd']==1 and out['df']==2


@pytest.mark.parametrize('values',[[True,2],['1',2],[float('inf'),2]])
def test_group_types(values):
    with pytest.raises(c.PreconditionError):c.complete_statistic(values,2)


def nifti_bytes(values,*,endian='<',slope=1.,intercept=0.):
    values=np.asarray(values);header=nib.Nifti1Header(endianness=endian)
    header.set_data_dtype(np.dtype(endian+'f4'));header.set_data_shape(values.shape)
    header.set_xyzt_units('mm','sec');header['vox_offset']=352
    header.set_sform(np.diag([2.,3.,4.,1.]),code=2);header['scl_slope']=slope;header['scl_inter']=intercept
    if values.ndim==4:header['pixdim'][4]=2
    raw=header.binaryblock+b'\0'*4+values.astype(endian+'f4').tobytes(order='F')
    return gzip.compress(raw),raw


@pytest.mark.parametrize('endian',['<','>'])
@pytest.mark.parametrize('scaling',[(1.,0.),(2.,-3.),(0.,float('nan')),(float('nan'),float('nan'))])
def test_samebuffer_nifti_native_scaling_endian_fortran(endian,scaling):
    values=np.arange(2*3*4*5,dtype=float).reshape(2,3,4,5)
    raw,_=nifti_bytes(values,endian=endian,slope=scaling[0],intercept=scaling[1])
    data,head=sr.decode_nifti(raw,full=True);empty,header_only=sr.decode_nifti(raw)
    assert empty is None and header_only==head and head['shape']==[2,3,4,5] and head['header_TR']==2
    assert np.dtype(head['source_dtype'])==np.dtype(endian+'f4')
    expected=values*2-3 if scaling[0]==2 else values
    np.testing.assert_array_equal(data,expected)


@pytest.mark.parametrize('defect',['truncated','extra','nonfinite','bad_intercept'])
def test_nifti_failure_preconditions(defect):
    values=np.ones((2,2,2,3))
    if defect=='nonfinite':values[0,0,0,0]=np.nan
    packed,raw=nifti_bytes(values,slope=2 if defect=='bad_intercept' else 1,intercept=float('nan') if defect=='bad_intercept' else 0)
    if defect=='truncated':packed=gzip.compress(raw[:-1])
    elif defect=='extra':packed=gzip.compress(raw+b'x')
    with pytest.raises(c.PreconditionError):sr.decode_nifti(packed,full=True)


@pytest.mark.parametrize('token',['NaN','inf','NA','None',' '])
def test_exact_missing_tokens(token):
    with pytest.raises(c.PreconditionError):sr.number(token,missing=True)
    assert sr.number('n/a',missing=True) is None and sr.number('',missing=True) is None


def test_documentary_duplicate_only_exact_identical_exemption():
    raw=b'{"NEO_A":{"a":1},"NEO_A":{"a":1}}'
    obj,duplicates=sr.strict_json(raw,documentary_path='participants.json')
    assert obj=={'NEO_A':{'a':1}} and duplicates==[dict(path='participants.json',key='NEO_A',occurrences=2,identical=True,analysis_use=False)]
    for bad in [b'{"x":1,"x":1}',b'{"NEO_A":1,"NEO_A":2}',b'{"NEO_A":1,"NEO_A":1,"NEO_A":1}',b'{"x":1e999}']:
        with pytest.raises(c.PreconditionError):sr.strict_json(bad,documentary_path='participants.json')
    with pytest.raises(c.PreconditionError):sr.strict_json(raw)


def test_events_original_order_tokens_and_model_support():
    raw=b'onset\tduration\tresponse_time\ttrial_type\n10\t5.0036\tn/a\temotion\n20\t2\t2\tcontrol\n30\t1\t1\tother\n40\t4\t4\temotion\n'
    header,rows,median,diag=sr.events(raw,'sub-test')
    assert median==3 and len(rows)==4 and [r['source_event_row'] for r in rows]==[0,1,2,3]
    assert rows[0]['source_duration_s']==5.0036 and rows[0]['duration_token']=='5.0036' and rows[0]['modelB_duration_s']==3
    assert rows[2]['rt_status']=='not_target' and rows[2]['modelA_duration_s'] is None
    assert diag['n_target_with_source_duration']==3 and diag['n_imputed_rt_and_duration']==1


@pytest.mark.parametrize('change',['duplicate_header','invalid_RT','invalid_onset','negative_duration'])
def test_event_failure_cases(change):
    raw='onset\tduration\tresponse_time\ttrial_type\n10\t1\t2\temotion\n'
    if change=='duplicate_header':raw=raw.replace('duration','onset')
    elif change=='invalid_RT':raw=raw.replace('\t2\t','\t-2\t')
    elif change=='invalid_onset':raw=raw.replace('10\t','-25\t')
    else:raw=raw.replace('\t1\t','\t-1\t')
    with pytest.raises(c.PreconditionError):sr.events(raw.encode(),'sub-test')


def test_same_file_bytes_authenticated_and_no_symlink(tmp_path):
    p=tmp_path/'source';p.write_bytes(b'abc');sha=hashlib.sha256(b'abc').hexdigest()
    assert sr.stable_bytes(p,3,sha256=sha)==b'abc'
    p.write_bytes(b'bad')
    with pytest.raises(c.PreconditionError):sr.stable_bytes(p,3,sha256=sha)
    link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(c.PreconditionError):sr.stable_bytes(link,3)


@pytest.mark.parametrize('mode',['overlap','inside','ancestor','symlink','dangling','dotdot','existing_evidence','private_overlap'])
def test_destinations_preserve_evidence(tmp_path,mode):
    source=tmp_path/'source';source.mkdir();(source/'keep').write_bytes(b'keep');out=tmp_path/'output';private=None
    if mode=='overlap':out=source
    elif mode=='inside':out=source/'out'
    elif mode=='ancestor':out=tmp_path
    elif mode in ('symlink','dangling'):out.symlink_to(source if mode=='symlink' else tmp_path/'absent')
    elif mode=='dotdot':out=str(source/'anything')+'/../outside'
    elif mode=='existing_evidence':out.mkdir();(out/'keep').write_bytes(b'keep')
    else:private=out
    with pytest.raises(c.PreconditionError):oracle.protected_destinations(out,private,[source])
    assert (source/'keep').read_bytes()==b'keep'


def test_failure_markers_preserve_existing_outputs(tmp_path):
    (tmp_path/'run_metadata.json').write_bytes(b'original')
    oracle.failure_evidence(tmp_path,ValueError('deliberate late failure'))
    assert (tmp_path/'run_metadata.json').read_bytes()==b'original'
    assert json.loads((tmp_path/'failure_report.json').read_text())['reason']=='deliberate late failure'
    assert (tmp_path/'findings.md').read_text()
    with pytest.raises(FileExistsError):oracle.failure_evidence(tmp_path,ValueError('second'))


@pytest.fixture
def manufactured_run(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir();env=SOLUTION.parent/'environment'
    labels={i:dict(label_name=f'label_{i}',network=c.NETWORKS[(i-1)%7]) for i in range(1,101)}
    roi_ids=[str(i) for i in range(1,101)]+list(c.SPHERES);cohort=[];all_events=[];persons={}
    manifest=dict(files=[])
    for i,pid in enumerate(sr.IDS):
        _,ev,median,_=sr.events(b'onset\tduration\tresponse_time\ttrial_type\n10\t1\t1\tcontrol\n40\t2\t2\temotion\n',pid)
        cohort.append(dict(source_row=i,participant_id=pid,selected=True,selection_reason='selected_fixed_cohort',source_status='ok'))
        all_events.extend(ev);persons[pid]=dict(header=dict(bold_shape=[111,1,1,135],affine=np.eye(4).tolist(),effective_TR_s=2.),
            events=ev,confound_effective=np.zeros((135,13)),confound_was_missing=np.zeros((135,13),dtype=bool))
    rows={(pid,'bold'):dict(path=pid+'.nii.gz') for pid in sr.IDS}
    monkeypatch.setattr(sr,'authenticate',lambda *a:(manifest,rows))
    monkeypatch.setattr(sr,'metadata',lambda *a:(cohort,all_events,persons,{}))
    monkeypatch.setattr(sr,'atlas',lambda *a:(np.ones((111,1,1),dtype=int),np.eye(4),labels,{}))
    data=np.sin(np.arange(135)[None,None,None,:]/8)+np.arange(111)[:,None,None,None]*.01
    monkeypatch.setattr(sr,'read_member',lambda *a:b'manufactured')
    monkeypatch.setattr(sr,'decode_nifti',lambda *a,**k:(data,dict(shape=[111,1,1,135],affine=np.eye(4).tolist())))
    def supports(pid,*args):
        s={key:np.array([i]) for i,key in enumerate(roi_ids)}
        return s,[dict(participant_id=pid,roi_id=key,n_voxels=1,support_status='ok') for key in roi_ids]
    monkeypatch.setattr(oracle,'support_rows',supports)
    args=SimpleNamespace(data_dir=str(root),output_dir=str(tmp_path/'output'),private_dir=str(tmp_path/'private'),
        source_manifest=str(env/'source_manifest.json'),method_contract=str(env/'method_contract.json'),output_schema=str(env/'output_schema.json'),pilot_subject='sub-0002')
    return args


@pytest.mark.parametrize('private',[True,False])
def test_manufactured_eight_artifact_pilot(manufactured_run,private):
    args=manufactured_run
    if not private:args.private_dir=None
    result=oracle.run(args);output=Path(args.output_dir)
    assert result['status']=='resource_pilot' and result['participants']==1 and result['fits']==2
    required={'cohort.csv','events.csv','roi_support.csv','glm_arrays.npz','activation.csv','group_stats.json','run_metadata.json','findings.md'}
    assert {p.name for p in output.iterdir()}==required
    with np.load(output/'glm_arrays.npz',allow_pickle=False) as a:
        assert a['roi_mean'].shape==(135,111) and a['beta'].shape==(2,20,111)
        assert a['column_present'].all() and a['fit_model'].tolist()==['modelA','modelB']
        np.testing.assert_allclose(a['contrast_estimate'],a['beta'][:,1]-a['beta'][:,0])
    groups=json.loads((output/'group_stats.json').read_text())
    assert len(groups['models'])==42 and len(groups['paired_changes'])==4
    assert all(r['statistic']['status']=='incomplete_support' for r in groups['models'])
    if private:assert json.loads((Path(args.private_dir)/'completion.json').read_text())['status']=='resource_pilot'


def test_manufactured_full20_no_optional_private(manufactured_run):
    args=manufactured_run;args.pilot_subject=None;args.private_dir=None
    result=oracle.run(args);assert result['participants']==20 and result['fits']==40
    groups=json.loads((Path(args.output_dir)/'group_stats.json').read_text())
    assert groups['status']=='complete' and groups['n_expected']==20
    assert all(r['statistic']['n_defined']==20 for r in groups['models'])


@pytest.mark.parametrize('failure',['private','late_json'])
def test_private_or_late_failure_authoritative_receipt(manufactured_run,monkeypatch,failure):
    args=manufactured_run
    if failure=='private':
        def reject(*a,**k):raise OSError('private evidence failure')
        monkeypatch.setattr(oracle,'write_npz',reject)
    else:
        original=oracle.write_json;raised=[]
        def reject(path,value):
            if path.name=='run_metadata.json' and not raised:raised.append(True);raise OSError('late public JSON failure')
            return original(path,value)
        monkeypatch.setattr(oracle,'write_json',reject)
    with pytest.raises(OSError):oracle.run(args)
    output=Path(args.output_dir);assert json.loads((output/'failure_report.json').read_text())['status']=='failed_precondition'
    assert not (Path(args.private_dir)/'completion.json').exists()
    if failure=='private':assert json.loads((output/'group_stats.json').read_text())['status']=='failed_precondition'


def test_actual_wrapper_help_and_missing_input_failure(tmp_path):
    result=subprocess.run(['bash',str(SOLUTION/'solve.sh'),'--help'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and '--pilot-subject' in result.stdout and '--data-dir' in result.stdout
    source=tmp_path/'source';source.mkdir();output=tmp_path/'output'
    command=['bash',str(SOLUTION/'solve.sh'),'--data-dir',str(source),'--output-dir',str(output),
        '--method-contract',str(tmp_path/'missing_method'),'--source-manifest',str(tmp_path/'missing_manifest'),
        '--output-schema',str(tmp_path/'missing_schema')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=15)
    assert result.returncode!=0 and json.loads((output/'failure_report.json').read_text())['reason']
    assert (output/'findings.md').read_text()
    prior={p.name:p.read_bytes() for p in output.iterdir()}
    result=subprocess.run(command,capture_output=True,text=True,timeout=15)
    assert result.returncode!=0 and prior=={p.name:p.read_bytes() for p in output.iterdir()}
