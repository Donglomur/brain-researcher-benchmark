"""Prediction metrics and declared aggregation; no fitting or target selection."""
from fractions import Fraction
import math
import numpy as np


def auc(labels, probabilities):
    y=np.asarray(labels);p=np.asarray(probabilities)
    if y.ndim!=1 or p.shape!=y.shape or not len(y) or y.dtype.kind not in 'biu' or p.dtype.kind!='f':raise ValueError('Complete primitive binary support')
    if not np.isin(y,[0,1]).all() or not np.isfinite(p).all() or (p<0).any() or (p>1).any():raise ValueError('Binary labels and finite probabilities in [0,1]')
    pos=int(y.sum());neg=len(y)-pos
    if not pos or not neg:return {'roc_auc':None,'status':'undefined_single_class','positive':pos,'negative':neg,'count':len(y)}
    order=np.argsort(p,kind='stable');yy=y[order];pp=p[order];twice_wins=0;lower_neg=0;i=0
    while i<len(y):
        j=i+1
        while j<len(y) and pp[j]==pp[i]:j+=1
        gp=int(yy[i:j].sum());gn=j-i-gp;twice_wins+=gp*(2*lower_neg+gn);lower_neg+=gn;i=j
    return {'roc_auc':float(Fraction(twice_wins,2*pos*neg)),'status':'defined','positive':pos,'negative':neg,'count':len(y)}


def exact_summary(values):
    """Native mean and sample-SD/sqrt(n); explicit undefined, exact constants."""
    if not values:raise ValueError('Empty complete cell roster')
    if any(v is None for v in values):return {'mean':None,'sem':None,'count':len(values),'defined':False}
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('Finite scalar values')
    fs=[Fraction.from_float(float(v)) for v in values];n=len(fs);mu=sum(fs)/n
    variance=sum((v-mu)**2 for v in fs)/(n*(n-1)) if n>1 else None
    return {'mean':float(mu),'sem':math.sqrt(float(variance)) if variance is not None else None,'count':n,'defined':True}


def aggregate(rows, expected):
    """Exact frozen ordered cell roster; no caller-selected favorable subset."""
    keys=('protocol','person','task','fold','seed','model')
    if len(rows)!=len(expected) or any(any(r.get(k)!=e[k] for k in keys) for r,e in zip(rows,expected)):raise ValueError('Complete source cell roster and order required')
    native={};people={}
    for row in rows:
        key=(row['protocol'],row['task'],row['model']);native.setdefault(key,[]).append(row['roc_auc']);people.setdefault(key,{}).setdefault(row['person'],[]).append(row['roc_auc'])
    result=[]
    for (protocol,task,model),values in native.items():
        pm=[exact_summary(v)['mean'] for _,v in sorted(people[(protocol,task,model)].items())]
        result.append({'protocol':protocol,'task':task,'model':model,'source_session_seed_fold_summary':exact_summary(values),'prospective_equal_person_summary':exact_summary(pm),'person_count':len(pm)})
    return result


def improvement(rows, expected, trusted):
    if len(rows)!=len(trusted) or len(rows)!=len(expected):raise ValueError('Complete paired source support')
    keys=('protocol','person','task','fold','seed')
    for r,b,e in zip(rows,trusted,expected):
        if any(r.get(k)!=e[k] or b.get(k)!=e[k] for k in keys):raise ValueError('Paired improvement identity')
    # AUC is bounded; subtraction cannot overflow. Keep every undefined cell.
    delta=[None if r['roc_auc'] is None or b['roc_auc'] is None else r['roc_auc']-b['roc_auc'] for r,b in zip(rows,trusted)]
    return {'absolute_improved_auc':exact_summary([r['roc_auc'] for r in rows]),'trusted_baseline_auc':exact_summary([r['roc_auc'] for r in trusted]),'paired_auc_gain':exact_summary(delta),'claim':'Prospective same-support comparison, not automatic significance or frontier improvement.'}
