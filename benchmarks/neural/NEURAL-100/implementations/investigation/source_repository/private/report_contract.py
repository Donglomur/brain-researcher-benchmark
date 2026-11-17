"""Strict numerical artifact, complete source cohort, no private reads."""
import math
from artifact_io import TASK,CONTRACT,Invalid
CONDITIONS=('primary','threshold_2_5','threshold_3_5','bins_2ms','boundary_erosion_one_depth','baseline_pseudo_onset','development_snr_bin_contact_matched','first_spike_median_descriptive')
AREAS=('A1','A2')
def need(v,s):
 if not v:raise Invalid(s)
def keys(v,k):need(type(v)is dict and set(v)==set(k),'exact fields: '+','.join(k))
def num(v):need(v is None or(type(v)in(int,float)and -50<=v<=50 and math.isfinite(v)),'finite latency milliseconds or null')
def integer(v,cap):need(type(v)is int and 0<=v<=cap,'bounded support integer')
def admit(v,roster):
 keys(v,('task_id','contract','recordings','areas'));need(v['task_id']==TASK and v['contract']==CONTRACT,'task identity')
 expected={r['recording_id']:r for r in roster};need(len(expected)==47,'operator roster')
 need(type(v['recordings'])is list and len(v['recordings'])==47,'complete47recording cohort');seen=set()
 for r in v['recordings']:
  keys(r,('recording_id','participant_id','area','conditions'));qid=r['recording_id'];need(type(qid)is str and qid in expected and qid not in seen,'recording ID')
  need(r['participant_id']==expected[qid]['participant_id']and r['area']==expected[qid]['area'],'participant/area join');seen.add(qid);keys(r['conditions'],CONDITIONS)
  for c in CONDITIONS:
   z=r['conditions'][c];keys(z,('L4','L6','delta_ms'))
   for layer in ('L4','L6'):
    a=z[layer];keys(a,('status','latency_ms'));need(a['status']in('defined','undefined'),'layer disposition');num(a['latency_ms']);need((a['latency_ms']is not None)==(a['status']=='defined'),'latency disposition')
   num(z['delta_ms']);need((z['delta_ms']is not None)==all(z[k]['status']=='defined'for k in('L4','L6')),'contrast disposition')
   if z['delta_ms']is not None:need(abs(z['delta_ms']-(z['L6']['latency_ms']-z['L4']['latency_ms']))<=1e-9,'arithmetic self-consistency')
 keys(v['areas'],CONDITIONS)
 for c in CONDITIONS:
  keys(v['areas'][c],AREAS)
  for area in AREAS:
   a=v['areas'][c][area];keys(a,('full_mean_ms','observed_only_mean_ms','participants','defined_participants','defined_draws','ci95_ms'))
   for k in('full_mean_ms','observed_only_mean_ms'):num(a[k])
   integer(a['participants'],41);integer(a['defined_participants'],41);integer(a['defined_draws'],1000)
   need(a['defined_participants']<=a['participants'],'participant support')
   need((a['full_mean_ms']is not None)==(a['participants']>0 and a['defined_participants']==a['participants']),'full-cohort disposition')
   need((a['observed_only_mean_ms']is not None)==(a['defined_participants']>0),'observed-only disposition')
   ci=a['ci95_ms'];need(ci is None or(type(ci)is list and len(ci)==2),'interval shape')
   if ci is not None:
    for x in ci:num(x);need(x is not None,'finite interval')
    need(ci[0]<=ci[1]and a['full_mean_ms']is not None and a['defined_draws']==1000,'complete interval disposition')
 return v

def project(result):
 rows=[]
 for r in result['per_recording']:
  conditions={}
  for c in CONDITIONS:
   a=r['conditions'][c];conditions[c]={k:{'status':a['layers'][k]['status'],'latency_ms':a['layers'][k]['latency_ms']}for k in('L4','L6')};conditions[c]['delta_ms']=a['delta_l6_minus_l4_ms']
  rows.append({k:r[k]for k in('recording_id','participant_id','area')}|{'conditions':conditions})
 areas={}
 for c in CONDITIONS:
  areas[c]={}
  for area in AREAS:
   a=result['conditions'][c][area];areas[c][area]={'full_mean_ms':a['full_area_mean_ms'],'observed_only_mean_ms':a['observed_only_mean_ms'],'participants':a['recorded_participants'],'defined_participants':a['defined_participants'],'defined_draws':a['bootstrap']['defined_draws'],'ci95_ms':a['bootstrap']['percentile_95_interval_ms']}
 return {'task_id':TASK,'contract':CONTRACT,'recordings':rows,'areas':areas}
