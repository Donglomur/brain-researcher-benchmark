"""Independent algebraic translations of newly recovered source, not RNG/backend parity.

Functions consume explicit variates/indices. The authoritative original .py
bodies remain unmodified in native_recovered. Published-method and corrected
scientific alternatives use different named kernels.
"""
from .custody import need
from .guard import integer,real
from .numerics import matrix,zscore
from .memory import nearest

def dense_from_variates(variates,*,distribution,nonsym,max_real):
    import numpy as np
    a=matrix(variates).copy();need(a.shape[0]==a.shape[1],'square independent base variates')
    real(nonsym,0,1);real(max_real,0,1);need(max_real<1,'strict stationary target')
    if distribution=='uniform':
        need((a>=0).all()and(a<1).all(),'uniform[0,1) variates');a=2*a-1
    elif distribution=='binary':a=np.where(a>0,1.,-1.)
    elif distribution=='gaussian':pass
    elif distribution=='trunc_gaussian':a=np.abs(a);a-=a.mean()
    elif distribution=='exponential':
        need((a>=0).all()and(a<1).all(),'uniform[0,1) variates');a=-np.log1p(-a)-1
    else:raise ValueError('recovered source distribution')
    if nonsym==0:a=np.tril(a,-1);a=a+a.T
    elif nonsym!=1:
        upper=np.triu(a);lower=np.tril(a);a=upper+(1-nonsym)*upper.T+nonsym*lower
    np.fill_diagonal(a,0);sd=a.std(ddof=1);need(sd>0,'source corrected sample SD')
    a/=len(a)**.5*sd;a/=2 if nonsym==0 else 1
    eigen=np.linalg.eigvals(a);edge=eigen.real.max();need(edge>0,'positive source maximum real part')
    a/=edge/max_real
    return {'connectivity':a,'eigenvalues':np.linalg.eigvals(a),'native_RNG_parity':False}

def structured_from_variates(uniform,probability,inhibitory_probability,*,maximum_eigenvalue,pre_scale):
    import numpy as np
    u=matrix(uniform);p=matrix(probability);q=matrix(inhibitory_probability)
    need(u.shape==p.shape==q.shape and len(u)==u.shape[1],'complete structured arrays')
    need((u>=0).all()and(u<1).all()and(p>=0).all()and(p<=1).all(),'valid explicit Bernoulli sampling')
    real(maximum_eigenvalue,0,1);need(maximum_eigenvalue<1,'strict source stability');real(pre_scale,0);need(pre_scale>0,'positive source preliminary scale')
    a=(u<p).astype('float64')-q;a=np.tril(a,-1);a=.5*(a+a.T)/pre_scale
    e,v=np.linalg.eigh(a);edge=e.max();need(edge>0,'positive structured source edge')
    a/=edge/maximum_eigenvalue;e/=edge/maximum_eigenvalue
    cov_e=.5/(1-e);cov=(v*cov_e)@v.T
    return {'connectivity':a,'connectivity_eigenvalues':e[::-1],'covariance':cov,
            'covariance_eigenvalues':cov_e[::-1],'eigenvectors':v[:,::-1]}

def local_probability(positions,*,sig,isig,plocal,pglobal,distance_variant):
    import numpy as np
    pos=matrix(positions);need(pos.shape[1]==2,'full 2D positions')
    real(sig,0);real(isig,0);real(plocal,0);real(pglobal,0,1);need(sig>0 and isig>0,'positive length scales')
    d=np.abs(pos[:,None,:]-pos[None,:,:])
    if distance_variant=='literal_unit_period_on_8000um':d=np.minimum(d,1-d)
    elif distance_variant=='corrected_8000um_torus':d=np.minimum(d,8000-d)
    else:raise ValueError('explicit original versus corrected distance')
    distance=np.sqrt((d*d).sum(axis=-1));p=plocal*np.exp(-distance/sig)/sig
    q=plocal*np.exp(-distance/(isig*sig))/(isig*sig);q/=q.mean()/p.mean()
    p=np.maximum(p,pglobal);q=np.maximum(q,pglobal);np.fill_diagonal(p,0);np.fill_diagonal(q,0)
    return {'probability':p,'inhibitory_probability':q,'distance_variant':distance_variant}

def strong_pairs_literal(covariance,positions,*,pstrong,bin_size,nbins,dist_min,sort_kind):
    import numpy as np
    c=matrix(covariance);pos=matrix(positions);n=len(c)
    need(c.shape==(n,n)and pos.shape==(n,2),'complete source pair geometry');real(pstrong,0,1)
    integer(nbins,1);real(bin_size,0);need(bin_size>0,'positive bins');real(dist_min,0)
    need(sort_kind in ('quicksort','stable'),'explicit NumPy source/backend tie convention')
    d=np.sqrt(((pos[:,None,:]-pos[None,:,:])**2).sum(axis=-1));valid=d>dist_min
    filtered=c.copy();filtered[~valid]=-np.inf
    order=np.argsort(filtered,axis=1,kind=sort_kind)[:,::-1];nstrong=int(np.round(pstrong*n))
    need(0<nstrong<n,'nonempty literal strong and other classes')
    bins=np.floor(d/bin_size).astype('int64');bins[~valid]=-1
    sortedbins=np.take_along_axis(bins,order,axis=1)
    sh=np.stack([(sortedbins[:,:nstrong]==j).sum(axis=1)for j in range(nbins)],axis=1)
    oh=np.stack([(sortedbins[:,nstrong:]==j).sum(axis=1)for j in range(nbins)],axis=1)
    raw_sh=sh.copy();raw_oh=oh.copy();sh=sh.astype('uint16');oh=oh.astype('uint16')
    covbin=[];empty=[]
    for i in range(n):
        row=[]
        for j in range(nbins):
            values=c[i,bins[i]==j];row.append(float(values.mean())if len(values)else None)
            if not len(values):empty.append([i,j])
        covbin.append(row)
    denominator=oh.mean(axis=0)/(n-nstrong);numerator=sh.mean(axis=0)/nstrong
    ratio=[float(a/b)if b else None for a,b in zip(numerator,denominator)]
    return {'strong_counts':sh,'other_counts':oh,'covariance_per_neuron_bin':covbin,'empty_bins':empty,
            'distance_enrichment':ratio,'nstrong':nstrong,'nother':n-nstrong,
            'count_overflow_cells':int((raw_sh>65535).sum()+(raw_oh>65535).sum()),
            'positive_only_filter':False,'strict_distance_threshold':dist_min}

def centroid_decode(readouts,labels,permutation,*,folds):
    import numpy as np
    x=zscore(matrix(readouts),1e-3);y=np.asarray(labels);perm=np.asarray(permutation);integer(folds,2)
    need(y.shape==perm.shape==(len(x),)and y.dtype.kind in 'iu'and set(perm)==set(range(len(x))),'complete labels and original fold permutation')
    classes=np.arange(int(y.max())+1);correct=np.empty(len(x),dtype=bool);pred=np.empty(len(x),dtype='int64')
    for k in range(folds):
        test=perm%folds==k;train=~test
        need(test.any()and train.any(),'nonempty original folds')
        membership=y[train,None]==classes[None,:]
        centroids=(x[train].T@membership)/(1e-4+membership.sum(axis=0))
        prediction,_=nearest(centroids.T,x[test]);pred[test]=prediction;correct[test]=prediction==y[test]
    return {'prediction':pred,'correct':correct,'accuracy':float(correct.mean()),'decoder':'source normalized class centroid; not 1NN'}

def ridge_retrieval(readouts,embedded_inputs,permutation,*,folds,ridge):
    import numpy as np
    x=zscore(matrix(readouts),1e-3);y=zscore(matrix(embedded_inputs),1e-3);p=np.asarray(permutation)
    integer(folds,2);real(ridge,0);need(x.shape==y.shape and p.shape==(len(x),)and set(p)==set(range(len(x))),'complete original embedded targets and folds')
    correct=np.empty(len(x),dtype=bool);prediction=np.empty(len(x),dtype='int64')
    for k in range(folds):
        te=p%folds==k;tr=~te;n=int(tr.sum());need(n>0 and te.any(),'nonempty original splits')
        coef=x[tr].T@np.linalg.solve(x[tr]@x[tr].T+ridge*n*np.eye(n),y[tr])
        decoded=x[te]@coef;idx,_=nearest(y[te],decoded)
        prediction[te]=np.flatnonzero(te)[idx];correct[te]=idx==np.arange(te.sum())
    return {'prediction_global_index':prediction,'correct':correct,'accuracy':float(correct.mean()),
            'ridge_normalization':'Gxx/n + lambda I','target':'embedded N-dimensional source input'}

def mutate_time_prefix(readouts,permutations):
    import numpy as np
    out=np.asarray(readouts,dtype='float64').copy()
    need(out.ndim==4 and np.isfinite(out).all(),'delay × stimulus × neuron × parallel trace')
    need(len(permutations)==len(out),'one source mutation schedule per output delay')
    snapshots=[]
    for j in range(len(out)):
        if j:
            schedule=np.asarray(permutations[j]);need(schedule.shape==(out.shape[1],out.shape[3],j),'all per-stimulus/trace permutations of preceding delays')
            for stimulus in range(out.shape[1]):
                for trial in range(out.shape[3]):
                    order=schedule[stimulus,trial];need(set(order)==set(range(j)),'source without replacement prefix permutation')
                    out[:j,stimulus,:,trial]=out[order,stimulus,:,trial]
        snapshots.append(out[0].copy())
    return {'decoded_snapshots':np.stack(snapshots),'final_mutated_readouts':out,
            'semantics':'literal cumulative prefix mutation, excludes current maximum delay'}

