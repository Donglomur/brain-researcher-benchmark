"""Prospective retrospective-LOO summaries; numerical imports only on explicit use."""
import math
import protocol as p

def design(rows,rotate=False):
 import numpy as np
 c=np.asarray([float(r['stimulus'])/100 for r in rows],float)
 a=np.asarray([r['condition']=='accuracy' for r in rows],float)
 side=np.asarray([r['response']=='right' for r in rows],float)
 p.need(all(r['condition'] in p.CONDITIONS and r['response'] in ('left','right') for r in rows),'Known instruction and actual response side required')
 p.need(np.all(np.isfinite(c)) and np.all((c>.025)&(c<1)),'Base contrast fraction domain')
 if rotate:
  c=c.copy()
  for condition in (0,1):
   for motor in (0,1):
    ix=np.flatnonzero((a==condition)&(side==motor));c[ix]=np.roll(c[ix],1)
 return np.column_stack((np.ones(len(c)),c,a,c*a,side))

def linear(y,x):
 import numpy as np
 # Explicit numerical-rank definition; no pseudoinverse interpretation of unidentified effects.
 s=np.linalg.svd(x,compute_uv=False);rank=int(np.sum(s>s[0]*1e-10)) if len(s) else 0
 if rank<5:return None,rank
 b=np.linalg.lstsq(x,y,rcond=1e-10)[0]
 return b,rank

def summarize_rows(rows,durations_ms,lags_ms):
 import numpy as np
 d=np.asarray(durations_ms,float);lags=np.asarray(lags_ms,float);n=len(rows)
 p.need(d.shape==(n,6) and lags.shape==(n,5) and np.all(np.isfinite(d)) and np.all(np.isfinite(lags)),'Six ordered marginal-mode intervals and five response lags')
 y=np.column_stack((d,d[:,1]+d[:,2],d[:,3]+d[:,4]));x=design(rows);xr=design(rows,True)
 b,rank=linear(y,x);br,_=linear(y,xr);out={}
 for j,s in enumerate(p.STAGES):
  values=[float(y[:,j].mean()),None if b is None else b[1,j],None if b is None else b[1,j]+b[3,j],None if b is None else b[4,j],None if br is None else br[1,j],None if br is None else br[1,j]+br[3,j]]
  for key,v in zip(p.EFFECTS,values):out[s+'/'+key]=p.cell(v,n if v is not None else 0,None if v is not None else 'rank_deficient')
 lb,_=linear(lags,x)
 for j in range(5):
  values=[float(lags[:,j].mean()),None if lb is None else lb[1,j],None if lb is None else lb[1,j]+lb[3,j]]
  for key,v in zip(('mean_ms','contrast_speed_ms','contrast_accuracy_ms'),values):out['event_'+str(j)+'/response_lag_'+key]=p.cell(v,n if v is not None else 0,None if v is not None else 'rank_deficient')
 return out,rank,int(np.any(d<0,axis=1).sum()),y

def curve_evidence(training,held_rows,held_y,latency_class):
 """Exact author curve formulas/bounds; NEW held-person averaging/validation."""
 import numpy as np
 out={}
 for sidx,stage in enumerate(p.STAGES):
  for condition in p.CONDITIONS:
   hi=[i for i,r in enumerate(held_rows) if r['condition']==condition]
   xs=sorted(set(float(held_rows[i]['stimulus'])/100 for i in hi))
   for model in p.CURVES:
    key=stage+'/'+condition+'/'+model+'_rmse_ms'
    if not xs:
     out[key]=p.cell(None,0,'insufficient_support');continue
    preds=[];reason=None
    for rows,y in training:
     ti=[i for i,r in enumerate(rows) if r['condition']==condition]
     tx=np.asarray([float(rows[i]['stimulus'])/100 for i in ti]);ty=np.asarray([y[i,sidx]/1000 for i in ti])
     if len(set(tx))<4:
      reason='insufficient_support';break
     try:
      obj=latency_class(model,ty,tx);obj.fit();v=np.asarray(obj.lat_func(np.asarray(xs),*obj.pars),float)*1000
      if v.shape!=(len(xs),) or not np.all(np.isfinite(v)):raise ValueError('Nonfinite curve')
      preds.append(v)
     except (ValueError,RuntimeError,FloatingPointError,OverflowError):
      reason='fit_failed';break
    if reason is not None:out[key]=p.cell(None,0,reason);continue
    p.need(len(preds)==25,'All25trainingpeople; no dropped fit')
    prediction=np.mean(preds,axis=0)
    observed=np.asarray([np.mean([held_y[i,sidx] for i in hi if float(held_rows[i]['stimulus'])/100==x]) for x in xs])
    out[key]=p.cell(np.sqrt(np.mean((observed-prediction)**2)),len(xs))
 return out
