"""Prospective full-workload capacity checks; no small-run substitute."""
from .core import need,Budget
def validate(profile):
    need(profile['scope']=={'people':10,'arms':3,'roles':4,'query_shape':[200,17,100]},'full scope')
    configs=profile['trial_configs'];need(type(configs)is list and 1<=len(configs)<=8,'finite predeclared candidates')
    K=len(configs);R=profile['investigator_policy']['max_rounds']
    need(type(R)is int and 2<=R<=16,'finite investigator inspection/finalization rounds')
    contexts=270*K+30;fit_query=2940+1080*K
    frounds=profile['F_authoring_rounds'];need(type(frounds)is int and 1<=frounds<=contexts*R,'F matched model-call ceiling')
    calls=frounds+contexts*R;operations=12+fit_query+frounds+contexts*(2*R-1)
    need(profile['investigator_contexts']==contexts and profile['fit_predict_processes']==fit_query,'full graph capacity identity')
    for name in ('whole_wall_ns','case_wall_ns','case_controller_cpu_ns','whole_disk_reservation_bytes','logical_source_input_retention_bytes','terminal_ns','case_terminal_ns','programme_terminal_bytes','case_terminal_bytes'):
        need(type(profile[name])is int and profile[name]>0,'finite positive complete capacity')
    need(set(profile['whole_limits'])==set(Budget.KEYS) and set(profile['case_limits'])==set(Budget.KEYS),'complete cost dimensions')
    for values in (profile['whole_limits'],profile['case_limits']):
        need(all(type(v)is int and v>0 for v in values.values()),'positive finite budgets')
    need(profile['whole_limits']['process_starts']>=operations and profile['whole_limits']['fits']>=fit_query//2
         and profile['whole_limits']['model_calls']>=calls,'no truncated fit/model/process capacity')
    tokens=profile['investigator_policy']['tokens_per_round']
    need(all(type(tokens[k])is int and tokens[k]>0 for k in ('input','output')),'positive provider token ceilings')
    for key in ('input','output'):
        ceiling=contexts*R*tokens[key]
        need(profile['F_authoring_tokens'][key]==ceiling,'equal available whole-role token budgets')
        need(profile['whole_limits'][key+'_tokens']>=2*ceiling,'both full role ceilings')
    need(profile['whole_wall_ns']>profile['terminal_ns'] and profile['case_wall_ns']>profile['case_terminal_ns'],'reserved terminal intervals')
    need(profile['programme_terminal_bytes']>=65536 and profile['case_terminal_bytes']>=8192,'bounded complete cost slots')
    need(profile['runtime']['terminal_bytes']>=65536 and profile['runtime']['terminal_ns']>0,'reserved operation terminal')
    need(profile['outer']['terminal_file_bytes']>=max(2*profile['programme_terminal_bytes']+65536,profile['runtime']['terminal_bytes']),'external terminal recapture cap')
    # Each operation retains its output cap and two original stream caps. Exact
    # input/model/runtime extents and operator packet copies are additional.
    runtime=profile['runtime']
    retention=operations*(runtime['output_bytes']+2*runtime['stream_bytes']+runtime['terminal_bytes'])+profile['logical_source_input_retention_bytes']+2*profile['programme_terminal_bytes']+20*profile['case_terminal_bytes']
    need(profile['whole_disk_reservation_bytes']>=retention,'complete conservative retained-output reservation')
    need(profile['whole_limits']['written']>=retention,'whole output/input-copy write capacity')
    need(profile['case_limits']['written']>=profile['case_terminal_bytes'],'reserved per-case evidence share')
    per_case_pairs=27*K+3;per_case_calls=(27*K+3)*R
    need(profile['case_limits']['fits']>=per_case_pairs and
         profile['case_limits']['process_starts']>=2*per_case_pairs+(27*K+3)*(2*R-1)
         and profile['case_limits']['model_calls']>=per_case_calls,'same complete I-capable per-case ceiling also assigned F')
    return {'K':K,'R':R,'I_contexts':contexts,'fit_predict_processes':fit_query,
            'maximum_controlled_processes':operations,'maximum_provider_calls':calls,
            'conservative_retention_bytes':retention,'measured_capacity':False}

