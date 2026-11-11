"""Prospective identical ridge selection per arm. No empirical fit performed."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from io_contract import capture,decode

ALPHAS=(.01,.1,1.,10.,100.)


def fit(x,y,alpha):
    center=y.mean(0);coef=np.linalg.solve(x@x.T/x.shape[1]+alpha*np.eye(len(x)),y-center)
    if not np.isfinite(coef).all():raise ValueError('Finite ridge coefficients required')
    return x,center,coef


def predict(model,x):
    training,center,coef=model;result=x@training.T/training.shape[1]@coef+center
    if not np.isfinite(result).all():raise ValueError('Finite predictions required')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--view',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists() or a.out.is_symlink():raise ValueError('Fresh result directory')
    scope=decode(capture(a.view/'SCOPE.json',100000));x={};y={}
    for split,size in (('fit',900),('validation',100),('query',102)):
        # Trusted isolated view contains only primitive operator-prepared arrays.
        values=np.load(a.view/('x_'+split+'.npy'),allow_pickle=False)
        if values.shape!=(size,scope['feature_columns']) or not np.isfinite(values).all():raise ValueError('Complete design')
        x[split]=values
        if split!='query':
            values=np.load(a.view/('y_'+split+'.npy'),allow_pickle=False)
            if values.shape!=(size,127,150) or not np.isfinite(values).all():raise ValueError('Complete permitted target')
            y[split]=values.reshape(size,-1)
    losses=[]
    for alpha in ALPHAS:
        loss=float(np.mean((predict(fit(x['fit'],y['fit'],alpha),x['validation'])-y['validation'])**2))
        if not np.isfinite(loss):raise ValueError('Finite validation selection loss')
        losses.append(loss)
    chosen=min(range(len(ALPHAS)),key=lambda i:(losses[i],i))
    model=fit(np.concatenate((x['fit'],x['validation'])),np.concatenate((y['fit'],y['validation'])),ALPHAS[chosen])
    values=predict(model,x['query']).reshape(102,127,150)
    a.out.mkdir();path=a.out/'prediction.npy';np.save(path,values,allow_pickle=False);body=path.read_bytes()
    result={'schema':'neural080_arm_result_v1','subject':scope['subject'],'arm':scope['arm'],
            'query_sha256':scope['query_sha256'],'file':'prediction.npy','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    with (a.out/'RESULT.json').open('x') as f:json.dump(result,f,allow_nan=False,indent=2)


if __name__=='__main__':main()
