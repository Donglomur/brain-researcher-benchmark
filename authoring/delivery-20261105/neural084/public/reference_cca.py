"""Unfitted phase-invariant two-harmonic CCA reference for the new representation.

This is independent Python source, not numerically qualified MATLAB parity.
"""
import argparse
import io
from pathlib import Path
import numpy as np
from protocol import *
from io_utils import need, read, json_file, resolve, put


def orthonormal_span(a):
    a=np.asarray(a,dtype=np.float64)
    need(a.ndim==2 and np.isfinite(a).all(),"finite matrix")
    # Normalize before centering/SVD; finite extreme input cannot overflow sums.
    scale=float(np.max(np.abs(a)))
    if scale==0:return np.zeros((a.shape[0],0))
    a=a/scale;a=a-a.mean(axis=0,keepdims=True)
    u,s,_=np.linalg.svd(a,full_matrices=False)
    if not len(s) or s[0]==0:return u[:,:0]
    threshold=max(a.shape)*np.finfo(np.float64).eps*s[0]
    return u[:,s>threshold]


def scores(epoch):
    need(epoch.shape==(10,400) and np.isfinite(epoch).all(),"finite10x400 query")
    x=orthonormal_span(epoch.T)
    time=np.arange(400)/100.0+0.0045
    result=[]
    for f in FREQUENCIES:
        columns=[g(2*np.pi*h*f*time) for h in (1,2) for g in (np.sin,np.cos)]
        y=orthonormal_span(np.asarray(columns).T)
        if x.shape[1]==0 or y.shape[1]==0:r=0.0
        else:r=float(np.linalg.svd(x.T@y,compute_uv=False)[0])
        need(np.isfinite(r) and -1e-12<=r<=1+1e-12,"defined canonical correlation")
        result.append(min(1.0,max(0.0,r)))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mode",choices=("cca","constant","frequency-permuted"),default="cca");a=p.parse_args()
    meta=json_file(a.input/"fold.json",262144)
    need(meta["schema"]=="neural084_fold_v1" and len(meta["ids"])==400,"full fold")
    d=meta["queries"];x=np.load(io.BytesIO(read(resolve(a.input,d["path"]),7000000,{k:d[k] for k in ("bytes","sha256")})),allow_pickle=False)
    need(x.dtype==np.dtype("float32") and x.shape==(400,10,400),"public query schema")
    predictions=[]
    for qid,epoch in zip(meta["ids"],x):
        values=[0.0]*4 if a.mode=="constant" else scores(epoch)
        if a.mode=="frequency-permuted":values=values[1:]+values[:1]
        predictions.append({"id":qid,"scores":values})
    put(a.out,{"schema":SCHEMA,"generation":meta["generation"],"fold":meta["fold"],
               "predictions":predictions},MAX_SUBMISSION_BYTES)


if __name__=="__main__":main()
