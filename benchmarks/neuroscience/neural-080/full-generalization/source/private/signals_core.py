"""Deterministic source-data projections; no model or scientific contrast."""
import numpy as np


def need(ok,msg):
    if not ok:raise ValueError(msg)


def eeg_bins(x):
    x=np.asarray(x,dtype=np.float64)
    need(x.ndim==3 and x.shape[1:]==(127,1800) and np.isfinite(x).all(),'Finite released trial×127×1800 EEG')
    bins=x[:,:,50:1550].reshape(len(x),127,150,10);anchor=bins[:,:,:,0]
    return anchor+(bins-anchor[:,:,:,None]).mean(axis=-1)


def training_stats(chunks):
    n=0;mean=np.zeros((127,150));m2=np.zeros_like(mean);anchor=None;minimum=None;maximum=None
    for values in chunks:
        x=np.asarray(values,float);need(x.ndim==3 and x.shape[1:]==(127,150) and np.isfinite(x).all(),'Finite joined FIT EEG')
        k=len(x)
        if not k:continue
        if anchor is None:anchor=x[0].copy();minimum=x.min(0);maximum=x.max(0)
        else:minimum=np.minimum(minimum,x.min(0));maximum=np.maximum(maximum,x.max(0))
        # Center at an observed binary64 value first, avoiding false variance
        # from summing an exactly constant nonbinary decimal such as0.1.
        x=x-anchor;need(np.isfinite(x).all(),'Finite anchored training deviations')
        mu=x.mean(0);varsum=((x-mu)**2).sum(0);d=mu-mean;total=n+k
        m2+=varsum+d*d*n*k/total;mean+=d*k/total;n=total
    need(n>=2,'At least two joined FIT trials per session')
    sd=np.sqrt(m2/n)
    need(np.isfinite(mean).all() and np.isfinite(sd).all() and (sd>0).all() and (minimum!=maximum).all(),
         'Every127×150 training-only target scale must be defined; no dropped coordinate')
    return anchor,mean,sd,n


def eye_bins(x):
    """3means+3absolute-derivative means+observed fraction+pair fraction.

    Means use available native samples inside each20ms bin. A bin without
    support uses zero plus its explicit zero availability. No interpolation.
    Derivative pairs are adjacent native samples WITHIN a bin; no edge wrap.
    """
    x=np.asarray(x,dtype=np.float64)
    need(x.ndim==3 and x.shape[1:]==(3,1800) and not np.isinf(x).any(),'Source trial×3×1800 eye array, finite or NaN')
    valid=np.isfinite(x)
    need(np.array_equal(valid[:,0],valid[:,1]) and np.array_equal(valid[:,0],valid[:,2]),'Released co-missing gaze/pupil sample mask')
    a=x[:,:,50:1550].reshape(len(x),3,150,10);good=np.isfinite(a);n=good.sum(-1)
    filled=np.where(good,a,0.)
    anchor=np.take_along_axis(filled,np.argmax(good,axis=-1)[...,None],axis=-1)[...,0]
    means=anchor+np.where(good,filled-anchor[...,None],0.).sum(-1)/np.maximum(n,1)
    pairs=good[:,:,:,:-1]&good[:,:,:,1:]
    # Differences are formed only on observed values, not NaN-filled signals.
    previous=np.where(pairs,a[:,:,:,:-1],0.);current=np.where(pairs,a[:,:,:,1:],0.)
    speed=np.abs(current-previous)*500.;pn=pairs.sum(-1)
    derivative=speed.sum(-1)/np.maximum(pn,1)
    features=np.concatenate((means,derivative,n[:,:1]/10.,pn[:,:1]/9.),axis=1)
    need(np.isfinite(features).all(),'Finite eye projection')
    return features.transpose(0,2,1)  # trial×150×8


def timing_features(rows):
    """Per-video source repeat-context proportions, never EEG-derived quality."""
    need(rows,'At least one exact joined trial for a video')
    sessions=np.zeros(8);runs=np.zeros(16);positions=[]
    for row in rows:
        s=row['session'];r=row['run'];t=row['trial']
        need(type(s) is int and 1<=s<=8 and type(r) is int and 1<=r<=16 and type(t) is int and 1<=t<=66,'Exact source timing indices')
        sessions[s-1]+=1;runs[r-1]+=1;positions.append((t-1)/65.)
    p=np.asarray(positions);delta=p-p[0]
    return np.r_[sessions/len(rows),runs/len(rows),p[0]+delta.mean(),delta.std()]


def standardize_fit(x,fit_indices):
    """Training-only transforms; constant training columns stay zero in query."""
    x=np.asarray(x,float);need(x.ndim==2 and np.isfinite(x).all(),'Finite feature table')
    fit=x[fit_indices];need(len(fit)>=2,'At least two fit rows')
    anchor=fit[0].copy();shifted=fit-anchor
    need(np.isfinite(shifted).all(),'Finite anchored fit features')
    keep=fit.min(0)!=fit.max(0);spread=np.max(np.abs(shifted),axis=0)
    normalized=np.zeros_like(fit);normalized[:,keep]=shifted[:,keep]/spread[keep]
    mean=normalized.mean(0);sd=normalized.std(0)
    need(np.isfinite(sd).all() and (sd[keep]>0).all(),'Defined nonconstant feature scaling')
    result=np.zeros_like(x);result[:,keep]=((x[:,keep]-anchor[keep])/spread[keep]-mean[keep])/sd[keep]
    need(np.isfinite(result).all(),'Finite training-only feature scaling')
    return result,{'anchor':anchor,'spread':spread,'mean_scaled':mean,'sd_scaled':sd,'keep':keep}
