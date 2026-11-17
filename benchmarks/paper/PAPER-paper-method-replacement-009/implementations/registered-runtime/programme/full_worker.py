"""Fixed trusted future worker. Called only inside the selected OCI image.
Preparation, fitting and diagnostics have real implementations; no provider callbacks.
"""
from pathlib import Path
import json,sys,io
from .native.io import read,load,write_new,dump,identity,need,relative
from .native.observation import Observation
from .domain import MissingDefinition,Refusal

def array_write(root,name,array):
 import numpy as np
 a=np.asarray(array);need(a.dtype.kind in'biuf'and not a.dtype.hasobject,'primitive array only')
 stream=io.BytesIO();np.save(stream,a,allow_pickle=False);body=stream.getvalue();pin=write_new(Path(root)/relative(name),body,len(body))
 return {'path':name,**pin,'shape':list(a.shape),'dtype':a.dtype.str}

def array_read(root,row):
 import numpy as np
 body=read(Path(root)/relative(row['path']),row['bytes'],row);a=np.load(io.BytesIO(body),allow_pickle=False)
 need(list(a.shape)==row['shape']and a.dtype.str==row['dtype']and not a.dtype.hasobject,'exact array axes/domain');return a

def partitions(case,compiled,definition,common):
 from .interchange import prospective_split
 if case['cohort']=='prospective40':
  # A single all-target eligible union is frozen before materializing any case.
  assignments=common[case['session']]
  return [assignments[str(i)]for i in compiled['trial_ids']]
 original=definition['split']
 need(original['source']is not None and original['recipe']=='original_ordered_assignments','original historical folds required')
 assignments={json.dumps(i,sort_keys=True):p for i,p in zip(original['trial_ids'],original['partition'])}
 need(len(assignments)==len(original['trial_ids']),'unique historical trial IDs')
 return [assignments[json.dumps(i,sort_keys=True)]for i in compiled['trial_ids']]

def prepare(request,inputs,output):
 import numpy as np
 from .full_inputs import read_local,compile_case
 from .full_state import original_fitted_prior
 from .interchange import prospective_split
 study=load(inputs/'study.json');definitions=load(inputs/'definitions.json');compiled={};states={};errors={};raws={};priors={}
 owner=Observation('full_preparation');owner.record['cases']=states
 for case in study['cases']:
  key=case['id'];states[key]={'status':case['status'],'reason':case['reason']}
  if case['status']!='available':continue
  try:
   definition=definitions[key];session=(case['dataset'],case['session'])
   if session not in raws:raws[session]=read_local(definition)
   raw=raws[session];prior=None
   if case['target']=='prior':
    if session not in priors:priors[session]=original_fitted_prior(raw['trials'],definition['prior'],Path('/scratch/prior')/case['session'])
    prior=priors[session]
   compiled[key]=compile_case(raw,case,definition,prior);states[key]={'status':'compiled','reason':None}
  except BaseException as exc:
   owner.fail(exc,'prepare:'+key);errors[key]=exc;states[key]={'status':'failed','reason':type(exc).__name__}
 # Compile the RE union before any split-specific files are emitted. Missing
 # target support remains a failed session, never a smaller replacement union.
 common={}
 for session in {c['session']for c in study['cases']if c['cohort']=='prospective40'}:
  group=[c for c in study['cases']if c['cohort']=='prospective40'and c['session']==session]
  if any(c['status']=='available'and c['id']not in compiled for c in group):
   for c in group:
    if c['id']in compiled:del compiled[c['id']];states[c['id']]={'status':'failed','reason':'common_target_union_unavailable'}
   continue
  union=sorted({int(t)for c in group if c['id']in compiled for t in compiled[c['id']]['trial_ids']})
  ids=[{'kind':'integer','value':i}for i in union];parts=prospective_split(session,ids)
  common[session]={str(i):p for i,p in zip(union,parts)}
 published=[]
 for case in study['cases']:
  key=case['id']
  if key not in compiled:continue
  try:
   data=compiled[key];part=partitions(case,data,definitions[key],common);meta={k:v for k,v in data.items()if k not in('x','y')};meta.update(case=case,partition=part,arrays={})
   meta['arrays']['all_x']=array_write(output,'public/'+key+'/all_x.npy',data['x'])
   meta['arrays']['truth']=array_write(output,'private/'+key+'/truth.npy',data['y'])
   for role in('train','validation','test'):
    indices=np.asarray([i for i,p in enumerate(part)if p==role],dtype=np.int64);need(len(indices)>0,'complete split '+role)
    meta['arrays'][role+'_x']=array_write(output,'public/'+key+'/'+role+'_x.npy',data['x'][indices])
    if role!='test':meta['arrays'][role+'_y']=array_write(output,'public/'+key+'/'+role+'_y.npy',data['y'][indices])
   public=dict(meta);public['arrays']={k:v for k,v in meta['arrays'].items()if k!='truth'}
   dump(output/('public/'+key+'/case.json'),public);dump(output/('private/'+key+'/case.json'),meta)
   published.append(key);states[key]={'status':'complete','reason':None}
  except BaseException as exc:owner.fail(exc,'materialize:'+key);states[key]={'status':'failed','reason':type(exc).__name__}
 dump(output/'PREPARATION.json',{'schema':'trial_full_preparation_v4','cases':states,'published':published,'common_split':common,'failures':owner.secondary(),'first':owner.failure(),'complete':all(x['status']=='complete'for x in states.values())})
 return {'stage':'prepare','cases':states}

def training_view(inputs,case):
 import numpy as np
 from .interchange import normalize_train_only
 d=load(inputs/('public/'+case['id']+'/case.json'));arrays=d['arrays'];x=array_read(inputs,arrays['all_x'])
 # Build training/validation target carrier with zero placeholders only for
 # withheld query rows. The normalizer fits on TRAIN and never sees query truth.
 target=case['target'];train=array_read(inputs,arrays['train_y']);valid=array_read(inputs,arrays['validation_y']);p=d['partition']
 classes=None
 if target in('gabors','static-gratings'):
  classes=np.unique(train.reshape(-1));need(len(classes)==(3 if target=='gabors'else 6),'complete TRAIN categorical vocabulary')
  mapping={float(k):i for i,k in enumerate(classes)};need(all(float(k)in mapping for k in valid.reshape(-1)),'unknown validation category is not fitted')
  train=np.asarray([mapping[float(k)]for k in train.reshape(-1)]).reshape(-1,1);valid=np.asarray([mapping[float(k)]for k in valid.reshape(-1)]).reshape(-1,1)
 y=np.zeros((len(x),train.shape[1]),dtype=float);y[[i for i,v in enumerate(p)if v=='train']]=train;y[[i for i,v in enumerate(p)if v=='validation']]=valid
 clf=target in('choice','lick','gabors','static-gratings')
 if target in('gabors','static-gratings'):
  means=x[[i for i,v in enumerate(p)if v=='train']].mean(axis=(0,2),keepdims=True);std=x[[i for i,v in enumerate(p)if v=='train']].std(axis=(0,2),keepdims=True);std[std==0]=1;z=(x-means)/std;yy=y;normal={'x_mean':means,'x_sd':std,'y_mean':np.zeros((1,y.shape[1])),'y_sd':np.ones((1,y.shape[1]))}
 else:z,yy,normal=normalize_train_only(x,y,p,clf)
 out={'case':case,'case_id':case['id'],'session':case['session'],'region':case['region'],'all_x':z,'metadata':d,'normalization':normal,'classes':None if classes is None else classes.tolist()}
 for role in('train','validation','test'):
  idx=[i for i,v in enumerate(p)if v==role];out[role+'_x']=z[idx]
  if role!='test':out[role+'_y']=yy[idx]
 return out

def capture_parameters(output,model,method,views):
 import numpy as np
 parameters={k:v.detach().cpu().numpy()for k,v in model.state_dict().items()}if method!='linear'else{'coef':model.coef_,'intercept':model.intercept_}
 rows=[]
 for i,(name,value)in enumerate(sorted(parameters.items())):rows.append({'name':name,'array':array_write(output,'model/'+str(i)+'.npy',np.asarray(value))})
 normal=[]
 for i,v in enumerate(views):
  normal.append({k:array_write(output,'normalization/'+str(i)+'-'+k+'.npy',np.asarray(a))for k,a in v['normalization'].items()})
 dump(output/'MODEL.json',{'parameters':rows,'normalization':normal});return rows

def reference(request,inputs,output):
 import numpy as np
 from .full_models import fit_linear_full,fit_neural,predict
 job=request['job'];cases=request['cases'];configuration=load(inputs/'configuration.json');views=[training_view(inputs,c)for c in cases]
 need(len({c['target']for c in cases})==1,'one target per fitted model');target=cases[0]['target'];method=job['method']
 if method=='linear':need(len(views)==1,'per-session linear');model,selection=fit_linear_full(views[0],target,configuration)
 elif method in('single_rrr','mlp','multi_rrr','multi_region_rrr','multi_linear','multi_mlp'):model,selection=fit_neural(method,views,target,configuration)
 else:return state_reference(request,inputs,output,views,configuration)
 capture_parameters(output,model,method,views);dump(output/'SELECTION.json',selection);predictions=[]
 for i,(case,v)in enumerate(zip(cases,views)):
  allp=predict(model,method,v['all_x'],i,target)
  if target not in('choice','lick','gabors','static-gratings'):allp=allp*v['normalization']['y_sd']+v['normalization']['y_mean']
  indices=[j for j,p in enumerate(v['metadata']['partition'])if p=='test'];pred=allp[indices]
  predictions.append({'case':case['id'],'classes':v['classes'],'query_rows':indices,'trial_ids':[v['metadata']['trial_ids'][j]for j in indices],
   'prediction':array_write(output,case['id']+'/prediction.npy',pred),'all_prediction':array_write(output,case['id']+'/all_prediction.npy',allp)})
 doc={'schema':'trial_full_job_output_v4','job':job['id'],'arm':job['arm'],'cases':job['cases'],'predictions':predictions,'selection':identity(read(output/'SELECTION.json',1048576)),'source_recipe':configuration['recipe']}
 dump(output/'RESULT.json',doc);return doc

def state_reference(request,inputs,output,views,configuration):
 import numpy as np
 from .full_state import source_module,empirical_bmm,bmm_fit,empirical_lg,lg_fit,integer_keys
 job=request['job'];method=job['method'];source=configuration['original_module'];module=source_module(source['path'],source)
 training=[]
 from .full_models import fit_linear_full,fit_neural,predict
 fold=load(inputs/'FOLD_TRAINING.json');need(len({v['session']for v in views})==1,'one held session per state fold')
 configuration=dict(configuration,target_session=views[0]['session'])
 for case in fold['cases']:
  need(case['session']not in fold['query_sessions'],'no held-session prior truth')
  v=training_view(inputs/'fold_training',case);meta=load(inputs/('fold_training/private/'+case['id']+'/case.json'))
  truth=array_read(inputs/'fold_training',meta['arrays']['truth']);base_method=configuration['prior_base_method'];cfg=configuration['prior_base_configuration']
  model,selected=fit_linear_full(v,case['target'],cfg)if base_method=='linear'else fit_neural(base_method,[v],case['target'],cfg)
  prediction=predict(model,base_method,v['all_x'],0,case['target'])
  if case['target']not in('choice','lick'):prediction=prediction*v['normalization']['y_sd']+v['normalization']['y_mean']
  for segment in dict.fromkeys(meta['sequence_segments']):
   idx=[i for i,s in enumerate(meta['sequence_segments'])if s==segment]
   training.append({'session':case['session'],'truth':truth[idx],'decoder':prediction[idx]})
  dump(output/('prior-training/'+case['id']+'/SELECTION.json'),selected)
 prior=empirical_bmm(training,configuration)if method=='empirical_bmm_hmm'else empirical_lg(training,configuration)if method=='empirical_lg_ar1'else None
 predictions=[]
 for v in views:
  row=configuration['base_predictions'][v['case_id']];d=array_read(inputs,row);meta=v['metadata'];segments=meta['sequence_segments']
  need(len(d)==len(meta['trial_ids'])==len(segments),'full sequence with original gaps')
  result=np.empty_like(d,dtype=float)
  for segment in dict.fromkeys(segments):
   idx=[i for i,s in enumerate(segments)if s==segment];need(all(meta['row_inverse'][b]==meta['row_inverse'][a]+1 for a,b in zip(idx,idx[1:])),'no compressed sequence gaps')
   if method=='hmm':
    need(configuration['hmm_readout_source']is not None,'original HMM discrete/readout definition')
    sequence=(d[idx].reshape(-1)>.5).astype(int).tolist();model=module.HMM(integer_keys(configuration['hmm_initial_log_probabilities']));model.update(sequence,configuration['convergence_cutoff'])
    alpha=model.forward(sequence);beta=model.backward(sequence);xis=[model.xi_matrix(k,sequence,alpha,beta)for k in range(len(sequence)-1)]
    result[idx]=np.asarray([sum(np.exp(model.gamma(k,sequence,alpha,beta,xis)[h]+model.b[h][1])for h in(0,1,2))for k in range(len(sequence))]).reshape(-1,1)
   elif method in('bmm_hmm','empirical_bmm_hmm'):result[idx],model=bmm_fit(module,d[idx],configuration,prior,configuration['recipe'])
   elif method in('lg_ar1','empirical_lg_ar1'):result[idx],model=lg_fit(d[idx],configuration,prior)
   else:raise Refusal('state family')
   state={}
   if method in('hmm','bmm_hmm','empirical_bmm_hmm'):
    for name in('pi','a','b','phi','beta_a','beta_b'):
     if hasattr(model,name):
      value=getattr(model,name);value=list(value.values())if isinstance(value,dict)else value
      value=[list(x.values())if isinstance(x,dict)else x for x in value]
      state[name]=array_write(output,v['case_id']+'/state-'+str(segment)+'-'+name+'.npy',np.asarray(value))
   else:
    for name in('rho','xi','theta','mu','eps'):
     value=prior[name]if prior is not None else model.get_values(name).mean(axis=0)
     state[name]=array_write(output,v['case_id']+'/state-'+str(segment)+'-'+name+'.npy',np.asarray(value))
   dump(output/(v['case_id']+'/STATE-'+str(segment)+'.json'),{'parameters':state,'row_indices':idx,'offline_smoothing':True,'query_truth_read':False})
  query=[i for i,p in enumerate(meta['partition'])if p=='test']
  predictions.append({'case':v['case_id'],'query_rows':query,'trial_ids':[meta['trial_ids'][i]for i in query],
   'prediction':array_write(output,v['case_id']+'/prediction.npy',result[query]),'all_prediction':array_write(output,v['case_id']+'/all_prediction.npy',result)})
 if prior is not None:
  for name,value in prior.items():
   if name not in('training_sessions','sequence_lengths','recipe'):array_write(output,'state-prior/'+name+'.npy',np.asarray(value))
 dump(output/'SELECTION.json',{'configuration':configuration,'non_target_sessions':[s['session']for s in training],'query_truth_read':False})
 doc={'schema':'trial_full_job_output_v4','job':job['id'],'arm':job['arm'],'cases':job['cases'],'predictions':predictions,'source_recipe':configuration['recipe']};dump(output/'RESULT.json',doc);return doc

def main():
 request=json.load(sys.stdin);inputs=Path('/inputs');output=Path('/output');stage=request['stage']
 if stage=='prepare':result=prepare(request,inputs,output)
 elif stage=='reference':result=reference(request,inputs,output)
 elif stage=='literal_release':
  from .released_diagnostic import run
  result=run(inputs,output)
 elif stage=='score':
  from .full_score import score_worker
  result=score_worker(request,inputs,output)
 elif stage=='panel':
  from .full_panels import run_panel
  result=run_panel(request,inputs,output)
 else:raise Refusal('fixed worker stage')
 print(json.dumps({'stage':stage,'result':'captured_in_output','qualified':False}))
if __name__=='__main__':main()
