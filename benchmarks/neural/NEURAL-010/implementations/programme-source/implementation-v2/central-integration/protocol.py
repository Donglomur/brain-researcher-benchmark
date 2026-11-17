"""Closed metadata schemas; complete source-owned phase rosters."""
from pathlib import Path

TASK='NEURAL-010'
CONDITION='full686_monitoring_analysis_two_modes_v2'
PHASES=('fixed-authors','references','release','analysts','grade')
SCOPE={'recordings':686,'people':23,'reference_fits':9706,'reference_native_invocations':29781,
       'final_detector_outputs':92,'analyst_contexts':12,'phases':list(PHASES)}
COUNTERS=('read_bytes','write_bytes','native_cpu_seconds','native_processes','host_processes',
          'provider_requests','provider_tokens','stream_bytes','tool_processes')

def exact(v,keys):u.need(type(v)is dict and set(v)==set(keys),'closed typed metadata fields')
def same(a,b):return type(a)is type(b) and (set(a)==set(b)and all(same(a[k],b[k])for k in a)if type(a)is dict else len(a)==len(b)and all(same(x,y)for x,y in zip(a,b))if type(a)is list else a==b)
def read_pin(reader,d,cap=2097152):
    u.descriptor(d);return reader.json(d['path'],cap,u.only_pin(d))[0]
def strict_zero(v):u.need(type(v)is int and v==0,'strict observed integer-zero')
def validate_phase_response(v):
    exact(v,('authority',));u.descriptor(v['authority'])

def roster(phase,root,cap):
    u.integer(cap,1);root=u.absolute(str(root));rows=[]
    def add(role,name):rows.append({'kind':role,'path':str(root/name),'max_bytes':cap})
    if phase=='fixed-authors':
        for i in range(3):add('fixed_source_'+str(i),f'{i}/SEALED_PROGRAM.py');add('fixed_author_'+str(i),f'{i}/AUTHOR.json')
    elif phase=='references':
        add('reference_study','REFERENCE_STUDY.json');add('master','seal/MASTER.json');add('admission','seal/ADMISSION.json')
        for arm in ('candidate','signal_reference','montage_only','matched_no_eeg'):add('merged_'+arm,f'seal/{arm}.predictions.json')
    elif phase=='release':
        for role,name in [('historical','H.json'),('matched','M.json'),('envelope','ENVELOPE.json'),('release_receipt','RELEASE.json')]:add(role,name)
    elif phase=='analysts':
        for i in range(12):
            for role,name in [('submission','execution/000000/work/SUBMISSION.json'),('context','CONTEXT.json'),('view','VIEW.json'),('request','REQUEST.json'),('native','execution/000000/NATIVE.json')]:add(role+'_'+str(i),f'{i:02d}/{name}')
    else:u.need(phase=='grade','complete known phase')
    add('phase_result','RESULT.json');return rows

def limits(v,seconds):
    exact(v,('seconds',*COUNTERS));u.need(type(v['seconds'])in(int,float)and u.finite(v['seconds'])==seconds,'same original full interval')
    for k in COUNTERS:u.integer(v[k])
    return v

def review(v,args):
    exact(v,('schema','task_id','condition','campaign_request','work_sha256','program','source_manifest',
             'original_origin','scientific_deadline','final_deadline','outer_deadline','other_reserve_bytes'))
    u.need(v['schema']=='neural010-central-review-v1'and v['task_id']==TASK and v['condition']in(None,CONDITION),'exact whole programme review')
    for k in ('campaign_request','program','source_manifest'):u.descriptor(v[k])
    u.only_pin({'bytes':1,'sha256':v['work_sha256']})
    for k in ('original_origin','scientific_deadline','final_deadline','outer_deadline'):v[k]=u.finite(v[k])
    u.need(v['original_origin']<v['scientific_deadline']<=v['final_deadline']<=v['outer_deadline'],'ordered original-clock endpoints')
    u.integer(v['other_reserve_bytes']);u.need(v['other_reserve_bytes']==args['other_reserve_bytes'],'selected unrelated resource reservation')
    u.need(v['program']['path']==args['program'],'actual exact selected programme path')
    return {**v,'actual_program_path':args['program'],'actual_output_path':args['output'],'actual_review_path':args['review']}

def programme(v,review,env):
    exact(v,('schema','task_id','parent_source','run','python','analyst_config','reference_seal_settings',
             'capture_roots','protected_root','phase_roots','observation_envelopes','central_limits'))
    u.need(v['schema']=='neural010-central-programme-v1'and v['task_id']==TASK and same(v['parent_source'],env['parent_pin']),'exact original whole parent source')
    for k in ('run','python'):u.descriptor(v[k])
    u.absolute(v['protected_root']);u.need(type(v['capture_roots'])is list and 1<=len(v['capture_roots'])<=64,'complete explicitly qualified read roots')
    for root in v['capture_roots']:u.absolute(root)
    exact(v['phase_roots'],PHASES);exact(v['observation_envelopes'],PHASES)
    roots=[u.absolute(review['actual_output_path'])]
    for phase in PHASES:
        rr=v['phase_roots'][phase];exact(rr,('worker','observer','root'))
        for role in rr:roots.append(u.absolute(rr[role]))
        u.need(u.absolute(rr['root']).is_relative_to(u.absolute(v['protected_root'])),'root observations stay under selected protected root')
        ee=v['observation_envelopes'][phase];exact(ee,('worker','observer','root','output_manifest_cap'))
        u.integer(ee['output_manifest_cap'],1)
        for role in ('worker','observer','root'):
            exact(ee[role],('seconds','cleanup_seconds','stream_cap'))
            for key in ('seconds','cleanup_seconds'):u.need(u.finite(ee[role][key])>0,'positive selected observation interval')
            u.integer(ee[role]['stream_cap'],1)
    for i,a in enumerate(roots):
        for b in roots[i+1:]:u.need(a!=b and not a.is_relative_to(b)and not b.is_relative_to(a),'disjoint fresh phase/central outputs')
    cl=v['central_limits'];exact(cl,('metadata_read_bytes','metadata_write_bytes','phase_limits','combined_limits','other_reserve_bytes'))
    u.integer(cl['metadata_read_bytes'],1);u.integer(cl['metadata_write_bytes'],1)
    u.need(type(cl['other_reserve_bytes'])is int and cl['other_reserve_bytes']==review['other_reserve_bytes'],'same reviewed resource reserve')
    exact(cl['phase_limits'],PHASES);exact(cl['combined_limits'],COUNTERS)
    for k in COUNTERS:u.integer(cl['combined_limits'][k])
    seconds=review['scientific_deadline']-review['original_origin']
    for phase in PHASES:
        row=limits(cl['phase_limits'][phase],seconds)
        u.need(row['host_processes']>=1,'one actual original root process reserved')
        for k in ('provider_requests','provider_tokens','native_cpu_seconds','native_processes','tool_processes'):u.need(row[k]==0,'central does not run a separate scientific producer')
    return v

def allocation(v,run,review,c):
    cl=v['central_limits'];budget=c.Budget(review['original_origin'],cl['phase_limits'][PHASES[0]])
    u.need(same(run['original_origin'],review['original_origin'])and same(run['original_deadline'],review['scientific_deadline']),'same literal original run clock')
    for key in COUNTERS:
        amount=run['whole_limits'][key]+sum(cl['phase_limits'][ph][key]for ph in PHASES)
        if key=='read_bytes':amount+=cl['metadata_read_bytes']
        if key=='write_bytes':amount+=cl['metadata_write_bytes']
        u.need(amount<=cl['combined_limits'][key],'complete parent plus central prospective envelope')
    return budget
