"""Complete independent step metadata contract, separate from numeric LR arithmetic."""
from .errors import require
from .objects import fields,canonical,digest
STEP_FIELDS=('microbatch','optimizer_before','optimizer_after','scheduler_before','scheduler_after','rank','accumulation_index','overflow_skipped','lr_applied','windows','patches','samples','people_support','state_pin','state_before')
CENSUS_FIELDS=('independent_source','source','configuration','environment','resume','rank_count','ranks','expected_steps','ordered_keys','parameter_groups','start_states','end_states','total_updates','total_windows','total_patches','total_samples')
def validate_census(trace,profile,census,rank_exposure,guard=None):
    fields(census,CENSUS_FIELDS)
    require(census['independent_source'],'independent complete schedule census')
    require(all(census[k]==profile[k] for k in ('source','configuration','environment','resume','rank_count')),'schedule original source/resume binding')
    ranks=list(range(profile['rank_count']))
    require(census['ranks']==ranks and census['parameter_groups'],'complete rank/group definitions')
    expected=census['expected_steps'];ordered=census['ordered_keys']
    require(len(trace)==len(expected)==len(ordered)>0,'complete step support including endpoints')
    require(len({tuple(x) for x in ordered})==len(ordered),'duplicate planned step key')
    actual=[];seen={r:[] for r in ranks}
    for i,(row,want) in enumerate(zip(trace,expected)):
        if guard:guard()
        fields(row,STEP_FIELDS);fields(want,STEP_FIELDS)
        key=[row['rank'],row['microbatch']];require(key==ordered[i],'original complete ordered rank/microbatch census')
        require(row['rank'] in seen,'unexpected rank')
        # LR values are numerically checked separately; all other facts are exact.
        require(all(row[k]==want[k] for k in STEP_FIELDS if k!='lr_applied'),'original update/exposure/state trajectory mismatch')
        require(len(row['lr_applied'])==len(want['lr_applied'])==len(census['parameter_groups']),'complete optimizer parameter-group LR vector')
        require(all(type(row[k])is int and row[k]>=0 for k in ('windows','patches','samples')) and row['people_support'] and row['state_pin'] and row['state_before'],'complete nonnegative exposure/state identity')
        actual.append(key);seen[row['rank']].append(row)
    require(all(seen.values()),'every selected rank must appear')
    fields(rank_exposure,('ranks','ordered_keys','resume','start_states','end_states','total_updates','total_windows','total_patches','total_samples'))
    require(all(rank_exposure[k]==census[k] for k in rank_exposure),'complete declared rank/resume/exposure census')
    for rank,rows in seen.items():
        if guard:guard()
        start=census['start_states'][str(rank)];end=census['end_states'][str(rank)]
        fields(start,('microbatch','optimizer','scheduler','state_pin'));fields(end,('microbatch','optimizer','scheduler','state_pin'))
        require([rows[0]['microbatch'],rows[0]['optimizer_before'],rows[0]['scheduler_before']]==[start['microbatch'],start['optimizer'],start['scheduler']],'original first counters')
        require([rows[-1]['microbatch'],rows[-1]['optimizer_after'],rows[-1]['scheduler_after'],rows[-1]['state_pin']]==[end['microbatch'],end['optimizer'],end['scheduler'],end['state_pin']],'original final counters/state')
        require(rows[0]['state_before']==start['state_pin'],'original first state lineage')
        require(all(a['state_pin']==b['state_before'] for a,b in zip(rows,rows[1:])),'complete consecutive state lineage')
        require(sum(r['optimizer_after']-r['optimizer_before'] for r in rows)==census['total_updates'][str(rank)],'per-rank complete update total')
        for field,total in (('windows','total_windows'),('patches','total_patches'),('samples','total_samples')):
            require(sum(r[field] for r in rows)==census[total][str(rank)],'per-rank complete exposure total')
        if profile['resume']:
            require(profile['resume']['rank_states'][str(rank)]==start,'exact resume start state')
        else:require(start['state_pin'],'original initial state')
    return {'independent_census':digest(canonical(census)),'entries':len(trace),'ranks':ranks,'complete_ordered_support':True,'numeric_LR_checked_separately':True}
