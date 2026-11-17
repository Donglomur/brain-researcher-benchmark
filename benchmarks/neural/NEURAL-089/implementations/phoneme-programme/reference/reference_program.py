"""Independent prospective original-SGD recipe; trusted reference artifacts only.

This program never accepts a candidate artifact. The operator must bind its
exact role/source/model lineage before launching it. No empirical competence or
numerical packaging parity is claimed by this source.
"""
import hashlib, json, math, pickle
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import SGDClassifier

def need(ok,message):
    if not ok:raise ValueError(message)

def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate field');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))

def features(windows):
    x=np.asarray(windows)
    need(x.ndim==3 and x.shape[1:]==(306,125) and np.isfinite(x).all(),'complete fixed MEG windows')
    return x.astype(np.float64).reshape(len(x),306,5,25).mean(axis=3).reshape(len(x),1530)

def verify_file(root,pin):
    p=root/pin['path'];need(p.resolve().is_relative_to(root.resolve()) and not p.is_symlink() and p.stat().st_size==pin['bytes'],'bounded local input')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    need(h.hexdigest()==pin['sha256'],'source pin');return p

def training_batches(root,rows):
    for row in rows:
        if row['partition']!='train':continue
        p=verify_file(root,row['features']);lp=verify_file(root,row['labels'])
        x=np.load(p,mmap_mode='r',allow_pickle=False);y=np.memmap(lp,mode='r',dtype='<i2')
        need(x.shape==(row['windows'],306,125) and x.dtype==np.dtype('<f4') and y.shape==(row['windows'],),'complete original run geometry')
        for start in range(0,row['windows'],128):
            yy=np.asarray(y[start:start+128]);need(((yy>=0)&(yy<39)).all(),'39-class permitted labels')
            yield features(x[start:start+128]),yy

def fit_training(batches,make=None):
    if make is None:
        scaler=StandardScaler();model=SGDClassifier(loss='log_loss',penalty='l2',alpha=1e-4,fit_intercept=True,learning_rate='optimal',random_state=89,shuffle=False,average=False,tol=None,max_iter=1)
    else:scaler,model=make()
    seen=0
    for x,y in batches():need(len(x)==len(y),'training label alignment');scaler.partial_fit(x);seen+=len(x)
    need(seen>0,'full nonempty training')
    for epoch in range(5):
        count=0
        for x,y in batches():model.partial_fit(scaler.transform(x),y,classes=np.arange(39));count+=len(x)
        need(count==seen,'same full training every epoch')
    need(list(model.classes_)==list(range(39)),'fixed class order')
    return {'kind':'neural','scaler':scaler,'model':model,'training_count':seen,'passes':5}

def main():
    root=Path('/input');v=strict((root/'INPUT.json').read_bytes());mode=v['mode']
    need(v['schema']=='neural089-program-input-v1','input schema')
    if mode=='fit_neural':
        need(set(v)=={'schema','mode','runs'} and len(v['runs'])==89 and sum(r['partition']=='train' for r in v['runs'])==88 and sum(r['partition']=='validation' for r in v['runs'])==1,'full original fitting view')
        state=fit_training(lambda:training_batches(root,v['runs']))
    elif mode=='fit_prior':
        need(set(v)=={'schema','mode','counts'},'counts-only prior')
        counts=v['counts'];need(len(counts)==39 and all(type(x)is int and x>=0 for x in counts) and sum(counts)>0,'training prior support')
        state={'kind':'prior','probabilities':[(x+1)/(sum(counts)+39) for x in counts]}
    elif mode in ('infer_neural','infer_prior'):
        # Only this independently sealed reference's artifact reaches this path.
        with Path('/model/model.bin').open('rb') as f:state=pickle.load(f)
        if mode=='infer_prior':
            need(set(v)=={'schema','mode'} and state['kind']=='prior','no query exposure in prior')
            out={'probabilities':state['probabilities']}
        else:
            need(set(v)=={'schema','mode','query_id','features'} and state['kind']=='neural','same trained neural artifact')
            x=np.load(verify_file(root,v['features']),allow_pickle=False)
            need(x.shape==(306,125) and x.dtype==np.dtype('<f4'),'one complete query')
            p=state['model'].predict_proba(state['scaler'].transform(features(x[None])))[0]
            out={'query_id':v['query_id'],'probabilities':p.tolist()}
        p=out['probabilities'];need(len(p)==39 and all(type(x)in(int,float) and math.isfinite(x) and 0<=x<=1 for x in p) and abs(math.fsum(p)-1)<=1e-6,'probability simplex')
        with Path('/output/prediction.json').open('x') as f:json.dump(out,f,allow_nan=False,separators=(',',':'));f.write('\n')
        return
    else:raise ValueError('unknown phase')
    with Path('/output/model.bin').open('xb') as f:pickle.dump(state,f,protocol=5)

if __name__=='__main__':main()
