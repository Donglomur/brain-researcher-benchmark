"""Full prospective prediction admission and protected memory-scoring consumer."""
from .core import *
from .programme import improvement
from . import tensors
def specification(design):
 cfg=improvement();expected=[cfg['primary_stratum']]+cfg['secondary_strata']
 need(design['strata']==expected and design['reference_ids']==cfg['reference_ids'],'all prespecified strata/references')
 need(design['network_ids']==['network_%02d'%i for i in range(20)],'all 20 independent test networks per stratum')
 need(design['kind']=='improvement' and design['profile']=='prospective_memory','prospective design')
 return cfg
def delays(stratum,cfg):return cfg['aligned_delays_seconds'] if stratum.endswith('_aligned') else cfg['independent_delays_seconds']
def validate_predictions(raw,design,run):
 cfg=specification(design);d=decode(raw,design['result_cap_bytes'])
 exact(d,('schema','design_sha256','condition','strata'),'prediction result')
 need(d['schema']=='critical_init_memory_predictions_v1' and d['design_sha256']==design['design_sha256'] and d['condition']==run.exposure.condition,'actual prediction design/condition')
 need(type(d['strata']) is list and [x['stratum'] for x in d['strata']]==design['strata'],'complete ordered strata')
 for s in d['strata']:
  exact(s,('stratum','networks'),'stratum')
  need([x['network'] for x in s['networks']]==design['network_ids'],'retain every planned network, including failures')
  for n in s['networks']:
   exact(n,('network','status','reason','predictions'),'network prediction')
   need(n['status'] in ('complete','operational_failure','not_attempted'),'prediction status')
   if n['status']!='complete':need(n['predictions']==[] and type(n['reason']) is str and bool(n['reason']),'explicit failure without partial success');continue
   need(n['reason'] is None and len(n['predictions'])==len(delays(s['stratum'],cfg)),'all prespecified delays')
   for v in n['predictions']:tensors.validate(v,{'shape':[1000,100],'kind':'real'},run.output_path.parent,run.owner.output_cost)
 return d
def array(value,shape,root,cost):
 import numpy as np
 return np.asarray(list(tensors.values(value,{'shape':shape,'kind':'real'},root,cost))).reshape(shape)
def score(raw,design,run,vault):
 from .sandbox import actual_closed
 from .memory_reference import retrieval
 from .scoring import paired_improvement
 actual_closed(run);need(run.returncode==0 and run.output_sha256==pin(raw)['sha256'],'successful closed actual candidate')
 candidate=validate_predictions(raw,design,run)
 # Every candidate shard is admitted before the first protected target read.
 target=decode(vault.open_for(run,design),design['target_metadata_cap_bytes'])
 exact(target,('schema','design_sha256','strata'),'protected memory target')
 need(target['schema']=='critical_init_memory_targets_v1' and target['design_sha256']==design['design_sha256'],'same protected task')
 need([s['stratum'] for s in target['strata']]==design['strata'],'full target strata')
 cfg=specification(design);scores=[];cost=run.owner.output_cost
 for c,t in zip(candidate['strata'],target['strata']):
  exact(t,('stratum','networks'),'protected stratum');need([n['network'] for n in t['networks']]==design['network_ids'],'full target network support')
  cs={};rs={};grid=delays(c['stratum'],cfg)
  for n,h in zip(c['networks'],t['networks']):
   exact(h,('network','prototypes','gram','truth','references'),'protected network')
   need(len(h['truth'])==len(grid),'full protected delay support')
   need(set(h['references'])==set(design['reference_ids']),'all fixed references')
   rs[n['network']]=h['references']
   if n['status']!='complete':cs[n['network']]={'status':n['status'],'reason':n['reason']};continue
   proto=array(h['prototypes'],[1000,100],vault.path.parent,cost);gram=array(h['gram'],[100,100],vault.path.parent,cost)
   values=[]
   for v,truth in zip(n['predictions'],h['truth']):
    prediction=array(v,[1000,100],run.output_path.parent,cost)
    values.append(sum(retrieval(prediction,proto,truth,gram))/1000)
   cs[n['network']]={'status':'complete','accuracy':values}
  local={**cfg,'network_ids':design['network_ids'],'delays_seconds':grid}
  scores.append({'stratum':c['stratum'],'primary':c['stratum']==cfg['primary_stratum'],**paired_improvement(cs,rs,local)})
 return {'schema':'critical_init_memory_score_v1','strata':scores,'all_strata_denominator':len(scores),'research_qualified':False,
  'claim_scope':'Prospective matched fixed-split simulation readout improvement only; no full-paper reproduction or general neuroscience SOTA claim.'}
