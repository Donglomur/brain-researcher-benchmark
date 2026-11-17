"""Prospective fixed spectral ridge control. Source only; no construction fit calls.

This is not a published REVE baseline. It fixes spectral features, training-only
standardization, five ridge penalties, validation-only monitor selection and first
penalty tie. No pretrained weights, hidden labels or data downloader are used.
"""
import numpy as np
from .metric_core import classify

def need(v,m):
 if not v:raise ValueError(m)
BANDS=((1.,4.),(4.,8.),(8.,13.),(13.,30.),(30.,45.))
PENALTIES=(0.001,0.01,0.1,1.,10.)

def features(epoch,sampling_hz):
 a=np.asarray(epoch,dtype=np.float64);need(a.ndim==3 and a.shape[2]>=128 and sampling_hz in (200,256),'epochs/channels/time; declared rate')
 need(np.isfinite(a).all() and (np.abs(a)<=1e6).all(),'bounded canonical millivolt epochs')
 # Whole-epoch noncausal feature; no online latency claim. No outcome fitting.
 # Center differences from an observed sample so exactly constant decimal
 # epochs remain exact zero rather than acquiring mean-rounding spectral power.
 a=a-a[:,:,:1];a=a-a.mean(axis=2,keepdims=True);window=np.hanning(a.shape[2]);power=np.abs(np.fft.rfft(a*window,axis=2))**2/(sampling_hz*np.dot(window,window));frequency=np.fft.rfftfreq(a.shape[2],1/sampling_hz)
 result=[]
 for low,high in BANDS:
  keep=(frequency>=low)&(frequency<high);need(keep.any(),'complete fixed frequency bands')
  result.append(np.log1p(power[:,:,keep].mean(axis=2)))
 return np.stack(result,axis=2).reshape(len(a),-1)

def standardization(train):
 x=np.asarray(train,dtype=np.float64);need(x.ndim==2 and len(x)>0 and np.isfinite(x).all() and (np.abs(x)<=1e6).all(),'finite bounded training features')
 anchor=x[0].copy();constant=np.all(x==anchor,axis=0);spread=np.max(np.abs(x-anchor),axis=0);spread[constant]=1.
 normalized=(x-anchor)/spread;center=normalized.mean(0);scale=np.sqrt(np.mean((normalized-center)**2,axis=0));scale[constant]=1.
 need(np.isfinite(scale).all() and (scale>0).all(),'nonconstant training variation must be representable')
 return {'anchor':anchor,'spread':spread,'center':center,'scale':scale,'constant':constant}

def transform(x,normalizer):
 x=np.asarray(x,dtype=np.float64);need(x.ndim==2 and x.shape[1]==len(normalizer['anchor']) and np.isfinite(x).all() and (np.abs(x)<=1e6).all(),'complete finite features')
 with np.errstate(over='raise',divide='raise',invalid='raise'):
  z=((x-normalizer['anchor'])/normalizer['spread']-normalizer['center'])/normalizer['scale']
 z[:,normalizer['constant']]=0.;need(np.isfinite(z).all(),'finite transformed features');return z

def fit(train_x,train_y,val_x,val_y,classes):
 """Future authorized fit only; input rows already isolated by qualified people."""
 x=np.asarray(train_x,dtype=np.float64);v=np.asarray(val_x,dtype=np.float64);y=np.asarray(train_y);z=np.asarray(val_y)
 need(x.ndim==v.ndim==2 and x.shape[1]==v.shape[1] and x.shape[1]<=2000 and 1<=len(x) and len(y)==len(x) and len(z)==len(v),'complete train/validation features')
 need(np.isfinite(x).all() and np.isfinite(v).all() and (np.abs(x)<=1e6).all() and (np.abs(v)<=1e6).all(),'finite features')
 need(np.equal(y,np.floor(y)).all() and (y>=0).all() and (y<classes).all() and len(set(y))==classes,'training class support')
 normalizer=standardization(x);x=transform(x,normalizer);v=transform(v,normalizer)
 x=np.column_stack((np.ones(len(x)),x));v=np.column_stack((np.ones(len(v)),v));one=np.eye(classes)[y.astype(int)];gram=x.T@x/len(x);rhs=x.T@one/len(x);penalty=np.eye(x.shape[1]);penalty[0,0]=0
 best=None;score=None;selected=None;monitor='cohen_kappa' if classes>2 else 'auroc'
 for alpha in PENALTIES:
  beta=np.linalg.solve(gram+alpha*penalty,rhs);logit=v@beta;logit-=logit.max(1,keepdims=True);prob=np.exp(logit);prob/=prob.sum(1,keepdims=True)
  value=classify(z,prob,classes)[monitor]
  if value is not None and (score is None or value>score):best=beta;score=value;selected=alpha
 need(best is not None,'undefined validation monitor; no assessment fallback')
 return {'normalizer':normalizer,'beta':best,'penalty':selected,'validation_monitor':score,'source_parity':False}

def predict(model,x):
 x=transform(x,model['normalizer']);x=np.column_stack((np.ones(len(x)),x));a=x@model['beta'];a-=a.max(1,keepdims=True);p=np.exp(a);return p/p.sum(1,keepdims=True)
