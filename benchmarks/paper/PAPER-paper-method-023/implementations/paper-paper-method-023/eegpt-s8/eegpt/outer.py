"""Actual outer Linux observer for the indivisible programme and private scorer.

The whole coordinator, all numerical grading and every nested candidate/native
process share one cgroup ancestry. Nested meters are views of that work; they
are never added to this inclusive original CPU/RAM observation.
"""
import os,resource
from pathlib import Path
from .protocol import validate_code_source_manifest,Directory,fields,need,identity,encode,decode,persist,read_metadata,stream_capture,observation,Refusal
from .budget import Budget,JOB_FIELDS
from .execution import Cgroup,ProcessCustody,_control,observe_child,traced_read_bytes


def operate(package,configuration,outer,*,operation='programme',origin=None,public_invocation=None,admission_budget=None,custody_out=None):
    need(operation in ('programme','prepare_assets'),'whole selected operation kind')
    fields(outer,('schema','run_id','observer_root','cgroup_root','python_root','python','strace_root','strace','source_manifest','limits','child_reservation','qualification'),'whole actual trusted coordinator observer');need(outer['schema']=='eegpt_inclusive_linux_outer_v1','one full scientific lifetime');need(os.uname().sysname=='Linux','actual complete Linux deployment required')
    budget=admission_budget if admission_budget is not None else Budget(outer['limits'],origin=origin,label='inclusive original outer physical observation');need(budget.limits==outer['limits'] and (origin is None or budget.origin==origin),'same actual admission/outer budget, no read-cost or original clock reset');record=None;group=None;observer=None;result=None;failure=None;captures=[];handles=[];leaf=None;outer_selection_pin=None;outside_outer=None;work=Path(configuration['work_root'] if operation=='programme' else configuration['output_root']);terminal=None;requested=outer['child_reservation'];fields(requested,JOB_FIELDS,'full original coordinator child reservation')
    # Root-owned outer accounting capacity is separate from the scientific
    # actor/campaign allocation; complete logs consume this explicit reserve.
    reserve=outer['limits']['metadata_bytes']
    custody=ProcessCustody(outer['run_id']);custody.original_outer_exceptions=[];primary=None;secondary=custody.record['secondary_failures'];config_pin=None
    if custody_out is not None:custody_out.append(custody)
    def note(exc,phase):
        nonlocal primary,failure
        custody.original_outer_exceptions.append(exc)
        if primary is None:primary=exc
        row={'phase':phase,**observation(exc)}
        if failure is None:failure=row
        else:secondary.append(row)
        custody.record['primary_failure']=failure;custody.record['secondary_failures']=secondary
    def budget_report(phase):
        try:return budget.report()
        except BaseException as exc:note(exc,phase);return None
    try:
        budget.reserve('output_bytes',reserve);budget.reserve_file()
        if operation=='programme':
            need(public_invocation is not None and public_invocation['origin_ns']==budget.origin and public_invocation['source_identity']==configuration['qualification']['operative_source_identity'],'whole original public invocation selected before launch')
            need(public_invocation['configuration_identity']==identity(configuration) and public_invocation['code_manifest']==outer['source_manifest']==configuration['qualification']['source_manifest'],'exact selected public configuration and code manifest before launch')
        observer=Directory(outer['observer_root']);need(not os.listdir(observer.fd),'fresh original outer observation directory');source=Directory(str(package));handles.append(source)
        manifest=validate_code_source_manifest(decode(read_metadata(source,outer['source_manifest'],cap=budget.limits['metadata_bytes'],ledger=budget)));need(manifest['operative_source_identity']==identity(manifest['operative_members'])==(configuration['qualification']['operative_source_identity'] if operation=='programme' else configuration['operative_source_identity']),'same accepted entire operative package and exact complete body inventory')
        if operation=='programme':
            need(public_invocation['source_identity']==manifest['operative_source_identity'],'separate original deployment binds this exact immutable code source')
            if public_invocation['mode']=='default':stream_capture(source,'DEPLOYMENT.json',expected=public_invocation['deployment']['member'],ledger=budget,cap=budget.limits['metadata_bytes'])
        for member in manifest['operative_members']:stream_capture(source,member['path'],expected=member,ledger=budget,cap=budget.limits['per_file_bytes'])
        python_root=Directory(outer['python_root']);handles.append(python_root);trace_root=Directory(outer['strace_root']);handles.append(trace_root)
        for root,member in ((python_root,outer['python']),(trace_root,outer['strace'])):stream_capture(root,member['path'],expected=member,ledger=budget,cap=budget.limits['per_file_bytes'])
        group=Cgroup(outer['cgroup_root'],outer['run_id'],budget.limits);_control(group.path/'cgroup.subtree_control','+cpu +memory +pids');leaf=group.path/'coordinator';os.mkdir(leaf,0o700)
        if operation=='programme':need(configuration['executor']['cgroup_root']==str(group.path),'every inner worker is a descendant of THIS inclusive original cgroup')
        # Configuration is captured before the child exists. The input hash is
        # not changed to make a convenient runtime path or resumed lifecycle.
        outer_selection_pin=persist(observer,'OUTER_SELECTION.json',encode(outer),ledger=budget)
        config_pin=persist(observer,'CONFIGURATION.json',encode(configuration),ledger=budget)
        remaining=requested;need(all(v>=(configuration['campaign_limits'] if operation=='programme' else configuration['limits'])[k] for k,v in remaining.items()),'inclusive child funded for full original inner campaign and numerical coordinator');record=budget.begin(outer['run_id'],remaining,development=False);custody.record['original_budget_record']=record
        trace=observer.path/'coordinator-trace.txt';argv=[str(trace_root.path/outer['strace']['path']),'-f','-qq','-s','0','-e','trace=read,pread64,readv,preadv,preadv2,mmap','-o',str(trace),str(python_root.path/outer['python']['path']),'-I','-B',str(Path(package)/'programme_worker.py'),'--operation',operation,'--configuration',str(observer.path/'CONFIGURATION.json'),'--configuration-sha256',config_pin['sha256'],'--origin-ns',str(budget.origin),'--deadline-ns',str(budget.deadline)]
        def enter():
            _control(leaf/'cgroup.procs',os.getpid());resource.setrlimit(resource.RLIMIT_FSIZE,(budget.limits['per_file_bytes'],budget.limits['per_file_bytes']));cpu=max(1,(remaining['cpu_milliseconds']+999)//1000);resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu))
        result=observe_child(argv,cwd=str(work),environment={'LANG':'C','LC_ALL':'C','PATH':'/nonexistent'},stdout_path=observer.path/'coordinator-stdout.txt',stderr_path=observer.path/'coordinator-stderr.txt',deadline=budget.deadline,requested=remaining,limits=budget.limits,cgroup=group,preexec=enter,custody=custody)
    except BaseException as exc:note(exc,'original_outer_operation')
    finally:
        # The outer owner exists before launch and is authoritative even when
        # observe_child cannot construct/return its final hash-bearing result.
        actual=custody.actual;actual['observer_complete']=False
        if observer is not None:
            for name in ('coordinator-trace.txt','coordinator-stdout.txt','coordinator-stderr.txt'):
                try:
                    path=observer.path/name
                    if not path.exists():continue
                    pin=stream_capture(observer,name,size=path.stat(follow_symlinks=False).st_size,cap=budget.limits['per_file_bytes'],ledger=budget);captures.append({'name':name,'original':pin})
                    if name=='coordinator-trace.txt':
                        raw=read_metadata(observer,pin['source'],cap=budget.limits['metadata_bytes'],ledger=budget);parsed=traced_read_bytes(raw.decode('utf8').splitlines());actual['read_bytes']=parsed['known_logical_read_bytes'];actual['observer_complete']=parsed['complete'] and actual['descendants_closed'] and result is not None
                except BaseException as exc:captures.append({'name':name,'original_capture_failure':observation(exc)});note(exc,'original_capture:'+name)
        if group is not None:
            try:
                sample=group.sample()
                if sample['populated']:
                    actual['descendants_closed']=False;actual['observer_complete']=False;group.kill();raise Refusal('original whole cgroup not closed')
                actual['cpu_milliseconds']=sample['cpu_milliseconds'];actual['peak_resident_bytes']=sample['peak_resident_bytes'];actual['gpu_milliseconds']=0;actual['peak_gpu_resident_bytes']=0
                if leaf is not None:os.rmdir(leaf)
                group.cleanup()
            except BaseException as exc:note(exc,'original_outer_cgroup_cleanup')
        for handle in handles:
            try:handle.close()
            except BaseException as exc:note(exc,'original_outer_handle_close')
        if record is not None:
            if actual['scratch_bytes'] is not None:actual['output_bytes']=actual['scratch_bytes']
            actual['artifacts']=captures
            if failure is not None:actual['failures'].append(failure)
            try:record=budget.end(record,actual);custody.record['original_budget_record']=record
            except BaseException as exc:note(exc,'original_outer_accounting')
        # Freeze a nonrecursive view before adding outer finalization fields to
        # the strong record. Current unknown launch facts are never replaced by
        # a fabricated no-launch/closed observation.
        terminal={'schema':'eegpt_inclusive_outer_terminal_v1','original_observation':custody.record['original_process'],'process_custody':dict(custody.record),'original_budget':budget_report('original_terminal_budget_report'),'captures':captures,'failure':failure,'secondary_failures':secondary,'child_original_configuration':config_pin,'outer_selection':outer_selection_pin,'inner_accounting_added_to_inclusive_totals':False,'scientific_status_requires_original_report_and_qualification':True};terminal_pin=None
        custody.record['original_outer_terminal']=terminal
        if observer is not None:
            try:
                raw=encode(terminal);need(len(raw)<=reserve,'complete original outer observation reserve');terminal_pin=persist(observer,'ORIGINAL_OUTER_TERMINAL.json',raw,ledger=None);custody.record['original_outer_terminal_pin']=terminal_pin;budget.observe('output_bytes',len(raw))
            except BaseException as exc:note(exc,'original_outer_terminal_publication');terminal['original_terminal_publication_failure']=observation(exc)
            try:observer.close();observer_close={'status':'closed'}
            except BaseException as exc:note(exc,'original_observer_close');terminal['original_observer_close_failure']=observation(exc);observer_close={'status':'failed','failure':observation(exc)}
    try:
        budget.guard('after_original_outer_terminal_publication_and_observer_close')
        from .completion import budget_summary
        budget_summary(budget.report(),outer['limits'],require_jobs=True)
    except BaseException as exc:note(exc,'original_outer_final_admission')
    outside_outer={'terminal_identity':None,'observer_handle_close':locals().get('observer_close'),'final_budget':budget_report('outside_original_budget_report'),'late_failure':failure,'secondary_failures':secondary}
    custody.record['outside_outer_closure']=outside_outer
    try:outside_outer['terminal_identity']=identity(terminal)
    except BaseException as exc:note(exc,'original_outer_final_identity')
    outside_outer['late_failure']=failure;terminal['failure']=failure
    if failure is not None:terminal['outside_final_closure']=outside_outer
    if primary is not None:
        primary.original_process_custody=custody.record
        primary.original_outer_terminal=terminal
        primary.observation={'original_primary_observation':getattr(primary,'observation',None),'original_outer_terminal':terminal}
        raise primary
    if record is None or record['status']!='completed':
        exc=Refusal('original inclusive EEGPT operation failed or remains unqualified',observation=terminal);exc.original_process_custody=custody.record;raise exc
    return {'original_outer_terminal':terminal_pin,'original_natural_exit':custody.actual['natural_exit'],'operation':operation,'inner_scientific_report':str(work/'SCIENTIFIC_REPORT.json') if operation=='programme' else None,'scientific_completion_not_inferred_from_exit':True,'outside_outer_closure':outside_outer,'public_invocation':public_invocation}
