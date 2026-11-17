"""Prospective competent-reference candidates, never qualified by construction.

No fitting, scipy/numpy import or scoring occurs at import. All estimators use
training patients only; nested validation is equal patient weighted. These are
N041 decoder baselines, not a claim to reproduce the paper's PAC estimators.
"""
from core import need
from schema import REFERENCES

BANDS=((2,4),(4,8),(8,13),(13,30),(30,55),(70,110),(130,170))
C_GRID=(.01,.1,1.,10.,100.)

def summarize(v):
    import numpy as np
    if len(v)==0:return [float('nan'),float('nan')]
    return [float(np.median(v)),float(np.quantile(v,.75)-np.quantile(v,.25))]

def features(epoch,regions,method):
    import numpy as np
    from scipy.signal import welch
    need(method in REFERENCES,'fixed reference family')
    if method=='prior':return np.zeros(1)
    x=epoch['lfp'];lr=epoch['lfp_region'];ur=epoch['unit_region'];offsets=epoch['spike_offsets']
    rate=np.diff(offsets)/2.5
    # Availability is intentionally exposed as a diagnostic comparator, not a
    # neural success claim; it catches clinical/missing-modality confounding.
    available=[];powers=[];rates=[]
    if method in('power_only','combined') and len(x):
        f,psd=welch(x,fs=400.,window='hann',nperseg=400,noverlap=200,nfft=400,detrend='constant',scaling='density',axis=1)
        bp=np.stack([np.sum(psd[:,(f>=a)&(f<b)],axis=1)*(f[1]-f[0]) for a,b in BANDS],axis=1)
    else:bp=np.empty((0,len(BANDS)))
    for r in range(len(regions)):
        available.extend([int((lr==r).sum()),int((ur==r).sum())])
        rates.extend(summarize(np.log1p(rate[ur==r])))
        for j in range(len(BANDS)) if method in('power_only','combined') else ():
            # 1e-30 V² is a specified numerical floor, not an observed noise
            # threshold. Its sensitivity and units require independent checks.
            powers.extend(summarize(np.log(np.maximum(bp[lr==r,j],1e-30))))
    selected=available if method=='availability_only' else rates if method=='rate_only' else powers if method=='power_only' else powers+rates
    return np.asarray(selected,dtype=float)

def patient_weights(groups):
    import numpy as np
    groups=np.asarray(groups);unique=np.unique(groups)
    return np.asarray([len(groups)/(len(unique)*int((groups==x).sum())) for x in groups])

class Transform:
    def fit(self,x):
        import numpy as np
        need(x.ndim==2 and len(x),'training feature matrix')
        self.median=np.asarray([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0. for c in x.T])
        filled=np.where(np.isfinite(x),x,self.median)
        self.center=np.median(filled,axis=0);self.scale=np.quantile(filled,.75,axis=0)-np.quantile(filled,.25,axis=0)
        self.scale=np.where(self.scale>0,self.scale,1.)
        return self
    def apply(self,x):
        import numpy as np
        # Structural unavailability remains explicit. No held-patient median,
        # normalization, feature selection or calibration is fitted.
        missing=~np.isfinite(x);filled=np.where(missing,self.median,x)
        return np.c_[(filled-self.center)/self.scale,missing.astype(float)]

def fit_model(x,y,groups,c):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    need(set(np.asarray(y).tolist())=={0,1},'both classes required in training, no silent fold deletion')
    transform=Transform().fit(x)
    # lbfgs is deterministic for this fixed initial state and has no shuffled
    # optimization. Nonconvergence is a failed reference, not a scored model.
    model=LogisticRegression(C=c,solver='lbfgs',max_iter=2000,tol=1e-7)
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        model.fit(transform.apply(x),y,sample_weight=patient_weights(groups))
    return transform,model

def log_loss(y,p):
    import numpy as np
    # The same fixed clipping convention is used in protected final scoring.
    q=np.clip(p,1e-15,1-1e-15)
    return float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q)))

def fit_state(train,method):
    import numpy as np
    x=np.stack([r['features'] for r in train]);y=np.asarray([r['target'] for r in train]);groups=np.asarray([r['group'] for r in train])
    patients=np.unique(groups)
    need(len(patients)>=2,'nested whole-patient validation')
    if method=='prior':
        p=float(np.average(y,weights=patient_weights(groups)))
        return {'method':method,'prior':p},{'method':method,'training_patients':len(patients)}
    candidates=[]
    for c in C_GRID:
        losses=[]
        for held in patients:
            fit=groups!=held;val=~fit
            transform,model=fit_model(x[fit],y[fit],groups[fit],c)
            p=model.predict_proba(transform.apply(x[val]))[:,1]
            losses.append(log_loss(y[val],p))
        candidates.append((float(np.mean(losses)),c))
    _,chosen=min(candidates)
    transform,model=fit_model(x,y,groups,chosen)
    return {'method':method,'transform':transform,'model':model},{'method':method,'chosen_C':chosen,'inner_patient_log_loss':candidates,'train_only_transform':True}

def predict_state(state,query):
    import numpy as np
    if state['method']=='prior':return np.full(len(query),state['prior'])
    q=np.stack([r['features'] for r in query])
    return state['model'].predict_proba(state['transform'].apply(q))[:,1]

def run(view,reader,method):
    train=[];query=[]
    for role,out in(('training',train),('query',query)):
        for row in view[role]:out.append(dict(row,features=features(reader(row),view['regions'],method)))
    state,report=fit_state(train,method);p=predict_state(state,query)
    return {'schema':'n041_predictions_v1','probabilities':[{'id':r['id'],'p_high':float(v)} for r,v in zip(query,p)]},report
