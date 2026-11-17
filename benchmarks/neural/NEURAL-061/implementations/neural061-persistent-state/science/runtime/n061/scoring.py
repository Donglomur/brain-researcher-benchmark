"""Paired, mask-exact animal evidence; no scientific scoring run in this build."""
from collections import defaultdict
from .contracts import need, HEADS, ARMS, CONTRASTS, MATCH_SEEDS, BUDGETS

def finite_mean(values):
    """Mean of finite binary64 values without an overflowing intermediate sum.

    fsum preserves ordinary cancellation accuracy. If its intermediate sum
    overflows, exact rational accumulation is used only for that exceptional
    reduction. The mathematical mean of finite values is within their range;
    no clipping, dropping, rescaling of weights or scientific exclusion occurs.
    """
    import math
    from numbers import Real
    numbers=[]
    for value in values:
        need(isinstance(value,Real) and not isinstance(value,bool),'real nonboolean mean operand')
        try: number=float(value)
        except (ValueError,OverflowError):
            need(False,'binary64 mean operand')
        need(math.isfinite(number),'finite mean operand')
        numbers.append(number)
    need(numbers,'nonempty finite mean')
    try: result=math.fsum(numbers)/len(numbers)
    except OverflowError:
        from fractions import Fraction
        result=float(sum((Fraction.from_float(x) for x in numbers),Fraction())/len(numbers))
    need(math.isfinite(result),'finite representable mean')
    return result

def arm_window_means(window_losses,arms):
    """Equal timestamps within each window, then equal windows for each arm."""
    need(window_losses,'complete session windows')
    return {arm:finite_mean(finite_mean(w[arm]) for w in window_losses) for arm in arms}

def joined_losses(target, predictions, head,required_arms=ARMS):
    import numpy as np
    from .models import loss
    need(tuple(required_arms) in (ARMS,('BR','BC')),'closed reference-six or candidate-two grammar')
    need(set(predictions)==set(required_arms),'all selected required arms before any contrast')
    ids=target['ids'];mask=np.asarray(target['mask']);y=np.asarray(target['values'])
    need(mask.dtype.kind=='b' and mask.shape==y.shape and len(ids)==len(y),'canonical masked target axis')
    need(len(set(ids))==len(ids) and mask.any(),'unique complete nonempty support')
    result={}
    for arm,row in predictions.items():
        need(row['ids']==ids and row['target_axis']==target['axis'],'no intersection/reordering/target substitution')
        p=np.asarray(row['values']);need(len(p)==len(y),'all target positions before masking')
        result[arm]=loss(y[mask],p[mask],head)
    need(all(np.isfinite(x).all() for x in result.values()),'finite full paired losses')
    return result

def session_contrasts(window_losses,contrasts=CONTRASTS):
    """Equal windows, then equal original timestamps within each window."""
    need(window_losses,'complete session windows')
    return {name:finite_mean(finite_mean(w[left]-w[right]) for w in window_losses)
            for name,left,right in contrasts}

def reduce_common(records,support,region,panel,fields):
    """One actual CommonSupport; ten seeds, then sessions, then equal animals.

    No local available-row selection is possible here. Even competence and
    mode/tool contrasts must supply every planned session/seed disposition.
    """
    from .outputs import Disposition
    support.validate();cat=support.collection.catalogue
    indexed={}
    for row in records:
        key=(row['session'],row['match_seed'])
        need(key not in indexed and row['region']==region and row['panel']==panel,'unique exact same-estimand row')
        indexed[key]=row
    need(set(indexed)=={(s,seed) for s in cat.evaluation for seed in MATCH_SEEDS},'all ten seeds and original sessions including exclusions')
    by_animal=defaultdict(list);coverage=[]
    for admitted in support.region(region):
        rows=tuple(indexed[admitted.session,seed] for seed in MATCH_SEEDS)
        need(all(r['animal']==admitted.animal and r['support'] is admitted for r in rows),'same original support and animal operand')
        need(all(r['status']==admitted.status.value for r in rows),'no independent available subset')
        coverage.append({'session':admitted.session,'animal':admitted.animal,'status':admitted.status.value,
                         'required_seeds':MATCH_SEEDS,'complete_seeds':admitted.complete_seeds,'causes':admitted.causes})
        if admitted.status is not Disposition.COMPLETE:continue
        need(all(set(r['values'])==set(fields) for r in rows),'closed complete reduced quantities')
        by_animal[admitted.animal].append({f:finite_mean(r['values'][f] for r in rows) for f in fields})
    animals={a:{f:finite_mean(s[f] for s in sessions) for f in fields} for a,sessions in sorted(by_animal.items())}
    return {'region':region,'panel':panel,'head':cat.policy.head,'budget':10,'realization':'anatomy',
            'animals':animals,'planned_animals':cat.animals,'coverage':tuple(coverage),'n_animals':len(animals),
            'means':{f:finite_mean(v[f] for v in animals.values()) if animals else None for f in fields},
            'support':support,'population_claim':False,'estimand':'equal animal, equal eligible sessions, all ten seeds; one common selected-operand support'}

def aggregate(records, expected_sessions, region, head, budget, realization, panel):
    """Matching repetitions are averaged before sessions, then before animals."""
    need(head in HEADS and budget in BUDGETS,'fixed estimator scope')
    indexed={}
    for r in records:
        key=(r['session'],r['match_seed'])
        need(key not in indexed,'unique session/sampling-seed disposition')
        need((r['region'],r['head'],r['budget'],r['realization'],r['panel'])==(region,head,budget,realization,panel),'same complete paired estimand')
        indexed[key]=r
    expected={(s,seed) for s in expected_sessions for seed in MATCH_SEEDS}
    need(set(indexed)==expected,'all sessions and seeds, unavailable included')
    by_animal=defaultdict(list);coverage=[]
    for session,animal in expected_sessions.items():
        rows=[indexed[session,seed] for seed in MATCH_SEEDS]
        need(all(r['animal']==animal for r in rows),'actual animal join')
        statuses={r['status'] for r in rows}
        if statuses!={'complete'}:
            need(statuses<={'complete','unavailable'},'failed production cannot become scientific exclusion')
            coverage.append({'session':session,'animal':animal,'status':'unavailable','seed_dispositions':rows});continue
        values={name:finite_mean(r['contrasts'][name] for r in rows) for name,_,_ in CONTRASTS}
        by_animal[animal].append(values);coverage.append({'session':session,'animal':animal,'status':'complete'})
    animals={a:{name:finite_mean(r[name] for r in v) for name,_,_ in CONTRASTS} for a,v in sorted(by_animal.items())}
    return {'region':region,'head':head,'budget':budget,'realization':realization,'panel':panel,
            'animals':animals,'coverage':coverage,'n_animals':len(animals),
            'means':{name:finite_mean(v[name] for v in animals.values()) if animals else None for name,_,_ in CONTRASTS},
            'population_claim':False,'estimand':'equal-animal mean over prespecified match-eligible sessions, conditional on realized trained policies'}

def sign_interval_and_p(values,alpha=.05):
    """Finite exact two-sided sign test and distribution-free median interval.

    No symmetry assumption for a mean sign-flip test. Mean effects are descriptive.
    Independent animal sampling is still an empirical assumption, not proven here.
    """
    import math
    from .contracts import finite
    x=sorted(finite(v) for v in values);n=len(x)
    if n<5:return {'status':'descriptive_only','n':n,'p':None,'median_interval':None}
    positive=sum(v>0 for v in x);negative=sum(v<0 for v in x);nz=positive+negative
    p=min(1.,2.*sum(math.comb(nz,j) for j in range(min(positive,negative)+1))/(2**nz)) if nz else 1.
    k=0
    for j in range(1,n//2+1):
        if 2.*sum(math.comb(n,i) for i in range(j))/(2**n)<=alpha:k=j
    interval=None if k==0 else (x[k-1],x[n-k])
    return {'status':'conditional_animal_sign_test','n':n,'nonzero':nz,'p':p,'median_interval':interval,'confidence':1-alpha}

def holm_family(rows, expected_keys):
    """All prespecified cells stay in multiplicity denominator; unavailable p=1."""
    need(set(rows)==set(expected_keys),'whole prespecified family, including absent regions')
    ordered=sorted(rows,key=lambda k:(1. if rows[k] is None else rows[k],k));m=len(ordered);previous=0.;out={}
    for i,key in enumerate(ordered):
        p=rows[key];need(p is None or 0<=p<=1,'valid finite family probability')
        adjusted=max(previous,min(1.,(m-i)*(1. if p is None else p)));previous=adjusted
        out[key]={'raw_p':p,'holm_p':adjusted,'tested':p is not None,'family_size':m}
    return out
