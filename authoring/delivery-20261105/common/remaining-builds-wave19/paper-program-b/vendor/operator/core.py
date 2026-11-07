"""Source-faithful formatting/lag arithmetic and separately declared purged split.
No estimators are imported or fitted in this module.
"""
import random
import numpy as np
from delivery_io import need


def smooth3(y):
    y=np.asarray(y,dtype=np.float64);need(y.ndim==2 and len(y)>=3 and np.isfinite(y).all(),'Finite matrix')
    # Same cumulative sum arithmetic as the author per-neuron running_mean.
    c=np.concatenate([np.zeros((1,y.shape[1])),np.cumsum(y,axis=0)],axis=0)
    out=np.zeros_like(y);out[1:-1]=(c[3:]-c[:-3])/3
    need(np.isfinite(out).all(),'Representable smoothed data');return out


def format_words(timing,qid,features,n):
    timing=np.asarray(timing,dtype=np.float64);qid=np.asarray(qid);features=np.asarray(features,dtype=np.float64)
    need(timing.shape==(len(qid),2) and features.ndim==2 and len(features)==len(qid),'Word geometry')
    need(np.isfinite(timing).all() and np.all(timing>=0) and np.all(timing[:,1]>=timing[:,0]) and
         np.isfinite(features).all() and np.all((qid>=0)&(qid<99990)),'Finite word metadata/features')
    bins=(timing*10).astype(np.int64);need(np.all(bins<=n),'Timing inside complete neural clock')
    x=np.tile(features.mean(axis=0),(n,1));q=np.full(n,99999,dtype=np.int64)
    for (a,b),label,row in zip(bins,qid,features):x[a:b]=row;q[a:b]=label
    return x,q


def native_rows(y,x,speaker,q,lag):
    """Literal author asymmetric lag/speaker/sentinel support, including zero padding."""
    y=np.asarray(y);x=np.asarray(x);q=np.asarray(q);n=len(y)
    need(len(x)==len(q)==len(speaker)==n and abs(lag)<n,'Aligned arrays')
    if lag<0:
        yy=np.concatenate([np.zeros((-lag,y.shape[1])),y])[:lag];xx=x;qq=q
    elif lag>0:
        yy=y;xx=np.concatenate([np.zeros((lag,x.shape[1])),x])[:-lag]
        qq=np.concatenate([np.zeros(lag,dtype=q.dtype),q])[:-lag]
    else: yy=y;xx=x;qq=q
    keep=(speaker==1)&(qq<99990)
    return xx[keep],yy[keep],qq[keep]


def sentence_swap_indices(q):
    q=np.asarray(q);groups={int(k):np.flatnonzero(q==k) for k in np.unique(q)}
    rng=random.Random(20);out=[]
    for k,idx in groups.items():
        others=[j for j,v in groups.items() if len(v)==len(idx) and j!=k]
        out.extend(groups[rng.choice(others) if others else k])
    return np.asarray(out,dtype=np.int64)


def correlation(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    need(y.shape==p.shape and y.ndim==2 and len(y)>=2 and np.isfinite(y).all() and np.isfinite(p).all(),'Paired finite predictions')
    # Exact binary scaling avoids overflow/underflow and preserves adjacent
    # floating-point differences around a large common offset.
    def centered(v):
        _,exponent=np.frexp(np.max(np.abs(v),axis=0))
        a=np.ldexp(v,-exponent)
        a=a-a[0]  # offset removal before a potentially rounded mean
        a-=a.mean(axis=0)
        _,second=np.frexp(np.max(np.abs(a),axis=0))
        a=np.ldexp(a,-second)
        a-=a.mean(axis=0)
        return a
    a=centered(y);b=centered(p)
    aa=np.sum(a*a,axis=0);bb=np.sum(b*b,axis=0);mask=(aa>0)&(bb>0)
    r=np.zeros(y.shape[1]);r[mask]=np.sum(a*b,axis=0)[mask]/np.sqrt(aa[mask]*bb[mask])
    need(np.isfinite(r).all(),'Representable correlations');return np.clip(r,-1,1),mask.astype(np.uint8)


def folds(q):
    """First-occurrence sentence order, never derived from firing rates."""
    q=np.asarray(q);ids=list(dict.fromkeys(int(x) for x in q));need(len(ids)>=10,'At least ten represented sentences')
    return [np.isin(q,z) for z in np.array_split(np.asarray(ids),5)]


def prospective_support(timing,qid,features,n,speaker):
    # Require complete finite lexical support, matched for every arm.
    valid=np.ones(len(qid),dtype=bool)
    for f in ('sem_syn','word2vec','syn'):valid &= np.isfinite(features[f][:,0,0])
    need(valid.any(),'Nonempty common lexical support')
    x,q=format_words(timing[valid],qid[valid],features['context'][valid,:,0],n)
    t=np.flatnonzero((speaker==1)&(q<99990)&(np.arange(n)>=11)&(np.arange(n)<n))
    need(len(t)>0,'Nonempty prospective support')
    return t,q[t],valid


def purged_split(t,q,fold):
    masks=folds(q);query=masks[fold];train=~query
    # Target centers are t-10, each contains raw bins center-1:center+1.
    # Any training target sharing a raw firing bin with query target is removed.
    query_t=t[query];j=np.searchsorted(query_t,t)
    for delta in (-1,0):
        k=np.clip(j+delta,0,len(query_t)-1);train &= np.abs(t-query_t[k])>2
    need(train.any() and query.any(),'Nonempty purged fold')
    return train,query


def hierarchical(values):
    """Equal biological people, equal their sessions. Undefined propagates."""
    people={}
    for session,value in values.items():people.setdefault(session.split('_')[0],[]).append(value)
    means={k:(float(np.mean(v)) if all(x is not None for x in v) else None) for k,v in people.items()}
    return {'people':means,'mean':float(np.mean(list(means.values()))) if all(x is not None for x in means.values()) else None}
