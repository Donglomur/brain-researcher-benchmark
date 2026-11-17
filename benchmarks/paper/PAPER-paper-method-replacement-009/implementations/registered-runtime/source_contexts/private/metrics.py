"""Declared prospective metrics. No fitting, threshold selection or target masking."""
import math
import numpy as np

class ArithmeticUnavailable(Exception):
    pass

def finite(x):
    z=float(x)
    if not math.isfinite(z):raise ArithmeticUnavailable('metric outside finite float64')
    return z

def centered(x):
    x=np.asarray(x,dtype=np.float64).ravel()
    if len(x)<2 or np.all(x==x[0]):return None
    mid=float(np.min(x))/2+float(np.max(x))/2
    delta=x-mid;scale=float(np.max(np.abs(delta)))
    if scale==0:raise ArithmeticUnavailable('nonconstant range underflow')
    z=delta/scale;z=z-math.fsum(float(v)/len(z) for v in z)
    return z,scale

def pearson(y,p):
    a=centered(y);b=centered(p)
    if a is None or b is None:return None
    z=a[0];w=b[0]
    return float(np.clip(np.dot(z,w)/math.sqrt(np.dot(z,z)*np.dot(w,w)),-1,1))

def r2(y,p):
    y=np.asarray(y,dtype=float).ravel();p=np.asarray(p,dtype=float).ravel()
    c=centered(y)
    if c is None:return None
    z,ys=c
    with np.errstate(over='ignore',invalid='ignore'):diff=p-y
    multiplier=1.
    if not np.isfinite(diff).all():diff=p/2-y/2;multiplier=2.
    scale=float(np.max(np.abs(diff)))
    if scale==0:return 1.
    ss=float(np.dot(diff/scale,diff/scale));tt=float(np.dot(z,z))
    logratio=math.log(ss)-math.log(tt)+2*(math.log(scale)+math.log(multiplier)-math.log(ys))
    if logratio>math.log(np.finfo(float).max):raise ArithmeticUnavailable('R2 outside finite float64')
    return finite(1-math.exp(logratio))

def auc(y,p):
    y=np.asarray(y).ravel();p=np.asarray(p).ravel();pos=int(np.sum(y==1));neg=len(y)-pos
    if not pos or not neg:return None
    order=np.argsort(p,kind='stable');sorted_p=p[order];rank=np.empty(len(p),float);i=0
    while i<len(p):
        j=i+1
        while j<len(p) and sorted_p[j]==sorted_p[i]:j+=1
        rank[order[i:j]]=(i+1+j)/2;i=j
    return finite((math.fsum(rank[y==1])-pos*(pos+1)/2)/(pos*neg))

def metric(fn,*args):
    try:
        x=fn(*args)
        return {'value':x,'status':'defined' if x is not None else 'undefined_fixed_support'}
    except (ArithmeticUnavailable,FloatingPointError,OverflowError):
        return {'value':None,'status':'valid_unscorable_arithmetic'}

def summary(values):
    good=[x for x in values if x is not None]
    def mean(v):return finite(math.fsum(x/len(v) for x in v)) if v else None
    return {'total':len(values),'defined':len(good),'mean_all':mean(good) if len(good)==len(values) else None,'defined_only_diagnostic':mean(good)}

def evaluate_case(target,y,p,template,groups):
    if target=='choice':
        return {'auc':metric(auc,y,p),'accuracy':metric(lambda a,b:float(np.mean((b>0.5)==a)),y,p),
                'template_auc':metric(auc,y,template)}
    out={'r2':metric(r2,y,p),'pearson':metric(pearson,y,p),'template_r2':metric(r2,y,template)}
    if y.shape[1]>1:
        diagnostics={}
        for j,name in enumerate(['block','choice','reward']):
            a=[];b=[];pairs=[];group_values=np.unique(groups[:,j])
            # Separate observed and predicted group means: a descriptive assessment
            # decomposition, never a transform made available to a candidate.
            unavailable={'value':None,'status':'valid_unscorable_arithmetic'}
            try:
                with np.errstate(over='raise',invalid='raise'):
                    for group in group_values:
                        ix=groups[:,j]==group;yy=y[ix];pp=p[ix]
                        ym=np.sum(yy/len(yy),axis=0);pm=np.sum(pp/len(pp),axis=0)
                        if not np.isfinite(ym).all() or not np.isfinite(pm).all():raise ArithmeticUnavailable('group mean overflow')
                        a.append(ym);b.append(pm);pairs.append((yy,pp,ym,pm))
                group_metric=metric(r2,np.asarray(a),np.asarray(b))
            except (ArithmeticUnavailable,FloatingPointError,OverflowError):
                group_metric=unavailable;residual_metric=unavailable
            else:
                try:
                    with np.errstate(over='raise',invalid='raise'):
                        yr=[yy-ym for yy,pp,ym,pm in pairs];pr=[pp-pm for yy,pp,ym,pm in pairs]
                    residual_metric=metric(r2,np.concatenate(yr),np.concatenate(pr))
                except (ArithmeticUnavailable,FloatingPointError,OverflowError):residual_metric=unavailable
            diagnostics[name]={'group_mean_r2':group_metric,
                'within_group_residual_r2':residual_metric,
                'groups':len(group_values),'trials':len(y),'status':'retrospective_assessment_diagnostic'}
        out['conditional_structure']=diagnostics
    return out

def evaluate(panel,truth,template,groups,pred):
    result=[];methods=panel['methods']
    for c in panel['cases']:
        a,b=c['offset'];shape=(c['query_trials'],c['output_bins']);y=truth[a:b].reshape(shape);t=template[a:b].reshape(shape)
        g=groups[c['group_offset'][0]:c['group_offset'][1]]
        row={k:c[k] for k in ['case_id','eid','animal_id','target','query_trials']};row['methods']={}
        for j,name in enumerate(methods):
            try:row['methods'][name]=evaluate_case(c['target'],y,pred[a:b,j].reshape(shape),t,g)
            except (ArithmeticUnavailable,FloatingPointError,OverflowError):row['methods'][name]={'status':'valid_unscorable_arithmetic'}
        result.append(row)
    aggregates={}
    for target in sorted({c['target'] for c in result}):
        key='auc' if target=='choice' else 'pearson' if target=='prior' else 'r2';rr=[c for c in result if c['target']==target]
        def value(c,m):return c['methods'][m].get(key,{}).get('value')
        mm={}
        for m in methods:
            animals=sorted({c['animal_id'] for c in rr})
            av=[summary([value(c,m) for c in rr if c['animal_id']==a])['mean_all'] for a in animals]
            mm[m]={'session_macro':summary([value(c,m) for c in rr]),'animal_macro':summary(av)}
        pairs={}
        for lhs,rhs in [('multi_rrr','single_rrr'),('multi_rrr','linear'),('improved','multi_rrr')]:
            vals=[]
            for c in rr:
                x=value(c,lhs);y=value(c,rhs)
                vals.append(metric(lambda a,b:finite(a-b),x,y)['value'] if x is not None and y is not None else None)
            animals=sorted({c['animal_id'] for c in rr})
            animal_values=[summary([v for c,v in zip(rr,vals) if c['animal_id']==a])['mean_all'] for a in animals]
            pairs[lhs+'_minus_'+rhs]={'session_macro':summary(vals),'animal_macro':summary(animal_values)}
        aggregates[target]={'primary_metric':key,'methods':mm,'paired_session_contrasts':pairs}
    return {'per_session':result,'aggregate':aggregates,'success_threshold':None,'inference':'descriptive; no fitted-model, algorithm-identity or paper-reproduction verification'}
