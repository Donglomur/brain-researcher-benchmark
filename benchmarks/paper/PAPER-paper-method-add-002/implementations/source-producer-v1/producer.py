"""Original Churchland source producer; no historical-factor or paper-win claim.

All source-shaped preparation/model calls are opt-in operator APIs. Importing
this module does not open data, fit a model, or invoke callbacks. Generated
controls use numerical arrays unrelated to the scientific originals.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import stat
import numpy as np
import scipy
from scipy.ndimage import gaussian_filter1d

ENDPOINTS = Path(__file__).resolve().parents[1]/'source-endpoints-v1'/'endpoints.py'
ENDPOINTS_SHA256='5e33cbf59c352951d53c0b4d544ab3ff0887c51b6a0e5eff171be43c6f62d049'
if hashlib.sha256(ENDPOINTS.read_bytes()).hexdigest()!=ENDPOINTS_SHA256:
 raise ValueError('source-endpoints-v1 dependency hash differs')
spec=importlib.util.spec_from_file_location('churchland_source_endpoints',ENDPOINTS)
endpoints=importlib.util.module_from_spec(spec);spec.loader.exec_module(endpoints)
SOURCE_REVISION='62b0ca1267fe9d615111a193080577eda601687e'
ORIGINALS={
 'neurons_10_straight_Churchland.npy':(57876128,'b0fda8d0fa20c9836b58c043b3c32cd0bd1a455c936bcbcf12d30ce0fa7dd7ef',(265,182,150)),
 'neurons_10_curved_Churchland.npy':(53726528,'3ae736672516af6f6049def187790d93ccd45cf202c74772874d1d42f2acf22d',(246,182,150)),
 'movement.npy':(1226528,'38eecbc01d91e930aef5514ab46de8511a7219023a3b0e0dbb773f930487c12c',(150,511,2)),
 'target_angle.npy':(4216,'33c29f956be9bec148eee78e36c00a0968fd6c9fcc01b0a79db45b7306ea5a8d',(511,)),
 'target_pos.npy':(8304,'86fe9d8633c7df7694d7a824621a1ac3892888768f469fe9419c5c9a4db96e23',(511,2)),
 'condition.npy':(4216,'451b595347e92ba51dda1521a93923336d168ac93363c39909b4fd17002078da',(511,)),
}
# Rank ordering is named explicitly. Source tensors are trial x neuron x time.
MODEL_ROSTER={
 'raw':{'kind':'raw'},
 'neuron_nmf12':{'kind':'slice','ranks':{'trial':0,'neuron':12,'time':0}},
 'trial_nmf12':{'kind':'slice','ranks':{'trial':12,'neuron':0,'time':0}},
 'tca12':{'kind':'cp','rank':12},
 'mixed_slice12_1':{'kind':'slice','ranks':{'trial':12,'neuron':0,'time':1}},
 'lfads':{'kind':'external','historical_outputs_available':False},
}

def mixed_optimizer_recipe(route):
 """Explicit released447-step versus paper-described450-step configurations."""
 need(route in ('source_notebook447','paper_described450'),'named optimizer route required')
 updates=149 if route=='source_notebook447' else 150
 return {'route':route,'ranks':{'trial':12,'neuron':0,'time':1},'nonnegative':True,'parameter_to_factor':'absolute_value_per_factor','initialization':'uniform_positive','learning_rate':0.02,'optimizer':'Adam','phases':[{'updates':updates,'omitted_entry_fraction':fraction,'reset_optimizer':True,'reset_torch_seed':True} for fraction in (0.8,0.4,0.2)],'mask_refresh_updates':20,'fixed_cross_validation':False,'orthogonal_penalty':False,'source_seed_roster':list(range(10)),'runtime_and_historical_fit_authenticated':False}

def need(ok,message):
 if not ok:raise ValueError(message)

def real(value,name,ndim=None):return endpoints._real(value,name,ndim)

def file_hash(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
 return h.hexdigest()

def load_originals(directory):
 """Authenticate each exact numeric NPY before decoding, with no pickle support."""
 result={}
 for name,(size,sha,shape) in ORIGINALS.items():
  path=Path(directory)/name
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as f:
   before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and before.st_size==size,'source extent: '+name)
   h=hashlib.sha256()
   for block in iter(lambda:f.read(1024**2),b''):h.update(block)
   need(h.hexdigest()==sha,'source hash: '+name);f.seek(0)
   values=np.load(f,allow_pickle=False,max_header_size=4096)
   need(isinstance(values,np.ndarray) and values.shape==shape and values.dtype.kind in 'fiu','source shape/type: '+name)
   values=real(values,name)
   after=os.fstat(f.fileno())
   need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'source changed while reading')
   result[name]=values
 need(np.equal(result['condition.npy'],np.floor(result['condition.npy'])).all(),'noninteger condition labels')
 return result

def preprocess_neural(trial_neuron_time):
 """Source count*100, Gaussian sigma2 bins, per-neuron full-data min/max."""
 x=real(trial_neuron_time,'neural',3).copy()
 need(np.all(x>=0),'neural input contains negative counts')
 x*=100.0
 gaussian_filter1d(x,2,axis=2,output=x,mode='reflect',truncate=4.0)
 minimum=x.min(axis=(0,2),keepdims=True);x-=minimum
 scale=x.max(axis=(0,2),keepdims=True)
 need(np.all(scale>0) and np.isfinite(scale).all(),'undefined neuron scaling')
 x/=scale
 return x.astype(np.float32),{'minimum_hz':minimum.ravel(),'range_hz':scale.ravel(),'exposure':'all trials, all time bins before decoder folds','sigma_source_bins':2,'bin_width_ms':10,'filter_mode':'reflect','filter_truncate':4.0}

def prepare_arrays(originals):
 need(set(originals)==set(ORIGINALS),'exact six originals required')
 for name,(_,_,shape) in ORIGINALS.items():need(real(originals[name],name).shape==shape,'full original shape required: '+name)
 joined=np.concatenate((originals['neurons_10_straight_Churchland.npy'],originals['neurons_10_curved_Churchland.npy']),axis=0)
 neural,normalization=preprocess_neural(joined)
 return {'neural':neural,'movement':originals['movement.npy'],'target_angle':originals['target_angle.npy'],'target_pos':originals['target_pos.npy'],'condition':originals['condition.npy'],'normalization':normalization,'source_trial_indices':np.arange(511),'biological_trial_ids_authenticated':False}

def slice_reconstruction(factors,shape,*,modes=('trial','neuron','time'),components=None):
 """Already-exported nonnegative factors; no arbitrary gauge rotation or refit."""
 need(len(shape)==3 and all(type(v) is int and v>0 for v in shape),'trial/neuron/time shape required')
 need(set(factors)=={'trial','neuron','time'},'all three named factor families required')
 need(len(set(modes))==len(modes) and set(modes)<=set(factors),'unknown or duplicate slicing mode')
 need(components is None or (isinstance(components,dict) and set(components)<=set(factors)),'unknown component selector')
 out=np.zeros(shape,dtype=np.float64)
 for axis,mode in enumerate(('trial','neuron','time')):
  pair=factors[mode];need(isinstance(pair,(tuple,list)) and len(pair)==2,'vector/slice pair required')
  v=np.asarray(pair[0]);s=np.asarray(pair[1]);rank=v.shape[0] if v.ndim==2 else -1
  expected=(rank,)+tuple(n for i,n in enumerate(shape) if i!=axis)
  need(v.shape==(rank,shape[axis]) and s.shape==expected,'factor dimensions: '+mode)
  need(v.dtype.kind in 'fiu' and s.dtype.kind in 'fiu' and np.isfinite(v).all() and np.isfinite(s).all() and np.all(v>=0) and np.all(s>=0),'nonnegative exported factors required')
  selected=list(range(rank)) if components is None else list(components.get(mode,[]))
  need(len(set(selected))==len(selected) and all(type(k) is int and 0<=k<rank for k in selected),'component selection differs')
  if mode not in modes:continue
  for k in selected:
   if mode=='trial':out+=v[k,:,None,None]*s[k,None,:,:]
   elif mode=='neuron':out+=v[k,None,:,None]*s[k,:,None,:]
   else:out+=v[k,None,None,:]*s[k,:,:,None]
 need(np.isfinite(out).all(),'reconstruction overflow')
 return out

def cp_reconstruction(factors):
 need(set(factors)=={'trial','neuron','time'},'CP must contain three axis factors')
 arrays=[real(factors[k],k,2) for k in ('trial','neuron','time')]
 need(len({a.shape[0] for a in arrays})==1 and all(np.all(a>=0) for a in arrays),'CP ranks/nonnegativity differ')
 output=np.einsum('ri,rj,rk->ijk',*arrays,optimize=True)
 need(np.isfinite(output).all(),'CP reconstruction overflow');return output

def materialize_model(neural,model_name,callback,*,seed,optimizer_spec,mask_identity,reference_identity):
 """Explicit callback interface; a returned factor set does not validate a fit.

 The caller owns execution admission. LFADS must supply an independent complete
 output; it is never synthesized from another comparator.
 """
 x=real(neural,'neural',3);need(x.shape==(511,182,150),'complete Churchland tensor required')
 need(model_name in MODEL_ROSTER,'unknown source model')
 if model_name=='raw':return {'reconstruction':x.copy(),'factors':None,'source_fit_authenticated':False,'exposure':'all neural data'}
 need(type(seed) is int and isinstance(optimizer_spec,dict) and optimizer_spec and isinstance(mask_identity,str) and mask_identity and isinstance(reference_identity,str) and reference_identity,'explicit seed, optimizer, mask and reference identities required')
 need(callable(callback),'model producer callback required; no placeholder reconstruction')
 spec=copy.deepcopy(MODEL_ROSTER[model_name])
 result=callback(x.copy(),model_name=model_name,model_spec=copy.deepcopy(spec),seed=seed,optimizer_spec=copy.deepcopy(optimizer_spec),mask_identity=mask_identity)
 need(isinstance(result,dict) and 'factors' in result,'callback must supply named factors')
 factors=result['factors']
 if spec['kind']=='slice':
  need({k:np.asarray(factors[k][0]).shape[0] for k in ('trial','neuron','time')}==spec['ranks'],'wrong source rank roster')
  reconstruction=slice_reconstruction(factors,x.shape)
 elif spec['kind']=='cp':
  need(np.asarray(factors['trial']).shape[0]==spec['rank'],'wrong CP rank');reconstruction=cp_reconstruction(factors)
 else:
  reconstruction=real(result.get('reconstruction'),'external LFADS output',3)
  need(factors is None,'LFADS factor decomposition is not provided by this source route')
 need(reconstruction.shape==x.shape,'complete model reconstruction required')
 partials={}
 if model_name=='mixed_slice12_1':
  partials={'mixed_full':reconstruction,'mixed_trial_only':slice_reconstruction(factors,x.shape,modes=('trial',)), 'mixed_time_only':slice_reconstruction(factors,x.shape,modes=('time',))}
 return {'reconstruction':reconstruction,'partial_reconstructions':partials,'factors':factors,'seed':seed,'optimizer_spec':optimizer_spec,'mask_identity':mask_identity,'reference_identity':reference_identity,'source_fit_authenticated':False,'exposure':'all neural data; decoder folds do not protect representation fitting'}

def fit_linear(x,y,*,recipe):
 need(recipe in endpoints.RECIPES,'explicit paper_ols0 or source_code_ridge1 recipe required')
 x=real(x,'decoder features');y=real(y,'decoder targets')
 need(x.shape[:-1]==y.shape[:-1] and x.ndim>=2 and y.shape[-1]==2,'decoder axes differ')
 design=np.concatenate((x.reshape(-1,x.shape[-1]),np.ones((np.prod(x.shape[:-1]),1))),axis=1)
 target=y.reshape(-1,2);alpha=endpoints.RECIPES[recipe]
 if alpha==0:coeff=np.linalg.lstsq(design,target,rcond=None)[0]
 else:coeff=np.linalg.solve(design.T@design+alpha*np.eye(design.shape[1]),design.T@target)
 need(np.isfinite(coeff).all(),'nonfinite fitted coefficients')
 return {'weight':coeff[:-1].T,'bias':coeff[-1],'recipe':recipe,'bias_penalized':bool(alpha)}

def predict_positions(model,x,initial_position):
 values=real(x,'test neural',3);initial=real(initial_position,'true initial position',2)
 need(initial.shape==(values.shape[1],2) and model['weight'].shape==(2,values.shape[2]),'prediction feature/initial axes differ')
 delta=values[:-1]@model['weight'].T+model['bias']
 return endpoints.integrate_displacements(delta,initial)

def fit_velocity(data,movement,*,recipe):
 x=real(data,'decoder neural',3);y=real(movement,'movement',3)
 need(x.shape[:2]==y.shape[:2] and x.shape[0]>=2,'neural/position time-trial axes differ')
 return fit_linear(x[:-1],np.diff(y,axis=0),recipe=recipe)

def repeated_decoding(neural_time_trial_neuron,movement,*,recipe):
 x,y=endpoints.source_windows(neural_time_trial_neuron,movement)
 results={}
 for condition in endpoints.CONDITIONS:
  plan=endpoints.source_schedule(condition);width=plan['test'].shape[-1]
  predictions=np.empty((20,5,80,width,2))
  for repeat in range(20):
   for fold in range(5):
    train=plan['train'][repeat,fold];test=plan['test'][repeat,fold]
    model=fit_velocity(x[:,train],y[:,train],recipe=recipe)
    predictions[repeat,fold]=predict_positions(model,x[:,test],y[0,test])
  summary,details=endpoints.score_condition(movement,condition,predictions,plan['test'])
  summary['descriptive_mean_within_fold_sem_ddof0']=float(details['fold_population_sd'].mean()/np.sqrt(width))
  summary['descriptive_mean_within_fold_sem_ddof1']=float(details['r2'].std(axis=-1,ddof=1).mean()/np.sqrt(width))
  summary['original_plot_errorbar_aggregation_authenticated']=False
  results[condition]={'prediction':predictions,'test_indices':plan['test'],'summary':summary,'details':details}
 return {'recipe':recipe,'conditions':results,'representation_exposure':'supplied full-data reconstruction; no representation holdout claim'}

def averaged_half(data,movement,angles,train,test,*,recipe):
 labels=np.unique(angles[np.concatenate((train,test))]);need(all(np.any(angles[train]==a) and np.any(angles[test]==a) for a in labels),'a condition is missing from a half; source would yield NaN')
 def average(x,ids):return np.stack([x[:,ids[angles[ids]==a]].mean(axis=1) for a in labels],axis=1)
 xtrain,ytrain=average(data,train),average(movement,train)
 xtest,ytest=average(data,test),average(movement,test)
 decoder=fit_velocity(xtrain,ytrain,recipe=recipe);prediction=predict_positions(decoder,xtest,ytest[0])
 return {'condition_labels':labels,'target':ytest,'prediction':prediction,'r2':endpoints.trajectory_r2(ytest,prediction)['r2'],'train_indices':train.copy(),'test_indices':test.copy()}

def condition_average_control(neural_time_trial_neuron,movement,angles,*,recipe):
 """Exact source two-half/20-repeat cumulative shuffle, distinct from five-fold.

 Source plot_k_fold resets MT19937 to0 for each model/condition. Its final
 curved call consumes20permutations of246 before get_r2_all uses global state.
 """
 x,y=endpoints.source_windows(neural_time_trial_neuron,movement);a=real(angles,'target angles',1)
 need(a.shape==(511,),'all source angles required')
 rng=np.random.RandomState(0)
 for _ in range(20):rng.permutation(246)
 result={}
 for condition,(start,stop) in endpoints.CONDITIONS.items():
  order=np.arange(start,stop);half=len(order)//2;rows=[]
  for repeat in range(20):
   order=order[rng.permutation(len(order))] # source permutes already-permuted arrays
   pair=[]
   for current in (order,order[::-1]):
    pair.append(averaged_half(x,y,a,current[:half],current[half:],recipe=recipe))
   rows.append(pair)
  scores=np.stack([np.stack([row['r2'] for row in pair]) for pair in rows])
  result[condition]={'rows':rows,'r2':scores,'mean_condition_half_repeat_r2':float(scores.mean()),'independent_unit':'condition averages; not trial-wise five-fold control','uncertainty':'none; dependent repeated halves','rng_origin':'after final seed0 curved five-fold20-repeat source call'}
 return {'recipe':recipe,'conditions':result}

def component_results(factors,condition,target_pos,*,recipe,region_map,target_projection_route,preparatory_time_indices=None):
 """Source Figure2 numerical panels; retain supplied component order/gauge.

 Target projection follows released in-sample fitting, not a claimed five-fold
 historical target-decoding replication. No rotation/orthogonalization is added.
 """
 shapes={'trial':((12,511),(12,182,150)),'neuron':((0,182),(0,511,150)),'time':((1,150),(1,511,182))}
 need(set(factors)==set(shapes),'complete mixed factor families required')
 for mode,(vshape,sshape) in shapes.items():
  v,s=map(np.asarray,factors[mode]);need(v.shape==vshape and s.shape==sshape,'mixed component shape differs')
  need(np.isfinite(v).all() and np.isfinite(s).all() and np.all(v>=0) and np.all(s>=0),'invalid exported factors')
 c=real(condition,'condition',1);target=real(target_pos,'target position',2)
 need(c.shape==(511,) and target.shape==(511,2),'complete component labels required')
 need(region_map in ('source_code_92_90','paper_counts_unbound'),'explicit region mapping route required')
 trial_weights,trial_slices=factors['trial'];time_vector,time_slice=factors['time'];preparatory=time_slice[0]
 source_condition_order=(20,22,10,34,18,39,32,5,37,35,26,31)
 need(np.isin(c,source_condition_order).all(),'unknown source component condition label')
 order=np.concatenate([np.flatnonzero(c[lo:hi]==label)+lo for lo,hi in ((0,265),(265,511)) for label in source_condition_order])
 need(len(order)==511 and len(np.unique(order))==511,'source condition ordering loses trials')
 correlation={}
 selections={'all':slice(None)}
 if region_map=='source_code_92_90':selections.update({'source_code_M1':slice(0,92),'source_code_PMd':slice(92,None)})
 for label,columns in selections.items():
  values=preparatory[order,columns]
  need(np.all(values.std(axis=1)>0),'undefined component row correlation')
  correlation[label]=np.corrcoef(values)
 need(target_projection_route in ('source_raw_factor','paper_partial_average_ols'),'explicit target projection route required')
 projection_features=preparatory
 if target_projection_route=='paper_partial_average_ols':
  need(recipe=='paper_ols0','paper target projection requires OLS')
  indices=np.asarray(preparatory_time_indices)
  need(indices.ndim==1 and indices.size>0 and indices.dtype.kind in 'iu' and np.all((indices>=0)&(indices<150)) and len(np.unique(indices))==len(indices),'explicit unique preparatory source-bin indices required; no inferred physical window')
  projection_features=time_vector[0,indices].mean()*preparatory
 centered=target-target.mean(axis=0);projections={}
 for reach,(lo,hi) in endpoints.CONDITIONS.items():
  model=fit_linear(projection_features[lo:hi],centered[lo:hi],recipe=recipe)
  projections[reach]={'target':centered[lo:hi],'prediction':projection_features[lo:hi]@model['weight'].T+model['bias'],'fit_support':'same trials as displayed; in-sample result only','paper_fivefold_target_projection_reproduced':False}
 return {'trial_weights':np.asarray(trial_weights).copy(),'trial_slices':np.asarray(trial_slices).copy(),'time_vector':np.asarray(time_vector).copy(),'preparatory_trial_neuron_slice':preparatory.copy(),'trial_slice_peak_bin_by_neuron':np.asarray(trial_slices).argmax(axis=2),'first_supplied_trial_component_neuron_order':np.argsort(np.asarray(trial_slices)[0].argmax(axis=1)),'condition_sorted_trial_indices':order,'condition_correlations':correlation,'target_projections':projections,'target_projection_route':target_projection_route,'preparatory_time_indices':preparatory_time_indices,'preparatory_physical_window_authenticated':False,'factor_gauge':'as supplied; no historical identity or nonnegative gauge equivalence claimed','region_mapping':region_map,'paper_region_counts':{'M1':90,'PMd':92},'source_code_region_counts':{'M1':92,'PMd':90}}

def score_reconstruction_cell(neural,reconstruction,training_mask,*,cut_bins):
 return endpoints.reconstruction_error(neural,reconstruction,training_mask,cut_bins=cut_bins)

def preparatory_subspace(factors,condition,target_pos,*,route):
 """Figure2h source route; explicit whole-span orthogonalization is separate.

 Paper's target axes orthogonalized to curvature are not equated to this source
 default or its whole-three-axis-span orth() option. No factor gauge changes.
 """
 from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
 from scipy.linalg import orth
 need(route in ('source_default_axes','source_orthogonal_span'),'named source subspace route required')
 matrix=real(factors['time'][1],'preparatory slices',3)
 c=real(condition,'conditions',1);target=real(target_pos,'target positions',2)
 need(matrix.shape==(1,511,182) and c.shape==(511,) and target.shape==(511,2),'complete Figure2h operands required')
 need(np.all(matrix>=0),'nonnegative exported preparatory slice required')
 x=matrix[0,265:];centered=target-target.mean(axis=0)
 y=centered[265:];labels=np.where(np.isin(c[265:],(5,18,20,22,26,35,39)),0,1)
 need(len(np.unique(labels))==2,'both curved-direction source classes required')
 discriminant=LinearDiscriminantAnalysis().fit(x,labels).coef_[0]
 target_axes=np.linalg.lstsq(x,y,rcond=None)[0].T # source no-intercept axes
 axes=np.concatenate((discriminant[None],target_axes),axis=0)
 projection_axes=axes.T if route=='source_default_axes' else orth(axes.T)
 coordinates=x@projection_axes
 need(np.isfinite(coordinates).all(),'nonfinite preparatory subspace')
 return {'coordinates':coordinates,'projection_axes':projection_axes,'source_class_labels':labels,'source_trial_indices':np.arange(265,511),'route':route,'fit_support':'all curved trials; in-sample explanatory projection','paper_target_axes_orthogonalization_reproduced':False,'historical_factor_gauge_authenticated':False}

def source_result_family(prepared,model_results,*,recipe,region_map,target_projection_route,subspace_route,preparatory_time_indices=None):
 """Executable same-task result producer, with every unavailable model explicit.

 Calling this function fits linear decoders. Authentic use requires separate
 execution admission. Model/decomposition fitting is supplied independently;
 absent LFADS or historical factors can never become a paper-complete roster.
 """
 neural=real(prepared['neural'],'prepared neural',3)
 need(neural.shape==(511,182,150),'complete original neural tensor required')
 need(set(model_results)<=set(MODEL_ROSTER)-{'raw'},'unknown supplied model')
 representations={'raw':neural}
 for name,result in model_results.items():
  reconstruction=real(result['reconstruction'],name,3)
  need(reconstruction.shape==neural.shape,'incomplete model reconstruction')
  representations[name]=reconstruction
  if name=='mixed_slice12_1':
   need(result.get('factors') is not None,'mixed source components required')
   factors=result['factors']
   need(set(factors)=={'trial','neuron','time'} and {k:np.asarray(factors[k][0]).shape[0] for k in factors}==MODEL_ROSTER[name]['ranks'],'mixed source factor ranks differ')
   need(np.array_equal(reconstruction,slice_reconstruction(factors,neural.shape)),'mixed full reconstruction differs from the factors used for partials')
   representations['mixed_trial_only']=slice_reconstruction(factors,neural.shape,modes=('trial',))
   representations['mixed_time_only']=slice_reconstruction(factors,neural.shape,modes=('time',))
 decoding={name:repeated_decoding(x.transpose(2,0,1),prepared['movement'],recipe=recipe) for name,x in representations.items()}
 averaged=condition_average_control(neural.transpose(2,0,1),prepared['movement'],prepared['target_angle'],recipe=recipe)
 components=None;subspace=None
 if 'mixed_slice12_1' in model_results:
  components=component_results(model_results['mixed_slice12_1']['factors'],prepared['condition'],prepared['target_pos'],recipe=recipe,region_map=region_map,target_projection_route=target_projection_route,preparatory_time_indices=preparatory_time_indices)
  subspace=preparatory_subspace(model_results['mixed_slice12_1']['factors'],prepared['condition'],prepared['target_pos'],route=subspace_route)
 return {'single_trial_decoding':decoding,'raw_condition_average_control':averaged,'component_results':components,'preparatory_subspace':subspace,'unavailable_required_models':sorted(set(MODEL_ROSTER)-{'raw'}-set(model_results)),'figure2e_mixed_readout':'mixed_trial_only','mixed_full_key':'mixed_slice12_1','reconstruction_panel':'requires externally authenticated mask/rank/seed cells through score_reconstruction_cell','paper_reproduction_admitted':False,'paper_improvement_admitted':False,'historical_reference_scores_authenticated':False}

def prepare_cli(inputs,output):
 destination=Path(output);need(not destination.exists(),'fresh private output required')
 originals=load_originals(inputs);prepared=prepare_arrays(originals)
 destination.mkdir(mode=0o700,parents=True)
 for key in ('neural','movement','target_angle','target_pos','condition','source_trial_indices'):
  with (destination/(key+'.npy')).open('xb') as f:np.save(f,prepared[key],allow_pickle=False)
  os.chmod(destination/(key+'.npy'),0o600)
 norm=prepared['normalization'];np.savez(destination/'normalization.npz',minimum_hz=norm['minimum_hz'],range_hz=norm['range_hz'])
 os.chmod(destination/'normalization.npz',0o600)
 manifest={'task_id':'PAPER-paper-method-add-002','source_revision':SOURCE_REVISION,'status':'complete_original_array_preparation_only','trials':511,'straight_trials':265,'curved_trials':246,'neurons':182,'source_bins':150,'decoded_bins':80,'models_fitted':0,'scientific_scores':0,'candidate_attempts':0,'paper_reproduction_admitted':False,'biological_trial_ids_authenticated':False,'exposure':norm['exposure'],'files':{p.name:{'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in destination.iterdir()}}
 manifest['source_files']={name:{'bytes':size,'sha256':sha,'shape':shape} for name,(size,sha,shape) in ORIGINALS.items()}
 manifest['runtime']={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__}
 manifest['producer_sha256']=file_hash(__file__)
 need(sum(row['bytes'] for row in manifest['files'].values())<=96*1024**2,'prepared output size cap')
 (destination/'COMPLETE.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');os.chmod(destination/'COMPLETE.json',0o600)
 return manifest

def main():
 parser=argparse.ArgumentParser(description='Only complete original-array preparation; no model/scoring CLI.')
 parser.add_argument('--inputs',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args();report=prepare_cli(args.inputs,args.output)
 print(json.dumps({'status':report['status'],'trials':511,'models_fitted':0}));return 0

if __name__=='__main__':raise SystemExit(main())
