"""Paired arm effects with failed attempts included, no population significance claim."""
from .guard import need,encoded,bare

def compare(records):
    need(bool(records),'predeclared attempt pairs required');seen=set();deltas=[];rows=[]
    for pair in records:
        need(pair['pair_id'] not in seen,'no duplicate attempt pair');seen.add(pair['pair_id'])
        a,b=pair['A'],pair['B']
        need(a['common_inputs']==b['common_inputs'] and a['budget_identity']==b['budget_identity'],'matched input and resource identity')
        need(a['independent_fresh_workspace'] is True and b['independent_fresh_workspace'] is True,'no cross-arm answers/cache')
        need(a['arm']=='A' and b['arm']=='B','fixed code-access labels')
        complete=a['status']==b['status']=='complete_numerical_comparison'
        delta=b['balanced_RSA_MAE']-a['balanced_RSA_MAE'] if complete else None
        if delta is not None:deltas.append(delta)
        rows.append({'pair_id':pair['pair_id'],'A':a,'B':b,'B_minus_A_error':delta})
    return {'paired_records':rows,'attempt_pairs':len(rows),'complete_pairs':len(deltas),'complete_pair_mean_error_delta':sum(deltas)/len(deltas) if deltas else None,'failure_pairs_retained':len(rows)-len(deltas),'failure_penalty_score':None,'population_effect_qualified':False,'source_record_pin':bare(encoded(records))}
