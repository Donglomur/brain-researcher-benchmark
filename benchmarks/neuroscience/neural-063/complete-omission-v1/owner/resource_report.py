"""Actual bound controller cost/failure inventory and explicit missing counters.

Controller observations and trusted-stage cgroup counters are separate classes;
peaks are not summed and overlapping child CPU is never added to cgroup CPU.
Unmeasured physical I/O or failed-job token counters remain unknown.
"""
import math
from .io import Artifact, ContractError
from .scoring import finite

CONDITIONS=tuple(f'{m}-{v}-{t}' for m in ('F','I') for v in ('T','N') for t in ('G','R'))
SUM_FIELDS=('model_calls','tool_calls','trusted_capture_calls','input_tokens','output_tokens','cpu_core_seconds',
            'gpu_device_seconds','logical_read_bytes','logical_write_bytes','retained_bytes','wall_seconds')
PEAK_FIELDS=('ram_peak_bytes','vram_peak_bytes')


def aggregate(records,field,*,peak=False):
    values=[];unknown=[]
    for identity,record in records:
        value=record.get('usage',{}).get(field)
        missing=record.get('failed_usage_unknown',[])
        if missing is True or (isinstance(missing,(list,dict)) and (field in missing or 'all' in missing)):
            unknown.append(identity)
            partial=record.get('known_completed_usage',{}).get(field)
            if finite(partial) and partial>=0:values.append(float(partial))
            continue
        if not finite(value) or value<0:
            unknown.append(identity);continue
        values.append(float(value))
    try: observed=max(values,default=0) if peak else math.fsum(values)
    except (OverflowError,ValueError): observed=None
    if observed is None or not math.isfinite(observed):
        return {'status':'unavailable','value':None,'reason':'derived_resource_counter_overflow','missing':unknown}
    return {'status':'unavailable' if unknown else 'observed','value':None if unknown else observed,
            'known_observed_part':observed,'missing':unknown,'aggregation':'maximum' if peak else 'sum'}


def controllers(ctx,query_ids):
    development=ctx.read_input('development_bundle',roles={'development_bundle'},cap=1_500_000_000)
    events=ctx.read_input('event_runs',roles={'event_runs'},cap=1_500_000_000)
    narratives=ctx.read_input('narrative_receipts',roles={'narrative_receipts'},cap=100_000_000)
    if set(development.get('conditions',{}))!=set(CONDITIONS) or set(narratives.get('reports',{}))!=set(CONDITIONS):
        raise ContractError('all8 development/report cost identities required')
    selected=[]
    for condition in CONDITIONS:
        selected.append((condition,'development',None,development['conditions'][condition]['controller_receipt']))
        selected.append((condition,'report',None,narratives['reports'][condition]['controller_receipt']))
    seen=set()
    for row in events.get('records',[]):
        ident=(row.get('condition'),row.get('id'))
        if ident in seen or ident[0] not in CONDITIONS or ident[1] not in query_ids:
            raise ContractError('duplicated/extraneous event controller receipt')
        seen.add(ident);selected.append((ident[0],'event',ident[1],row['controller_receipt']))
    if seen!={(c,i) for c in CONDITIONS for i in query_ids}:
        raise ContractError('full8-by-query-event controller cost roster required')
    records=[];descriptors=set();failures=[]
    for condition,kind,event_id,raw in selected:
        ref=Artifact.parse(raw)
        if ref.role!='controller_receipt' or ref.sha256 in descriptors:
            raise ContractError('unique exact controller receipt descriptors required')
        descriptors.add(ref.sha256)
        value=ctx.store.read_json(ref.object(),roles={'controller_receipt'},cap=16_000_000)
        if (value.get('schema')!='neural063_controller_receipt_v1' or value.get('condition')!=condition or
                value.get('kind')!=kind or value.get('event_id')!=event_id or value.get('status') not in {'complete','failed'}):
            raise ContractError('actual controller usage belongs to another job')
        identity=value.get('controller')
        if not isinstance(identity,str) or not identity:raise ContractError('actual controller identity absent')
        jobs=[]
        for raw_job in value.get('job_receipts',[]):
            job_ref=Artifact.parse(raw_job)
            job=ctx.store.read_json(job_ref.object(),roles={'runtime_job_receipt'},cap=16_000_000)
            if job.get('schema')!='neural063_runtime_job_v1':raise ContractError('actual nested job usage receipt required')
            jobs.append({'receipt':job_ref.object(),'actual_record':job})
        unavailable=value.get('failed_usage_unknown',[])
        if kind=='event' and value.get('usage',{}).get('trusted_capture_calls')!=1:
            raise ContractError('every complete event must have one protected capture')
        exact_counts={'model_calls','tool_calls','trusted_capture_calls','wall_seconds'}
        unknown_fields=[k for k in (*SUM_FIELDS,*PEAK_FIELDS) if k not in exact_counts] if unavailable else []
        record={'condition':condition,'kind':kind,'event_id':event_id,'receipt':ref.object(),
                'status':value['status'],'failure':value.get('failure'),'budget':value['budget'],'usage':value['usage'],
                'failed_usage_unknown':unknown_fields,'failed_job_receipts':unavailable,
                'known_completed_usage':value['usage'],
                'unused_allocations':value.get('unused_allocations'),'actual_nested_jobs':jobs}
        records.append((identity,record))
        if value['status']!='complete':failures.append(identity)
    if len({x for x,_ in records})!=len(records):raise ContractError('controller identity reused across biological cases or conditions')
    by_condition={}
    for condition in CONDITIONS:
        subset=[r for r in records if r[1]['condition']==condition]
        by_condition[condition]={field:aggregate(subset,field) for field in SUM_FIELDS}
        by_condition[condition].update({field:aggregate(subset,field,peak=True) for field in PEAK_FIELDS})
        by_condition[condition]['controllers']=len(subset)
    totals={field:aggregate(records,field) for field in SUM_FIELDS}
    totals.update({field:aggregate(records,field,peak=True) for field in PEAK_FIELDS})
    return {'schema':'neural063_actual_resource_report_v1','query_events':len(query_ids),
            'controller_count':len(records),'expected_controller_count':16+8*len(query_ids),
            'conditions':by_condition,'runtime_controller_totals':totals,
            'controller_records':{identity:record for identity,record in records},'failed_controllers':failures,
            'common_cost_finalizer':'The signed E02 completion adds all28 trusted-stage cgroup and guardian records, including E02 itself. Its CPU class excludes daemon-owned runtime containers and is reported separately, with common/8 amortization.',
            'physical_os_io_bytes':None,'physical_os_io_status':'not measured by these logical counter interfaces; independent complete-cost audit remains required',
            'wall_policy':'sum is consumed controller-wall allocation, not elapsed parallel attempt duration',
            'peak_policy':'maximum observed peaks, never sum of RAM/VRAM peaks',
            'failure_policy':'Unknown failed counters stay null with known observed parts. No successful zero is substituted.'}


def trusted_closure(receipts,current):
    """Parent-only E02 finalization after the current worker has actually stopped."""
    stages={**receipts,'E02':current}
    if len(stages)!=28:raise ContractError('all28 actual trusted-stage receipts required for complete cost closure')
    actual={};known_cpu=0.0;unknown=[]
    for stage,record in stages.items():
        worker=record.get('worker_usage',{})
        guardian=worker.get('cgroup_guardian',{})
        cpu=guardian.get('observations',{}).get('cpu',{}).get('usage_usec')
        gu=guardian.get('process_usage',{})
        g_cpu=[gu.get('user_cpu_seconds'),gu.get('system_cpu_seconds')]
        actual[stage]={'worker_usage':worker,'parent_cleanup':record.get('runtime_parent_cleanup'),
                      'retained_outputs':record.get('retained_outputs'),'failure':record.get('failure'),
                      'proof_read_bytes':record.get('proof_read_bytes'),'journal_usage_before_receipt':record.get('journal_usage_before_receipt'),
                      'publication_observation':record.get('publication_observation',{'status':'unavailable',
                          'reason':'current E02 provisional body precedes its own commit/acknowledgement',
                          'unobserved_costs':None,'committed_authority_changed':False})}
        if type(cpu) is not int or cpu<0 or any(not finite(v) or v<0 for v in g_cpu):unknown.append(stage)
        else:known_cpu+=cpu/1000000+sum(g_cpu)
    return {'schema':'neural063_complete_trusted_resource_closure_v1','stages':actual,
            'common_observed_cpu_seconds':None if unknown else known_cpu,'known_observed_cpu_part':known_cpu,
            'missing_cpu_stages':unknown,'amortized_common_cpu_per_condition':None if unknown else known_cpu/8,
            'publication_unknown_stages':[stage for stage,record in actual.items()
                if record['publication_observation'].get('status')!='authenticated'],
            'publication_cost_policy':'Provisional, terminal publication, acknowledgement and telemetry are common controller costs, not additional candidate/scientific allocation. Authenticated observations retain wall tails and overruns; absent custody remains unknown. The current E02 commit/delivery cannot be inside its own immutable precommit body; its returned observation and independent outer cost capture remain required. Cost availability does not alter a timely committed scientific fact.',
            'physical_total_cpu_seconds':None,
            'physical_total_status':'Controller preflight, shared engine/service and physical I/O overhead need independent measurement; source counters do not fabricate a physical total.',
            'self_completion_bytes':'Excluded from self-referential counter; exact signed descriptor byte count is available to the next authorized reader.',
            'double_count_policy':'Do not add descendant reference RUSAGE counters to trusted cgroup CPU or controller nested job counters to controller totals.'}
