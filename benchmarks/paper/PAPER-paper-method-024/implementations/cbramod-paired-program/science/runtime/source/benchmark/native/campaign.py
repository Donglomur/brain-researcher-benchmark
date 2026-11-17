"""Full finite campaign inventory; no baseline substitution or silent thinning."""
from ..public.contract import cases
from .policy import method_route,MissingSource,need,digest

def coverage(panel,purpose='reproduction',reference=False):
 jobs=cases(panel,purpose,reference);rows=[]
 for job in jobs:
  try:route=method_route(job['dataset'],job['method']);missing=None
  except MissingSource as e:route=None;missing=str(e)
  rows.append({**job,'native_route':route,'missing_source':missing})
 return {'schema':'cbramod_campaign_source_coverage_v1','purpose':purpose,'reference':reference,
  'cases':rows,'required':len(rows),'source_routed':sum(x['native_route']is not None for x in rows),
  'source_complete':all(x['native_route']is not None for x in rows),'scientifically_qualified':False}

def bind_campaign(panel,plans,purpose='reproduction',reference=False):
 """Reject the full missing-method roster before any model/data dispatch."""
 status=coverage(panel,purpose,reference)
 need(status['source_complete'],'complete selected comparator/variant executable source missing; never thin campaign')
 need(type(plans)is list and len(plans)==status['required'],'all selected source plans required')
 from .policy import validate_plan
 rosters={};selected={}
 for p,j in zip(plans,status['cases']):
  validate_plan(p)
  need((p['dataset_id'],p['method'],p['seed_slot'])==(j['dataset'],j['method'],j['seed_slot']),'exact campaign/source order')
  key=(p['dataset_id'],p['method']);roster=tuple(p['seed_values'])
  need(key not in rosters or rosters[key]==roster,'one immutable five-seed roster across all slots of a dataset/method')
  rosters[key]=roster;selected.setdefault(key,[]).append(p['seed_values'][p['seed_slot']])
 for key,values in selected.items():need(len(values)==5 and len(set(values))==5 and tuple(values)==rosters[key],'all five distinct selected seeds in declared slot order')
 return {'status':status,'plans_sha256':digest(plans)}
