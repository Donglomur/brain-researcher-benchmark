"""Independent prospective weighted multilabel logistic reference and train-only calibration.

All native imports are inside scientific functions. This module is statically reviewed,
not fitted or numerically exercised by source-construction controls.
"""
from .domain import need,CATEGORIES

LAMBDAS=(.01,.1,1.)

def weights(people,concepts):
    import numpy as np
    from collections import Counter
    need(len(people)==len(concepts)>0,'complete training grouping')
    ps=sorted(set(people));cs={p:set(c for q,c in zip(people,concepts) if q==p) for p in ps};n=Counter(zip(people,concepts))
    return np.array([1/(len(ps)*len(cs[p])*n[p,c]) for p,c in zip(people,concepts)],dtype=float)

def train(x,y,w,lam):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit
    need(x.ndim==2 and y.shape==(len(x),CATEGORIES) and w.shape==(len(x),),'complete matrix support')
    need(np.isfinite(x).all() and np.isin(y,[0,1]).all() and np.isfinite(w).all() and (w>0).all(),'finite typed scientific input')
    need(lam in LAMBDAS,'fixed regularization grid')
    center=np.sum(w[:,None]*x,axis=0)/w.sum();scale=np.sqrt(np.sum(w[:,None]*(x-center)**2,axis=0)/w.sum());scale[scale==0]=1
    z=(x-center)/scale;coef=np.zeros((x.shape[1]+1,CATEGORIES));constant=np.zeros(CATEGORIES,dtype=bool)
    # Weights sum to one; all 53 label losses remain in selection. No class dropping.
    wn=w/w.sum()
    for k in range(CATEGORIES):
        yy=y[:,k]
        if len(np.unique(yy))==1:
            # Smoothing uses distinct training concepts, not person/repeat pseudocounts;
            # n_effective is passed as the number of concept units through weights.
            constant[k]=True
            continue
        def objective(theta):
            score=z@theta[:-1]+theta[-1]
            loss=np.dot(wn,np.logaddexp(0,score)-yy*score)+lam*.5*np.dot(theta[:-1],theta[:-1])
            residual=wn*(expit(score)-yy)
            return loss,np.r_[z.T@residual+lam*theta[:-1],residual.sum()]
        result=minimize(objective,np.zeros(x.shape[1]+1),jac=True,method='L-BFGS-B',options={'maxiter':2000,'ftol':1e-12,'gtol':1e-7,'maxls':40})
        need(result.success and np.isfinite(result.x).all(),'reference optimizer converged; no failed-fit substitution')
        coef[:,k]=result.x
    return {'center':center,'scale':scale,'coef':coef,'constant':constant,'lambda':lam}

def logits(state,x):
    import numpy as np
    need(np.isfinite(x).all() and x.shape[1]==len(state['center']),'same feature dimension and finite values')
    return ((x-state['center'])/state['scale'])@state['coef'][:-1]+state['coef'][-1]

def set_constant_priors(state,y,concepts):
    import numpy as np
    unique=sorted(set(concepts));rows=[concepts.index(c) for c in unique]
    yy=y[rows];p=(yy.sum(axis=0)+.5)/(len(unique)+1)
    state['prior']=p
    state['coef'][-1,state['constant']]=np.log(p[state['constant']]/(1-p[state['constant']]))

def logloss(logit,y,w):
    import numpy as np
    return float(np.dot(w/w.sum(),np.mean(np.logaddexp(0,logit)-y*logit,axis=1)))

def calibrate(state,x,y,w):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit
    z=logits(state,x);a=np.ones(CATEGORIES);b=np.zeros(CATEGORIES);wn=w/w.sum()
    for k in range(CATEGORIES):
        # A missing calibration class preserves the fitted training predictor.
        if state['constant'][k] or len(np.unique(y[:,k]))<2:continue
        def objective(theta):
            v=z[:,k]*theta[0]+theta[1];r=wn*(expit(v)-y[:,k]);d=theta-np.array([1.,0.])
            return np.dot(wn,np.logaddexp(0,v)-y[:,k]*v)+.5*np.dot(d,d),np.array([np.dot(r,z[:,k]),r.sum()])+d
        fit=minimize(objective,np.array([1.,0.]),jac=True,method='L-BFGS-B',bounds=[(0.,10.),(-10.,10.)],options={'maxiter':1000,'ftol':1e-12,'gtol':1e-7})
        need(fit.success and np.isfinite(fit.x).all(),'calibration optimizer converged')
        a[k],b[k]=fit.x
    state['cal_a']=a;state['cal_b']=b
    return state

def fit_reference(x,y,people,concepts,roles,groups,mode):
    import numpy as np
    need(mode in ('F','I'),'precommitted F/I reference')
    def take(ps,cs): return np.array([i for i,(p,c) in enumerate(zip(people,concepts)) if p in ps and c in cs],dtype=int)
    inner=take(roles['inner_train'],groups['fit']);tune=take((roles['inner_tune'],),groups['tune']);cal=take(roles['final_train'],groups['calibrate'])
    final=take(roles['final_train'],groups['fit']+groups['tune'])
    need(all(len(v)>0 for v in (inner,tune,cal,final)),'nonempty shared fixed training/tuning/calibration supports')
    def fit(ids,lam):
        cs=[concepts[i] for i in ids];s=train(x[ids],y[ids],weights([people[i] for i in ids],cs),lam);set_constant_priors(s,y[ids],cs);return s
    attempts=[];lam=1.
    if mode=='I':
        for candidate in LAMBDAS:
            state=fit(inner,candidate)
            loss=logloss(logits(state,x[tune]),y[tune],weights([people[i] for i in tune],[concepts[i] for i in tune]))
            attempts.append({'lambda':candidate,'loss':loss})
        lam=min(attempts,key=lambda r:(r['loss'],r['lambda']))['lambda']
    state=fit(final,lam)
    calibrate(state,x[cal],y[cal],weights([people[i] for i in cal],[concepts[i] for i in cal]))
    return state,{'mode':mode,'attempts':attempts,'selected_lambda':lam,'inner_rows':len(inner),'tune_rows':len(tune),'calibration_rows':len(cal),'final_fit_rows':len(final),'outer_person_used':False,'query_used':False}

def predict(state,x):
    from scipy.special import expit
    return expit(logits(state,x)*state['cal_a']+state['cal_b'])

def save_state(path,state):
    import numpy as np
    # Only arrays/scalars; never pickle or arbitrary estimator objects.
    np.savez(path,**state)

def load_state(path):
    import numpy as np
    with np.load(path,allow_pickle=False) as z:
        need(set(z.files)=={'center','scale','coef','constant','lambda','prior','cal_a','cal_b'},'complete fixed reference state')
        s={k:z[k].copy() for k in z.files}
    d=len(s['center']);need(s['center'].shape==s['scale'].shape==(d,) and s['coef'].shape==(d+1,CATEGORIES),'fixed state dimensions')
    need(all(s[k].shape==(CATEGORIES,) for k in ('constant','prior','cal_a','cal_b')),'53 label state entries')
    need(s['constant'].dtype.kind=='b' and (s['scale']>0).all() and all(np.isfinite(v).all() for v in s.values()),'finite safe state')
    return s
