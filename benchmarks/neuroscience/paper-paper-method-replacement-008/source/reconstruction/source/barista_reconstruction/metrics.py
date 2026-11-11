"""Unsmoothed normalized-time-series reconstruction; no paper R² is inferred."""
from fractions import Fraction
import math
import numpy as np
from .protocol import PEOPLE,COUNTS,ARMS,MODELS,requests,validate_panel


def masked_channel_mse(target,prediction):
    """One channel across all supplied segments/samples. No support dropping."""
    a=np.asarray(target);b=np.asarray(prediction)
    if a.ndim!=2 or a.size==0 or a.shape!=b.shape or any(x.dtype.kind!='f'or x.dtype.itemsize not in(4,8)for x in(a,b)):raise ValueError('Matched nonempty real2D float32/64 arrays')
    if not np.isfinite(a).all()or not np.isfinite(b).all():raise ValueError('Complete finite targets/predictions required; no NaN filtering')
    with np.errstate(over='ignore',invalid='ignore'):
        error=np.subtract(a,b,dtype=np.float64)
    n=error.size
    if not np.isfinite(error).all():return {'status':'numeric_unavailable','mse':None,'sample_count':n}
    scale=float(np.max(np.abs(error)))
    if scale==0:return {'status':'ok','mse':0.0,'sample_count':n}
    flat=error.ravel();partials=[]
    for at in range(0,n,65536):
        normalized=flat[at:at+65536]/scale
        partials.append(math.fsum(float(x)*float(x)for x in normalized))
    normalized_mean=math.fsum(partials)/n
    mantissa,exponent=math.frexp(scale)
    try:value=math.ldexp(normalized_mean*mantissa*mantissa,2*exponent)
    except OverflowError:value=math.inf
    if not math.isfinite(value)or value<=0:return {'status':'numeric_unavailable','mse':None,'sample_count':n}
    return {'status':'ok','mse':value,'sample_count':n}


def _mean(values):
    # Exact binary-float sum avoids intermediate overflow and constant drift.
    exact=sum((Fraction.from_float(x)for x in values),Fraction())/len(values)
    try:value=float(exact)
    except OverflowError:return None
    return value if math.isfinite(value)and(value!=0 or exact==0)else None


def _sem(values):
    vals=[Fraction.from_float(x)for x in values];n=len(vals);mu=sum(vals,Fraction())/n
    scale=max(abs(x-mu)for x in vals)
    if scale==0:return 0.0
    normalized=sum(((x-mu)/scale)**2 for x in vals)/((n-1)*n)
    result=float(scale)*math.sqrt(float(normalized))
    return result if math.isfinite(result)and result>0 else None


def aggregate_channel_results(rows,panel):
    """Full12model×2arm grid. No best-model choice or cross-model averaging."""
    validate_panel(panel)
    expected=list(requests(panel))
    if not isinstance(rows,list)or len(rows)!=len(expected):raise ValueError('Full reconstruction result support')
    groups={(arm,model):{p:[]for p in PEOPLE}for arm in ARMS for model in MODELS}
    for row,e in zip(rows,expected):
        if not isinstance(row,dict)or set(row)!={'id','status','mse','sample_count'}or row['id']!=e['id']or type(row['sample_count'])is not int or row['sample_count']!=e['shape'][0]*e['shape'][1]:raise ValueError('Exact complete result identities/counts')
        if row['status']=='ok':
            value=row['mse']
            if type(value)not in(int,float)or not math.isfinite(value)or value<0:raise ValueError('Finite nonnegative MSE')
            value=float(value)
        elif row['status']=='numeric_unavailable'and row['mse']is None:value=None
        else:raise ValueError('Explicit numeric status required')
        groups[e['arm'],e['model']][e['person']].append(value)
    output=[]
    for arm in ARMS:
        for model in MODELS:
            persons=groups[arm,model];all_values=[x for p in PEOPLE for x in persons[p]]
            by_person=[{'person':p,'channels':COUNTS[p][3],'mse':None if any(x is None for x in persons[p])else _mean(persons[p])}for p in PEOPLE]
            means=[x['mse']for x in by_person]
            complete=all(x is not None for x in all_values+means)
            primary=_mean(means)if complete else None
            sem=_sem(means)if complete else None
            pooled=_mean(all_values)if complete else None
            complete=complete and all(x is not None for x in (primary,sem,pooled))
            output.append({'arm':arm,'model':model,'status':'ok'if complete else'numeric_unavailable','person_results':by_person,'equal_person_mse':primary if complete else None,'person_sample_sem':sem if complete else None,'channel_pooled_mse':pooled if complete else None,'all945_channels_retained':True,'historical_r2':None,'historical_r2_convention_resolved':False,'exact_paper_aggregation_parity':False})
    return {'schema':'barista_reconstruction_metrics_v1','model_results':output,'aggregation':'MSE within each channel over complete segments/samples; primary equal channel mean within person then equal7person mean. Channel-pooled descriptive alternative retained. No model pooling or significance test.','scientific_execution_verified':False}
