"""Concrete working-memory drive, observation and decoding algorithms."""
from .custody import need
from .guard import integer,real
from .numerics import matrix

def embed(features,input_map,*,magnitude):
    f=matrix(features);w=matrix(input_map);real(magnitude)
    need(f.shape[1]==w.shape[1],'all input features accounted for')
    return magnitude*f@w.T

def drive_patterns(patterns,onsets,*,steps,pulse_steps):
    import numpy as np
    p=matrix(patterns);s=np.asarray(onsets);integer(steps,1);integer(pulse_steps,1)
    need(s.ndim==1 and len(s)==len(p)and s.dtype.kind in 'iu'and(s>=0).all(),'complete onset schedule')
    need(np.all(np.diff(s)>=pulse_steps)and int(s[-1])+pulse_steps<=steps,'nonoverlapping full pulses')
    out=np.zeros((steps,p.shape[1]))
    for row,start in zip(p,s):out[start:start+pulse_steps]=row
    return out

def readouts(activity,onsets,delays,*,window_steps):
    import numpy as np
    x=matrix(activity);s=np.asarray(onsets);d=np.asarray(delays);integer(window_steps,1)
    need(s.shape==d.shape and s.ndim==1 and s.dtype.kind in 'iu' and d.dtype.kind in 'iu','explicit fixed or sampled readout schedule')
    begins=s+d;need((begins>=0).all()and(begins+window_steps<=x.shape[1]).all(),'every complete original readout window')
    return np.stack([x[:,k:k+window_steps].mean(axis=1)for k in begins])

def nearest(train,test):
    import numpy as np
    a=matrix(train);b=matrix(test);need(a.shape[1]==b.shape[1],'same representation')
    # Iteration avoids a test×train×feature tensor; ties deterministically first source row.
    out=np.empty(len(b),dtype='int64');distance=np.empty(len(b))
    for i,row in enumerate(b):
        d=((a-row)**2).sum(axis=1);out[i]=int(np.argmin(d));distance[i]=float(d[out[i]])
    return out,distance

def binary(train,test,train_labels,test_labels):
    import numpy as np
    a=matrix(train);b=matrix(test);y=np.asarray(train_labels);z=np.asarray(test_labels)
    need(y.shape==(len(a),)and z.shape==(len(b),)and set(np.unique(y))=={0,1}and set(np.unique(z))=={0,1},'both binary classes present in both splits')
    idx,dist=nearest(a,b);prediction=y[idx]
    return {'prediction':prediction,'accuracy':float(np.mean(prediction==z)),'nearest_distance':dist,'n_train':len(a),'n_test':len(b)}

def zero_shot(train,test,train_features,test_targets,*,ridge):
    import numpy as np
    a=matrix(train);b=matrix(test);f=matrix(train_features);g=matrix(test_targets);real(ridge,0)
    need(len(a)==len(f) and len(b)==len(g) and a.shape[1]==b.shape[1]and f.shape[1]==g.shape[1],'full aligned distinct train/test patterns')
    # Dual solve is mathematically equivalent and avoids a 10000² readout matrix.
    coef=a.T@np.linalg.solve(a@a.T+ridge*np.eye(len(a)),f)
    decoded=b@coef;idx,dist=nearest(g,decoded)
    return {'decoded_features':decoded,'retrieved_pattern':idx,'accuracy':float(np.mean(idx==np.arange(len(g)))),
            'nearest_distance':dist,'feature_mse':float(np.mean((decoded-g)**2)),'ridge':ridge}

def subspace_map(spontaneous,components):
    import numpy as np
    x=matrix(spontaneous);integer(components,1,min(x.shape))
    u,_,_=np.linalg.svd(x-x.mean(axis=1,keepdims=True),full_matrices=False)
    return u[:,:components]

