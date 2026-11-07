"""Future operator baseline recipe. No fitted result or model weights bundled.
Nested sentence-group selection is confined to the training packet. All four
baseline outputs must be independently captured and pinned by the operator.
"""
import argparse,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import need,read,decode,pin,put,resolve
from array_io import arrays,fresh_output
from protocol import P,FAMILIES,ARMS
from core import correlation


def options(packet,arm):
    if arm=='clock':return [packet['clock']]
    if arm=='lexical':return [packet[f][:,:,0] for f in ('sem_syn','word2vec','syn')]
    family='context' if arm=='context' else 'random_token'
    return [packet[family][:,:,i] for i in range(33)]


def fit_predict(x,y,z,alpha):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    model=make_pipeline(StandardScaler(),Ridge(alpha=alpha,fit_intercept=True))
    model.fit(x,y);return model.predict(z)


def run(train,query,arm):
    xs=options(train,arm);zs=options(query,arm);q=train['sentence'];y=train['target']
    ids=list(dict.fromkeys(int(v) for v in q));need(len(ids)>=6,'Nested training sentence support')
    groups=np.array_split(ids,3);best=None
    for option,x in enumerate(xs):
        for alpha in P['prospective']['alpha_grid']:
            pred=np.empty_like(y)
            for g in groups:
                te=np.isin(q,g);tr=~te
                times=train['row'];held=times[te];j=np.searchsorted(held,times)
                for delta in (-1,0):tr &= np.abs(times-held[np.clip(j+delta,0,len(held)-1)])>2
                need(tr.any() and te.any(),'Nested purged group support')
                pred[te]=fit_predict(x[tr],y[tr],x[te],alpha)
            rho,mask=correlation(y,pred)
            # No outcome-based unit exclusion: full unit support required.
            need(mask.all(),'Undefined nested selection support; no post-hoc unit removal')
            key=(float(rho.mean()),float(alpha),-option)
            if best is None or key>best[0]:best=(key,option,alpha)
    _,option,alpha=best
    return fit_predict(xs[option],y,zs[option],alpha),{'feature_option':option,'alpha':alpha,'selection':'training_only_three_group_folds'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();fresh_output(a.output)
    case_raw=read(a.case,2000000);c=decode(case_raw)
    def get(key,keys):
        r=c[key];return arrays(read(resolve(a.root,r['path']),256*1024**2,{k:r[k] for k in ('bytes','sha256')}),keys,256*1024**2)
    train=get('training',['target','sentence','row',*FAMILIES,'clock']);query=get('query',[*FAMILIES,'clock'])
    out={};selected={}
    for arm in ARMS[1:]:out[arm],selected[arm]=run(train,query,arm)
    np.savez_compressed(a.output,**out)
    put(str(a.output)+'.metadata.json',{'case_sha256':pin(case_raw)['sha256'],'baselines':pin(read(a.output,32*1024**2)),'selected':selected},100000)
if __name__=='__main__':main()
