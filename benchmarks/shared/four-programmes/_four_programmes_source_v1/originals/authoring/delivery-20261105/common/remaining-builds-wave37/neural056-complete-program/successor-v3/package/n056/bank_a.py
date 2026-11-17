"""NumPy numerical path. No import or invocation occurs in source-only inspection."""
def ridge_fit(x,y,alpha=1.0):
    import numpy as np
    from .core import need
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    need(x.ndim==y.ndim==2 and len(x)==len(y)>1 and x.shape[1]>0 and y.shape[1]>0,'ridge matrix shapes')
    need(np.isfinite(x).all() and np.isfinite(y).all() and type(alpha)in(int,float) and np.isfinite(alpha) and alpha>0,'finite positive ridge')
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        mu=x.mean(0);sd=x.std(0);sd[sd==0]=1;ym=y.mean(0);z=(x-mu)/sd
        coef=np.linalg.solve(z.T@z+alpha*np.eye(x.shape[1]),z.T@(y-ym))
    need(all(np.isfinite(v).all() for v in (mu,sd,ym,coef)),'finite fitted ridge')
    return {'mean_x':mu,'scale_x':sd,'mean_y':ym,'coef':coef}
def ridge_predict(model,q):
    import numpy as np
    from .core import need
    q=np.asarray(q,dtype=np.float64)
    need(q.ndim==2 and q.shape[1]==len(model['mean_x']) and np.isfinite(q).all(),'query support')
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        y=(q-model['mean_x'])/model['scale_x']@model['coef']+model['mean_y']
    need(np.isfinite(y).all(),'finite ridge predictions');return y
def correlation(y,p):
    import numpy as np
    from .core import need
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    need(y.shape==p.shape and y.ndim==2 and len(y)>1 and np.isfinite(y).all() and np.isfinite(p).all(),'finite complete correlation support')
    ys=np.max(np.abs(y),axis=0);ps=np.max(np.abs(p),axis=0);ys[ys==0]=1;ps[ps==0]=1
    a=y/ys;b=p/ps;a-=a.mean(0);b-=b.mean(0)
    sy=np.sum(a*a,axis=0);sp=np.sum(b*b,axis=0);valid=sy>0;vary=sp>0;r=np.zeros(y.shape[1])
    both=valid&vary;r[both]=np.sum(a*b,axis=0)[both]/np.sqrt(sy[both]*sp[both]);r=np.clip(r,-1,1)
    need(np.isfinite(r).all(),'representable correlations')
    return {'raw':[float(v) if valid[i] and vary[i] else None for i,v in enumerate(r)],
            'score':[float(v) if valid[i] else None for i,v in enumerate(r)],
            'constant_target':int((~valid).sum()),'constant_prediction':int((~vary).sum()),
            'mean':float(r.mean()) if valid.all() else None}
def macro(values):
    from .core import need
    need(len(values)>0,'full nonempty support')
    return None if any(v is None for v in values) else sum(values)/len(values)

