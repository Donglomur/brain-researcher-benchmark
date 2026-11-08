"""Distinct post-exit caller: full-source replay and actual terminal primitives."""
import dataclasses
from pathlib import Path

FIELDS={'schema','status','task_id','run_id','central_source','source_closure_digest','program_pin','mode','origin_ns',
        'deadline_ns','host_identity','files','phase_count','phase_head','phase_counts','parent_entry_calls',
        'parent_controller_executions','external_numerical_grader_calls','publication_started_ns',
        'logical_metadata_costs','routing','scientific_qualification_claim','physical_qualification_claim','new_canonical_ids'}

def summary_join(summary,env,operands):
    job=operands['job']
    u.need(type(summary)is dict and set(summary)==FIELDS and summary['schema']=='paper020_central_provisional_v1'
           and summary['status']=='provisional_pending_external_natural_exit'
           and summary['task_id']=='PAPER-ROOT-ADD-020' and summary['run_id']==job['run_id']
           and summary['central_source']==env['source_pin'] and summary['program_pin']==operands['program_pin']
           and summary['source_closure_digest']==u.sha(u.canonical(env['source_rows']))
           and summary['mode']==job['mode'] and summary['origin_ns']==job['origin_ns'] and summary['deadline_ns']==job['deadline_ns'],
           'exact central/source/job/original-clock provisional join')
    for k in ('phase_count','parent_entry_calls','parent_controller_executions','external_numerical_grader_calls','new_canonical_ids'):
        u.need(type(summary[k])is int,'typed exact central cardinalities')
    u.need(summary['phase_count']==23786 and summary['parent_entry_calls']==summary['parent_controller_executions']==1
           and summary['external_numerical_grader_calls']==summary['new_canonical_ids']==0
           and summary['scientific_qualification_claim']is False and summary['physical_qualification_claim']is False
           and set(summary['files'])=={'phases.jsonl','artifacts.json','inner.json'},'complete one-entry provisional envelope')
    u.need(type(summary['publication_started_ns'])is int and job['origin_ns']<=summary['publication_started_ns']<job['deadline_ns'],
           'publication belongs to original strict clock')
    costs=summary['logical_metadata_costs'];u.need(type(costs)is dict and costs.get('physical_accounting')is False,'logical costs cannot impersonate OS evidence')
    for k in ('logical_read_reserved','logical_read_observed','logical_write_bytes','hash_input_bytes'):
        u.need(type(costs.get(k))is int and costs[k]>=0,'typed retained central cost evidence')
    u.need(costs['logical_read_reserved']<=job['metadata_limits']['read_bytes']
           and costs['logical_read_observed']<=costs['logical_read_reserved']
           and costs['logical_write_bytes']<=job['metadata_limits']['write_bytes'],'central logical bound differs')

def terminal_join(first,t,summary,provisional,document):
    origin,deadline=summary['origin_ns'],summary['deadline_ns'];expected=u.sha(u.canonical(provisional))
    u.need(t['natural_complete']is True and t['all_descendants_closed']is True and type(t['exit_code'])is int and t['exit_code']==0
           and not t['failures'] and t['host_identity']==summary['host_identity'] and t['host_identity']!=t['observer_identity']
           and t['observer_identity']==first['observer_identity'] and t['host_finished_ns']==first['host_finished_ns']
           and t['child_ledger_digest']==first['child_ledger_digest']
           and t['full_result_digest']==first['full_result_digest']==expected
           and t['origin_ns']==first['origin_ns']==origin and t['deadline_ns']==first['deadline_ns']==deadline
           and provisional['result']['finished_ns']<=summary['publication_started_ns']<=t['host_finished_ns']
           <=first['observed_ns']<=t['observed_ns']<deadline,
           'same naturally exited host and entire immutable central bundle required')
    for key in ('read_bytes','write_bytes','retained_bytes','live_bytes','cpu_ns','memory_peak_bytes'):
        u.need(type(t['resources'][key])is int and 0<=t['resources'][key]<=document['terminal_profile'][key], 'complete terminal physical cap')
        if key not in ('live_bytes','memory_peak_bytes'):
            u.need(t['resources'][key]>=first['resources'][key],'terminal lifetime accounting regressed')

def observe(env,reader,operands,output,route,expected_command):
    root=u.components(output);job=operands['job'];d=operands['runtime_document']
    summary,spin=reader.json(root/'summary.json',131072);summary_join(summary,env,operands)
    expected_writes=sum(m.size_bytes for m in env['parent']['members'])+sum(u.only_pin(p)['bytes']for p in summary['files'].values())+spin['bytes']
    u.need(summary['logical_metadata_costs']['logical_write_bytes']==expected_writes,'entire staged/journal/artifact/inner/summary write charge required')
    # Rebind the actual original run command; this observer does not dispatch it.
    old=summary['routing'];u.need(type(old)is dict and old.get('current_request_and_work_rechecked_before_launch')is True,
                                'original pre-dispatch route receipt required')
    for key,value in route.items():
        if key!='metadata_read_charge_bytes':u.need(old.get(key)==value,'original routing/exposure metadata differs from current selection')
    u.need(old.get('invocation')==u.pin(env['gate'].encode({'argv':expected_command,'working_directory':str(env['repo'])})),
           'exact original registered run invocation differs')
    files=summary['files'];raw=reader.read(root/'phases.jsonl',job['metadata_limits']['trace_bytes'],files['phases.jsonl'])
    index,_=reader.json(root/'artifacts.json',job['metadata_limits']['artifact_index_bytes'],files['artifacts.json'])
    provisional,_=reader.json(root/'inner.json',67_108_864,files['inner.json'])
    # Reimport the exact staged source only after current fixed/source/job gates.
    entry=env['dispatch'].load_adapter(env,reader,root/'source-stage')
    u.need(provisional.get('host_identity')==summary['host_identity'],'same actual central and scientific host required')
    validated=env['transcript'].validate(entry,operands['contract'],d,provisional,raw)
    u.need(summary['phase_head']==validated['head'] and summary['phase_counts']==validated['counts'],'full actual phase counts/head differ')
    artifacts=env['artifacts'].validate(index,validated,d,reader)
    # This executes the captured original complete grade/cardinality/terminal
    # admission. It does not execute the scientific controller or numerical grade.
    inner=entry.accept_external_terminal(operands['runtime_envelope'],operands['public_key'],provisional)
    u.need(inner['status']=='complete_physical_execution' and inner['result']==provisional['result'],'actual parent terminal admission required')
    package=entry.__package__;import importlib
    host=importlib.import_module(package+'.host_observer');process=importlib.import_module(package+'.process_control')
    authority=entry.Authority(operands['runtime_envelope'],operands['public_key'])
    value=dict(d['host_accounting']);value['process']=entry._qualification(value['process']);q=host.HostQualification(**value)
    transport=process.SubprocessCommandTransport(q.process,authority.process_qualification)
    observer=host.ExternalHostTerminalObserver(q,transport,authority.process_qualification,complete_profile=d['terminal_profile'])
    seals={'central_summary':spin['sha256'],'phase_transcript':files['phases.jsonl']['sha256'],
           'artifact_index':files['artifacts.json']['sha256'],'central_source':env['source_pin']['sha256'],
           'source_closure':summary['source_closure_digest']}
    terminal=observer.observe_terminal(summary['host_identity'],job['origin_ns'],job['deadline_ns'],
                 u.sha(u.canonical(provisional)),expected_bundle_digests=seals)
    t=dataclasses.asdict(terminal);first=inner['external_terminal_evidence']
    terminal_join(first,t,summary,provisional,d)
    # Captured bytes/immutable terminal proof bind the complete output; an
    # external observer's own eventual exit is not asserted by this live call.
    finished=reader.tick()
    return {'schema':'paper020_central_external_admission_v1','status':'subject_natural_completion_admitted',
        'task_id':'PAPER-ROOT-ADD-020','summary_pin':spin,'phase_count':23786,'artifact_evidence':artifacts,
        'parent_terminal':first,'complete_bundle_terminal':t,'source_closure_digest':summary['source_closure_digest'],
        'origin_ns':job['origin_ns'],'deadline_ns':job['deadline_ns'],'observed_ns':finished,
        'observer_logical_metadata_costs':reader.report(),'observer_own_natural_exit_attested':False,
        'numerical_result':provisional['result']['result'],'scientific_qualification_claim':False,'new_canonical_ids':0}
