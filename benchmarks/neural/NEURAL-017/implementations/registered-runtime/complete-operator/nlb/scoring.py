"""Independent full-panel scientific scoring SOURCE; only protected worker imports."""
from .contracts import Custody, diagnostic, UncertaintyDrawFailure

def failed_draw(family,seed,index,indices,blocks,denominator,values,original):
 """Encode one actual failed draw; this helper performs no draw or inference."""
 import math
 error=UncertaintyDrawFailure(family,seed,index,indices,blocks,denominator,values,original)
 def scalar(x):
  if x is None:return {'status':'unobserved','value':None}
  v=float(x)
  return {'status':'finite','value':v}if math.isfinite(v)else{'status':'nonfinite','representation':repr(v)}
 def sequence(x):return x.tolist()if hasattr(x,'tolist')else list(x)
 try:
  error.protected_observation.update(sampled_trial_indices=[]if indices is None else sequence(indices),sampled_block_indices=None if blocks is None else sequence(blocks),denominator=scalar(denominator),draw_values=None if values is None else[scalar(v)for v in values],original_cause=diagnostic(original),capture_complete=True)
 except BaseException as secondary:
  error.custody.fail(secondary,'draw_capture');error.protected_observation['capture_failure_type']=diagnostic(secondary)['type']
 return error

def publish_draw_failure(error,trace):
 """Actual worker consumes the same failure; trace failure cannot replace it."""
 if type(error)is not UncertaintyDrawFailure:raise error
 try:trace(error.protected_observation)
 except BaseException as secondary:error.custody.fail(secondary,'draw_publication')
 raise error from error.original_exception

def arithmetic_failure(key,original,total,failure_owners):
 """Retain an admitted method's local arithmetic failure; no metric is run."""
 owner=Custody('grade:'+key);failure_owners.append(owner);owner.fail(original,'valid_unscorable_arithmetic')
 return {'status':'valid_unscorable_arithmetic','co_bps':None,'reason':'arithmetic_failure','diagnostic':diagnostic(original),'target_spikes':total,'valid_cells':3616200}

def grade(predictions,targets,support,contrasts,failure_owners):
 import numpy as np,math
 from .contracts import need
 from .programme import expected_groups,group_id,group_key,CONDITIONS,allowed_references,bank_id
 from .metric_core import poisson_bits_per_spike
 from .arrays import prediction
 expected={group_id(g)for g in expected_groups()}|{bank_id(c,r)for c in CONDITIONS for r in allowed_references(c)}|{'TOOL_ONLY_BATCH','TOOL_ONLY_CASE'}
 need(set(predictions)==expected,'entire fixed assessment union');need(len(contrasts['contrasts'])==65,'fixed contrast union')
 y=np.asarray(targets['counts_heldout'],dtype=np.float64);mask=np.asarray(targets['valid_mask']);need(y.shape==(574,140,45)and mask.shape==y.shape and mask.dtype==np.bool_ and mask.all(),'complete fixed target support')
 need(np.isfinite(y).all()and (y>=0).all()and (y==np.floor(y)).all()and(y<=2**53).all(),'valid original count targets')
 need(np.array_equal(targets['trial_ids'],support['eval_trial_ids'])and np.array_equal(targets['unit_ids'],support['heldout_unit_ids']),'target axes')
 need(str(targets['panel_fingerprint'].item())==support['panel_fingerprint'],'sealed target fingerprint')
 spikes=y.sum(axis=(1,2));total=float(spikes.sum());need(math.isfinite(total),'target sum overflow')
 scores={};per_trial={};normalizer=np.maximum(y.sum(axis=(0,1))/mask.sum(axis=(0,1)),0);normalizer[normalizer==0]=1e-9
 for key,raw in predictions.items():
  p=prediction(raw,support);lam=p['expected_counts'].astype(np.float64,copy=False)
  try:score=poisson_bits_per_spike(y,lam,mask)
  except ValueError as e:
   # Domain was already admitted; arithmetic overflow is an unscorable valid
   # method, never retroactively described as cheating or clipped into success.
   score=arithmetic_failure(key,e,total,failure_owners)
  scores[key]=score
  with np.errstate(over='ignore',invalid='ignore'):ledger=(y*(np.log(lam)-np.log(normalizer))+normalizer-lam).sum(axis=(1,2),dtype=np.float64)
  per_trial[key]=ledger if np.isfinite(ledger).all()else None
 comparisons={};ledgers={}
 for c in contrasts['contrasts']:
  need(sum(t['coefficient']for t in c['terms'])==0,'paired null cancellation contract');parts=[];missing=[]
  for term in c['terms']:
   if term['kind']=='agent_mean_over_all_five_seeds':
    mode,view=term['arm'].split('-');keys=[group_key(term['condition'],mode,view,s)for s in range(1,6)]
   else:need(term['kind']=='deterministic_reference','contrast term');keys=[bank_id(term['condition'],term['reference'])]
   if any(per_trial[k]is None or scores[k]['status']!='scored'for k in keys):missing+=keys
   else:parts.append(term['coefficient']*np.mean(np.stack([per_trial[k]for k in keys]),axis=0))
  if missing or total==0:comparisons[c['id']]={'status':'unavailable','family':c['family'],'reason':'unscorable required component or zero spikes','components':missing};continue
  with np.errstate(over='ignore',invalid='ignore'):delta=np.sum(np.stack(parts),axis=0);point=float(delta.sum()/(total*math.log(2)))
  if not np.isfinite(delta).all()or not math.isfinite(point):comparisons[c['id']]={'status':'valid_unscorable_arithmetic','family':c['family']};continue
  ledgers[c['id']]=delta;comparisons[c['id']]={'status':'scored','family':c['family'],'difference_bps':point,'all_five_seeds':True,'paired_trials':574}
 baseline=bank_id('intact','R1');old={}
 for g in expected_groups():
  key=group_id(g)
  if g['condition']=='intact':old[key]=None if scores[key]['co_bps']is None or scores[baseline]['co_bps']is None else scores[key]['co_bps']-scores[baseline]['co_bps']
 return {'schema':'NLB017_full_protected_grade_v1','scores':scores,'contrasts':comparisons,'original_R1_delta':old,'target_spikes':total,'valid_cells':3616200,'negative_results_retained':True}, {'trial_spikes':spikes,**{'contrast_'+k:v for k,v in ledgers.items()}}

def uncertainty(grade_result,private,contrasts,support):
 import numpy as np,math
 from .contracts import need
 need(set(grade_result['contrasts'])=={x['id']for x in contrasts['contrasts']},'unchanged 65 contrast family')
 ids=[x['id']for x in contrasts['contrasts']];spikes=np.asarray(private['trial_spikes']);need(spikes.shape==(574,),'whole trial support');available=[k for k in ids if 'contrast_'+k in private]
 matrix=np.stack([private['contrast_'+k]for k in available])if available else np.empty((0,574))
 def draw(seed,blocks=None):
  rng=np.random.Generator(np.random.PCG64(seed));values=np.empty((10000,len(available)),dtype=np.float64)
  for start in range(0,10000,256):
   for j in range(start,min(start+256,10000)):
    selected_blocks=None;ix=None;denom=None;draw_values=None
    try:
     if blocks is None:ix=rng.integers(0,574,size=574)
     else:selected_blocks=rng.integers(0,len(blocks),size=len(blocks));ix=np.concatenate([blocks[x]for x in selected_blocks])
     denom=float(spikes[ix].sum());need(math.isfinite(denom)and denom>0,'failed uncertainty: zero/nonfinite draw; no deletion/redraw')
     draw_values=matrix[:,ix].sum(axis=1)/(denom*math.log(2));values[j]=draw_values;need(np.isfinite(draw_values).all(),'failed nonfinite draw; no deletion/redraw')
    except BaseException as original:
     # No RNG call occurs while capturing the original draw. All observations
     # remain private and the original failure exits the stage without retry.
     error=failed_draw('whole_trial'if blocks is None else'chronology_blocks',seed,j,ix,selected_blocks,denom,draw_values,original)
     raise error from original
  return values
 def summaries(values):
  out={}
  for j,key in enumerate(available):
   fam=grade_result['contrasts'][key]['family'];m=contrasts['families'][fam];alpha=.05
   out[key]={'status':'complete','draws':10000,'interval_family_bonferroni':np.quantile(values[:,j],[alpha/(2*m),1-alpha/(2*m)],method='linear').tolist(),'interval_optional_global65':np.quantile(values[:,j],[alpha/130,1-alpha/130],method='linear').tolist(),'fraction_positive_not_p_value':float((values[:,j]>0).mean()),'family':fam,'family_size':m}
  for key in set(ids)-set(available):out[key]={'status':'unavailable','reason':'required score or contrast unavailable','draws':0}
  return out
 trial=draw(20261103);result={'schema':'NLB017_full_uncertainty_v1','whole_trial':summaries(trial),'paired_seed_policy':'mean of all five seeds before identical trial resamples','conditional_on_one_public_session':True}
 chrono=support.get('chronological_eval_trial_ids')
 if chrono is None:result['chronology']={'status':'unavailable','reason':'original acquisition chronology absent; opaque IDs are not chronology'};block_values=None
 else:
  need(len(chrono)==574 and set(chrono)==set(support['eval_trial_ids']),'exact original chronology');ix={x:i for i,x in enumerate(support['eval_trial_ids'])};ordered=np.asarray([ix[x]for x in chrono]);blocks=[ordered[i:i+10]for i in range(0,574,10)]
  need(len(blocks)==58 and [len(x)for x in blocks]==[10]*57+[4],'fixed unequal final block');block_values=draw(20261104,blocks);result['chronology']={'status':'complete','block_lengths':[10]*57+[4],'sampling':'58 blocks with replacement; variable retained trial count','contrasts':summaries(block_values)}
 result['complete_inference']=len(available)==65 and result['chronology']['status']=='complete';return result,{'trial_draws':trial,**({}if block_values is None else{'chronology_draws':block_values})}
