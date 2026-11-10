"""Independent downstream artifact metrics; no EEG/model or author-code execution.

Both PR definitions and both seed SD conventions are named until the original
source ABI is authenticated. They are never silently substituted for one another.
"""
import math
from collections import Counter
import numpy as np


def need(value,message):
    if not value:raise ValueError(message)


def finite_scalar(value):
    if type(value) not in (int,float):return False
    try:return math.isfinite(value)
    except (ValueError,OverflowError):return False


def weights(n,groups=None):
    if groups is None:return np.ones(n,dtype=np.float64)
    need(type(groups) is list and len(groups)==n and all(type(g) is str and g for g in groups),'complete biological groups')
    counts=Counter(groups)
    return np.asarray([1/counts[g] for g in groups],dtype=np.float64)


def rankings(y,p,w):
    """Weighted tied-score ROC and PR, with explicit unavailable one-class case."""
    positives=float(w[y==1].sum());negatives=float(w[y==0].sum())
    if positives==0 or negatives==0:
        return {'auroc':None,'average_precision':None,'trapezoidal_pr_auc':None}
    order=np.argsort(-p,kind='stable');yy=y[order];pp=p[order];ww=w[order]
    tp=fp=0.;roc=ap=pr=0.;prev_tpr=prev_fpr=prev_recall=0.;prev_precision=1.
    i=0
    while i<len(y):
        j=i+1
        while j<len(y) and pp[j]==pp[i]:j+=1
        tp+=float(ww[i:j][yy[i:j]==1].sum());fp+=float(ww[i:j][yy[i:j]==0].sum())
        tpr=recall=tp/positives;fpr=fp/negatives;precision=tp/(tp+fp)
        roc+=(fpr-prev_fpr)*(tpr+prev_tpr)/2
        ap+=(recall-prev_recall)*precision
        pr+=(recall-prev_recall)*(precision+prev_precision)/2
        prev_tpr,prev_fpr,prev_recall,prev_precision=tpr,fpr,recall,precision;i=j
    return {'auroc':roc,'average_precision':ap,'trapezoidal_pr_auc':pr}


def classify(target,probabilities,classes,groups=None):
    y=np.asarray(target);p=np.asarray(probabilities,dtype=np.float64)
    need(type(classes) is int and classes>=2 and y.ndim==1 and len(y)>0 and p.shape==(len(y),classes),'complete multiclass rectangle')
    need(np.isfinite(y).all() and np.equal(y,np.floor(y)).all() and (y>=0).all() and (y<classes).all(),'integer class ontology')
    need(np.isfinite(p).all() and (p>=0).all() and (p<=1).all() and np.all(np.abs(p.sum(axis=1)-1)<=1e-6),'bounded normalized probabilities')
    y=y.astype(np.int64);w=weights(len(y),groups)
    # Canonical artifact tie rule: lowest class index, hence class0 for binary .5.
    pred=np.argmax(p,axis=1);matrix=np.zeros((classes,classes),dtype=np.float64)
    np.add.at(matrix,(y,pred),w)
    support=matrix.sum(axis=1);predicted=matrix.sum(axis=0);diag=np.diag(matrix);total=float(support.sum())
    complete=bool((support>0).all())
    balanced=float(np.mean(diag/support)) if complete else None
    denominator=support+predicted;f1=np.divide(2*diag,denominator,out=np.zeros(classes),where=denominator>0)
    weighted_f1=float(np.dot(f1,support)/total)
    po=float(diag.sum()/total);pe=float(np.dot(support/total,predicted/total))
    kappa=None if pe==1. else (po-pe)/(1-pe)
    result={'balanced_accuracy':balanced,'cohen_kappa':kappa,'weighted_f1':weighted_f1,
        'class_support':support.tolist(),'all_classes_present':complete,'samples':len(y),
        'weighting':'epoch_pooled' if groups is None else 'equal_person_total_weight',
        'confusion':matrix.tolist()}
    if classes==2:result.update(rankings(y,p[:,1],w))
    return result


def classify_scores(target,scores,classes,groups=None):
    """Source-conditioned REVE raw-logit rank ABI, never silent softmax conversion."""
    y=np.asarray(target);a=np.asarray(scores)
    need(a.dtype.kind in 'fiu' and a.shape==(len(y),classes) and np.isfinite(a).all() and (np.abs(a)<=1e100).all(),'complete finite raw scores')
    hard=np.eye(classes)[np.argmax(a,axis=1)];result=classify(y,hard,classes,groups)
    if classes==2:result.update(rankings(y.astype(np.int64),a[:,1],weights(len(y),groups)))
    result['prediction_values']='raw_logits';return result
