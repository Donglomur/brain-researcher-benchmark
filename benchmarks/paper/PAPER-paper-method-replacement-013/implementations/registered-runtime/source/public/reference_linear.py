"""Prospective fixed train-only ridge control for continuous VisNav behavior.

This is not an implementation of the paper's Lasso/GLM/MLP/GRU or Neuroformer.
It consumes only observed neural history/current counts, never speed/gaze/video.
No fitting occurs at import. Build checks exercise feature/constant boundaries.
"""
import argparse,json
from pathlib import Path
import numpy as np
from io_contract import require

PENALTIES=(.01,.1,1.,10.,100.)

def features(history,current):
    for a in (history,current):require(a.dtype.kind in 'iuf' and a.ndim==3 and np.isfinite(a).all() and (a>=0).all(),'finite nonnegative neural context')
    require(history.shape[0]==current.shape[0] and history.shape[2]==current.shape[2] and history.shape[1]==30 and current.shape[1]==10,'complete context')
    # Ten consecutive20ms aggregate bins retain short-range temporal structure.
    v=np.concatenate((history,current),axis=1).reshape(len(current),10,4,current.shape[2]).sum(2,dtype=np.float64)
    return np.log1p(v).reshape(len(current),-1)

def normalize_fit(x):
    require(x.ndim==2 and x.shape[0]>1 and np.isfinite(x).all(),'training features')
    constant=(x==x[0]).all(0);anchor=x[0].copy();center=(x-anchor).mean(0);scale=np.sqrt(((x-anchor-center)**2).mean(0));scale[constant]=1
    return anchor,center,scale,constant

def normalize(x,state):
    a,c,s,constant=state;out=(x-a-c)/s;out[:,constant]=0;require(np.isfinite(out).all(),'finite normalized features');return out

def fit(train_x,train_y,val_x,val_y):
    state=normalize_fit(train_x);a=normalize(train_x,state);b=normalize(val_x,state);mu=train_y.mean(0);target=train_y-mu
    best=None
    # Dual system keeps the number of parameters tied to labeled windows.
    gram=a@a.T
    for penalty in PENALTIES:
        coef=a.T@np.linalg.solve(gram+penalty*np.eye(len(a)),target)
        loss=float(np.mean((b@coef+mu-val_y)**2));require(np.isfinite(loss),'finite validation loss')
        item=(loss,penalty,coef)
        if best is None or item[:2]<best[:2]:best=item
    return state,mu,best[2],best[1]

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--view',required=True);a.add_argument('--output',required=True);z=a.parse_args();r=Path(z.view);case=json.loads((r/'CASE.json').read_text())
    require(case['definition']['kind'] in ('regression','joint'),'continuous behavior control only')
    xs={}
    for s in ('train','validation','test'):xs[s]=features(np.load(r/(s+'_neural_history.npy'),allow_pickle=False),np.load(r/(s+'_neural_current.npy'),allow_pickle=False))
    train=np.load(r/'train_labels.npy',allow_pickle=False);val=np.load(r/'validation_labels.npy',allow_pickle=False)
    state,mu,coef,penalty=fit(xs['train'],train,xs['validation'],val);p=normalize(xs['test'],state)@coef+mu
    require(np.isfinite(p).all() and list(p.shape)==case['output_shape'],'complete finite prediction')
    with Path(z.output).open('xb') as f:np.save(f,p.astype('<f8'),allow_pickle=False)
if __name__=='__main__':main()
