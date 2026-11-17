"""Future independent NCM convention; not yet authenticated original REVE ABI.

No embeddings, weights, fit or prediction are obtained on import. Euclidean
centroids are an explicit prospective convention until original source is bound.
"""
import math
import numpy as np

def need(v,m):
 if not v:raise ValueError(m)
def centroids(features,labels,classes):
 """Future authorized calibration fit only; never invoked by construction checks."""
 raw=np.asarray(features);need(raw.dtype.kind in 'fiu','real embeddings');x=raw.astype(np.float64);y=np.asarray(labels)
 need(x.ndim==2 and y.ndim==1 and len(x)==len(y) and 0<x.shape[1]<=100000 and np.isfinite(x).all() and (np.abs(x)<=1e6).all(),'complete bounded frozenfeatures')
 need(type(classes) is int and classes>=2 and np.equal(y,np.floor(y)).all() and (y>=0).all() and (y<classes).all(),'calibration ontology')
 out=[]
 for c in range(classes):
  a=x[y==c];need(len(a)>0,'N labels in each class');anchor=a[0];out.append(anchor+(a-anchor).mean(0))
 return np.asarray(out)
def probabilities(features,centers):
 """Hard Euclidean NCM encoded as one-hot probabilities; exact distance ties use first class.

math.hypot scales each individual distance to preserve tiny nonzero geometry.
This endpoint is balanced accuracy, not a calibrated probability objective.
"""
 rx=np.asarray(features);rc=np.asarray(centers);need(rx.dtype.kind in 'fiu' and rc.dtype.kind in 'fiu','real embeddings and centroids');x=rx.astype(np.float64);c=rc.astype(np.float64)
 need(x.ndim==c.ndim==2 and 0<x.shape[1]==c.shape[1]<=100000 and len(x)>0 and len(c)>=2 and np.isfinite(x).all() and np.isfinite(c).all() and (np.abs(x)<=1e6).all() and (np.abs(c)<=1e6).all(),'complete boundedfrozen embeddings')
 out=np.zeros((len(x),len(c)),dtype=np.float64)
 for i,row in enumerate(x):
  distances=[math.hypot(*(float(a)-float(b) for a,b in zip(row,center))) for center in c];out[i,min(range(len(c)),key=distances.__getitem__)]=1.
 return out
