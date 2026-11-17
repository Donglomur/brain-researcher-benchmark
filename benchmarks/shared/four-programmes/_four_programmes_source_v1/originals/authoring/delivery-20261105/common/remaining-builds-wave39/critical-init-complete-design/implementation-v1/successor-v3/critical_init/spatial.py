"""Full-pair Figure4 estimators with explicit edge, tie and denominator policies."""
from .custody import need
from .guard import real
from .numerics import matrix,zscore

def pair_statistics(activity,positions,*,edges,minimum_distance,strong_percent,tie_policy,pair_policy,truth=None):
    import numpy as np
    x=zscore(activity);pos=matrix(positions);n=len(x);need(pos.shape==(n,2),'complete neuron positions')
    e=np.asarray(edges,dtype='float64');need(e.ndim==1 and len(e)>1 and np.isfinite(e).all()and(np.diff(e)>0).all(),'complete increasing source bins')
    real(minimum_distance,0);real(strong_percent,0,100)
    need(tie_policy in ('stable_index','include_boundary')and pair_policy in ('directed','undirected_union','undirected_mutual'),'adjudicated source pair semantics')
    corr=x@x.T/x.shape[1];delta=pos[:,None,:]-pos[None,:,:];dist=np.sqrt((delta*delta).sum(axis=-1))
    valid=(dist>=minimum_distance)&~np.eye(n,dtype=bool);strong=np.zeros((n,n),dtype=bool)
    for i in range(n):
        eligible=np.flatnonzero(valid[i]&(corr[i]>0))
        count=int(np.ceil(len(eligible)*strong_percent/100))
        if count:
            order=np.argsort(-corr[i,eligible],kind='stable');selected=eligible[order[:count]]
            if tie_policy=='include_boundary':selected=eligible[corr[i,eligible]>=corr[i,selected[-1]]]
            strong[i,selected]=True
    if pair_policy!='directed':
        strong=(strong|strong.T)if pair_policy=='undirected_union'else(strong&strong.T)
        valid&=np.triu(np.ones((n,n),dtype=bool),1)
    strong&=valid;other=valid&~strong
    sh=np.histogram(dist[strong],e)[0];oh=np.histogram(dist[other],e)[0]
    ratio=np.full(len(e)-1,np.nan)
    if sh.sum()and oh.sum():
        np.divide(sh/sh.sum(),oh/oh.sum(),out=ratio,where=oh>0)
    mean=[];sd=[];counts=[]
    for lo,hi in zip(e[:-1],e[1:]):
        vals=corr[valid&(dist>=lo)&(dist<hi)]
        mean.append(float(vals.mean())if len(vals)else None);sd.append(float(vals.std())if len(vals)else None);counts.append(len(vals))
    enrichment=None
    if truth is not None:
        tr=np.asarray(truth);need(tr.shape==(n,n)and tr.dtype.kind=='b','complete simulation truth graph')
        chance=float(tr[valid].mean())if valid.any()else 0
        enrichment=float(tr[strong].mean()/chance)if strong.any()and chance else None
    return {'correlation':corr,'distance':dist,'strong':strong,'bin_edges':e,
            'mean':mean,'sd':sd,'counts':counts,'strong_counts':sh,'other_counts':oh,
            'distance_enrichment':[None if not np.isfinite(v)else float(v)for v in ratio],
            'true_edge_enrichment':enrichment,'pair_policy':pair_policy,'tie_policy':tie_policy,
            'tissue_connectivity_identified':False}

def pc_maps(activity,components):
    import numpy as np
    x=zscore(activity);need(type(components)is int and 0<components<=min(x.shape),'complete PC map support')
    u,s,_=np.linalg.svd(x,full_matrices=False)
    return {'loadings':u[:,:components],'variance':s[:components]**2/x.shape[1]}

