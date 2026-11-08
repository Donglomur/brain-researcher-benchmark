"""Source-owned complete held-person HMP summaries for postseal explanations."""
import math
from .common import need,finite,pin

def describe(values):
    if not values:return {'n':0,'mean':None,'minimum':None,'maximum':None,'population_sd':None}
    for x in values:finite(x)
    mean=math.fsum(values)/len(values)
    return {'n':len(values),'mean':mean,'minimum':min(values),'maximum':max(values),
        'population_sd':math.sqrt(math.fsum((x-mean)**2 for x in values)/len(values))}

def hmp_summaries(tool,person):
    out=[]
    for evaluation in tool['evaluations']:
        if evaluation['support']!='held':continue
        k=evaluation['events'];entropies=[[] for _ in range(k)];mass=[];delta=[];timing=[[] for _ in range(k)];failures=[]
        for row in evaluation['rows']:
            if row['log_mass'] is not None:mass.append(finite(row['log_mass']))
            if row['log_mass_delta_ordinary_minus_zero'] is not None:delta.append(finite(row['log_mass_delta_ordinary_minus_zero']))
            if row['times_ms'] is not None:
                for j,t in enumerate(row['times_ms']):
                    if t is not None:timing[j].append(finite(t))
            if row['marginals'] is not None:
                array=row['marginals'];n=row['samples'];need(array['shape']==[n,k] and len(array['values'])==n*k,'complete marginal sample/event geometry')
                for j in range(k):
                    values=[array['values'][t*k+j] for t in range(n)]
                    if any(x is None for x in values):continue
                    need(all(finite(x)>=0 for x in values),'nonnegative model posterior')
                    total=math.fsum(values)
                    if total<=0:continue
                    # Exact delivered posterior normalized for descriptive entropy;
                    # no replacement of the source posterior/scientific likelihood.
                    ps=[x/total for x in values];entropies[j].append(-math.fsum(p*math.log(p) for p in ps if p>0))
            if row['status']!='complete':failures.append({'epoch':row['epoch'],'status':row['status'],'failure':row['failure']})
        out.append({'person':person,'events':k,'gain':evaluation['gain'],'support':'held','n_trials':len(evaluation['rows']),
            'source_state_pin':evaluation['state_pin'],'source_evaluation_pin':pin(evaluation,128*1048576),
            'groups':evaluation['groups'],'log_mass_nats':describe(mass),'ordinary_minus_zero_log_mass_nats':describe(delta),
            'event_times_ms':[describe(x) for x in timing],'within_model_event_entropy_nats':[describe(x) for x in entropies],
            'failures':failures,'timing_is_cognitive_ground_truth':False,'entropy_is_calibrated_biological_uncertainty':False})
    need(len(out)==6,'all three counts by ordinary/zero on held person');return out
