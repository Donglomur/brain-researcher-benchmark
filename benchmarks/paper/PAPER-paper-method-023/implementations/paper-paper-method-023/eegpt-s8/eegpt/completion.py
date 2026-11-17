"""Late, acyclic admission of the ORIGINAL complete producer and outer result.

All inputs are independently selected original files. This does not run a model,
resume a participant, infer an exit from a report, or rewrite historical evidence.
"""
from .protocol import validate_code_source_manifest,observation,boundary,Directory,fields,need,identity,decode,read_metadata,stream_capture
from .budget import COUNTERS,JOB_FIELDS


def budget_summary(row,limits,*,require_jobs=False):
    need(row['limits']==limits,'same original selected resource allowances')
    need(not row['unknown'],'no unknown original final resource observation')
    need(row['origin_ns']<=row['observed_at_ns']<=row['deadline_ns']<=row['origin_ns']+limits['wall_milliseconds']*1000000,'original final observation inside selected lifetime')
    for key in COUNTERS:
        actual,reserved=row['known'][key],row['reserved'][key]
        need(type(actual) is int and type(reserved) is int and 0<=actual<=reserved<=limits[key],'original complete final allowance '+key)
    need(type(row['files_reserved']) is int and 0<=row['files_reserved']<=limits['files'],'original final file allowance')
    for key,limit in [('peak_resident_bytes','resident_bytes'),('peak_gpu_resident_bytes','gpu_resident_bytes')]:
        value=row[key]
        need(value is None or (type(value) is int and 0<=value<=limits[limit]),'original final peak allowance')
    if require_jobs:
        need(row['jobs'] and not row['failures'],'complete outer original job and no final accounting failure')
        for job in row['jobs']:
            need(job['status']=='completed' and not job.get('failures'),'original final job admission')
            process_observation(job['observation'],job['reserved'],limits)
    return True


def process_observation(actual,reservation,limits):
    need(actual['spawned'] is True and actual['natural_exit']==0 and actual['forced_exit'] is None and actual['timed_out'] is False and actual['reaped'] is True and actual['descendants_closed'] is True and actual['observer_complete'] is True and not actual['failures'],'actual natural zero exit and complete original cleanup/observer')
    for key in JOB_FIELDS:
        value=actual[key];need(type(value) is int and 0<=value<=reservation[key]<=limits[key],'actual original final per-job allowance '+key)
    for key,lim in [('peak_resident_bytes','resident_bytes'),('peak_gpu_resident_bytes','gpu_resident_bytes')]:need(type(actual[key]) is int and 0<=actual[key]<=limits[lim],'actual final original job peak')


def admit_original_completion(selection,report_member,report,budget):
    fields(selection,('schema','work_root','observer_root','source_root','capture_root','configuration','source_manifest','inner_terminal','outer_terminal','outer_selection','outer_return','outer_invocation','deployment'),'complete independently selected original producer closure')
    need(selection['schema']=='eegpt_original_completion_selection_v1','full original chain; no report-only completion inference')
    roots={};captures=[]
    def read(which,member):
        raw=read_metadata(roots[which],member,cap=budget.limits['metadata_bytes'],ledger=budget);captures.append({'root_role':which,'member':member});return decode(raw)
    try:
        for name in ('work','observer','source','capture'):roots[name]=Directory(selection[name+'_root'])
        config=read('observer',selection['configuration']);outer_policy=read('observer',selection['outer_selection']);manifest=validate_code_source_manifest(read('source',selection['source_manifest']))
        need(config['work_root']==selection['work_root'] and outer_policy['observer_root']==selection['observer_root'],'original selected output roots, no copied-root assertion')
        need(manifest['operative_source_identity']==identity(manifest['operative_members'])==config['qualification']['operative_source_identity']==report['scientific_qualification']['operative_source_identity'],'exact original complete operative source identity')
        need(config['qualification']==report['scientific_qualification'],'same original scientific qualification/configuration')
        for member in manifest['operative_members']:stream_capture(roots['source'],member['path'],expected=member,cap=budget.limits['per_file_bytes'],ledger=budget)
        terminal=read('work',selection['inner_terminal']);outer=read('observer',selection['outer_terminal']);returned=read('capture',selection['outer_return']);invocation=read('capture',selection['outer_invocation'])
        need(terminal['schema']=='eegpt_original_operation_terminal_v1' and terminal['stage']=='full_operation_returned' and terminal['original_failure'] is None and not terminal['original_close_failures'],'actual complete original coordinator returned before immutable terminal')
        need(terminal['result_identity']==identity(report) and terminal['publications']['scientific_report']==report_member and terminal['source_scope_identity']==config['qualification']['scope_identity'],'same original report/source scope publication')
        need(outer['schema']=='eegpt_inclusive_outer_terminal_v1' and outer['failure'] is None and outer['child_original_configuration']==selection['configuration'] and outer['outer_selection']==selection['outer_selection'],'same originally observed coordinator configuration and outer policy')
        budget_summary(outer['original_budget'],outer_policy['limits'],require_jobs=True)
        need(len(outer['original_budget']['jobs'])==1 and outer['original_budget']['jobs'][0]['reserved']=={**outer_policy['child_reservation'],'processes':1,'calls':1,'development_requests':0},'one original whole coordinator reservation')
        process_observation(outer['original_observation']['actual'],outer_policy['child_reservation'],outer_policy['limits'])
        from pathlib import Path
        argv=[str(Path(outer_policy['strace_root'])/outer_policy['strace']['path']),'-f','-qq','-s','0','-e','trace=read,pread64,readv,preadv,preadv2,mmap','-o',str(roots['observer'].path/'coordinator-trace.txt'),str(Path(outer_policy['python_root'])/outer_policy['python']['path']),'-I','-B',str(roots['source'].path/'programme_worker.py'),'--operation','programme','--configuration',str(roots['observer'].path/'CONFIGURATION.json'),'--configuration-sha256',selection['configuration']['sha256'],'--origin-ns',str(outer['original_budget']['origin_ns']),'--deadline-ns',str(outer['original_budget']['deadline_ns'])]
        need(outer['original_observation']['argv_identity']==identity(argv) and outer['original_observation']['cgroup_observed'] is True and outer['original_observation']['natural_exit_observed_after_parent_deadline'] is False,'original source-owned whole coordinator invocation and inclusive physical observation')
        streams={row['name']:row for row in outer['captures']};need(set(streams)=={'coordinator-trace.txt','coordinator-stdout.txt','coordinator-stderr.txt'},'all original outer stream captures retained')
        stream_bodies={}
        for name,item in streams.items():
            need(set(item)=={'name','original'} and item['original']['source']['path']==name,'original complete stream, not failed/partial capture')
            stream_bodies[name]=read_metadata(roots['observer'],item['original']['source'],cap=budget.limits['metadata_bytes'],ledger=budget)
        inner=decode(stream_bodies['coordinator-stdout.txt']);need(inner['status']=='original_operation_returned','original coordinator stdout returned result')
        result=inner['result'];need(result['report']==report_member and result['terminal']==selection['inner_terminal'],'original returned report and terminal pins')
        outside=result['outside_final_closure'];need(type(outside['final_observed_ns']) is int and outside['final_observed_ns']<=outside['original_deadline_ns'],'original inner final close/admission within original lifetime')
        need(outside['original_terminal']==selection['inner_terminal'] and outside['original_terminal_identity']==identity(terminal) and outside['work_handle_close']=={'status':'closed'} and outside['costs_complete'] is True and outside['late_failure'] is None,'post-publication original inner handle/accounting closure')
        for key in COUNTERS:need(type(outside['final_known_counters'][key]) is int and 0<=outside['final_known_counters'][key]<=outside['final_reserved_counters'][key]<=config['campaign_limits'][key],'original final inner known/reserved allowance '+key)
        # The full original ledger is streamed JSON records, not a scientific
        # array. Actual final publication costs are joined by outside above.
        ledger_member=terminal['publications']['ledger'];ledger=read_metadata(roots['work'],ledger_member,cap=budget.limits['metadata_bytes'],ledger=budget)
        summaries={};jobs=[]
        for line in ledger.splitlines():
            row=decode(line)
            if row['kind']=='budget_summary':summaries[row['scope']]=row['summary']
            elif row['kind']=='jobs':jobs.append(row)
            elif row['kind']=='unknown':raise ValueError('unknown original inner resource measurement')
        need('campaign' in summaries and 'operator' in summaries,'complete original campaign/operator ledger')
        for scope,summary in summaries.items():
            limits=config['campaign_limits'] if scope=='campaign' else config['operator_limits'] if scope=='operator' else config['episode_limits']
            budget_summary({**summary,'unknown':[]},limits)
        for row in jobs:
            job=row['original'];need(job['status']=='completed' and not job.get('failures'),'every required original episode process complete for promotion')
            limits=config['campaign_limits'] if row['scope']=='campaign' else config['operator_limits'] if row['scope']=='operator' else config['episode_limits'];process_observation(job['observation'],job['reserved'],limits)
        failures=read_metadata(roots['work'],terminal['publications']['failures'],cap=budget.limits['metadata_bytes'],ledger=budget)
        need(not failures.strip(),'no original scientific lifecycle failure before completion promotion')
        # The external invocation observation is independently selected after the
        # CLI returned. It records the actual command/exit/streams; it is not a
        # replacement for the source-owned inner and outer chains above.
        fields(invocation,('schema','argv','cwd','started_ns','finished_ns','natural_exit','forced_exit','timed_out','reaped','descendants_closed','stdout','stderr','source_identity','root_selection_identity'),'actual independently captured original outer invocation')
        need(invocation['schema']=='eegpt_original_outer_invocation_v1' and invocation['source_identity']==manifest['operative_source_identity'] and invocation['natural_exit']==0 and invocation['forced_exit'] is None and invocation['timed_out'] is False and invocation['reaped'] is True and invocation['descendants_closed'] is True and invocation['finished_ns']>=invocation['started_ns'],'original outer invocation natural completion, never inferred from report')
        need(invocation['stdout']==selection['outer_return'] and invocation['root_selection_identity']==config['qualification']['selection_identity'],'same original outer returned stream and source/science selection')
        deployment=selection['deployment'];fields(deployment,('root','member'),'independently selected original deployment bytes');roots['deployment']=Directory(deployment['root']);deployed=read('deployment',deployment['member'])
        need(Path(deployed['configuration_path']).is_absolute() and deployed['configuration_sha256']==selection['configuration']['sha256'] and deployed['outer']==outer_policy and deployed['root_selection']==invocation['root_selection_identity'],'original public deployment joins exact configuration/outer/source selection')
        admit_public_invocation(returned['public_invocation'],invocation,selection,manifest,config,outer_policy)
        need(returned['public_invocation']['origin_ns']==outer['original_budget']['origin_ns'] and invocation['finished_ns']<=outer['original_budget']['deadline_ns'],'same original public origin and complete outside observed return before deadline; no child/outer reset')
        read_metadata(roots['capture'],invocation['stderr'],cap=budget.limits['metadata_bytes'],ledger=budget)
        need(returned['original_outer_terminal']==selection['outer_terminal'] and returned['original_natural_exit']==0 and returned['operation']=='programme','actual whole outer returned result')
        final=returned['outside_outer_closure'];need(final['terminal_identity']==identity(outer) and final['observer_handle_close']=={'status':'closed'} and final['late_failure'] is None,'outer final publication and handle closure')
        budget_summary(final['final_budget'],outer_policy['limits'],require_jobs=True)
        need(final['final_budget']['jobs']==outer['original_budget']['jobs'],'same complete original outer physical job ledger')
        budget.guard('before_original_complete_chain_return')
        return {'status':'original_complete_producer_chain_admitted','original_configuration_identity':identity(config),'source_identity':manifest['operative_source_identity'],'original_inner_terminal':selection['inner_terminal'],'original_outer_terminal':selection['outer_terminal'],'original_outer_return':selection['outer_return'],'original_invocation':selection['outer_invocation'],'report_identity':identity(report),'captures':captures,'no_rerun_or_relabel':True}
    finally:
        import sys
        primary=sys.exc_info()[1];errors=[]
        for root in roots.values():
            try:root.close()
            except BaseException as exc:errors.append(observation(exc))
        try:budget.guard('after_original_completion_close')
        except BaseException as exc:errors.append(observation(exc))
        if errors:
            from .protocol import Refusal
            raise Refusal('original completion inspection handle closure',observation={'primary':None if primary is None else observation(primary),'close_failures':errors}) from primary


def public_invocation_binding(package,outer,configuration,*,mode,deployment,argv,cwd,origin_ns):
    """Select one exact public command before any producer exists."""
    from pathlib import Path
    fields(deployment,('root','member'),'original deployment descriptor');from .protocol import descriptor
    descriptor(deployment['member']);root=Path(deployment['root']);package=Path(package)
    need(root.is_absolute() and '..' not in root.parts and str(root)==deployment['root'],'canonical deployment root')
    need(mode in ('default','named'),'explicit original public invocation mode')
    need(outer['source_manifest']==configuration['qualification']['source_manifest'] and outer['source_manifest']['path']=='SOURCE.json','exact immutable code manifest shared by configuration and outer selection')
    base=[str(Path(outer['python_root'])/outer['python']['path']),'-I','-B',str(package/'cli.py'),'run']
    if mode=='default':need(root==package and deployment['member']['path']=='DEPLOYMENT.json','default is exact package-relative deployment')
    else:base+=['--deployment',str(root/deployment['member']['path']),'--deployment-sha256',deployment['member']['sha256']]
    need(argv==base and cwd==str(package),'exact original interpreter/script/flags/cwd/command form')
    need(type(origin_ns) is int and origin_ns>=0,'original invocation origin')
    return {'schema':'eegpt_exact_public_invocation_v1','mode':mode,'argv':base,'cwd':cwd,'deployment':deployment,'source_identity':configuration['qualification']['operative_source_identity'],'root_selection_identity':configuration['qualification']['selection_identity'],'configuration_identity':identity(configuration),'code_manifest':outer['source_manifest'],'origin_ns':origin_ns}


def admit_public_invocation(binding,invocation,selection,manifest,config,outer_policy):
    """Join both supported modes to the actual outside observed command."""
    fields(binding,('schema','mode','argv','cwd','deployment','source_identity','root_selection_identity','configuration_identity','code_manifest','origin_ns'),'exact prelaunch public invocation')
    expected=public_invocation_binding(selection['source_root'],outer_policy,config,mode=binding['mode'],deployment=selection['deployment'],argv=invocation['argv'],cwd=invocation['cwd'],origin_ns=binding['origin_ns'])
    need(binding==expected and binding['schema']=='eegpt_exact_public_invocation_v1','same exact selected prelaunch and outside original invocation')
    need(invocation['started_ns']<=binding['origin_ns']<=invocation['finished_ns'],'prelaunch binding belongs to original outside observed lifetime')
    validate_code_source_manifest(manifest)
    need(binding['source_identity']==manifest['operative_source_identity'],'runtime deployment and code source have distinct exact identities')
    if binding['mode']=='default':need(binding['deployment']['root']==selection['source_root'] and binding['deployment']['member']['path']==manifest['runtime_deployment_role']['path'],'exact package-relative runtime slot, never a substituted template')
    return expected
