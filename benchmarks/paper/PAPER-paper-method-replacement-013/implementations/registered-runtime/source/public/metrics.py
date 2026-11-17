"""Declared finite artifact diagnostics. Physical spike identity is not inferred."""
import math
from io_contract import require,number

def mean(v):
    require(len(v)>0,'nonempty support')
    for x in v:number(x)
    scale=max(abs(x) for x in v)
    return 0.0 if scale==0 else math.fsum(x/scale for x in v)/len(v)*scale

def unit_center(v):
    require(len(v)>0,'nonempty support')
    for x in v:number(x)
    if min(v)==max(v):return None
    s=max(abs(x) for x in v);u=[x/s for x in v];a=u[0];d=[x-a for x in u];m=mean(d);d=[x-m for x in d]
    norm=math.hypot(*d);require(norm>0,'representable centered variation')
    return [x/norm for x in d]

def pearson(y,p):
    require(len(y)==len(p)>0,'paired Pearson support');a=unit_center(y);b=unit_center(p)
    if a is None or b is None:return None
    return max(-1.,min(1.,math.fsum(x*z for x,z in zip(a,b))))

def regression(y,p):
    require(len(y)==len(p)>0,'paired regression support')
    for x in y+p:number(x)
    scale=max(abs(x) for x in y+p)
    e=[(x/scale-z/scale) for x,z in zip(y,p)] if scale else [0.]*len(y)
    rms=math.hypot(*e)/math.sqrt(len(e))*scale
    if not math.isfinite(rms):rms=None
    r2=None
    if min(y)!=max(y):
        ys=max(abs(x) for x in y);z=[x/ys for x in y];anchor=z[0];z=[x-anchor for x in z];m=mean(z);sd=math.hypot(*(x-m for x in z))
        if sd>0:
            ratio=(math.hypot(*e)/sd)*(scale/ys)
            r2=1-ratio*ratio if math.isfinite(ratio) and ratio<=math.sqrt(float.fromhex('0x1.fffffffffffffp+1023')) else None
    return {'pearson_r':pearson(y,p),'r2':r2,'rmse':rms,'n':len(y),'undefined_or_overflow_remains_null':True}

def classification(y,p,centers):
    require(len(y)==len(p)>0 and len(centers)==25,'25-class support');cm=[[0]*25 for _ in range(25)];decoded=[]
    for t,probs in zip(y,p):
        require(type(t) is int and 0<=t<25 and len(probs)==25,'classes')
        for x in probs:require(0<=number(x)<=1,'probability')
        require(abs(math.fsum(probs)-1)<=1e-8,'probability simplex')
        c=max(range(25),key=lambda k:probs[k]);cm[t][c]+=1;decoded.append(centers[c])
    n=len(y);rec=[];f=[]
    for k in range(25):
        tp=cm[k][k];support=sum(cm[k]);pred=sum(r[k] for r in cm);rec.append(tp/support if support else None);f.append(2*tp/(support+pred) if support+pred else None)
    return {'accuracy':sum(cm[k][k] for k in range(25))/n,'balanced_accuracy':mean(rec) if all(x is not None for x in rec) else None,
      'weighted_f1':sum((f[k] or 0)*sum(cm[k]) for k in range(25))/n,'confusion_true_rows_pred_columns':cm,
      'decoded_center_pearson':pearson([centers[k] for k in y],decoded) if n>1 else None,'class_center_decoding_is_prospective':True}

def event_counts(y,p):
    require(len(y)==len(p)>0,'aligned complete count support')
    for v in y+p:require(type(v) is int and 0<=v<=2147483647,'nonnegative integer calcium-event counts')
    observed=sum(y);predicted=sum(p);tp=sum(min(a,b) for a,b in zip(y,p));presence_tp=sum(a>0 and b>0 for a,b in zip(y,p));positives=sum(a>0 for a in y);predpos=sum(b>0 for b in p)
    return {'count_intersection_f1':2*tp/(observed+predicted) if observed+predicted else None,
       'presence_f1':2*presence_tp/(positives+predpos) if positives+predpos else None,
       'precision':tp/predicted if predicted else None,'recall':tp/observed if observed else None,
       'target_events':observed,'predicted_events':predicted,'support_bins':len(y),
       'source_f1_abi_qualified':False,'physical_spike_ground_truth':False}

def source_interval_id_scores(true_sets,pred_sets):
    """Two literal source formulas, not a selected paper metric or dense-bin F1.

    analysis.py compute_scores visits true-present intervals and has the
    preserved FP==0/FN==0 shortcut. compute_scores_scikit visits predicted-
    present intervals and weights binary F1 over the active ID union.
    The caller's window/token conversion and paper branch remain unqualified.
    """
    require(len(true_sets)==len(pred_sets)>0,'same complete interval roster')
    original=[];weighted=[]
    for t,p in zip(true_sets,pred_sets):
        require(type(t) is set and type(p) is set,'explicit per-interval ID sets')
        require(all(type(i) is int and i>=0 for i in t|p),'nonnegative neural IDs')
        tp=len(t&p);fp=len(p-t);fn=len(t-p)
        if t:
            if tp==0:pr=rc=0.
            elif fp==0 or fn==0:pr=rc=1.
            else:pr=tp/(tp+fp);rc=tp/(tp+fn)
            original.append((pr,rc,2*pr*rc/(pr+rc) if pr+rc else 0.))
        if p:
            # Union has no true-negative IDs. Its negative-class F1 is zero.
            weighted.append((2*tp/(2*tp+fp+fn))*(tp+fn)/(tp+fp+fn))
    return {'compute_scores_true_present_intervals':{'precision':mean([v[0] for v in original]) if original else None,
      'recall':mean([v[1] for v in original]) if original else None,'f1':mean([v[2] for v in original]) if original else None,'included_intervals':len(original)},
      'compute_scores_scikit_predicted_present_intervals':{'weighted_binary_f1':mean(weighted) if weighted else None,'included_intervals':len(weighted)},
      'complete_intervals':len(true_sets),'paper_branch_and_window_conversion_qualified':False}
