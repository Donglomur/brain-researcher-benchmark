"""Original Cycle geometry preparation joins; no inferred historical policies."""
from .validation import exact,need,digest,integer


def payload(value,binding):
    exact(value,('state_ids','neural_a','neural_b','muscle','phase','velocity'),'Cycle state output')
    exact(binding,('rows','bin_ms','partition_a_trials','partition_b_trials','parameters','policy_sha256'),'protected geometry policy')
    need(binding['bin_ms']==10,'published10ms trajectories')
    need(value['state_ids']==[r['id'] for r in binding['rows']],'original condition/time identity')
    a,b=binding['partition_a_trials'],binding['partition_b_trials']
    need(a and b and not set(a)&set(b),'matched disjoint original trial partitions')
    need(len(binding['rows'])==len(value['neural_a']),'complete original states')
    for row in binding['rows']:
        exact(row,('id','condition','neural_tick_ms','muscle_tick_ms','kinematic_tick_ms','partition_tick_ms','behavior_partition'),'state-clock joins')
        need(row['muscle_tick_ms']-row['neural_tick_ms']==50 and row['kinematic_tick_ms']-row['neural_tick_ms']==150 and row['partition_tick_ms']==row['neural_tick_ms'],'original muscle/kinematic latency joins')
        need(row['behavior_partition']=='A','only matched partition A drives behavior comparison')
    out=dict(binding['parameters'])
    for name in ('neural_a','neural_b','muscle','phase','velocity'):out[name]=value[name]
    need(len(out['ordering_draws'])==100000,'complete published original ordering draws; tiny primitive controls are distinct')
    return out
