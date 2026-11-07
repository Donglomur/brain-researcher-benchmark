"""Future native numerical producer, not run in construction. No saved answers."""
import argparse,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import read,decode,pin,put,need,fresh
from array_io import fresh_output
from protocol import SESSIONS,FAMILIES,PROTOCOL_SHA,native_shapes,design_check
from prepare import load_session
from core import smooth3,format_words,native_rows,correlation,sentence_swap_indices


def loso(x,y,q):
    from sklearn.linear_model import Ridge
    need(np.isfinite(x).all() and np.isfinite(y).all() and len(np.unique(q))>=2,'Finite LOSO support')
    p=np.empty_like(y)
    for label in np.unique(q):
        te=q==label;tr=~te;need(tr.any() and te.any(),'Sentence-disjoint fold')
        model=Ridge(alpha=.01,fit_intercept=True);model.fit(x[tr],y[tr]);p[te]=model.predict(x[te])
    return correlation(y,p)


def curve(a,y,f,lags,shuffle=False,swap=False):
    e=a[f];timing=a['timing'];q=a['qid']
    if f in ('sem_syn','word2vec'):
        keep=~np.isnan(e[:,0,0]);e=e[keep];timing=timing[keep];q=q[keep]
    need(np.isfinite(e).all(),'Native finite embeddings after exact lexical exclusion')
    if swap:e=e[sentence_swap_indices(q)]
    if shuffle:y=np.random.RandomState(20).permutation(y)
    values=np.zeros((y.shape[1],len(lags),e.shape[2]));defined=np.zeros(values.shape,dtype=np.uint8)
    for layer in range(e.shape[2]):
        x,s=format_words(timing,q,e[:,:,layer],len(y))
        for k,lag in enumerate(lags):
            xx,yy,qq=native_rows(y,x,a['speaker'],s,lag)
            values[:,k,layer],defined[:,k,layer]=loso(xx,yy,qq)
    return values,defined


def compute(a):
    population=smooth3(a['fr'].mean(axis=1,keepdims=True));units=smooth3(a['fr'])
    out={}
    specs=[('population','context',population,list(range(-20,20)),False,False),
           ('unit','context',units,list(range(-20,20)),False,False),
           ('time_shuffle','context',population,list(range(-20,20)),True,False),
           ('random_token','random_token',population,[-10],False,False),
           ('sentence_swap','context',population,[-10],False,True)]
    specs += [(f,f,population,[-10],False,False) for f in FAMILIES if f.startswith('ngram')]
    specs += [(f+suffix,f,population,[-3,-2,-1],bool(suffix),False) for f in ('sem_syn','word2vec','syn') for suffix in ('','_shuffle')]
    for name,f,y,lags,shuffle,swap in specs:
        v,m=curve(a,y,f,lags,shuffle,swap)
        if name!='unit':v=v[0];m=m[0]
        out['value_'+name]=v;out['defined_'+name]=m
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--design',required=True);p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    fresh_output(a.output);raw=read(a.design,500000);d=design_check(decode(raw));out=fresh(a.output);rows=[]
    for s in SESSIONS:
        result=compute(load_session(a.root,d,s));target=out/(s+'.npz');np.savez_compressed(target,**result);target.chmod(0o444)
        rows.append({'id':s,'path':target.name,**pin(read(target,32*1024**2))})
    put(out/'submission.json',{'schema':'language_submission_v1','mode':'native','protocol_sha256':PROTOCOL_SHA,'design_sha256':pin(raw)['sha256'],'files':rows},500000)
if __name__=='__main__':main()
