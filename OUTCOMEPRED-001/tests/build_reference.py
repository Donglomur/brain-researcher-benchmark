"""Third original-source route: HDF5 + Python bisect + manual SKF/scaling + SciPy.

No oracle or independent-checker numerical imports; no model/count receipts are
inputs. Only local verifier schema/parsing helpers are shared. Original-source
runs require the parent's separately recorded scientific/resource gate.
"""
import argparse
from bisect import bisect_left
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import warnings
import h5py
import numpy as np
import scipy
from scipy.optimize import minimize
from scipy.special import expit
import prediction_contract as q
import proof_of_work as proof

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def safe_path(path):
    path=Path(path).absolute()
    q.require(not any(p.is_symlink() for p in (path,*path.parents)),'Symlink path/ancestor prohibited')

def validate_destinations(output,report,source_dir=None):
    paths=[Path(output),Path(report)]
    for p in paths:
        safe_path(p); q.require(not p.exists(),'Refuse to overwrite evidence')
    a,b=[p.resolve() for p in paths]
    q.require(a!=b and a not in b.parents and b not in a.parents,'Output/report destinations must be distinct files')
    if source_dir is not None:
        root=Path(source_dir).resolve()
        q.require(all(p!=root and root not in p.parents for p in (a,b)),'Evidence destinations must stay outside immutable source directory')

def load_sources(root,method_path):
    root,method_path=Path(root),Path(method_path)
    for p in (root,method_path,root/'source_manifest.json',root/'session.nwb'): safe_path(p)
    q.require(digest(method_path)==proof.METHOD_SHA256,'Frozen method hash mismatch')
    q.require(digest(root/'source_manifest.json')==proof.SOURCE_MANIFEST_SHA256,'Frozen manifest hash mismatch')
    manifest=q.json_load(root/'source_manifest.json'); method=q.json_load(method_path)
    q.require({p.name for p in root.iterdir()}=={'session.nwb','source_manifest.json'},'Exact two-file source layout required')
    q.require(len(manifest['files'])==1 and manifest['files'][0]['path']=='session.nwb' and manifest['files'][0]['role']=='session_nwb','Wrong source identity')
    path=root/'session.nwb'; item=manifest['files'][0]
    q.require(path.is_file() and path.stat().st_size==item['size_bytes'] and digest(path)==proof.SOURCE_SHA256==item['sha256'],'Original NWB integrity mismatch')
    return path,method

def text(x):
    return x.decode('utf8') if isinstance(x,(bytes,np.bytes_)) else str(x)

def trial_folds(labels):
    labels=np.asarray(labels)
    q.require(labels.ndim==1 and set(labels.tolist())=={0,1} and min(np.bincount(labels,minlength=2))>=5,'Five-fold support requires both classes')
    _,first,inverse=np.unique(labels,return_index=True,return_inverse=True)
    _,appearance=np.unique(first,return_inverse=True); encoded=appearance[inverse]
    sorted_labels=np.sort(encoded)
    allocation=np.array([np.bincount(sorted_labels[i::5],minlength=2) for i in range(5)])
    rng=np.random.RandomState(0); folds=np.empty(len(labels),dtype=np.int64)
    for c in range(2):
        order=np.repeat(np.arange(5),allocation[:,c]); rng.shuffle(order); folds[encoded==c]=order
    return folds

def select_trials(trials):
    ids=q.int_array(trials['id'],'original trial IDs'); n=len(ids)
    q.require(ids.ndim==1 and len(set(ids.tolist()))==n,'Unique original trial IDs required')
    q.require(np.asarray(trials['is_mouse_rewarded']).dtype.kind=='b','Original reward must be Boolean')
    for x in trials.values(): q.require(np.asarray(x).shape==(n,),'Inconsistent source trial column')
    reward=np.asarray(trials['is_mouse_rewarded']).astype(np.int64)
    reasons=[]
    for c,s,f in zip(trials['mouse_wheel_choice'],trials['gabor_stimulus_onset_time'],trials['feedback_time']):
        reasons.append('invalid_choice' if c not in ('clockwise','counter_clockwise') else 'nonfinite_stimulus' if not np.isfinite(s) else 'nonfinite_feedback' if not np.isfinite(f) else 'eligible_not_sampled')
    eligible=np.array([r=='eligible_not_sampled' for r in reasons]); pos=np.flatnonzero(eligible&(reward==1)); neg=np.flatnonzero(eligible&(reward==0)); k=min(len(pos),len(neg))
    q.require(k>=5,'Insufficient balanced five-fold support')
    rng=np.random.RandomState(0); selected=np.sort(np.r_[rng.choice(pos,k,replace=False),rng.choice(neg,k,replace=False)])
    folds=trial_folds(reward[selected]); selected_lookup={int(row):int(fold) for row,fold in zip(selected,folds)}
    rows=[]
    mapping={'stimulus_time_s':'gabor_stimulus_onset_time','feedback_time_s':'feedback_time','choice_registration_time_s':'choice_registration_time','wheel_movement_onset_time_s':'wheel_movement_onset_time'}
    for i in range(n):
        row=dict(source_trial_row=i,trial_id=int(ids[i]),choice=str(trials['mouse_wheel_choice'][i]),rewarded=int(reward[i]),eligible=int(eligible[i]),selected=int(i in selected_lookup),selection_reason='selected' if i in selected_lookup else reasons[i],fold=selected_lookup.get(i))
        row.update({k:float(trials[v][i]) if np.isfinite(trials[v][i]) else None for k,v in mapping.items()}); rows.append(row)
    return selected,reward[selected],folds,rows

def count_train(train,starts,ends):
    """Python binary search, independently of oracle NumPy searchsorted."""
    values=np.asarray(train,dtype=np.float64)
    q.require(values.ndim==1 and np.isfinite(values).all() and np.all(values>=0) and np.all(np.diff(values)>=0),'Invalid original spike train')
    original=values.tolist()
    return np.array([bisect_left(original,float(b))-bisect_left(original,float(a)) for a,b in zip(np.ravel(starts),np.ravel(ends))],dtype=np.int64).reshape(np.shape(starts))

def support_rows(trials,selected,task_start,task_stop):
    feedback=trials['feedback_time'][selected]; result=[]
    for name,start,end in q.WINDOWS:
        a,b=feedback+np.float64(start/1000),feedback+np.float64(end/1000)
        counts=[np.sum(a<trials['start_time'][selected]),np.sum(b>trials['stop_time'][selected]),np.sum(a<trials['gabor_stimulus_onset_time'][selected]),np.sum(b>trials['choice_registration_time'][selected]),np.sum(a<task_start),np.sum(b>task_stop),sum(int(np.sum((a[i]<b[i+1:])&(a[i+1:]<b[i]))) for i in range(len(a)))]
        result.append(dict(analysis=name,**{k:int(v) for k,v in zip(q.SUPPORT_FIELDS,counts)}))
    return result

def source_recompute(root,method_path):
    path,method=load_sources(root,method_path)
    with h5py.File(path,'r') as h:
        t=h['intervals/trials']; u=h['units']
        trials={k:np.asarray(t[k]) for k in method['source_validation']['trial_paths']}
        trials['mouse_wheel_choice']=np.array([text(x) for x in trials['mouse_wheel_choice']])
        selected,labels,folds,rows=select_trials(trials)
        unit_ids=q.int_array(u['id'][:],'unit IDs'); ends=q.int_array(u['spike_times_index'][:],'ragged spike index')
        spikes=u['spike_times']; q.require(spikes.dtype.kind=='f' and spikes.dtype.itemsize==8,'Original float64 spike seconds required')
        q.require(unit_ids.ndim==1 and len(set(unit_ids.tolist()))==len(unit_ids) and ends.shape==unit_ids.shape and len(ends)>0 and np.all(ends>=0) and np.all(np.diff(ends)>=0) and ends[-1]==len(spikes),'Invalid unit/ragged identity')
        q.require('obs_intervals' not in u and 'invalid_times' not in h['intervals'],'Changed source observation support')
        clock=text(h['session_start_time'][()]); reference_clock=text(h['timestamps_reference_time'][()]); q.require(clock==reference_clock,'Source time clocks differ')
        q.require(text(h['general/subject/subject_id'][()])==method['source']['subject_id'] and text(h['general/session_id'][()])==method['source']['session_id'],'Wrong session/subject')
        epochs=h['intervals/epochs']; task=[i for i,x in enumerate(epochs['protocol_type'][:]) if text(x)=='task']; q.require(len(task)==1,'Unique source task epoch required')
        task_start=float(epochs['start_time'][task[0]]); task_stop=float(epochs['stop_time'][task[0]])
        q.require(np.isfinite([task_start,task_stop]).all() and task_stop>task_start,'Invalid source task epoch')
        starts=np.array([a/1000 for _,a,_ in q.WINDOWS]); stops=np.array([b/1000 for _,_,b in q.WINDOWS])
        a=trials['feedback_time'][selected][None,:]+starts[:,None]; b=trials['feedback_time'][selected][None,:]+stops[:,None]
        counts=np.empty((21,len(selected),len(unit_ids)),dtype=np.int64); previous=0; duplicates=0
        for ui,end in enumerate(ends):
            train=np.asarray(spikes[previous:int(end)],dtype=np.float64); counts[:,:,ui]=count_train(train,a,b); duplicates+=int(np.sum(np.diff(train)==0)); previous=int(end)
        summary=dict(n_source_trials=len(rows),n_units=len(unit_ids),n_stored_spikes=len(spikes),duplicate_adjacent_spike_pairs=duplicates,nwb_version=text(h.attrs['nwb_version']),session_start_time=clock,timestamps_reference_time=reference_clock,
            kilosort_label_counts=dict(Counter(text(x) for x in u['kilosort2_label'][:])),ibl_quality_score_counts=dict(Counter(str(float(x)) for x in u['ibl_quality_score'][:])),probe_counts=dict(Counter(text(x) for x in u['probe_name'][:])),observation_support='unknown',task_epoch_start_s=task_start,task_epoch_stop_s=task_stop)
    metadata=dict(source=method['source'],source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,method=method,source_summary=summary,support_by_analysis=support_rows(trials,selected,task_start,task_stop),software=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,h5py=h5py.__version__))
    return dict(analysis=np.array(q.NAMES),window_start_s=starts,window_end_s=stops,source_trial_row=selected,trial_id=trials['id'][selected],source_unit_row=np.arange(len(unit_ids)),unit_id=unit_ids,spike_count=counts,labels=labels,folds=folds,source_rows=rows,metadata=metadata,
        provenance=dict(builder_id=proof.BUILDER_ID,source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,source_sha256=proof.SOURCE_SHA256,status='unfitted'))

def scale_training(x):
    x=np.asarray(x,dtype=np.float64); q.require(x.ndim==2 and len(x)>0 and np.isfinite(x).all(),'Invalid training counts')
    mean=x.mean(axis=0); centered=x-mean
    var=(np.sum(centered*centered,axis=0)-centered.sum(axis=0)**2/len(x))/len(x)
    q.require(np.isfinite(var).all() and np.all(var>=0),'Invalid population variance')
    eps=np.finfo(float).eps; scale=np.sqrt(var); scale[var<=len(x)*eps*var+(len(x)*mean*eps)**2]=1
    return mean,scale,centered/scale

def objective(p,x,y):
    z=x@p[:-1]+p[-1]; prob=expit(z); residual=prob-y
    value=float(np.sum(np.logaddexp(0,(1-2*y)*z))+.5*np.dot(p[:-1],p[:-1]))
    gradient=np.r_[x.T@residual+p[:-1],residual.sum()]; weight=prob*(1-prob); wx=x*weight[:,None]
    hessian=np.empty((len(p),len(p))); hessian[:-1,:-1]=x.T@wx+np.eye(x.shape[1]); hessian[:-1,-1]=wx.sum(axis=0); hessian[-1,:-1]=hessian[:-1,-1]; hessian[-1,-1]=weight.sum()
    return value,gradient,hessian

class FitFailure(RuntimeError):
    def __init__(self,diagnostic):
        super().__init__('Independent fit violates public finite mean-gradient criterion')
        self.diagnostic=diagnostic

def independent_fit(train,y,test):
    mean,scale,x=scale_training(train); y=np.asarray(y,dtype=float)
    q.require(set(y.tolist())=={0.,1.} and len(y)==len(x),'Both training classes required')
    cache={}
    def evaluate(p):
        if 'p' not in cache or not np.array_equal(cache['p'],p): cache.update(p=p.copy(),answer=objective(p,x,y))
        return cache['answer']
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fit=minimize(lambda p:evaluate(p)[0],np.zeros(x.shape[1]+1),method='trust-exact',jac=lambda p:evaluate(p)[1],hess=lambda p:evaluate(p)[2],options=dict(gtol=len(x)*1e-11,maxiter=500))
    loss,g,_=evaluate(fit.x); norm=float(np.max(np.abs(g))/len(x))
    diagnostic=dict(optimizer_status=int(fit.status),optimizer_success=bool(fit.success),optimizer_message=str(fit.message),iterations=int(fit.nit),
        mean_gradient_inf=norm if np.isfinite(norm) else None,finite_parameters=bool(np.isfinite(fit.x).all()),warnings=[f'{w.category.__name__}: {w.message}' for w in caught])
    if not np.isfinite(fit.x).all() or not np.isfinite(norm) or norm>1e-9:
        raise FitFailure(diagnostic)
    score=((test-mean)/scale)@fit.x[:-1]+fit.x[-1]; q.require(np.isfinite(score).all(),'Nonfinite decision scores')
    return score,dict(scaler_mean=mean,scaler_scale=scale,coef=fit.x[:-1],intercept=float(fit.x[-1]),gradient_inf=norm,optimizer_status=int(fit.status),optimizer_success=bool(fit.success),optimizer_message=str(fit.message),iterations=int(fit.nit),objective=loss,warnings=[f'{w.category.__name__}: {w.message}' for w in caught])

def fit_all(ref,pilot=False):
    specs=[(a,f) for a in range(21) for f in range(5)] if not pilot else [(0,0),(1,0)]
    scores=np.full((21,len(ref['labels'])),np.nan); models=[]; diagnostics=[]
    for ai,fold in specs:
        train,test=ref['folds']!=fold,ref['folds']==fold
        try:
            values,model=independent_fit(ref['spike_count'][ai,train],ref['labels'][train],ref['spike_count'][ai,test])
        except FitFailure as error:
            error.diagnostic.update(analysis=q.NAMES[ai],fold=fold)
            raise
        scores[ai,test]=values
        model.update(model_analysis=ai,model_fold=fold); models.append(model)
        diagnostics.append(dict(analysis=q.NAMES[ai],fold=fold,mean_gradient_inf=model['gradient_inf'],finite_parameters=True,optimizer_status=model['optimizer_status'],warnings=model['warnings'],optimizer_success=model['optimizer_success'],optimizer_message=model['optimizer_message'],iterations=model['iterations']))
    ref['scores']=scores
    for key in ('model_analysis','model_fold','scaler_mean','scaler_scale','coef','intercept','gradient_inf'): ref[key]=np.array([m[key] for m in models])
    ref['metadata']['fits']=diagnostics; ref['provenance']['status']='resource_pilot' if pilot else 'complete'
    return ref

def save_reference(path,ref):
    metadata={k:v for k,v in ref.items() if k not in proof.ARRAYS}
    with Path(path).open('xb') as f:
        np.savez_compressed(f,**{k:ref[k] for k in proof.ARRAYS},reference_json=np.array(json.dumps(metadata,allow_nan=False)))

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--source-dir',type=Path,default='/app/data/outcomepred'); p.add_argument('--method-contract',type=Path,default='/app/method_contract.json'); p.add_argument('--output',type=Path,required=True); p.add_argument('--report',type=Path,required=True); p.add_argument('--pilot',action='store_true'); p.add_argument('--oracle-output',type=Path); args=p.parse_args()
    validate_destinations(args.output,args.report,args.source_dir)
    q.require(args.pilot or args.oracle_output is not None,'Full bank must validate a genuine original-source oracle output')
    try:
        ref=fit_all(source_recompute(args.source_dir,args.method_contract),args.pilot)
    except FitFailure as error:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x') as f:
            json.dump(dict(status='failed_precondition',reason=str(error),fit_diagnostic=error.diagnostic,source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256),f,indent=2,allow_nan=False)
            f.write('\n')
        raise
    if not args.pilot: q.validate_output_directory(args.oracle_output,ref)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.report.parent.mkdir(parents=True,exist_ok=True); save_reference(args.output,ref)
    if not args.pilot: proof.load_reference(args.output)
    report=dict(status='resource_pilot' if args.pilot else 'complete',builder_id=proof.BUILDER_ID,source_manifest_sha256=proof.SOURCE_MANIFEST_SHA256,method_contract_sha256=proof.METHOD_SHA256,source_sha256=proof.SOURCE_SHA256,reference_sha256=digest(args.output),n_source_trials=len(ref['source_rows']),n_trials=len(ref['labels']),n_units=len(ref['unit_id']),n_models=len(ref['model_fold']),max_mean_gradient_inf=float(ref['gradient_inf'].max()),optimizer_diagnostics=ref['metadata']['fits'],source_only_construction=True,oracle_used_only_as_validation_target=True)
    with args.report.open('x') as f: json.dump(report,f,indent=2,allow_nan=False); f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='optimizer_diagnostics'},indent=2),flush=True)

if __name__=='__main__': main()
