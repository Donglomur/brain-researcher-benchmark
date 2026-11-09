"""Prospective full-workload resource and role configuration; no operands opened."""
from core import need,integer,finite,canonical,disjoint,descriptor,relative
from contracts import exact

RESOURCE_KEYS=('host_read_bytes','host_write_bytes','observer_read_bytes','observer_write_bytes','qualification_bytes',
 'projection_bytes','view_metadata_bytes','channel_bytes','producer_bytes','closure_bytes','operation_bytes','journal_bytes',
 'journal_event_bytes','native_inventory_bytes','whole_native_cpu_ns','whole_provider_tokens','whole_provider_calls',
 'whole_provider_money','native_operations','source_bytes','source_files','candidate_source_bytes','candidate_recipe_bytes',
 'candidate_report_bytes','reference_event_bytes','reference_journal_bytes','reference_report_bytes','reference_elements',
 'reference_work_units','reference_serialized_bytes','reference_events','reference_live_bytes','protocol_text_bytes')
PHASES=('author','f_case','i_case','reference','group')


def validate(a):
    resources=a['resources'];need(type(resources)is dict and set(resources)==set(RESOURCE_KEYS),'exact complete resource envelope')
    for key in RESOURCE_KEYS:
        if key=='whole_provider_money':need(finite(resources[key])>0,'positive actual spend ceiling')
        else:integer(resources[key],1)
    need(resources['source_bytes']<=16<<20 and resources['source_files']<=256,'bounded source graph')
    need(resources['native_operations']>=432+12,'all288 actor/144 reference cases plus12 complete aggregates')
    need(resources['journal_event_bytes']<=1<<20,'hash-chain decoder exact event cap')
    phases=a['phase_limits'];need(type(phases)is dict and set(phases)==set(PHASES),'all concrete phase limits')
    for name,v in phases.items():
        exact(v,('wall_seconds','cpu_ns','cpu_rate_ns','memory_bytes','pids','scratch_bytes','retirement_seconds',
                 'qualified_enforcement_lag_seconds','native_cpu_ns','gpu_device_seconds','provider_calls','tokens',
                 'per_response_tokens','request_bytes','response_bytes','money','steps','analysis_bytes'), 'exact phase profile')
        for k,x in v.items():
            if k in ('wall_seconds','retirement_seconds','qualified_enforcement_lag_seconds'):need(finite(x)>0,'positive time')
            elif k in ('gpu_device_seconds','money'):need(finite(x)>=0,'nonnegative allowance')
            else:integer(x,1)
        need(v['gpu_device_seconds']==0,'PAC CPU programme has no unqualified GPU use')
        need(v['cpu_ns']<=v['native_cpu_ns'],'phase fits complete episode CPU cap')
    total_cpu=0;total_operations=0
    for name in ('native_public','native_private'):
        v=a[name];need(type(v)is dict and v.get('api')=='v1.47','qualified exact Engine')
        need(v.get('clock_domain')=='qualified_shared_host_monotonic','actual host/container same clock; not inferred Mac/VM')
        image=v['image_id'];need(type(image)is str and image.startswith('sha256:')and len(image)==71
            and all(x in '0123456789abcdef' for x in image[7:]),'immutable image SHA')
        canonical(v['socket']);need(v['gpu_ids']==[],'no GPU device capability')
        output=canonical(v['output_root']);expected=canonical(a['roots']['output'] if name=='native_public' else a['roots']['private'])
        need(expected in output.parents,'role-specific native output namespace')
        need(v.get('whole_output_quota_qualified')is True and v['whole_output_quota_root']==str(output),'actual full-role hardquota')
        need(v.get('enforcement_lag_qualified')is True,'actual external enforcement-lag evidence')
        integer(v['whole_output_quota_bytes'],1);total_cpu+=integer(v['whole_cpu_ns'],1)
        total_operations+=integer(v['operations'],1)
        need(v['whole_gpu_device_seconds']==0 and v['operations']<=resources['native_operations'],'whole native allowance')
        need(v['study']==a['study_id']+'/'+name,'unique public/private study ownership labels')
        need(type(v['uid_gid'])is str and v['uid_gid']!='0:0','qualified unprivileged worker uid')
    need(total_cpu==resources['whole_native_cpu_ns'],'private/public CPU reservations sum to fullstudy cap')
    need(total_operations<=resources['native_operations'],'private/public operation ceilings within complete study cap')
    provider=a['provider'];need(provider['wire_protocol']=='neural042_chat_json_v1','qualified exact provider wire protocol')
    credential=canonical(provider['credential_path']);need(canonical(a['roots']['secrets'])in credential.parents,'host-only provider credential root')
    need(type(provider['seed_supported'])is bool and type(provider['determinism_qualified'])is bool,'honest provider seed/determinism declaration')
    for key in ('qualified_max_price_per_token','qualified_max_fee_per_request','temperature'):need(finite(provider[key])>=0,'finite provider cost/temperature')
    for key in ('token_bound_per_utf8_byte','token_bound_fixed_overhead'):integer(provider[key],0 if key.endswith('overhead') else 1)
    need(type(a['method_admissions'])is dict and a['method_admissions'],'explicit fixed dynamic-review paths')
    for name,path in a['method_admissions'].items():need(type(name)is str and str(relative(path)).startswith('methods/'),'protected exact method namespace')
    need(type(a['host_environment'])is dict and all(type(k)is str and type(v)is str for k,v in a['host_environment'].items()),'explicit host environment')
    canonical(a['host_python']);need(a['host_environment'].get('PYTHONHASHSEED')=='0','explicit reproducible hash setting')
    prep=a['preparation']
    exact(prep,('clinical_review','clinical_review_bytes','identity_key','control_seed','prestudy_control_seed_commitment','protocol','native_limits','planned_working_array_bytes','prepared_array_bytes'),'exact original preparation selection')
    exact(prep['clinical_review'],('path','pin'),'exact clinical review descriptor');relative(prep['clinical_review']['path']);descriptor(prep['clinical_review']['pin']);descriptor(prep['protocol'])
    for key in ('clinical_review_bytes','planned_working_array_bytes','prepared_array_bytes'):integer(prep[key],1)
    commitment=prep['prestudy_control_seed_commitment'];need(type(commitment)is str and len(commitment)==64 and all(c in '0123456789abcdef'for c in commitment),'private pre-study controlseed SHA')
    limits=prep['native_limits'];exact(limits,('max_axis','max_chunk_bytes','max_array_elements','total_elements','max_text_bytes','max_array_bytes'),'all bounded HDF5 limits')
    for v in limits.values():integer(v,1)
    return a
