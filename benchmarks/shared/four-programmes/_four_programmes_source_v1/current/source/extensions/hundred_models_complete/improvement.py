"""Prospective paired RSA improvement on independently admitted people/stimuli.

Never use the published panels for a frontier claim. Inputs are full pair vectors;
bootstrap biological units, not independent RDM-pair observations or layer choices.
"""
import math
from .guard import need,Unscorable,encoded,bare
from .endpoints import improvement_admission
from .consumer_production import load_numerical

def evaluate(package,protocol,records,draws,qualification,budget):
    improvement_admission(protocol)
    need(qualification.get('independent_test_qualified') is True,'future independent biological panel qualification required')
    need(qualification['protocol']==bare(encoded(protocol)) and qualification['records']==bare(encoded(records)),'exact frozen improvement protocol and private evidence')
    subjects=protocol['private_panel']['subjects'];stimuli=protocol['private_panel']['stimuli'];rois=protocol['rois'];models=protocol['model_pairs'];n=len(stimuli)
    need(len(subjects)==len(set(subjects))>=3 and n==len(set(stimuli))>=4,'independent complete biological axes')
    expected=[(m,r) for m in models for r in rois]
    need([(x['model_pair'],x['roi']) for x in records]==expected,'complete preregistered model/ROI comparisons')
    need(protocol['primary_metric']=='macro_signed_spearman_delta' and protocol['layer_choice']=='development_frozen','one fixed metric and no private layer/model selection')
    population=protocol['generalization_population'];ppl=population in ('new_people','new_people_and_stimuli');stm=population in ('new_stimuli','new_people_and_stimuli')
    plan=protocol['uncertainty_plan'];need(plan['method']=='paired_biological_percentile_bootstrap' and plan['stimulus_diagonal_policy']=='exclude_duplicate_original_identity','explicit supported biological uncertainty estimator')
    need(len(draws)==plan['replicates'] and len(draws)>=1000,'full preregistered uncertainty schedule')
    need(protocol['multiplicity_plan']['method']=='predeclared_family_alpha' and 0<protocol['multiplicity_plan']['family_alpha']<1,'explicit multiplicity allocation')
    pairs=[(i,j) for i in range(n) for j in range(i+1,n)];lookup={p:k for k,p in enumerate(pairs)}
    for row in records:
        need(row['subjects']==subjects and row['stimuli']==stimuli,'same paired biological identities')
        for name in ('brain','baseline','candidate'):
            values=row[name];need(len(values)==len(subjects) and all(len(x)==len(pairs) for x in values),'complete people by full pair geometry')
            need(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=2 for x in values for v in x),'finite correlation distances')
    numerical=load_numerical(package);budget.charge('work',plan['maximum_numeric_work'])
    nb=numerical.Budget(max_work=plan['maximum_numeric_work'],max_elements=plan['maximum_numeric_elements'],deadline_ns=budget.deadline_ns)
    def statistic(person_indices,stimulus_indices):
        indices=[lookup[tuple(sorted((stimulus_indices[i],stimulus_indices[j])))] for i in range(n) for j in range(i+1,n) if stimulus_indices[i]!=stimulus_indices[j]]
        if len(indices)<3:return None
        deltas=[]
        for row in records:
            people=[]
            for person in person_indices:
                brain=[row['brain'][person][k] for k in indices]
                baseline=numerical.spearman([row['baseline'][person][k] for k in indices],brain,budget=nb)
                candidate=numerical.spearman([row['candidate'][person][k] for k in indices],brain,budget=nb)
                if baseline is None or candidate is None:return None
                people.append(candidate-baseline)
            deltas.append(sum(people)/len(people))
        return sum(deltas)/len(deltas)
    observed=statistic(list(range(len(subjects))),list(range(n)));distribution=[]
    for draw in draws:
        pi=draw['people'];si=draw['stimuli']
        need(len(pi)==len(subjects) and all(type(i)is int and 0<=i<len(subjects) for i in pi),'full participant bootstrap draw')
        need(len(si)==n and all(type(i)is int and 0<=i<n for i in si),'full stimulus bootstrap draw')
        need(ppl or pi==list(range(len(subjects))),'fixed people for stimulus-only population')
        need(stm or si==list(range(n)),'fixed stimuli for people-only population')
        distribution.append(statistic(pi,si));budget.check()
    if observed is None or None in distribution:return {'status':'required_unscorable','gate':'G18','observed':observed,'bootstrap':distribution,'reason':'Undefined complete statistic; no dropped draws or units','scientific_qualification':False}
    ordered=sorted(distribution);alpha=protocol['multiplicity_plan']['family_alpha']
    def quantile(p):
        at=p*(len(ordered)-1);lo=int(at);hi=math.ceil(at);return ordered[lo]+(ordered[hi]-ordered[lo])*(at-lo)
    return {'status':'future_independent_panel_estimate_unqualified','generalization_population':population,'observed_delta':observed,'bootstrap':distribution,'percentile_interval':[quantile(alpha/2),quantile(1-alpha/2)],'subject_count':len(subjects),'stimulus_count':n,'draw_schedule':bare(encoded(draws)),'numeric_budget':nb.observation(),'scientific_qualification':False,'SOTA_claim':False}
