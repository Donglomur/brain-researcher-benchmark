"""Independent reference/calibration source, never executed on task data here.

This is a new draft ridge-all-coordinates reference, not author OLS/KernelPCA
reproduction. All feature transforms are fit inside the supplied split. The
caller must bind the actual participants/rows and use only inner-development
scores for temperature selection; array checks cannot prove that provenance.
"""
import math
import numpy as np

TEMPERATURES=(0.01,0.02,0.05,0.1,0.2,0.5,1.0,2.0,5.0,10.0)


def matrix(x,name):
    a=np.asarray(x)
    if a.ndim!=2 or a.dtype.kind!='f' or min(a.shape)<1 or not np.isfinite(a).all():raise ValueError(name+': finite floating matrix required')
    return a.astype(np.float64,copy=False)


def fit_ridge_encoder(image_features,eeg_by_person,fit_people,fit_rows,*,forbidden_people):
    """Train-only image standardization; mean eligible-person EEG; ridge alpha1.

    fit_rows excludes all330 development concepts in each inner fit. fit_people
    excludes the outer participant and the current inner validation participant.
    Final refit after selection uses allother9 original training people/concepts.
    """
    x=matrix(image_features,'image features')
    if not fit_people or len(set(fit_people))!=len(fit_people) or set(fit_people)&set(forbidden_people):raise ValueError('unique eligible fit people required')
    rows=np.asarray(fit_rows)
    if rows.ndim!=1 or rows.dtype.kind not in 'iu' or len(rows)<2 or len(set(rows.tolist()))!=len(rows) or np.min(rows)<0 or np.max(rows)>=len(x):raise ValueError('distinct eligible training rows required')
    ys=[matrix(eeg_by_person[p],'training EEG') for p in fit_people]
    if any(y.shape!=ys[0].shape or y.shape[0]!=len(x) for y in ys):raise ValueError('EEG feature axes must align acrosspeople andimages')
    train=x[rows];center=train.mean(axis=0);scale=train.std(axis=0);scale[scale==0]=1
    z=(train-center)/scale
    target=sum(y[rows] for y in ys)/len(ys);offset=target.mean(axis=0)
    gram=z.T@z;gram.flat[::len(gram)+1]+=1.0
    coefficient=np.linalg.solve(gram,z.T@(target-offset))
    if not np.isfinite(coefficient).all():raise ValueError('nonfinite reference fit')
    return {'center':center,'scale':scale,'coefficient':coefficient,'offset':offset,'ridge_alpha':1.0}


def predict_eeg(model,image_features):
    x=matrix(image_features,'image features')
    result=((x-model['center'])/model['scale'])@model['coefficient']+model['offset']
    if not np.isfinite(result).all():raise ValueError('nonfinite reference predictions')
    return result


def correlation_scores(query_eeg,synthetic_candidate_eeg):
    """Pearson across all flattened whitened coordinates; zero norm gives neutral0.

    The zero-norm convention is a new draft fallback, not a physiological claim.
    No coordinate selection uses target-person labeled training EEG.
    """
    q=matrix(query_eeg,'query EEG');c=matrix(synthetic_candidate_eeg,'synthetic EEG')
    if q.shape[1]!=c.shape[1]:raise ValueError('coordinate mismatch')
    q=q-q.mean(axis=1,keepdims=True);c=c-c.mean(axis=1,keepdims=True)
    qnorm=np.linalg.norm(q,axis=1,keepdims=True);cnorm=np.linalg.norm(c,axis=1,keepdims=True)
    q=np.divide(q,qnorm,out=np.zeros_like(q),where=qnorm!=0)
    c=np.divide(c,cnorm,out=np.zeros_like(c),where=cnorm!=0)
    return np.clip(q@c.T,-1.0,1.0)


def probabilities(scores,temperature):
    a=matrix(scores,'correlation scores')
    if a.shape[1]!=200 or np.min(a)<-1 or np.max(a)>1 or temperature not in TEMPERATURES:raise ValueError('200 candidate correlations and declared temperature required')
    z=a/temperature;z-=z.max(axis=1,keepdims=True);e=np.exp(z)
    return e/e.sum(axis=1,keepdims=True)


def fit_temperature(development_by_person,*,expected_people):
    """Equal-person natural-log loss on out-of-fit200-candidate inner panels.

    Exactly the nine nonouter people must contribute the same ten deterministic
    exemplar panels. The lowest grid temperature wins exact objective ties.
    Never call with outer query/gold. No empirical call was made in this build.
    """
    if len(expected_people)!=9 or len(set(expected_people))!=9 or set(development_by_person)!=set(expected_people):raise ValueError('all nine nonouter development people required')
    for person in expected_people:
        panels=development_by_person[person]
        if type(panels) is not list or len(panels)!=10:raise ValueError('ten exemplar panels perdevelopment person required')
        for scores,truth in panels:
            a=matrix(scores,'development correlations');y=np.asarray(truth)
            if a.shape!=(200,200) or y.shape!=(200,) or y.dtype.kind not in 'iu' or set(y.tolist())!=set(range(200)):raise ValueError('balanced200 image development panel required')
    objectives=[]
    for temperature in TEMPERATURES:
        person_values=[]
        for person in expected_people:
            panel_values=[]
            for scores,truth in development_by_person[person]:
                p=probabilities(scores,temperature);selected=p[np.arange(200),truth]
                panel_values.append(math.inf if np.any(selected==0) else float(-np.log(selected).mean()))
            person_values.append(math.fsum(panel_values)/10)
        objectives.append(math.fsum(person_values)/9)
    index=min(range(len(TEMPERATURES)),key=lambda i:(objectives[i],i))
    return {'temperature':TEMPERATURES[index],'grid':list(TEMPERATURES),'development_equal_person_log_losses':objectives,'source_scope':'development-only draft recipe; provenance must be separatelybound'}
