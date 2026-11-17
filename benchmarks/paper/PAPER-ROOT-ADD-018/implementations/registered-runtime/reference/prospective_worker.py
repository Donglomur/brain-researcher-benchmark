"""Actual train-only prospective reference learners and prefix predictors.

Authored/static only. Qualified normalized training views and hyperparameters
are required. Native equivalence is never inferred from this implementation.
"""
import argparse,json,pickle,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ofc.common import load,write_new,require
from ofc.universe import canonical_offer_sequence

def fit_references(view,settings):
 import numpy as np
 from scientific.latent import fit_ordinary_lds,fit_hierarchical,filter_sequence,hierarchical_schedule,svd_coordinate_gauge
 from scientific.behavior import divisive_features,inference_features,restricted_wait_fit
 from scientific.analysis import reward_decoder
 require(view['role']=='training_and_validation_only'and view['future_targets_present']is False,'reference information boundary')
 families=set(settings['reference_families']);require(families and families<={'I_NEURAL','I_REWARD','I_WAIT','I_SIM_ATI','I_ASSOCIATION','I_REAL_ATI'},'independently qualified comparator family support')
 result={'sessions':{},'behavior':{},'simulations':{},'settings':settings,'source_method':'prospective_reference_not_native_equivalent'}
 for session in view['neural_sessions']if families&{'I_NEURAL','I_REWARD','I_ASSOCIATION','I_REAL_ATI'}else[]:
  x=np.asarray(session['train_counts'],float);units=session['unit_ids'];require(x.shape[1]==len(units),'training unit geometry');kind=settings['neural_kind']
  if kind=='majority':
   labels=session['reward_training']['train_labels'];require(labels and set(labels)<={1,2,3,4,5},'training-majority five-class label domain');model={'kind':'majority','class':max(range(1,6),key=lambda c:(sum(y==c for y in labels),-c)),'units':units}
  elif kind=='mean':model={'kind':'mean','mean':np.mean(np.sqrt(x),axis=0),'units':units}
  elif kind in('lds11','lds10'):
   dim=11 if kind=='lds11'else 10;require(len(session['initial']['F'])==dim,'total-state comparator dimension')
   model={**fit_ordinary_lds(x,session['initial'],settings['iterations'],settings['tolerance']),'kind':kind,'units':units}
  else:
   require(kind=='hlds','unknown comparator');model={**fit_hierarchical(x,session['train_trial_ids'],session['initial'],settings['iterations'],settings['tolerance'],settings['boundary_policy']),'kind':'hlds','units':units}
   gauge=svd_coordinate_gauge(model['C'],model['A'],model['B'],np.zeros((1,10)));model['gauge']=gauge
  result['sessions'][session['id']]=model
  if 'I_REWARD'in families and kind!='majority':
   # Latents are produced by this actual fitted model, not an unbound saved
   # decoder/latent file. Labels enter only the downstream supervised probe.
   train_latents=all_neuron_latents(model,x,session['train_trial_ids'])
   validation=np.asarray(session['validation_counts'],float);val_latents=all_neuron_latents(model,validation,session['validation_trial_ids'])
   rt=session['reward_training'];tx=window_features(train_latents,rt['train_windows']);vx=window_features(val_latents,rt['validation_windows'])
   probe=reward_decoder(tx,rt['train_labels'],vx,rt['validation_labels'],vx,settings['regularization_grid'],settings['seed'])
   model['reward_probe']=probe['model'];model['probe_selection']=probe['validation_attempts']
 for session in view['behavior_sessions']if 'I_WAIT'in families else[]:
  kind=settings['behavior_kind'];offers=session['physical_offers']
  if kind=='mean':model={'kind':'mean','value':float(np.mean(np.asarray(session['restricted_wait'])[session['catch_mask']]))}
  else:
   if kind=='divisive':features=divisive_features(offers,settings['horizon'],settings['alpha']).reshape(-1,1)
   else:
    require(kind=='inference','behavior reference kind');features=inference_features(session['ordinal_offers'],settings['transition'],settings['emission'],settings['initial_belief'])
   model={**restricted_wait_fit(features,session['restricted_wait'],session['catch_mask'],settings['behavior_regularization']),'kind':kind}
  result['behavior'][session['id']]=model
 for case in view['simulation_cases']if 'I_SIM_ATI'in families else[]:
  # All200 original observed datasets; exact generator identities and hidden
  # truth are independently bound by operator, never included in this view.
  require('truth'not in case and 'mechanism'not in case,'simulation truth in fit view')
  model=fit_hierarchical(case['observed_counts'],case['trial_ids'],case['initial'],settings['iterations'],settings['tolerance'],settings['boundary_policy'])
  model['kind']='hlds';model['units']=case['unit_ids'];model['gauge']=svd_coordinate_gauge(model['C'],model['A'],model['B'],np.zeros((1,10)))
  states=all_neuron_latents(model,np.asarray(case['observed_counts'],float),case['trial_ids'],full_state=True)
  model['states_by_key']={key:state for key,state in zip(case['time_keys'],states)};result['simulations'][case['id']]=model
 if 'I_SIM_ATI'in families:require(len(result['simulations'])==200,'all original200 cases required')
 return result

def all_neuron_latents(model,counts,trial_ids,full_state=False):
 import numpy as np
 from scientific.latent import filter_sequence,hierarchical_schedule
 if model['kind']=='mean':raise ValueError('mean comparator has no latent decoder')
 if model['kind']=='hlds':
  F,Q=hierarchical_schedule(model['A'],model['B'],model['D'],model['fast_noise'],model['slow_noise'],trial_ids,model['boundary_policy']);C=np.column_stack((np.zeros(len(model['units'])),model['C']))
 else:F=[model['F']]*len(counts);Q=[model['Q']]*len(counts);C=model['C']
 F[0]=np.eye(len(model['m0']));Q[0]=np.zeros_like(model['P0']);filtered=filter_sequence(np.sqrt(counts),F,Q,C,model['R'],model['m0'],model['P0'],[np.ones(len(model['units']),bool)]*len(counts))
 states=np.stack([m for m,p in filtered['filtered']])
 return states if full_state else states[:,1:]if model['kind']=='hlds'else states

def window_features(latents,windows):
 import numpy as np
 features=[]
 for indices in windows:
  require(len(indices)==5,'250ms requires5native50ms bins');features.append(np.mean(latents[indices],axis=0))
 return np.asarray(features)

def step(model,query,state,held_unit=None):
 import numpy as np
 from scientific.latent import filter_sequence,hierarchical_schedule
 p=query['public'];observations=p.get('peer_observations',p.get('neural_observations',[]));units=model['units'];m=state.get('mean',model['m0']);P=state.get('covariance',model['P0']);last=state.get('trial',-1);trajectory=[]
 times=sorted({(x['trial_ordinal'],x['bin_ordinal'])for x in observations})
 for trial,bin_id in times:
  if 'watermark'in state and (trial,bin_id)<=state['watermark']:continue
  byunit={x['unit']:x['value']for x in observations if(x['trial_ordinal'],x['bin_ordinal'])==(trial,bin_id)};allowed=[u for u in units if u!=held_unit];require(set(byunit)==set(allowed),'complete peer/unit support')
  mask=np.array([u!=held_unit for u in units]);row=np.zeros((1,len(units)))
  for i,u in enumerate(units):
   if mask[i]:row[0,i]=byunit[u] # already square-root50ms counts by public schema
  if model['kind']=='hlds':
   fs,qs=hierarchical_schedule(model['A'],model['B'],model['D'],model['fast_noise'],model['slow_noise'],[last,trial],model['boundary_policy']);F,Q=fs[1],qs[1];C=np.column_stack((np.zeros(len(units)),model['C']))
  else:F,Q,C=model['F'],model['Q'],model['C']
  if 'watermark'not in state:F=np.eye(len(m));Q=np.zeros_like(P)
  filtered=filter_sequence(row,[F],[Q],C,model['R'],m,P,[mask]);m,P=filtered['filtered'][0];last=trial;trajectory.append(m.copy());state['watermark']=(trial,bin_id)
  state.setdefault('recent_states',{})[(trial,bin_id)]=m.copy();state['recent_states']={key:value for key,value in state['recent_states'].items()if key[0]==trial and key[1]>=bin_id-4}
 state.update({'mean':m,'covariance':P,'trial':last});require(trajectory,'query must contain new observations')
 return m,trajectory,C

def predict(model,query,state):
 import numpy as np
 from scientific.behavior import divisive_features,inference_features,restricted_wait_predict
 family=query['family_id'];p=query['public'];settings=model['settings'];session=query['group_keys'].get('session')
 if family=='I_WAIT':
  fitted=model['behavior'][session]
  if fitted['kind']=='mean':return fitted['value']
  offers=canonical_offer_sequence(query)
  if fitted['kind']=='divisive':features=divisive_features([x['physical_ul']for x in offers],settings['horizon'],settings['alpha']).reshape(-1,1)[-1:]
  else:features=inference_features([x['ordinal']for x in offers],settings['transition'],settings['emission'],settings['initial_belief'])[-1:]
  return float(restricted_wait_predict(fitted,features)[0])
 if family=='I_SIM_ATI':
  fitted=model['simulations'][query['group_keys']['case']];latent=fitted['states_by_key'][str(query['cutoff']['trial_ordinal'])+'.'+str(query['cutoff']['bin_ordinal'])]
 else:
  fitted=model['sessions'][session]
  if family=='I_REWARD'and fitted['kind']=='majority':return fitted['class']
  if family=='I_NEURAL'and fitted['kind']=='mean':return float(fitted['mean'][fitted['units'].index(p['target_unit'])])
  latent,trajectory,C=step(fitted,query,state,p['target_unit']if family=='I_NEURAL'else None)
  if family=='I_NEURAL':return float(C[fitted['units'].index(p['target_unit'])]@latent)
  if family=='I_REWARD':
   t=query['cutoff']['trial_ordinal'];b=query['cutoff']['bin_ordinal'];window=[state['recent_states'][(t,k)]for k in range(b-4,b+1)];fast=np.stack(window)[:,1:]if fitted['kind']=='hlds'else np.stack(window);return int(fitted['reward_probe'].predict(np.mean(fast,axis=0,keepdims=True))[0])
  if family=='I_ASSOCIATION':
   require(fitted['kind']=='hlds','slow latent definition');return {'latent':float(latent[0]),'coordinate_map_id':'train_C_SVD','null_specification_id':settings['null_specification_id']}
 require(fitted['kind']=='hlds','comparable ATI decomposition required');T=fitted['gauge']['T'];u=float(np.linalg.norm(T@fitted['B']*latent[0]));v=float(np.linalg.norm(T@fitted['A']@latent[1:]))
 return {'coordinate_map_id':'train_C_SVD','u':u,'v':v,'ratio_disposition':'zero_denominator'if u+v==0 else'defined','fitted_state_id':'sealed_reference_fit'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--output',required=True);p.add_argument('--inputs',required=True);p.add_argument('--model');a=p.parse_args();req=load(a.request);out=Path(a.output)
 if req['phase']=='build':write_new(out/'build.json',{'reference_source':'prospective_train_fit_predict','qualified_native_equivalence':False})
 elif req['phase']=='investigate':write_new(out/'investigation.json',{'test_feedback':False,'selection':'fixed train/validation budget'})
 elif req['phase']=='fit':
  view=load(Path(a.inputs)/'reference_training.json');settings=load(Path(a.inputs)/'reference_settings.json');fitted=fit_references(view,settings)
  with (out/'fitted.pkl').open('xb')as f:pickle.dump(fitted,f,protocol=5)
 elif req['phase']=='predict':
  # The model is self-produced fitted state, already sealed and mounted
  # read-only by trusted host; never a candidate pickle loaded by a grader.
  with (Path(a.model)/'fitted.pkl').open('rb')as f:model=pickle.load(f)
  state={}
  for line in sys.stdin:
   message=json.loads(line);q=message['query'];row={'family_id':q['family_id'],'query_id':q['query_id'],'disposition':'value','value':None,'reason':None,'watermark':q['cutoff']}
   try:
    require(q['family_id']in model['settings']['reference_families'],'this independent reference is not a comparator for this family')
    row['value']=predict(model,q,state)
   except(ValueError,KeyError,ArithmeticError)as error:
    row.update({'disposition':'declared_prediction_failure','value':None,'reason':type(error).__name__+': '+str(error)})
   print(json.dumps({'request_id':message['request_id'],'row':row},allow_nan=False),flush=True)
 else:raise ValueError('Prospective reference has no native reproduction substitute.')
if __name__=='__main__':main()
