"""Prospective stimulus/temporal projection, independent of neural responses."""
import hashlib,json,math
import numpy as np
FAMILIES=('drifting_gratings','gabors','flashes','static_gratings')
FIELDS=('orientation','spatial_frequency','temporal_frequency','contrast','phase','size','x_position','y_position','color','opacity','mask','units')
AREAS=('VISp','VISl','VISal','VISrl','VISam','VISpm')
EXPOSURE=.2

def scalar(v):
 if isinstance(v,np.generic):v=v.item()
 if isinstance(v,bytes):v=v.decode('utf-8')
 if v is None:return None
 if isinstance(v,str):
  if v.strip().lower() in ('null','nan','none',''):return None
  if len(v)>512:raise ValueError('oversized stimulus field')
  try:
   x=float(v)
   if math.isfinite(x):return x
  except ValueError:pass
  return v
 if type(v) in (int,float) and not isinstance(v,bool):return float(v) if math.isfinite(float(v)) else None
 raise ValueError('unsupported native stimulus scalar')

def condition(row):
 # Explicit native fields; no source precomputed neural tuning metrics.
 return json.dumps([row['family']]+[row['features'].get(k) for k in FIELDS],ensure_ascii=True,separators=(',',':'),allow_nan=False)

def overlap(a,b,invalid):return any(a<y and x<b for x,y in invalid)

def prediction_rows(native,invalid):
 rows=[];dis=[]
 for family in FAMILIES:
  if family not in native:raise ValueError('missing required stimulus family '+family)
  for raw in native[family]:
   onset=float(raw['start_time']);stop=float(raw['stop_time']);uid=family+':'+str(raw['id'])
   if not math.isfinite(onset) or not math.isfinite(stop) or onset<0 or stop<=onset:raise ValueError('invalid native trial clock')
   r={'id':uid,'family':family,'onset':onset,'stop':stop,'features':{k:scalar(raw.get(k)) for k in FIELDS},'block':scalar(raw.get('stimulus_block'))}
   key=condition(r);r['condition_key']=key
   r['split']='QUERY' if family=='static_gratings' else ('VALIDATION' if int(hashlib.sha256(('neural091-v1:'+key).encode()).hexdigest(),16)%10<2 else 'FIT')
   r['window']=[onset,onset+EXPOSURE]
   reason='insufficient_pre_history' if onset<.5 else 'short_native_stimulus' if stop<onset+EXPOSURE else ('invalid_time_overlap' if overlap(onset-.5,onset+EXPOSURE,invalid) else None)
   if reason:dis.append({'id':uid,'split':r['split'],'reason':reason})
   else:rows.append(r)
 held=[r['window'] for r in rows if r['split']!='FIT'];kept=[]
 for r in rows:
  if r['split']=='FIT' and any(r['window'][0]<b+1 and a-1<r['window'][1] for a,b in held):dis.append({'id':r['id'],'split':'FIT','reason':'one_second_held_window_guard'})
  else:kept.append(r)
 kept.sort(key=lambda r:(r['onset'],r['id']))
 if len({r['id'] for r in kept})!=len(kept):raise ValueError('duplicate trial IDs')
 if set(r['split'] for r in kept)!={'FIT','VALIDATION','QUERY'}:raise ValueError('required partition unavailable; no cohort replacement')
 return kept,dis

def state_rows(native,invalid):
 rawrows=native['drifting_gratings'];blocks=sorted({int(r['stimulus_block']) for r in rawrows if math.isfinite(float(r['stimulus_block'])) and float(r['stimulus_block']).is_integer()})
 if blocks!=[2,5,7]:raise ValueError('frozen native DG blocks2/5/7 required; no fallback')
 for left,right in zip(blocks,blocks[1:]):
  if max(float(r['stop_time']) for r in rawrows if int(r['stimulus_block'])==left)>min(float(r['start_time']) for r in rawrows if int(r['stimulus_block'])==right):raise ValueError('native block time order/overlap')
 mapping=dict(zip(blocks,('FIT','VALIDATION','QUERY')));rows=[];dis=[]
 for raw in rawrows:
  onset=float(raw['start_time']);stop=float(raw['stop_time']);block=int(raw['stimulus_block']);uid='drifting_gratings:'+str(raw['id'])
  if not math.isfinite(onset) or onset<0 or not math.isfinite(stop) or stop<=onset:raise ValueError('invalid native clock')
  if float(raw['stimulus_block'])!=block:raise ValueError('nonintegral block')
  r={'id':uid,'family':'drifting_gratings','onset':onset,'stop':stop,'block':block,'split':mapping[block],'features':{k:scalar(raw.get(k)) for k in FIELDS},'window':[onset+.05,onset+1.95]};r['condition_key']=condition(r)
  reason='insufficient_pre_history' if onset<.5 else 'short_native_stimulus' if stop<onset+1.95 else ('invalid_time_overlap' if overlap(onset-.5,onset+1.95,invalid) else None)
  if reason:dis.append({'id':uid,'split':r['split'],'reason':reason})
  else:rows.append(r)
 rows.sort(key=lambda r:(r['onset'],r['id']))
 if set(r['split'] for r in rows)!={'FIT','VALIDATION','QUERY'}:raise ValueError('required full block support unavailable')
 return rows,dis

def assign_states(rows,running,pupil):
 if len(rows)!=len(running) or len(rows)!=len(pupil):raise ValueError('state support')
 fit=[float(v) for r,v in zip(rows,pupil) if r['split']=='FIT' and v is not None and math.isfinite(float(v))]
 cut=np.quantile(np.array(fit),[1/3,2/3],method='linear').tolist() if len(fit)>=3 else None
 if cut and not cut[0]<cut[1]:cut=None
 out=[]
 for r,run,pup in zip(rows,running,pupil):
  s=dict(r);s['running_cm_per_s']=run;s['pupil_area']=pup
  s['run_bin']='MISSING' if run is None else ('REST' if run<=1 else 'RUN' if run>=5 else 'TRANSITION')
  s['pupil_bin']='MISSING' if pup is None or cut is None else ('LOW' if pup<=cut[0] else 'HIGH' if pup>cut[1] else 'MID')
  out.append(s)
 return out,{'FIT_pupil_observations':len(fit),'terciles':cut,'tie_policy':'LOW <= lower, MID lower < x <= upper, HIGH > upper; equal cutpoints unavailable'}
