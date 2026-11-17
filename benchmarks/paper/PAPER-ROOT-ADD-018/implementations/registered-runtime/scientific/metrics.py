"""Protected scientific arithmetic, authored only; use after full admission."""
def mean(values):
 if not values:raise ValueError('empty fixed support')
 return sum(values)/len(values)
def hierarchy(rows,levels,value_key):
 if not levels:return mean([r[value_key]for r in rows])
 groups={}
 for row in rows:groups.setdefault(row['group_keys'][levels[0]],[]).append(row)
 if not groups:raise ValueError('empty required grouping')
 return mean([hierarchy(g,levels[1:],value_key)for g in groups.values()])
def neural_loss(rows):
 enriched=[{**r,'error':(r['prediction']-r['target'])**2}for r in rows]
 return hierarchy(enriched,['rat','session','unit'],'error')
def waiting_loss(rows):
 enriched=[{**r,'error':(r['prediction']-r['target'])**2,'absolute':abs(r['prediction']-r['target'])}for r in rows]
 return {'MSE':hierarchy(enriched,['rat','session'],'error'),'MAE':hierarchy(enriched,['rat','session'],'absolute')}
def reward_balanced_accuracy(rows,required_strata):
 grouped={}
 for r in rows:grouped.setdefault(tuple(r['group_keys'][k]for k in('rat','session','window')),[]).append(r)
 if set(grouped)!=set(tuple(x)for x in required_strata):raise ValueError('fixed reward strata changed')
 windows=[]
 for key,rs in grouped.items():
  scores=[]
  for c in(1,2,3,4,5):
   selected=[r for r in rs if r['target']==c]
   if not selected:raise ValueError('missing reward class in required stratum')
   scores.append(mean([float(r['prediction']==c)for r in selected]))
  windows.append({'group_keys':dict(zip(('rat','session','window'),key)),'value':mean(scores)})
 return hierarchy(windows,['rat','session'],'value')
def simulation_recovery(rows,case_mechanisms):
 from .native_semantics import ati
 if len(case_mechanisms)!=200 or sum(v=='additive'for v in case_mechanisms.values())!=100 or sum(v=='divisive'for v in case_mechanisms.values())!=100:raise ValueError('original200mechanism support')
 groups={}
 for r in rows:groups.setdefault(r['group_keys']['case'],[]).append(r)
 if set(groups)!=set(case_mechanisms):raise ValueError('missing simulation')
 percase=[]
 for case,rs in groups.items():
  predicted=ati([r['prediction']['u']for r in rs],[r['prediction']['v']for r in rs]);target=ati([r['target']['u']for r in rs],[r['target']['v']for r in rs])
  if predicted['value']is None or target['value']is None:raise ValueError('undefined full-support simulation ATI')
  error=predicted['value']-target['value'];percase.append({'case':case,'mechanism':case_mechanisms[case],'squared':error**2,'absolute':abs(error),'bias':error})
 return {k:mean([r[k]for r in percase])for k in('squared','absolute','bias')}
def native_compare(candidate,reference,tolerances):
 """Whole component comparison; every requested scalar is evaluated."""
 rows=[]
 refs={r['component_id']:r for r in reference['components']}
 if set(refs)!={r['component_id']for r in candidate['components']}:raise ValueError('native component support')
 for c in candidate['components']:
  r=refs[c['component_id']];t=tolerances[c['component_id']]
  if c['axes']!=r['axes']or c['unit']!=r['unit']:raise ValueError('native component axes/units')
  if c['disposition']!='defined'or r['disposition']!='defined':
   if c['disposition']==r['disposition']=='provenance_only':
    rows.append({'component_id':c['component_id'],'score':None,'status':'provenance_compared','passed':c['data']==r['data']});continue
   raise ValueError('required native component scientifically undefined; keep native product, no quantitative pass')
  if len(c['data'])!=len(r['data']):raise ValueError('native component shape')
  errors=[abs(a-b)for a,b in zip(c['data'],r['data'])];passed=all(e<=t['atol']+t['rtol']*abs(b)for e,b in zip(errors,r['data']))
  rows.append({'component_id':c['component_id'],'max_absolute_error':max(errors)if errors else None,'status':'compared','passed':passed,'full_denominator':len(errors)})
 return rows
def paired_rat_interval(per_rat_differences,seed,replicates,alpha):
 """Planned rat-cluster bootstrap; no retry/drop of undefined replicates."""
 import numpy as np
 if not per_rat_differences or replicates<1 or not 0<alpha<1:raise ValueError('qualified uncertainty parameters required')
 x=np.array(list(per_rat_differences.values()),float)
 if not np.all(np.isfinite(x)):raise ValueError('undefined rat contrast')
 rng=np.random.default_rng(seed);samples=np.array([np.mean(x[rng.integers(0,len(x),len(x))])for _ in range(replicates)])
 return {'estimate':float(np.mean(x)),'lower':float(np.quantile(samples,alpha/2)),'upper':float(np.quantile(samples,1-alpha/2)),'unit':'rat','replicates':replicates,'seed':seed}
