"""Concrete independent original-clock process/daemon closure for the full study.

Future separately authorized execution only. No Docker/native process executes
at import. Linux pidfds bind signals to observed processes; a missing leader,
reused PID, surviving group or unknown creation acknowledgment stays unresolved.
"""
import time
BOOT=time.monotonic()
import argparse
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
from budget import Budget
from core import TASK, need, encoded, native_jobs, held_jobs, ROLES
from safe_io import capture, strict, pin
from operation import validate_operation
from transport.engine import BOOTSTRAP, process_identity


def absent(pgid):
    try:os.killpg(pgid,0)
    except ProcessLookupError:return True
    except PermissionError:return False
    return False


def identity_reader(pid,end,budget):
    def reserve(n):
        budget.tick();need(budget.reads+n<=budget.limits['read_bytes'],'Reserve bounded process identity before read')
    return process_identity(pid,end,budget.read,reserve)


def retire_cli(token,end,budget,grace):
    """Signal only an identity-bound leader; never authorize kill from PID alone.

    Group absence is separately observed. No claim to close an unrecorded child
    or surviving descendant follows from killing a leader.
    """
    result={'process_identity':token,'closed':False,'leader_signalled':False,'identity_match':False}
    fd=None
    try:
        budget.tick();pid=token['pid']
        if absent(token['pgid']):result.update(closed=True,group_absent=True);return result
        fd=os.pidfd_open(pid,0)
        fresh=identity_reader(pid,end,budget)
        need(fresh==token,'Exact UID/boot/start/PID/session identity before pidfd signal')
        result['identity_match']=True
        signal.pidfd_send_signal(fd,signal.SIGKILL,None,0);result['leader_signalled']=True
        cutoff=min(end,time.monotonic()+grace)
        while time.monotonic()<cutoff:
            budget.tick()
            if absent(token['pgid']):result.update(closed=True,group_absent=True);break
            time.sleep(min(.01,max(0,cutoff-time.monotonic())))
        result.setdefault('group_absent',False)
    except BaseException as error:
        result.update(error_type=type(error).__name__,group_absent=False)
        # ESRCH can mean the exact process just exited. Only fresh group absence
        # discharges custody; a birth mismatch never authorizes a group signal.
        try:
            if absent(token['pgid']):result.update(closed=True,group_absent=True)
        except BaseException:pass
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:result.update(closed=False,close_error=type(error).__name__)
    budget.tick();return result


def watch(argv,root,work_deadline,budget,grace,log_cap,host_memory):
    """Gated concrete controller child; all post-Popen work is custody-guarded."""
    import resource
    need(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'Identity-bound Linux process signaling')
    def limits():
        os.umask(0o077);resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(host_memory,host_memory))
    end=budget.end;need(budget.tick()<work_deadline<end,'Original work/terminal cutoffs')
    env={'PATH':'/usr/bin:/bin','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','TZ':'UTC','LC_ALL':'C'}
    process=None;selector=None;pidfd=None;token=None;code=None;primary=None;cleanup=[];forced=False
    buffers={'stdout':bytearray(),'stderr':bytearray()};started=budget.tick()
    try:
        process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',BOOTSTRAP,*argv],cwd=root,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,preexec_fn=limits)
        pidfd=os.pidfd_open(process.pid,0)
        token=identity_reader(process.pid,end,budget)
        budget.event({'event':'CONTROLLER-CHILD','process_identity':token,'exec_still_gated':True,'argv':argv})
        need(budget.tick()<work_deadline and os.write(process.stdin.fileno(),b'G')==1,'Durable controller ownership before release')
        process.stdin.close()
        selector=selectors.DefaultSelector()
        for name,stream in (('stdout',process.stdout),('stderr',process.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or process.poll() is None:
            need(budget.tick()<work_deadline,'Original whole-program work deadline')
            for key,_ in selector.select(min(.05,max(0,work_deadline-time.monotonic()))):
                remaining=log_cap-sum(map(len,buffers.values()))
                need(remaining>=0 and budget.reads+min(65536,remaining+1)<=budget.limits['read_bytes'],'Reserve streaming log read')
                data=os.read(key.fileobj.fileno(),min(65536,remaining+1));budget.read(len(data))
                if not data:selector.unregister(key.fileobj);continue
                need(len(data)<=remaining,'Bounded controller metadata logs');buffers[key.data].extend(data)
        code=process.wait(timeout=max(.001,min(grace,end-budget.tick())))
        need(absent(process.pid),'Controller leader exit cannot hide surviving process group')
    except BaseException as error:
        primary=error;forced=True
        # pidfd was opened while this exact Popen child was gated. It remains
        # identity-bound even if the numeric PID is reused; no killpg is sent.
        if pidfd is not None:
            try:signal.pidfd_send_signal(pidfd,signal.SIGKILL,None,0)
            except ProcessLookupError:pass
            except BaseException as secondary:cleanup.append({'action':'pidfd_kill','type':type(secondary).__name__})
        if process is not None:
            try:
                if process.stdin is not None and not process.stdin.closed:process.stdin.close()
                process.wait(timeout=max(.001,min(grace,end-time.monotonic())))
            except BaseException as secondary:cleanup.append({'action':'reap','type':type(secondary).__name__})
            code=process.returncode
    finally:
        actions=[]
        if selector is not None:actions.append(('selector.close',selector.close))
        if process is not None:
            actions.extend((name+'.close',s.close) for name,s in (('stdin',process.stdin),('stdout',process.stdout),('stderr',process.stderr)) if s is not None)
        if pidfd is not None:actions.append(('pidfd.close',lambda:os.close(pidfd)))
        for name,action in actions:
            try:action()
            except BaseException as error:cleanup.append({'action':name,'type':type(error).__name__})
    try:group_absent=process is None or absent(process.pid)
    except BaseException as error:
        group_absent=False;cleanup.append({'action':'final_group_observation','type':type(error).__name__})
    result={'schema':'osl_independent_controller_close_v1','argv':argv,'process_identity':token,
        'started':started,'finished':time.monotonic(),'work_deadline':work_deadline,'global_deadline':end,
        'exit_code':code,'natural_exit':not forced and code==0 and group_absent and not cleanup,'forced':forced,
        'reaped':process is None or process.returncode is not None,'process_group_absent':group_absent,
        'error_type':None if primary is None else type(primary).__name__,'cleanup_errors':cleanup,
        'logs':{k:pin(bytes(v)) for k,v in buffers.items()},
        'source_resource_semantics':'Actual process lifetime and enforced address-space ceiling; no exact RSS claim'}
    result['logs_data']={name:bytes(body) for name,body in buffers.items()}
    return result


def source_view(op,here,root,budget):
    """Host controller executes a copied immutable full source closure."""
    import staging
    s=op['source_manifest'];raw=budget.read_file(s['path'],{k:s[k] for k in ('bytes','sha256')},1048576)
    manifest=strict(raw)
    need(manifest.get('schema')=='osl_complete_executable_source_v1','Complete executable source closure')
    files={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in manifest['files']}
    need(len(files)==len(manifest['files']) and all(not n.startswith(('peer-review/','review-revisions/')) for n in files),'Unique production source only')
    need({'controller.py','supervisor.py','operation.py','transport/SOURCE_MANIFEST.json'}<=set(files),'Complete host/transport source')
    return staging.materialize(root,here,files,budget)


def inspect_cli(control,phase,request_pin,budget,limits,grace):
    """Close every durable pre-exec CLI identity before daemon recovery."""
    names=[]
    for entry in control.iterdir():
        need(len(names)<limits['max_records']+16,'Finite per-phase durable metadata inventory')
        names.append(entry.name)
    records=[];total=0
    for name in sorted(names):
        if not re.fullmatch('[0-9]{6}-CLI-CHILD.json',name):continue
        size=(control/name).stat().st_size
        need(0<size<=limits['max_record_bytes'] and total+size<=limits['max_metadata_bytes'],'Bounded durable CLI ownership')
        budget.read(size);raw=capture(control/name,limits['max_record_bytes']);total+=len(raw);row=strict(raw)
        need(row['schema']=='osl_transport_journal_v1' and row['phase_id']==phase and row['request_sha256']==request_pin['sha256']
             and row['event']=='CLI-CHILD' and name==f"{row['index']:06d}-CLI-CHILD.json",'Source-owned exact phase journal')
        value=row['value'];need(value['docker_exec_still_gated'] is True and value['independent_group'] is True
            and value['pid']==value['pgid']==value['process_identity']['pid'],'Gated durable CLI identity')
        close=retire_cli(value['process_identity'],budget.end,budget,grace)
        records.append({'record':pin(raw),'closure':close})
    return {'records':records,'all_recorded_cli_groups_absent':all(r['closure']['closed'] for r in records),
            'unrecorded_bootstrap_cannot_exec_docker':True}


def attempt_ledger(work,budget,max_record_bytes,max_events):
    """Every planned job remains explicit even after an abrupt controller stop."""
    planned={j['id']:j for factory in (native_jobs,held_jobs) for role in ROLES for j in factory(role)}
    starts={};dispositions={};pins={};error=None;names=[];root=work/'journal'
    try:
        if root.exists():
            for entry in root.iterdir():
                need(len(names)<max_events and re.fullmatch('[0-9]{7}.json',entry.name),'Bounded source-owned whole-program journal')
                names.append(entry.name)
        for index,name in enumerate(sorted(names)):
            need(name==f'{index:07d}.json','Contiguous complete durable event history')
            n=(root/name).stat().st_size;need(0<n<=max_record_bytes,'Whole-study journal record ceiling')
            budget.read(n);raw=capture(root/name,max_record_bytes);row=strict(raw)
            need(row['index']==index and row['ledger_clock']['origin']==budget.origin and row['ledger_clock']['deadline']==budget.end,'Original event clock/index')
            event=row.get('event')
            if event not in ('attempt_start','attempt_disposition','unadmitted_external_attempt'):continue
            job=row['job'];need(planned.get(job['id'])==job,'Exact source-planned attempt identity')
            key=job['id'];pins.setdefault(key,[]).append(pin(raw))
            if event=='attempt_start':
                need(key not in starts,'No hidden repeated attempt');starts[key]=row['request_id']
            elif event=='attempt_disposition':
                need(key in starts and key not in dispositions and row['status'] in ('completed','failed'),'One terminal observed disposition')
                dispositions[key]={'status':row['status'],'reason':row['reason'],'capture_pin':row['capture_pin'],
                                   'cost':row['cost'],'output_pins':row['outputs']}
            else:
                dispositions[key]={'status':'unadmitted_unknown','error_type':row['error_type'],
                                   'returned_closure':row.get('returned_closure'),'unknown_cost_not_zero':True}
    except BaseException as exc:error={'type':type(exc).__name__,'history_complete':False}
    rows=[]
    for key,job in planned.items():
        value=dispositions.get(key)
        if value is None:
            value={'status':'unknown_history' if error else 'started_without_admitted_closure' if key in starts else 'not_started',
                   'actual_cost':None,'unknown_cost_not_zero':key in starts or error is not None}
        rows.append({'job':job,**value,'evidence':pins.get(key,[])})
    return {'schema':'osl_independent_full_attempt_ledger_v1','planned':5853,'native':453,'held_hmm':5400,
            'rows':rows,'journal_error':error,'all_attempts_accounted_without_success_subsetting':True,
            'all_attempts_have_admitted_terminal_disposition':error is None and all(r['status'] in ('completed','failed') for r in rows),
            'all_numerical_attempts_completed':error is None and all(r['status']=='completed' for r in rows)}


def run(operation_path,operation_pin,output,origin=BOOT):
    from transport import Provider
    # A source-build approval does not manufacture this operation or these pins.
    raw=capture(operation_path,1048576,operation_pin);op=validate_operation(strict(raw))
    root=Path(output);need(not root.exists() and not root.is_symlink(),'Fresh outer operation directory')
    root.mkdir(mode=0o700,parents=False);(root/'journal').mkdir(mode=0o700)
    limits={'wall_seconds':op['limits']['wall_seconds'],'read_bytes':op['outer_read_bytes'],
            'write_bytes':op['outer_write_bytes'],'retained_bytes':op['outer_retained_bytes']}
    budget=Budget(limits,origin,root/'journal');budget.read(len(raw));end=budget.end;work_end=end-op['outer_cleanup_seconds']
    need(budget.tick()<work_end,'Operation parse is on the original clock')
    operation_copy=root/'OPERATION.json';budget.save(operation_copy,raw)
    for item in (op['host_python'],{'path':op['docker']['binary'],'pin':op['docker']['binary_pin']}):
        budget.read_file(item['path'],item['pin'],item['pin']['bytes'])
    here=Path(__file__).resolve().parent;view=source_view(op,here,root/'host_source',budget)
    # The controller source root is immutable for this operation. The external
    # source manifest remains an exact operator-owned input, re-read by it.
    loader='import sys,runpy; p=sys.argv.pop(1); sys.path.insert(0,p); runpy.run_path(p+"/controller.py",run_name="__main__")'
    argv=[op['host_python']['path'],'-I','-S','-B','-c',loader,view['root'],'--operation',str(operation_copy),
          '--operation-sha256',operation_pin['sha256'],'--output',str(root/'work'),'--origin',repr(origin)]
    result=watch(argv,here,work_end,budget,op['controller_grace_seconds'],op['controller_log_bytes'],op['host_memory_bytes'])
    logs=result.pop('logs_data');publication_errors=[]
    for name,body in logs.items():
        try:budget.save(root/(name+'.log'),body)
        except BaseException as error:publication_errors.append({'artifact':name+'.log','error_type':type(error).__name__})
    controller_body=encoded(result);controller_pin=pin(controller_body)
    try:budget.save(root/'CONTROLLER_CLOSE.json',controller_body)
    except BaseException as error:publication_errors.append({'artifact':'CONTROLLER_CLOSE.json','error_type':type(error).__name__})
    # The independently observed in-memory close still authorizes bounded
    # cleanup if its durable publication fails. It never becomes a successful
    # terminal receipt merely because recovery eventually removes resources.
    def recovery_journal(name,value):
        try:budget.event({'event':'outer_recovery','name':name,'value':value})
        except BaseException as error:
            publication_errors.append({'artifact':'outer_recovery_event','name':name,'value_pin':pin(encoded(value)),
                                       'error_type':type(error).__name__})
    controller_closed=result['reaped'] and result['process_group_absent']
    recovery=[];phases=root/'work'/'phases';directories=[]
    if phases.exists():
        for p in phases.iterdir():
            need(len(directories)<11725,'Full finite phase roster, no hidden retries');directories.append(p)
    for phase in sorted(directories):
        budget.tick();need(phase.is_dir() and not phase.is_symlink() and re.fullmatch('[a-f0-9]{64}',phase.name),'Exact owned phase directory')
        control=phase/'control'/phase.name;ownership=control/'OWNERSHIP.json'
        if not controller_closed:
            recovery.append({'phase_id':phase.name,'recovery_complete':False,'reason':'controller_custody_unclosed'});continue
        if not ownership.exists():
            # Pinned Provider publishes OWNERSHIP before any Docker CLI gate.
            recovery.append({'phase_id':phase.name,'resource_creation_not_started':True});continue
        limits=op['recovery_limits'];reservation='recovery_'+phase.name
        # Reserve even failures before source/daemon calls. Unknown outcomes do
        # not regain budget, and recovery never refreshes the original clock.
        budget.reserve_producer(reservation,limits['source_read_bytes'],limits['host_write_bytes'],limits['host_write_bytes'])
        try:
            request_size=(phase/'REQUEST.json').stat().st_size;budget.read(request_size)
            request_raw=capture(phase/'REQUEST.json',1048576);request=strict(request_raw);request_pin=pin(request_raw)
            owner_size=ownership.stat().st_size;budget.read(owner_size);owner_raw=capture(ownership,65536);owner_pin=pin(owner_raw)
            exposure=phase/'EXPOSURE.json';budget.read_file(exposure,request['exposure'],2097152)
            cli=inspect_cli(control,phase.name,request_pin,budget,limits,op['controller_grace_seconds'])
            if not cli['all_recorded_cli_groups_absent']:
                recovery.append({'phase_id':phase.name,'recovery_complete':False,'cli_custody':cli});continue
            provider=Provider(phase/'control',phase/'quarantine',op['docker']['binary'],op['docker']['socket'],
                op['engine_source_pin'],{request['exposure']['sha256']:str(exposure)},limits['source_read_bytes'],limits['host_write_bytes'])
            recovered=provider.recover(phase.name,request_pin,owner_pin,end,recovery_journal,limits,controller_pin)
            budget.tick();recovered['prior_cli_custody']=cli;recovery.append(recovered)
        except BaseException as error:
            row={'phase_id':phase.name,'recovery_complete':False,'error_type':type(error).__name__,
                 'actual_cost_unknown':True,'cleanup_errors':getattr(error,'cleanup_errors',[])}
            recovery.append(row);recovery_journal('RECOVERY-FAILED',row)
    recovered_all=controller_closed and all(r.get('resource_creation_not_started') is True or
        (r.get('receipt',{}).get('all_resource_custody_closed') is True and r['receipt'].get('all_namespaces_empty') is True
         and r['receipt'].get('cli_reaped') is True and r.get('prior_cli_custody',{}).get('all_recorded_cli_groups_absent') is True) for r in recovery)
    inner=None;inner_path=root/'work'/'INNER_RETURN.json'
    if inner_path.exists():
        n=inner_path.stat().st_size;budget.read(n);body=capture(inner_path,max(1,n));inner={'pin':pin(body),'value':strict(body)}
    maximum_events=16+4*5853+11725*(3*max(r['max_cli_calls'] for r in op['phase_resources'].values())+64)
    attempts=attempt_ledger(root/'work',budget,op['recovery_limits']['max_record_bytes'],maximum_events)
    report={'schema':'osl_complete_program_outer_receipt_v1','task_id':TASK,'operation':operation_pin,
        'origin':origin,'deadline':end,'controller_close':controller_pin,'controller_natural_exit':result['natural_exit'],
        'independent_recovery':recovery,'independent_terminal_absence_complete':recovered_all,'inner_return':inner,
        'independent_attempt_ledger':attempts,
        'global_limits':op['limits'],'outer_partition':budget.snapshot(),
        'whole_logical_charge_semantics':'Disjoint preallocated inner/outer partitions, conservative producer reservations; not kernel native I/O or RSS',
        'publication_errors':publication_errors,'controller_close_independently_observed_in_memory':result,
        'numerical_complete':bool(not publication_errors and attempts['all_attempts_have_admitted_terminal_disposition'] and result['natural_exit'] and recovered_all and inner and inner['value']['numerical_complete']),
        'actual_whole_producer_resources_measured':False,'runtime_qualified':False,'scientific_qualification':False,'whole_paper_reproduced':False}
    receipt=budget.save(root/'OUTER_RECEIPT.json',encoded(report));budget.tick();return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);p.add_argument('--operation-bytes',type=int,required=True)
    p.add_argument('--operation-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    run(a.operation,{'bytes':a.operation_bytes,'sha256':a.operation_sha256},a.output)


if __name__=='__main__':main()
