"""Future trusted grader mathematics; no model, fitting or participant imports."""
import math
import random
from collections import Counter
from .errors import require


def confusion(labels,scores,classes,weights=None,guard=None):
    if guard:guard()
    require(len(labels)==len(scores)>0 and classes>1,'metric support')
    weights=[1.0]*len(labels) if weights is None else weights
    require(len(weights)==len(labels) and all(math.isfinite(w) and w>0 for w in weights),'metric weights')
    matrix=[[0.0]*classes for _ in range(classes)]
    for y,row,w in zip(labels,scores,weights):
        if guard:guard()
        require(type(y) is int and 0<=y<classes and len(row)==classes and all(math.isfinite(v) for v in row),'prediction/class support')
        pred=max(range(classes),key=lambda k:row[k])
        matrix[y][pred]+=w
    return matrix


def classification(labels,scores,classes,weights=None,guard=None):
    if guard:guard()
    C=confusion(labels,scores,classes,weights,guard);total=math.fsum(map(sum,C))
    support=list(map(sum,C));pred=[sum(C[r][c] for r in range(classes)) for c in range(classes)]
    correct=sum(C[c][c] for c in range(classes));po=correct/total;pe=sum(a*b for a,b in zip(support,pred))/total**2
    f1=[2*C[c][c]/(support[c]+pred[c]) if support[c]+pred[c] else 0.0 for c in range(classes)]
    return {'balanced_accuracy':sum(C[c][c]/support[c] for c in range(classes))/classes if all(support) else None,
            'cohen_kappa':(po-pe)/(1-pe) if pe<1 else None,
            'weighted_f1':sum(a*b for a,b in zip(support,f1))/total,'confusion':C,'class_support':support,'all_classes_present':all(support)}


def binary_ranking(labels,positive_scores,weights=None,guard=None):
    if guard:guard()
    require(len(labels)==len(positive_scores)>0,'ranking support')
    weights=[1.0]*len(labels) if weights is None else weights
    require(len(weights)==len(labels) and set(labels)<={0,1} and all(math.isfinite(s) for s in positive_scores),'binary ranking')
    require(all(math.isfinite(w) and w>0 for w in weights),'ranking weights')
    P=sum(w for y,w in zip(labels,weights) if y==1);N=sum(w for y,w in zip(labels,weights) if y==0)
    if not P or not N:return {'auroc':None,'average_precision':None,'pr_trapezoid':None,'both_classes_present':False}
    ordered=sorted(zip(positive_scores,labels,weights),reverse=True)
    tp=fp=roc=ap=pr=0.0;old_tpr=old_fpr=old_recall=0.0;old_precision=1.0;i=0
    while i<len(ordered):
        if guard:guard()
        score=ordered[i][0]
        while i<len(ordered) and ordered[i][0]==score:
            _,y,w=ordered[i];tp+=w*y;fp+=w*(1-y);i+=1
        tpr=tp/P;fpr=fp/N;precision=tp/(tp+fp)
        roc+=(fpr-old_fpr)*(tpr+old_tpr)/2
        ap+=(tpr-old_recall)*precision;pr+=(tpr-old_recall)*(precision+old_precision)/2
        old_tpr=tpr;old_fpr=fpr;old_recall=tpr;old_precision=precision
    return {'auroc':roc,'average_precision':ap,'pr_trapezoid':pr,'both_classes_present':True}


def probability_diagnostics(labels,probabilities,weights=None,guard=None):
    if guard:guard()
    weights=[1.0]*len(labels) if weights is None else weights;den=sum(weights)
    require(len(labels)==len(probabilities)==len(weights)>0 and den>0,'probability support')
    brier=nll=0.0;clipped=0
    for y,row,w in zip(labels,probabilities,weights):
        if guard:guard()
        require(all(math.isfinite(x) and 0<=x<=1 for x in row) and abs(sum(row)-1)<=1e-6,'probability simplex')
        brier+=w*sum((p-int(k==y))**2 for k,p in enumerate(row))
        clipped+=int(row[y]<1e-12);nll-=w*math.log(max(row[y],1e-12))
    return {'brier':brier/den,'negative_log_likelihood':nll/den,'clipped_target_probabilities':clipped}


def person_weights(people):
    counts=Counter(people)
    return [1/counts[p] for p in people]


def fewshot_reduce(rows,guard=None):
    """All 1800 complete cells; draw means within person, then nine people."""
    by_key={(x['person'],x['shots'],x['draw'],x['method']):x for x in rows}
    expected={(p,n,d,m) for p in range(1,10) for n in (1,2,5,10,20) for d in range(20) for m in ('REVE-Base-PT','REVE-Base-XFT')}
    require(len(rows)==1800 and set(by_key)==expected,'complete fewshot reduction roster')
    out=[]
    for n in (1,2,5,10,20):
        if guard:guard()
        for method in ('REVE-Base-PT','REVE-Base-XFT'):
            people=[]
            for p in range(1,10):
                values=[by_key[p,n,d,method]['balanced_accuracy'] for d in range(20)]
                require(all(v is not None for v in values),'incomplete fewshot metric')
                people.append(sum(values)/20)
            out.append({'shots':n,'method':method,'people':people,'mean':sum(people)/9,'biological_N':9,'draws_per_person':20})
    return out


def holm_full_union(rows,expected):
    require(len(expected)==160 and len(rows)==160,'full 160-slot family')
    keys=lambda r:(r['arm'],r['dataset'],r['condition'],r['reference'])
    require({keys(x) for x in rows}=={keys(x) for x in expected} and len({keys(x) for x in rows})==160,'contrast identity')
    ps=[]
    for i,row in enumerate(rows):
        p=row['p_value']
        require(p is None or math.isfinite(p) and 0<=p<=1,'p value')
        ps.append((1.0 if p is None else p,i))
    adjusted=[None]*160;running=0.0
    for rank,(p,i) in enumerate(sorted(ps)):
        running=max(running,min(1.0,(160-rank)*p));adjusted[i]=running
    return [{**r,'holm_p':adjusted[i],'adjustment_only_missing_p':r['p_value'] is None,'intervals_simultaneous':False} for i,r in enumerate(rows)]


def paired_cluster_bootstrap(people,run_pairs,classes,seed,replicates=10000,guard=None):
    """Conditional fitted-state person-cluster inference; run averaging, not ensembling."""
    require(replicates==10000 and type(seed) is int and run_pairs,'fixed bootstrap manifest')
    unique=sorted(set(people));require(unique,'biological support');rng=random.Random(seed);counts=Counter(people)
    # BA depends on the pooled confusion matrices. Precompute exact per-person
    # contributions once instead of materializing every epoch on each draw.
    per_run=[]
    for pair in run_pairs:
        if guard:guard()
        require(len(pair['labels'])==len(pair['candidate'])==len(pair['reference'])==len(people),'run support')
        members={p:{'candidate':[[0.0]*classes for _ in range(classes)],'reference':[[0.0]*classes for _ in range(classes)]} for p in unique}
        for index,person in enumerate(people):
            y=pair['labels'][index];require(type(y) is int and 0<=y<classes,'bootstrap class')
            for role in ('candidate','reference'):
                scores=pair[role][index];require(len(scores)==classes and all(math.isfinite(v) for v in scores),'bootstrap scores')
                prediction=max(range(classes),key=lambda k:scores[k]);members[person][role][y][prediction]+=1/counts[person]
        per_run.append(members)
    def estimate(multiplicity):
        deltas=[]
        for members in per_run:
            values={}
            for role in ('candidate','reference'):
                C=[[math.fsum(multiplicity.get(p,0)*members[p][role][a][b] for p in unique) for b in range(classes)] for a in range(classes)]
                support=list(map(sum,C))
                if not all(support):return None
                values[role]=sum(C[c][c]/support[c] for c in range(classes))/classes
            deltas.append(values['candidate']-values['reference'])
        return sum(deltas)/len(deltas)
    observed=estimate(dict.fromkeys(unique,1));values=[];undefined=[]
    for index in range(replicates):
        if guard:guard()
        draw=[rng.choice(unique) for _ in unique];mult=Counter(draw);value=estimate(mult)
        if value is None:undefined.append(index)
        else:values.append(value)
    qualified=observed is not None and len(values)>=.95*replicates
    def percentile(q):
        ordered=sorted(values);x=(len(ordered)-1)*q;i=int(x);f=x-i
        return ordered[i]*(1-f)+ordered[min(i+1,len(ordered)-1)]*f
    return {'estimate':observed,'interval':[percentile(.025),percentile(.975)] if qualified else None,
            'p_value':(1+sum(abs(x-observed)>=abs(observed) for x in values))/(len(values)+1) if qualified else None,
            'valid_replicates':len(values),'undefined_indices':undefined,'biological_N':len(unique),'conditional_on_fitted_states':True,'bootstrap_empirically_calibrated':False}


def fewshot_uncertainty(rows,seed,guard=None):
    """Resample nine people jointly across every shot/method, preserving 20 draws."""
    curves=fewshot_reduce(rows,guard);rng=random.Random(seed);replicates=[[] for _ in curves]
    for _ in range(10000):
        if guard:guard()
        draw=[rng.randrange(9) for _ in range(9)]
        for i,curve in enumerate(curves):replicates[i].append(sum(curve['people'][p] for p in draw)/9)
    result=[]
    for curve,values in zip(curves,replicates):
        ordered=sorted(values)
        def quantile(q):
            x=(len(ordered)-1)*q;i=int(x);f=x-i
            return ordered[i]*(1-f)+ordered[min(i+1,len(ordered)-1)]*f
        draw_variation=[]
        for person in range(1,10):
            v=[r['balanced_accuracy'] for r in rows if r['person']==person and r['shots']==curve['shots'] and r['method']==curve['method']]
            mu=sum(v)/20;draw_variation.append({'person':person,'calibration_draw_sample_sd':math.sqrt(sum((x-mu)**2 for x in v)/19)})
        result.append({**curve,'interval':[quantile(.025),quantile(.975)],'draw_variation':draw_variation,'bootstrap_empirically_calibrated':False})
    return result


def fewshot_paired_uncertainty(rows,seed,guard=None):
    curves=fewshot_reduce(rows,guard);by={(r['shots'],r['method']):r for r in curves}
    people={n:[a-b for a,b in zip(by[n,'REVE-Base-XFT']['people'],by[n,'REVE-Base-PT']['people'])] for n in (1,2,5,10,20)}
    rng=random.Random(seed);draws={n:[] for n in people}
    for _ in range(10000):
        if guard:guard()
        sample=[rng.randrange(9) for _ in range(9)]
        for n,v in people.items():draws[n].append(sum(v[p] for p in sample)/9)
    out=[]
    for n,v in people.items():
        ordered=sorted(draws[n])
        def q(p):
            x=(len(ordered)-1)*p;i=int(x);f=x-i
            return ordered[i]*(1-f)+ordered[min(i+1,len(ordered)-1)]*f
        out.append({'shots':n,'direction':'XFT minus PT','people':v,'mean':sum(v)/9,'interval':[q(.025),q(.975)],'biological_N':9,'draws_per_person':20,'paired_all_shots_and_methods':True,'bootstrap_empirically_calibrated':False})
    return out
