"""Concrete independent pooled-feature references, source only until qualified.

No pickle/state callbacks. Model objects stay within the trusted reference child;
outputs are arrays plus exact selected fit lineage and original cost receipts.
"""
from .contracts import need, CLASSES

CONFIGS = (('linear', .01), ('linear', .1), ('linear', 1.), ('linear', 10.),
           ('trees', 5), ('trees', 20))

def fit(x, y, weights, head, config, seed):
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge, LogisticRegression, PoissonRegressor
    from sklearn.ensemble import ExtraTreesRegressor, ExtraTreesClassifier
    need(config in CONFIGS and x.ndim==2 and len(x)==len(y)==len(weights)>0, 'complete reference training axis')
    need(np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(weights).all() and np.all(weights>0), 'finite source training only')
    weights=np.asarray(weights,dtype=float);weights=weights/weights.sum()
    scaler=StandardScaler().fit(x,sample_weight=weights);z=scaler.transform(x)
    if head in CLASSES:
        need(set(y.tolist())==set(range(CLASSES[head])), 'all prespecified classes in source training')
    family,value=config
    if family=='trees':
        cls=ExtraTreesClassifier if head in CLASSES else ExtraTreesRegressor
        model=cls(n_estimators=512,min_samples_leaf=value,max_features=1.0,n_jobs=1,random_state=seed)
    elif head in CLASSES:
        model=LogisticRegression(C=1./value,max_iter=2000,tol=1e-8,solver='lbfgs',random_state=seed)
    elif head=='licking_rate':
        need(np.all(y>=0) and np.all(y==np.floor(y)), 'original lick-count target')
        model=PoissonRegressor(alpha=value,max_iter=2000,tol=1e-8)
    else:model=Ridge(alpha=value,solver='svd')
    # Scale sample weights to mean1, fixing the regularization convention.
    model.fit(z,y,sample_weight=weights*len(weights))
    if hasattr(model,'n_iter_'):need(np.max(model.n_iter_)<2000,'reference convergence required')
    return (scaler,model,head,config)

def predict(state,x):
    import numpy as np
    scaler,model,head,_=state;z=scaler.transform(x)
    out=model.predict_proba(z) if head in CLASSES else model.predict(z)
    need(np.isfinite(out).all(),'finite reference output')
    if head=='licking_rate':out=np.maximum(out,1e-12)
    return out

def loss(y,p,head):
    import numpy as np
    y=np.asarray(y);p=np.asarray(p)
    if head in CLASSES:
        need(p.shape==(len(y),CLASSES[head]) and np.all((p>=0)&(p<=1)) and np.allclose(p.sum(axis=1),1,rtol=0,atol=1e-8),'class probability simplex')
        need(y.dtype.kind in 'iu' and np.all((y>=0)&(y<CLASSES[head])),'original classes')
        return -np.log(np.clip(p[np.arange(len(y)),y],1e-12,1))
    need(p.shape==y.shape and np.isfinite(p).all(),'exact finite regression support')
    if head=='licking_rate':
        need(np.all(p>=0) and np.all(y>=0),'nonnegative predicted and observed counts')
        return np.maximum(p,1e-12)-y*np.log(np.maximum(p,1e-12))
    return (y-p)**2

def reference_select(folds,head,seed,tick):
    """folds carry full animal-disjoint source datasets, never evaluation targets."""
    import numpy as np
    need(len(folds)==5,'all five original source-animal folds')
    results=[]
    for config in CONFIGS:
        scores=[]
        for fold in folds:
            tick();train,val=fold
            need(not set(train['animals'])&set(val['animals']),'whole-animal source split')
            state=fit(train['x'],train['y'],train['weights'],head,config,seed)
            values=loss(val['y'],predict(state,val['x']),head)
            scores.append(float(np.sum(values*val['weights'])/np.sum(val['weights'])))
            tick()
        counts=[len(val['animals']) for _,val in folds]
        results.append({'config':config,'fold_losses':scores,'validation_animal_counts':counts,
                        'mean_loss':sum(v*n for v,n in zip(scores,counts,strict=True))/sum(counts)})
    winner=min(range(len(CONFIGS)),key=lambda i:(results[i]['mean_loss'],i))
    return CONFIGS[winner],results
