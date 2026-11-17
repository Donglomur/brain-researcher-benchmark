"""Full-unit, clipped-exposure features and source-only representation state."""
from core import need


def fit_representation(sessions):
    """Only complete training-fold sessions; one anatomical row per unit/session."""
    import numpy as np
    names=['<UNK>','<MISSING>'] + sorted({r for s in sessions for r in s['regions'] if r not in ('<UNK>','<MISSING>')})
    categories=[]
    for k in range(3):
        categories.append(sorted({float(w['context'][k]) for s in sessions for w in s['windows'] if w['context'][k] is not None}))
    locations=np.concatenate([s['locations'] for s in sessions]); missing=np.concatenate([s['location_missing'] for s in sessions])
    mean=np.zeros(3); scale=np.ones(3)
    for j in range(3):
        observed=locations[~missing[:,j],j]
        if len(observed):
            mean[j]=np.mean(observed,dtype=np.float64)
            sd=float(np.std(observed,dtype=np.float64)); scale[j]=sd if sd else 1.0
    return {'regions':names,'categories':categories,'location_mean':mean,'location_scale':scale}


def anatomy_features(locations, missing, regions, names):
    import numpy as np
    need(len(locations) == len(regions) and len(locations)>0, 'full unit anatomy')
    index = {r:i for i,r in enumerate(names)}
    codes = np.array([index.get(r,0) for r in regions], dtype=np.int64)
    n = len(regions)
    counts = np.bincount(codes, minlength=len(names)).astype(np.float64)
    values = [np.log1p(n),*np.log1p(counts)]
    for k in range(len(names)):
        xyz = locations[codes==k]
        values.extend(np.mean(xyz,axis=0) if len(xyz) else np.zeros(3))
        values.extend(np.std(xyz,axis=0) if len(xyz) else np.zeros(3))
        values.extend(np.mean(missing[codes==k],axis=0) if len(xyz) else np.zeros(3))
    return np.asarray(values,dtype=np.float64), codes


def spike_features(window, units):
    import numpy as np
    t=window['spike_times']; u=window['spike_units']; domains=window['neural_domain']
    a,b=window['support']; need(0 <= a < b <= 1.0, 'onset-relative original support')
    edges=np.arange(51,dtype=np.float64)*0.02
    exposure=np.zeros(50,dtype=np.float64)
    for left,right in domains:
        need(right>left, 'positive neural-domain interval')
        exposure += np.maximum(0, np.minimum(np.minimum(edges[1:],b),right)-np.maximum(np.maximum(edges[:-1],a),left))
    need(bool(np.all((exposure>=0)&(exposure<=0.02+1e-12))), 'disjoint clipped exposure')
    need(bool(np.all((t>=a)&(t<b))) and bool(np.all((u>=0)&(u<units))), 'full original spike membership')
    belongs=np.zeros(len(t),dtype=bool)
    for left,right in domains: belongs |= (t>=left)&(t<right)
    need(bool(np.all(belongs)), 'every original event must belong to admitted neural-domain support; no silent discarding')
    bins=np.searchsorted(edges,t,side='right')-1
    need(bool(np.all((bins>=0)&(bins<50))), 'one-second spike bins')
    counts=np.zeros((units,50),dtype=np.float64)
    np.add.at(counts,(u,bins),1)
    available=exposure>0
    need(bool(np.all(counts[:,~available]==0)), 'no event without admitted exposure')
    x=np.zeros_like(counts); x[:,available]=np.log1p(0.02*counts[:,available]/exposure[available])
    return x, exposure, available


def context_features(window, anatomy, categories):
    import numpy as np
    encoded=[]
    for value,known in zip(window['context'],categories,strict=True):
        # MISSING and UNK are distinct, with no vocabulary fitting on a held animal.
        i=0 if value is None else known.index(value)+2 if value in known else 1
        row=np.zeros(len(known)+2); row[i]=1; encoded.append(row)
    c=np.concatenate((*encoded,np.asarray(window['support'],dtype=np.float64),anatomy))
    t=np.asarray(window['times'],dtype=np.float64)
    time=np.column_stack([np.ones(len(t)),t,t*t]+[f(2*np.pi*k*t) for k in range(1,5) for f in (np.sin,np.cos)])
    return c,time


def encode(window, representation, role):
    import numpy as np
    need(role in ('C','J'),'explicit neural/context role')
    names=representation['regions']
    missing=window['location_missing']
    locations=(window['locations']-representation['location_mean'])/representation['location_scale']
    locations=np.where(missing,0.,locations)
    anatomy,codes=anatomy_features(locations,missing,window['regions'],names)
    context,time=context_features(window,anatomy,representation['categories'])
    base=np.column_stack((np.broadcast_to(context,(len(time),len(context))),time))
    result={'context':context,'time':time,'tabular':base,'codes':codes,
            'locations':locations,'unit':None,'exposure':None}
    if role=='J':
        x,e,available=spike_features(window,len(codes))
        # Each anatomical region contributes every bin; empty regions remain
        # explicit zeros. No unit alignment is presumed across source animals.
        pooled=[]
        for r in range(len(names)):
            rows=x[codes==r]; total=rows.sum(axis=0)
            pooled.extend((total,total/len(rows) if len(rows) else total))
        trajectories=np.stack(pooled)
        bin_index=np.floor(window['times']/0.02).astype(int)
        lag=[];lag_available=[]
        for offset in range(-5,6):
            idx=bin_index+offset; valid=(idx>=0)&(idx<50)
            z=np.zeros((len(time),len(trajectories)),dtype=np.float64)
            z[valid]=trajectories[:,idx[valid]].T; lag.append(z)
            mask=np.zeros(len(time),dtype=np.float64);mask[valid]=available[idx[valid]]
            lag_available.append(mask[:,None])
        static=np.concatenate((trajectories.reshape(-1),e/0.02,available.astype(float)))
        result['tabular']=np.column_stack((base,np.broadcast_to(static,(len(time),len(static))),*lag,*lag_available))
        result['unit']=np.column_stack((x,np.broadcast_to(e/0.02,(len(x),50)),
                                       np.broadcast_to(available,(len(x),50)),locations,missing.astype(float)))
        result['exposure']=e
    return result


def weighted_scaler(x,w):
    import numpy as np
    need(x.ndim==2 and w.shape==(len(x),) and bool(np.all(w>0)), 'full positive normalized weights')
    need(abs(float(w.sum())-1.0)<=1e-10, 'source weights sum to one')
    mean=(x*w[:,None]).sum(axis=0,dtype=np.float64)
    variance=((x-mean)**2*w[:,None]).sum(axis=0,dtype=np.float64)
    # Exact structural equality avoids rounding a constant positive column into
    # a tiny nonzero variance; no epsilon reclassifies near-constant columns.
    constant=np.all(x==x[0],axis=0)
    mean[constant]=x[0,constant];variance[constant]=0
    scale=np.sqrt(variance);need(bool(np.all(scale[~constant]>0)), 'nonconstant variance underflow requires explicit failed admission')
    scale[constant]=1
    return {'mean':mean,'scale':scale,'constant':constant}


def standardized(x,state):
    import numpy as np
    z=(x-state['mean'])/state['scale']; z[:,state['constant']]=0
    need(bool(np.isfinite(z).all()), 'finite training-only transformed features')
    return z
