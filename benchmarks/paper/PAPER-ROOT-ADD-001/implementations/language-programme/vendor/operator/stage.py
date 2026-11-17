"""One isolated purged sentence fold. Operator source tree is never a candidate mount."""
import argparse,hashlib,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import read,decode,pin,put,fresh,need
from array_io import fresh_output
from protocol import FAMILIES,PROTOCOL_SHA,SESSIONS,design_check
from prepare import load_session
from core import smooth3,format_words,prospective_support,purged_split


def episode(a,fold):
    n=len(a['fr']);t,q,valid=prospective_support(a['timing'],a['qid'],a,n,a['speaker'])
    tr,te=purged_split(t,q,fold);features={}
    for f in FAMILIES:
        e=a[f][valid];need(np.isfinite(e).all(),'All matched feature operands finite')
        x,_=format_words(a['timing'][valid],a['qid'][valid],e.reshape(len(e),-1),n)
        features[f]=x[t].reshape(len(t),30,e.shape[2])
    # Observed within-sentence position/duration and absolute session time only.
    clock=np.zeros((len(t),3))
    for k in np.unique(q):
        ix=np.flatnonzero(q==k);clock[ix,0]=(t[ix]-t[ix[0]])*.1;clock[ix,1]=(t[ix[-1]]-t[ix[0]]+1)*.1
    clock[:,2]=t*.1;features['clock']=clock
    y=smooth3(a['fr'])[t-10]
    train={'target':y[tr],'sentence':q[tr],'row':t[tr]};query={}
    for f,x in features.items():train[f]=x[tr];query[f]=x[te]
    # Relative time/order is disclosed; no claim of a neural-specific causal effect.
    return train,query,y[te],t[te]


def write_npz(path,values):
    np.savez_compressed(path,**values);path.chmod(0o444);return {'path':path.name,**pin(read(path,256*1024**2))}


def stage(root,design_path,session,fold,output,nonce):
    fresh_output(output);need(session in SESSIONS and type(fold) is int and 0<=fold<5 and len(nonce)>=16,'Declared episode/opaque nonce')
    raw=read(design_path,500000);d=design_check(decode(raw));a=load_session(root,d,session)
    tr,qu,y,t=episode(a,fold);out=fresh(output);pub=out/'candidate';pub.mkdir();priv=out/'operator';priv.mkdir()
    ids=[hashlib.sha256(f'{nonce}:{session}:{fold}:{int(v)}'.encode()).hexdigest() for v in t]
    train=write_npz(pub/'training.npz',tr);query=write_npz(pub/'query.npz',qu);target=write_npz(priv/'target.npz',{'target':y})
    case={'schema':'language_episode_v1','id':f'{session}_f{fold}','session':session,'fold':fold,'design_sha256':pin(raw)['sha256'],
          'protocol_sha256':PROTOCOL_SHA,'rows':len(y),'units':y.shape[1],'query_ids':ids,'training':train,'query':query}
    put(pub/'case.json',case,2000000);put(priv/'binding.json',{'case':case,'target':target,'source_rows':t.tolist()},2000000)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--design',required=True);p.add_argument('--session',required=True);p.add_argument('--fold',type=int,required=True);p.add_argument('--nonce',required=True);p.add_argument('--output',required=True);a=p.parse_args();stage(a.root,a.design,a.session,a.fold,a.output,a.nonce)
