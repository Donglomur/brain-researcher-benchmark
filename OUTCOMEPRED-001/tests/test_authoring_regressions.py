"""Source-free synthetic mechanics only; no fixture is a scientific reference."""
import copy
import csv
import json
from pathlib import Path
import numpy as np
import pytest
import prediction_contract as q
import build_reference as b
import proof_of_work as pw

def trials_fixture():
    n=20
    return dict(id=np.arange(n)+1000,start_time=np.arange(n)*2.,stop_time=np.arange(n)*2.+1.8,
        gabor_stimulus_onset_time=np.arange(n)*2.+.1,feedback_time=np.arange(n)*2.+1.,
        choice_registration_time=np.arange(n)*2.+.7,wheel_movement_onset_time=np.arange(n)*2.+.5,
        mouse_wheel_choice=np.array(['clockwise']*n),is_mouse_rewarded=np.arange(n)%2==0)

def toy_reference():
    tr=trials_fixture(); sel,y,f,rows=b.select_trials(tr); method=q.json_load(Path(__file__).parents[1]/'environment/method_contract.json')
    ref=dict(analysis=np.array(q.NAMES),window_start_s=np.array([a/1000 for _,a,_ in q.WINDOWS]),window_end_s=np.array([e/1000 for _,_,e in q.WINDOWS]),
        source_trial_row=sel,trial_id=tr['id'][sel],source_unit_row=np.arange(3),unit_id=np.array([42,5,19]),spike_count=np.arange(21*len(sel)*3).reshape(21,len(sel),3)%7,
        labels=y,folds=f,source_rows=rows,scores=np.tile((2*y-1).astype(float),(21,1)))
    summary=dict(n_source_trials=len(rows),n_units=3,n_stored_spikes=200,duplicate_adjacent_spike_pairs=2,nwb_version='synthetic-fixture',session_start_time='fixture',timestamps_reference_time='fixture',kilosort_label_counts={'mua':3},ibl_quality_score_counts={'0.0':3},probe_counts={'fixture':3},observation_support='unknown',task_epoch_start_s=0.,task_epoch_stop_s=50.)
    ref['metadata']=dict(source=method['source'],source_manifest_sha256=pw.SOURCE_MANIFEST_SHA256,method_contract_sha256=pw.METHOD_SHA256,method=method,source_summary=summary,support_by_analysis=b.support_rows(tr,sel,0.,50.),software={'mechanics':'fixture'},
        fits=[dict(analysis=name,fold=i,mean_gradient_inf=0.,finite_parameters=True,optimizer_status='fixture',warnings=[]) for name in q.NAMES for i in range(5)])
    return ref

def write_csv(path,fields,rows):
    with Path(path).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)

def write_submission(path,ref,scores=None):
    path=Path(path); path.mkdir(exist_ok=True)
    scores=ref['scores'] if scores is None else scores
    pred=(scores>0).astype(int); folds,curve,result=q.summarize(ref,pred)
    write_csv(path/'source_trials.csv',q.SOURCE_FIELDS,ref['source_rows'])
    with (path/'spike_counts.npz').open('wb') as f: np.savez_compressed(f,**{k:ref[k] for k in q.COUNT_FIELDS})
    rows=[]
    for ai,name in enumerate(q.NAMES):
        for i,source in enumerate(ref['source_trial_row']): rows.append(dict(analysis=name,source_trial_row=int(source),trial_id=int(ref['trial_id'][i]),fold=int(ref['folds'][i]),label=int(ref['labels'][i]),prediction=int(pred[ai,i]),decision_score=float(scores[ai,i]),window_start_s=float(ref['window_start_s'][ai]),window_end_s=float(ref['window_end_s'][ai])))
    write_csv(path/'trial_predictions.csv',q.PRED_FIELDS,rows); write_csv(path/'folds.csv',q.FOLD_FIELDS,folds); write_csv(path/'decoding_vs_window.csv',q.CURVE_FIELDS,curve)
    for name,obj in [('results.json',result),('run_metadata.json',ref['metadata'])]: (path/name).write_text(json.dumps(obj,allow_nan=False))
    (path/'findings.md').write_text('Synthetic parser/arithmetic fixture, never source evidence.\n')

@pytest.mark.parametrize('value,expected',[(0,0),('1e0',1),('2.000',2),('-3e1',-30),('9007199254740993',9007199254740993)])
def test_integral_notation(value,expected): assert q.integer(value)==expected

@pytest.mark.parametrize('value',[True,False,'NaN','Infinity','1.2','',None])
def test_invalid_integer(value):
    with pytest.raises(AssertionError): q.integer(value)

@pytest.mark.parametrize('value',[True,'NaN','inf',None,'text'])
def test_invalid_number(value):
    with pytest.raises(AssertionError): q.number(value)

@pytest.mark.parametrize('text',['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'])
def test_json_fail_closed(tmp_path,text):
    p=tmp_path/'x.json'; p.write_text(text)
    with pytest.raises(AssertionError): q.json_load(p)

@pytest.mark.parametrize('actual,expected',[(True,1),(False,0),(1,True),('1',1)])
def test_json_type_identity(actual,expected):
    with pytest.raises(AssertionError): q.match({'x':actual},{'x':expected})

def test_toy_complete_parser_only(tmp_path):
    ref=toy_reference(); write_submission(tmp_path,ref); assert q.validate_output_directory(tmp_path,ref)['headline']['mean_accuracy']==1

def test_no_accuracy_direction_gate(tmp_path):
    ref=toy_reference(); ref['scores']*=-1; write_submission(tmp_path,ref); assert q.validate_output_directory(tmp_path,ref)['headline']['mean_accuracy']==0

def test_consistent_axes_reorder(tmp_path):
    ref=toy_reference(); values={k:ref[k].copy() for k in q.COUNT_FIELDS}; a=np.arange(21)[::-1]; t=np.arange(20)[::-1]; u=np.array([2,0,1])
    for k in ('analysis','window_start_s','window_end_s'): values[k]=values[k][a]
    for k in ('source_trial_row','trial_id'): values[k]=values[k][t]
    for k in ('source_unit_row','unit_id'): values[k]=values[k][u]
    values['spike_count']=values['spike_count'][np.ix_(a,t,u)]
    np.savez(tmp_path/'counts.npz',**values); q.validate_counts(tmp_path/'counts.npz',ref)

@pytest.mark.parametrize('mutation',['bool','float','object','negative','wrap','wrong','missing_unit','duplicate_axis'])
def test_count_receipt_mutations(tmp_path,mutation):
    ref=toy_reference(); values={k:ref[k].copy() for k in q.COUNT_FIELDS}
    if mutation in ('bool','float','object'): values['spike_count']=values['spike_count'].astype({'bool':bool,'float':float,'object':object}[mutation])
    elif mutation=='negative': values['spike_count'][0,0,0]=-1
    elif mutation=='wrap': values['spike_count']=values['spike_count'].astype(np.uint64); values['spike_count'][0,0,0]=2**64-1
    elif mutation=='wrong': values['spike_count'][0,0,0]+=1
    elif mutation=='missing_unit': values['spike_count']=values['spike_count'][:,:,:-1]
    else: values['unit_id'][0]=values['unit_id'][1]
    np.savez(tmp_path/'counts.npz',**values)
    with pytest.raises((AssertionError,ValueError)): q.validate_counts(tmp_path/'counts.npz',ref)

def test_near_zero_sign_fairness(tmp_path):
    ref=toy_reference(); ref['scores'][0,0]=1e-9; submitted=ref['scores'].copy(); submitted[0,0]=-1e-9; write_submission(tmp_path,ref,submitted); q.validate_output_directory(tmp_path,ref)

def test_source_label_complement_fails(tmp_path):
    ref=toy_reference(); write_submission(tmp_path,ref); rows=q.csv_load(tmp_path/'trial_predictions.csv',q.PRED_FIELDS)
    for r in rows: r['label']=1-int(r['label']); r['prediction']=1-int(r['prediction'])
    with pytest.raises(AssertionError): q.validate_predictions(rows,ref)

@pytest.mark.parametrize('status',['failed_precondition','resource_pilot'])
def test_false_metadata_status(status):
    ref=toy_reference(); meta=copy.deepcopy(ref['metadata']); meta['status']=status
    with pytest.raises(AssertionError): q.validate_metadata(meta,ref)

def test_metadata_optional_status_warnings_and_versions():
    ref=toy_reference(); meta=copy.deepcopy(ref['metadata']); meta['software']={'independent':'v2'}; meta['fits'][0]['warnings']=['A retained numerical warning']; q.validate_metadata(meta,ref)

def test_method_extra_identity_rejected():
    ref=toy_reference(); meta=copy.deepcopy(ref['metadata']); meta['method']['hidden_feature_selection']=True
    with pytest.raises(AssertionError): q.validate_metadata(meta,ref)

def test_balancing_order():
    tr=trials_fixture(); tr['is_mouse_rewarded'][:5]=True; selected,y,folds,rows=b.select_trials(tr)
    rng=np.random.RandomState(0); positive=np.flatnonzero(tr['is_mouse_rewarded']); negative=np.flatnonzero(~tr['is_mouse_rewarded']); k=min(len(positive),len(negative))
    expected=np.sort(np.r_[rng.choice(positive,k,replace=False),rng.choice(negative,k,replace=False)])
    assert np.array_equal(selected,expected) and sum(y)*2==len(y)
    assert [r['source_trial_row'] for r in rows if r['selected']]==selected.tolist()

def test_original_boolean_required():
    tr=trials_fixture(); tr['is_mouse_rewarded']=tr['is_mouse_rewarded'].astype(int)
    with pytest.raises(AssertionError,match='Boolean'): b.select_trials(tr)

@pytest.mark.parametrize('first',[0,1])
def test_manual_fold_allocation(first):
    from sklearn.model_selection import StratifiedKFold
    y=np.array([first]*7+[1-first]*8)
    expected=np.empty(len(y),int)
    for fold,(_,test) in enumerate(StratifiedKFold(5,shuffle=True,random_state=0).split(np.zeros((len(y),1)),y)): expected[test]=fold
    assert np.array_equal(b.trial_folds(y),expected)

def test_half_open_duplicates():
    assert b.count_train(np.array([0.,1.,1.,2.]),np.array([0.,1.,2.]),np.array([1.,2.,3.])).tolist()==[1,2,1]

@pytest.mark.parametrize('train',[[1.,0.],[0.,np.nan],[-1.,0.]])
def test_invalid_spikes(train):
    with pytest.raises(AssertionError): b.count_train(train,[0.],[2.])

def test_support_overlap_half_open():
    tr=trials_fixture(); rows=b.support_rows(tr,np.arange(20),0.,50.)
    assert all(r['n_overlapping_selected_window_pairs']==0 for r in rows)

def test_scaler_constant_and_population():
    x=np.array([[1.,2.,7.],[2.,4.,7.],[3.,6.,7.]])
    mean,scale,z=b.scale_training(x)
    assert np.allclose(mean,[2,4,7]) and scale[-1]==1 and np.all(z[:,-1]==0)
    assert np.allclose(np.var(z[:,:2],axis=0),1)

def test_analytic_derivatives():
    rng=np.random.RandomState(4); x=rng.normal(size=(12,4)); y=np.arange(12)%2; p=rng.normal(size=5); _,g,h=b.objective(p,x,y); eps=1e-5
    for i in range(5):
        delta=np.eye(5)[i]*eps
        assert np.isclose(g[i],(b.objective(p+delta,x,y)[0]-b.objective(p-delta,x,y)[0])/(2*eps),atol=1e-7)
        assert np.allclose(h[:,i],(b.objective(p+delta,x,y)[1]-b.objective(p-delta,x,y)[1])/(2*eps),atol=1e-7)

def test_rank_deficient_more_features_than_trials():
    rng=np.random.RandomState(5); x=rng.poisson(2,size=(12,20)).astype(float); x[:,10:]=x[:,:10]; y=np.arange(12)%2
    scores,fit=b.independent_fit(x,y,x)
    assert scores.shape==(12,) and fit['gradient_inf']<=1e-9

def test_historical_bank_always_rejected(tmp_path):
    p=tmp_path/'old.npz'; np.savez(p,ref_stats=np.array('{}'),ref_fold_acc=np.zeros(5))
    with pytest.raises(AssertionError,match='Legacy'): pw.load_reference(p)

@pytest.mark.parametrize('kind',['existing','leaf_symlink','ancestor_symlink','same','nested'])
def test_evidence_safety(tmp_path,kind):
    output,report=tmp_path/'bank.npz',tmp_path/'report.json'
    if kind=='existing': output.write_bytes(b'existing')
    elif kind=='leaf_symlink': output.symlink_to(tmp_path/'absent')
    elif kind=='ancestor_symlink': (tmp_path/'link').symlink_to(tmp_path,target_is_directory=True); output=tmp_path/'link'/'bank.npz'
    elif kind=='same': report=output
    else: report=output/'child.json'
    with pytest.raises(AssertionError): b.validate_destinations(output,report)

def test_exclusive_bank_write(tmp_path):
    path=tmp_path/'evidence.npz'; path.write_bytes(b'keep')
    with pytest.raises(FileExistsError): b.save_reference(path,{})
    assert path.read_bytes()==b'keep'

def test_evidence_cannot_write_source(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    with pytest.raises(AssertionError,match='outside'):
        b.validate_destinations(source/'new.npz',tmp_path/'report.json',source)

def test_failed_optimizer_diagnostics_preserved(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(b,'minimize',lambda *args,**kwargs: SimpleNamespace(x=np.zeros(3),status=1,success=False,message='fixture iteration cap',nit=0))
    with pytest.raises(b.FitFailure) as error:
        b.independent_fit(np.array([[0.,1.],[1.,2.],[2.,3.],[3.,4.]]),np.array([0,0,1,1]),np.zeros((1,2)))
    assert error.value.diagnostic['optimizer_status']==1 and error.value.diagnostic['mean_gradient_inf']>1e-9

def test_public_frozen_contract_and_offline_entrypoint():
    task=Path(__file__).parents[1]
    assert b.digest(task/'environment/method_contract.json')==pw.METHOD_SHA256
    script=(task/'tests/test.sh').read_text(); assert 'python3 -m pytest' in script and 'curl' not in script and 'pip install' not in script
