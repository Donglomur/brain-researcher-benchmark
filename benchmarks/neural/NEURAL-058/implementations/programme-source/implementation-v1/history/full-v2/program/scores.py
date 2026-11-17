"""Exact animal-centered endpoints; no target I/O or numerical imports at load."""
from core import need


def animal_score(sessions):
    """Rows are complete sessions of one animal, each a list of full windows."""
    import numpy as np
    need(sessions and all(s for s in sessions), 'no empty required animal/session')
    mu=np.zeros(2,dtype=np.float64); records=[]; first=None;constant=np.ones(2,dtype=bool)
    for session in sessions:
        for y,pred in session:
            need(y.ndim==2 and y.shape[1]==2 and len(y)>0 and pred.shape==y.shape,
                 'both complete heads and all original positions')
            need(bool(np.isfinite(y).all() and np.isfinite(pred).all()), 'finite complete target/prediction')
            if first is None: first=y[0].copy()
            constant &= np.all(y==first,axis=0)
            w=1.0/(len(sessions)*len(session)*len(y))
            mu += w*y.sum(axis=0,dtype=np.float64); records.append((y,pred,w))
    mu[constant]=first[constant]
    sse=np.zeros(2,dtype=np.float64); sst=sse.copy();mae=sse.copy()
    for y,p,w in records:
        sse += w*((y-p)**2).sum(axis=0,dtype=np.float64)
        sst += w*((y-mu)**2).sum(axis=0,dtype=np.float64)
        mae += w*np.abs(y-p).sum(axis=0,dtype=np.float64)
    sst[constant]=0
    need(bool(np.all(sst[~constant]>0)), 'nonconstant denominator underflow requires explicit failed admission')
    need(bool(np.isfinite(sse).all() and np.isfinite(sst).all() and np.isfinite(mae).all()),'finite canonical diagnostic arithmetic')
    return {'mean':mu.tolist(),'sse':sse.tolist(),'sst':sst.tolist(),'mse':sse.tolist(),'mae':mae.tolist(),
            'support':{'sessions':len(sessions),'windows':sum(len(s) for s in sessions),
                       'timestamps':sum(len(y) for s in sessions for y,_ in s),
                       'per_session':[{'windows':len(s),'timestamps':sum(len(y) for y,_ in s)} for s in sessions]},
            'weight_rule':'1/(animal sessions * session windows * window timestamps); normalized mass1',
            'undefined_reason':['exact constant target' if d==0 else None for d in sst],
            'r2':[None if d==0 else float(1-n/d) for n,d in zip(sse,sst)]}


def macro(animals, expected):
    import numpy as np
    need(set(animals)==set(expected), 'all required animals; no surviving-case scoring')
    result=[]
    for h in range(2):
        values=[animals[a]['r2'][h] for a in expected]
        result.append(None if any(v is None for v in values) else float(np.mean(values,dtype=np.float64)))
    return {'velocity':result[0],'speed':result[1],'animals':animals,
            'zero_variance_disposition':'endpoint aggregate undefined; animal retained', 'negative_r2_clipped':False}


def paired_contrast(left,right,expected):
    """Each animal has three realized paired policy scores, not three animals."""
    import numpy as np
    need(set(left)==set(right)==set(expected), 'complete paired animal contrast')
    if any(any(v is None for v in left[a]+right[a]) for a in expected):
        return {'estimate':None,'interval':None,'reason':'undefined required animal endpoint'}
    need(all(len(left[a])==len(right[a])==3 for a in expected),'all three realizations')
    delta=np.array([np.mean(np.array(left[a])-np.array(right[a])) for a in expected],dtype=np.float64)
    rng=np.random.Generator(np.random.PCG64(580058)); samples=np.empty(10000,dtype=np.float64)
    for i in range(10000): samples[i]=np.mean(delta[rng.integers(0,len(delta),size=len(delta))])
    return {'estimate':float(np.mean(delta)), 'interval':np.quantile(samples,[.025,.975],method='linear').tolist(),
            'animal_deltas':delta.tolist(),'replicates':10000,'seed':580058,
            'interpretation':'descriptive conditional on fitted references and realized policies; no population/causal/SOTA claim'}
