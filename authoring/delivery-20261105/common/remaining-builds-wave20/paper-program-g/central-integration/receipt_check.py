"""Source-only post-dispatch metadata admission; never opens numerical artifacts.

Inner observed controller closure is distinct from the central entry's later
external natural exit. This module never manufactures that external proof.
"""
import hashlib,json,math
from pathlib import Path
TASK='PAPER-FIND-036'


def need(ok,message):
    if not ok:raise ValueError(message)


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def bare(d):return {k:d[k]for k in('bytes','sha256')}


def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(rows):
        v={}
        for k,x in rows:need(k not in v,'unique metadata keys');v[k]=x
        return v
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'finite metadata'))


def equal(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return set(a)==set(b) and all(equal(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b) and all(equal(x,y)for x,y in zip(a,b))
    return a==b


def finite(t):return type(t)in(int,float) and math.isfinite(t)


def validate(result,outer,dispatch,derived,collection,commitment,bound,q,op,env,origin,out,original_validate):
    work_end=origin+op['controller_limits']['wall_seconds'];end=origin+env['outer_limits']['wall_seconds']
    source=pin(q['parent_manifest']);control=out/'observer';work=out/'work'
    need(set(result)=={'observation','post_durability','original_deadline','success','persistence_error','independent_root_terminal_admission_still_required'},'exact original observer return ABI')
    need(result['success']is True and result['persistence_error']is None and result['independent_root_terminal_admission_still_required']is True,'successful provisional observer only')
    need(finite(result['post_durability']) and origin<=result['post_durability']<end
         and equal(result['original_deadline'],end),'same original outer return clock')
    need(outer['schema']=='foraging_outer_observation_v1' and outer['task_id']==TASK,'exact original observation')
    for k in ('natural_exit','owned_group_absent','streams_eof','collection_durable_before_deadline'):need(outer[k]is True,'observed original closure '+k)
    need(type(outer['exit_code'])is int and outer['exit_code']==0 and type(outer['controller_pid'])is int and outer['controller_pid']>0,'typed natural controller exit')
    need(outer['error']is None and outer['runtime_qualified']is False and outer['scientific_qualified']is False
         and outer['resource_custody']=='all1320recordedclosures','no qualification or custody promotion')
    need(equal(outer['source'],source) and equal(outer['original_origin'],origin)
         and equal(outer['original_deadline'],work_end) and equal(outer['outer_deadline'],end),'exact source and original clocks')
    times=[outer[k]for k in('collection_post_durability','natural_exit_observed_at','outer_before_final_persistence')]
    need(all(finite(x)for x in times) and origin<=times[0]<=times[1]<work_end
         and times[1]<=times[2]<=result['post_durability']<end,'ordered durable controller and observer timings')
    need(equal(outer['stderr'],pin(b'')),'original controller reported silent stderr')
    need(equal(outer['root_envelope'],pin(encode(env))) and equal(outer['root_controller_selection'],pin(encode(op))),'first source relocation identities')
    expected={**op,'root_source':str(control/'source'),
              'source_manifest':{'path':str(control/'source/SOURCE_MANIFEST.json'),**source}}
    need(equal(derived,expected),'unchanged second source-only relocation, all other fields literal')
    dp=pin(encode(derived));need(equal(outer['derived_selection'],dp),'second captured selection pin')
    want={'schema':'foraging_outer_dispatch_v1','root_envelope':{'path':str(out/'OBSERVER_ENVELOPE.json'),**pin(encode(env))},
          'root_controller_selection':pin(encode(op)),'derived_selection':dp,'source':source,
          'only_delta':['root_source','source_manifest.path'],'original_origin':origin,
          'original_deadline':work_end,'outer_deadline':end,'no_retry':True}
    need(equal(dispatch,want),'literal unchanged original observer dispatch')
    original_validate(collection,source,origin,work_end)
    need(collection['private_grade_called']is False and collection['runtime_qualified']is False
         and collection['scientific_qualified']is False and collection['full_paper_reproduction']is False,'ungraded original collection')
    need(collection['operation_id']==op['operation_id'] and equal(collection['model_cap_bytes'],op['model_cap_bytes']),'full original operation identity and model domain')
    need(equal(collection['prepared_admission'],bare(op['prepared_authority']))
         and equal(collection['paper_admission'],bare(op['paper_material_admission'])),'selected preparation and paper metadata only')
    need(Path(outer['collection']['path'])==work/'COLLECTION.json'
         and equal(bare(outer['collection']),pin(encode(collection))),'exact original collection location/content')
    need(Path(collection['commitment']['path'])==work/'COMMITMENT.json'
         and equal(bare(collection['commitment']),pin(encode(commitment))),'exact global commitment location/content')
    need(commitment['schema']=='foraging_global_four_program_freeze_v1' and commitment['task_id']==TASK
         and equal(commitment['pair'],bound['pair']) and commitment['all_four_before_numeric_views']is True
         and commitment['independent_context_history_is_external_attestation']is True
         and commitment['no_scientific_qualification']is True,'original four-program-before-numerical commitment')
    need(set(commitment['programs'])=={'A','B'},'both complete access arms')
    for arm in ('A','B'):
        need(set(commitment['programs'][arm])=={'native','improvement'},'two independent purposes per arm')
        for purpose in ('native','improvement'):
            expected={'path':str(work/'programs'/arm/(purpose+'.py')),**bare(bound['programs'][arm][purpose]['program'])}
            need(equal(commitment['programs'][arm][purpose],expected),'same authenticated frozen candidate source')
    previous=origin;names=set()
    for context,phase in zip(collection['contexts'],collection['phases']):
        need(previous<=phase['started']<=phase['finished'],'serial complete phase custody');previous=phase['finished']
        closures=phase['closures'];need(sorted(c['kind']for c in closures)==['container','container','volume'],'all resource kinds')
        local=[c['name']for c in closures];need(all(type(n)is str and n for n in local) and len(set(local))==3 and not names.intersection(local),'fresh transitive resource identities')
        names.update(local)
        # The parent complete validator is reused, with typed command/exit checks
        # added here; no original scientific artifact or scorer is invoked.
        need(equal(phase['natural_exit'],{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}),'typed native exit fields')
        for cmd in phase['command_records']:
            need(type(cmd['returncode'])is int and cmd['returncode']==0 and cmd['error_type']is None,'every managed CLI natural success')
            need(all(cmd[k]is True for k in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'))
                 and cmd['leader_exited_with_group_alive']is False and cmd['group_probe_or_cleanup_error']is None,'complete independent CLI custody')
            need(type(cmd['materialized_pipe_bytes'])is int and type(cmd['observed_retained_bytes'])is int
                 and cmd['materialized_pipe_bytes']>=cmd['observed_retained_bytes']>=0,'typed bounded CLI observations')
        d=phase['artifacts'];need(type(d['bytes'])is int and 0<d['bytes']<=context['output_bytes']
             and (context['kind']=='fit' or d['bytes']==context['output_bytes']),'full original artifact extents, never contents')
    need(finite(collection['before_final_persistence']) and previous<=collection['before_final_persistence']<=times[0]<work_end,'whole collection durability order')
    return {'sessions':40,'outer_folds':200,'phases':1320,'native_phases':120,'fit_phases':600,'predict_phases':600,
            'candidate_programs':4,'original_parent_collection_validator_reused':True,
            'prepared_roster_and_numerical_outputs_not_reopened':True,'protected_grade_called':False,
            'external_central_entry_natural_zero_still_required':True}


def capture_and_validate(io,out,result,bound,q,op,env,origin,original_validate):
    cap=env['metadata_cap_bytes'];control=out/'observer';work=out/'work'
    need(type(result)is dict and type(result.get('observation'))is dict,'original successful observation descriptor')
    outer=parse(io.capture(control/'OUTER.json',result['observation'],cap))
    dispatch=parse(io.capture(control/'DISPATCH.json',cap=cap))
    derived=parse(io.capture(control/'DERIVED_SELECTION.json',outer['derived_selection'],cap))
    need(Path(outer['collection']['path'])==work/'COLLECTION.json','fixed collection before capture')
    collection=parse(io.capture(work/'COLLECTION.json',outer['collection'],cap))
    need(Path(collection['commitment']['path'])==work/'COMMITMENT.json','fixed commitment before capture')
    commitment=parse(io.capture(work/'COMMITMENT.json',collection['commitment'],cap))
    summary=validate(result,outer,dispatch,derived,collection,commitment,bound,q,op,env,origin,out,original_validate)
    for arm in ('A','B'):
        for purpose in ('native','improvement'):
            d=commitment['programs'][arm][purpose]
            io.capture(d['path'],d,8*1024**2)
    return summary
