"""Declared NEURAL-001 metric. Pure supplied arrays; no fitting or data access."""
import math
import numpy as np
FISHER_BOUND=float(np.nextafter(1.,0.))

def average_ranks(x):
    x=np.asarray(x,dtype=np.float64);order=np.argsort(x,kind='stable');sorted_x=x[order];r=np.empty(x.size,dtype=np.float64);i=0
    while i<x.size:
        j=i+1
        while j<x.size and sorted_x[j]==sorted_x[i]:j+=1
        r[order[i:j]]=(i+j+1)/2.;i=j
    return r

def correlation(x,y):
    """Scale before centering so finite extreme inputs retain a defined correlation."""
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    if x.ndim!=1 or x.shape!=y.shape or x.size<4 or not np.isfinite(x).all()or not np.isfinite(y).all():raise ValueError('Complete finite paired vectors of length>=4')
    if np.all(y==y[0]):raise ValueError('Constant target: invalid operator packet')
    if np.all(x==x[0]):return 0.,True
    x=x/max(float(np.max(np.abs(x))),1e-300);y=y/max(float(np.max(np.abs(y))),1e-300)
    x=x-math.fsum(map(float,x))/x.size;y=y-math.fsum(map(float,y))/y.size
    nx=math.sqrt(math.fsum(float(z)*float(z)for z in x));ny=math.sqrt(math.fsum(float(z)*float(z)for z in y))
    if nx==0 or ny==0:raise ValueError('Unsupported derived correlation arithmetic')
    rho=math.fsum(float(a/nx)*float(b/ny)for a,b in zip(x,y))
    if not math.isfinite(rho)or abs(rho)>1+1e-12:raise ValueError('Unsupported derived correlation arithmetic')
    return max(-1.,min(1.,rho)),False

def sentence(pred,target):
    pearson,constant=correlation(pred,target);rho,_=correlation(average_ranks(pred),average_ranks(target))
    bounded=max(-FISHER_BOUND,min(FISHER_BOUND,rho));return dict(n=len(pred),spearman=rho,pearson=pearson,fisher_z_spearman=math.atanh(bounded),constant_prediction=constant,fisher_endpoint_clipped=abs(rho)>FISHER_BOUND)

def score_people(predictions,targets,offsets,ids):
    if not predictions or set(predictions)!=set(targets):raise ValueError('All declared persons required')
    people={}
    for person in predictions:
        p=np.asarray(predictions[person]);t=np.asarray(targets[person]);o=offsets[person]
        if p.shape!=t.shape or len(o)!=len(ids[person])+1 or o[0]!=0 or o[-1]!=len(p)or any(b-a<4 for a,b in zip(o,o[1:])):raise ValueError('Exact complete sentence support')
        rows=[dict(id=ident,**sentence(p[a:b],t[a:b]))for ident,a,b in zip(ids[person],o,o[1:])]
        people[person]=dict(sentences=len(rows),fisher_z_spearman=math.fsum(x['fisher_z_spearman']for x in rows)/len(rows),mean_raw_spearman=math.fsum(x['spearman']for x in rows)/len(rows),mean_raw_pearson=math.fsum(x['pearson']for x in rows)/len(rows),constant_predictions=sum(x['constant_prediction']for x in rows),per_sentence=rows)
    if not people:raise ValueError('No persons')
    score=math.fsum(x['fisher_z_spearman']for x in people.values())/len(people)
    return dict(status='scored',score=score,primary='person_macro_mean_sentence_fisher_z_spearman',higher_is_better=True,backtransformed_macro_spearman=math.tanh(score),persons=people,person_count=len(people),coverage=1.,scientific_success_reward=None,uncertainty=None,uncertainty_note='No independent-sample CI is inferred from repeated sentences; later study must cluster by participant and account for shared stimuli.')
