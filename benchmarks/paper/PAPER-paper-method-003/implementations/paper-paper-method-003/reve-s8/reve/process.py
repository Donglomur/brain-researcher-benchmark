"""Actual child stdin/streams/completion; Linux production sandbox and inert controls."""
from pathlib import Path
import os
import selectors
import signal
import subprocess
import sys
import time
from .errors import Refusal,require
from .deadline import boundary
from .custody import Custody,custody,text,observation,reader_details
from .objects import Reader,canonical,digest,fields,inventory,pin,positive,rel,snapshot,write_new


LIMITS=('wall_ms','cpu_ms','memory_bytes','processes','output_bytes','output_files','stream_bytes','request_bytes')
COSTS=('wall_ms','cpu_ms','output_bytes','output_files','stream_bytes','request_bytes')


def accounting_complete(receipt):
    """A closed child is not necessarily a reconciled resource lifetime."""
    state=receipt.get('resource_accounting',{})
    return (receipt.get('costs_charged') is True and state.get('status')=='complete'
            and state.get('unavailable_fields')==[]
            and all(value=='applied' for value in state.get('debit_status',{}).values())
            and set(state.get('debit_status',{}))==set(receipt.get('costs',{}))==set(COSTS)
            and all(type(value) is int and value>=0 for value in receipt['costs'].values()))


def validate_limits(value):
    fields(value,LIMITS)
    for key in LIMITS:positive(value[key],key)
    require(value['request_bytes']<=1024*1024,'request protocol limit')
    return value


class Cgroup:
    """A separately delegated cgroup v2 subtree is mandatory for production."""
    def __init__(self,parent,name,limits):
        self.path=Path(parent)/name
        require(sys.platform.startswith('linux') and Path(parent,'cgroup.controllers').is_file(),'cgroup v2 required')
        require(not self.path.exists() and '/' not in name,'fresh cgroup')
        self.path.mkdir()
        for field,value in [('memory.max',limits['memory_bytes']),('pids.max',limits['processes']),('memory.swap.max',0)]:
            (self.path/field).write_text(str(value))
        self.start=self.cpu()

    def cpu(self):
        rows=dict(line.split() for line in (self.path/'cpu.stat').read_text().splitlines())
        return int(rows['usage_usec'])

    def attach(self,pid):(self.path/'cgroup.procs').write_text(str(pid))

    def kill(self):
        (self.path/'cgroup.kill').write_text('1')

    def observe(self):
        return {'cpu_us':self.cpu()-self.start,'memory_peak':int((self.path/'memory.peak').read_text()),
                'memory_events':(self.path/'memory.events').read_text(),'pids_current':int((self.path/'pids.current').read_text())}


class Launcher:
    def __init__(self,work_root,ledger,mode,environment,aggregate,guard=None):
        self.custody=Custody();self.guard=guard
        if guard:guard()
        self.work=Path(work_root).absolute();self.work.mkdir(mode=0o700,parents=True,exist_ok=True)
        require(not self.work.is_symlink(),'work root')
        require(mode in ('inert-control','production'),'launch mode')
        self.ledger=ledger;self.mode=mode;self.environment=environment;self.aggregate=validate_limits(aggregate)
        self.spent={k:0 for k in COSTS}
        self.attempts=[];self.active={};self.owned={};self.accounting_pending={}

    def require_accounting_closed(self):
        require(not self.accounting_pending,'unresolved original resource accounting blocks further work or closure')

    def charge_original_costs(self,owned):
        """Apply known debits once; retain a hold for any missing/uncertain debit.

        The hold is allocated before effects and is not the live-process set.
        No retry, substitute clock sample or reset can erase a partial charge.
        """
        receipt=owned['receipt'];state=receipt['resource_accounting'];charges=receipt['costs']
        require(state['status']=='pending','original resource finalization replay')
        require(set(charges)==set(self.spent)==set(COSTS),'complete original debit fields')
        state['status']='charging'
        for key,value in charges.items():
            if value is None:continue
            require(type(value) is int and value>=0,'invalid original resource debit '+key)
            state['debit_status'][key]='applying'
            self.spent[key]+=value
            state['debit_status'][key]='applied'
        state['unavailable_fields']=[key for key,value in charges.items() if value is None]
        receipt['aggregate_spent']=dict(self.spent)
        if not state['unavailable_fields']:
            state['status']='complete';receipt['costs_charged']=True
            self.accounting_pending.pop(receipt['attempt_id'])
        else:state['status']='unresolved'

    def command(self,source,input_root,output_root,limit,attempt,guard=None):
        guard=guard or self.guard
        if guard:guard()
        if not hasattr(self,'preparation_reads'):self.preparation_reads=[]
        def observe_read(reader,rows,label):
            details={'label':label,'reader':None};self.preparation_reads.append(details)
            with observation(self,'Launcher.command',details,refresh=lambda d:d.update(reader=reader_details(reader))):
                for row in rows:reader.read(row)
        fields(source,('root','manifest','entrypoint','interpreter','environment','role','source_id'))
        reader=Reader(source['root'],sum(r['bytes']+1 for r in source['manifest'])+1,len(source['manifest'])+1,guard=guard)
        rows={r['path']:r for r in source['manifest']}
        require(source['entrypoint'] in rows,'entrypoint outside registered source')
        observe_read(reader,source['manifest'],'registered_source')
        require(source['source_id']==digest(canonical(source['manifest'])),'source identity')
        require(source['environment']==self.environment['identity'],'environment mismatch')
        if self.mode=='inert-control':
            require(self.environment.get('inert_control_only') is True,'inert selection')
            require(source['interpreter']==sys.executable,'inert interpreter')
            return [sys.executable,'-B','-s','-E',str(Path(source['root'])/source['entrypoint'])],None
        fields(self.environment,('identity','runtime_root','runtime_manifest','bwrap','bwrap_pin','interpreter','cgroup_parent','isolation_qualification','source_abi_qualification'))
        require(self.environment['isolation_qualification'] and self.environment['source_abi_qualification'],'production environment unqualified')
        require(source['interpreter']==self.environment['interpreter'],'selected interpreter')
        rr=Reader(self.environment['runtime_root'],sum(x['bytes']+1 for x in self.environment['runtime_manifest'])+1,len(self.environment['runtime_manifest'])+1,guard=guard)
        runtime_rows=self.environment['runtime_manifest']
        require(inventory(self.environment['runtime_root'],sum(x['bytes'] for x in runtime_rows)+1,len(runtime_rows)*8+1,guard=guard)==sorted((x['path'],x['bytes']) for x in runtime_rows),'runtime contains unselected files')
        observe_read(rr,self.environment['runtime_manifest'],'selected_runtime')
        binary=Path(self.environment['bwrap']);br=Reader(binary.parent,self.environment['bwrap_pin']['bytes']+1,1,guard=guard);observe_read(br,[self.environment['bwrap_pin']],'selected_sandbox_binary')
        cg=Cgroup(self.environment['cgroup_parent'],attempt,limit)
        # Everything visible is a selected immutable runtime/source/input; no host
        # home, working tree, target store, networking or writable shared cache.
        cmd=[str(binary),'--die-with-parent','--new-session','--unshare-all','--clearenv',
             '--ro-bind',str(Path(self.environment['runtime_root']).absolute()),'/',
             '--ro-bind',str(Path(source['root']).absolute()),'/source',
             '--ro-bind',str(input_root.absolute()),'/input',
             '--bind',str(output_root.absolute()),'/output',
             '--proc','/proc','--dev','/dev','--chdir','/output',
             '--setenv','HOME','/output','--setenv','TMPDIR','/output',
             '--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','PYTHONHASHSEED','0',
             '/'+rel(source['interpreter']).as_posix(),'-B','-s','-E','/source/'+source['entrypoint']]
        return cmd,cg

    def begin_boundary(self,phase):
        if phase=='Launcher.run':self.current_owned=None

    def release_boundary_success(self,phase):
        if phase=='Launcher.run':self.current_owned=None

    def retain_boundary_failure(self,exc,phase):
        # Covers the outer decorator's final authority check and return failures.
        owned=getattr(self,'current_owned',None)
        if owned is not None:
            owned['custody'].fail(exc,phase)
            receipt=owned['receipt'];receipt['natural_completion']=False
            if receipt['failure_reason'] is None:receipt['failure_reason']=type(exc).__name__+': '+text(exc)

    @boundary
    def run(self,attempt,source,input_root,request,limits):
        if self.guard:self.guard()
        require(not self.active,'unresolved original child completion blocks subsequent launches')
        self.require_accounting_closed()
        rel(attempt);require('/' not in attempt and attempt not in self.owned,'fresh flat attempt ID')
        limits=validate_limits(limits)
        for k in self.spent:require(self.spent[k]+limits[k]<=self.aggregate[k],'whole programme reservation '+k)
        require(limits['memory_bytes']<=self.aggregate['memory_bytes'] and limits['processes']<=self.aggregate['processes'],'whole peak-memory/process reservation')
        raw=canonical(request);require(len(raw)<=limits['request_bytes'],'request cap')
        evidence_reserve=8*len(raw)+4*len(canonical(source))+(limits['output_files']+8)*8192+65536
        self.ledger.ensure_capacity(evidence_reserve)
        # Every field needed for first-error custody is allocated BEFORE effects.
        state=Custody();stdout=bytearray();stderr=bytearray();cleanup=[];snapshot_observations=[];telemetry_observations=[]
        root=self.work/attempt;out=root/'output';logs=root/'original'
        receipt={'schema':'reve-original-process-receipt-v1','attempt_id':attempt,'mode':self.mode,'source_id':source['source_id'],
                 'environment':source['environment'],'request_body':request,'request':pin(raw,'request.json'),
                 'pid':None,'exit_code':None,'scope_quiescent':False,'scope_proof_kind':'pending','natural_completion':False,
                 'failure_reason':None,'outputs':[],'stdin_bytes_requested':len(raw),'stdin_bytes_delivered':0,
                 'stream_bytes_observed':0,'stream_capture_complete':True,'telemetry':None,'final_telemetry_known':False,
                 'telemetry_observations':telemetry_observations,'telemetry_observations_displaced':0,'telemetry_observation_count':0,'observed_cpu_lower_bound_us':None,
                 'limits':limits,'cleanup_observations':cleanup,'output_snapshot_observations':snapshot_observations,
                 'prospective_evidence_metadata_reserve':evidence_reserve,'scientifically_qualified':False,
                 'publication':{'stdout':False,'stderr':False,'receipt':False,'ledger':False},'costs_charged':False,
                 'costs':{k:None for k in self.spent},
                 'resource_accounting':{'status':'pending','debit_status':{k:'not_started' for k in self.spent},'unavailable_fields':list(self.spent)},
                 'monotonic_end_ns':None,'wall_ms':None}
        owned={'receipt':receipt,'custody':state,'child':None,'stdout_bytes':stdout,'stderr_bytes':stderr,
               'output_root':out,'phase':'reserved','launch_entered':False,'wait_observed':False,'spent':self.spent,
               'selector':None,'cgroup':None,'preparation_reads':[]}
        state.process=owned;self.custody.process=owned;self.current_owned=owned
        self.owned[attempt]=owned;self.attempts.append(receipt);self.active[attempt]=owned;self.accounting_pending[attempt]=owned
        begun=time.monotonic_ns();clock=time.time_ns();p=None;reason=None;sent=0;telemetry=None;cmd=[];cgroup=None
        termination_requested=False;stream_bytes_observed=0;stream_capture_complete=True;code=None
        scope_quiescent=False;cleanup_deadline=None;self.preparation_reads=owned['preparation_reads'];sel=None;publication_failed=False
        receipt['monotonic_start_ns']=begun;receipt['start_time_ns']=clock
        def remember_telemetry(value,phase):
            nonlocal telemetry
            telemetry=value;receipt['telemetry']=value
            cpu=value.get('cpu_us')
            if type(cpu) is int and cpu>=0:
                old=receipt['observed_cpu_lower_bound_us']
                receipt['observed_cpu_lower_bound_us']=cpu if old is None else max(old,cpu)
            # A long fit must not build an unbounded in-memory telemetry log.
            # Retain the first 31 and latest observation; all samples update the
            # high-water lower bound and the exact observation/displacement count.
            receipt['telemetry_observation_count']+=1
            observation={'phase':phase,'telemetry':value}
            if len(telemetry_observations)<32:telemetry_observations.append(observation)
            else:
                telemetry_observations[-1]=observation;receipt['telemetry_observations_displaced']+=1
        def validate_final_telemetry():
            require(type(telemetry['cpu_us']) is int and telemetry['cpu_us']>=0,'invalid final CPU observation')
            require(type(telemetry['memory_peak']) is int and telemetry['memory_peak']>=0,'invalid final memory observation')
            require(type(telemetry['pids_current']) is int and telemetry['pids_current']>=0,'invalid final descendant observation')
            require(type(telemetry['memory_events']) is str,'invalid final memory events')
        def final_resource_admission():
            require(telemetry['cpu_us']<=limits['cpu_ms']*1000,'final actor CPU budget')
            require(telemetry['memory_peak']<=limits['memory_bytes'],'final actor memory budget')
            require('oom_kill 0' in telemetry['memory_events'],'cgroup OOM event')
        def failure(exc,phase):
            nonlocal reason
            state.fail(exc,phase)
            if reason is None:reason=type(exc).__name__+': '+text(exc)
            receipt['failure_reason']=reason;receipt['natural_completion']=False
        def refusal(message,phase):failure(Refusal(message),phase)
        def execution_guard():
            if self.guard:self.guard()
            require(time.monotonic_ns()-begun<limits['wall_ms']*1000000,'original actor wall deadline')
        def cleanup_remaining():
            nonlocal cleanup_deadline
            if cleanup_deadline is None:cleanup_deadline=time.monotonic_ns()+2000000000
            return max(0,(cleanup_deadline-time.monotonic_ns())/1000000000)
        def cleanup_guard():require(cleanup_remaining()>0,'bounded failure cleanup exhausted')
        def terminate():
            nonlocal termination_requested
            cleanup_remaining()
            if termination_requested or p is None:return
            termination_requested=True
            try:
                if cgroup:cgroup.kill();cleanup.append({'operation':'cgroup.kill','status':'requested','pid':p.pid})
                elif p.poll() is None:os.killpg(p.pid,signal.SIGKILL);cleanup.append({'operation':'killpg','status':'requested','pid':p.pid})
                else:cleanup.append({'operation':'signal_not_sent','status':'child_already_observed_exited','pid':p.pid,'exit_code':p.returncode})
            except ProcessLookupError:cleanup.append({'operation':'kill','status':'already_absent','pid':p.pid})
            except BaseException as exc:
                failure(exc,'cleanup:kill')
                if not cgroup:
                    try:
                        if p.poll() is None:p.kill()
                    except BaseException as secondary:failure(secondary,'cleanup:owned_child_kill')
        def close_streams():
            if sel is not None:
                try:sel.close()
                except BaseException as exc:failure(exc,'cleanup:selector_close')
            if p is not None:
                for f in (p.stdin,p.stdout,p.stderr):
                    try:
                        if f is not None and not f.closed:f.close()
                    except BaseException as exc:failure(exc,'cleanup:stream_close')
        def observe_final_scope():
            nonlocal telemetry,scope_quiescent
            if cgroup is not None:
                try:
                    remember_telemetry(cgroup.observe(),'post_wait')
                    cleanup.append({'operation':'scope_observe','telemetry':telemetry})
                    validate_final_telemetry()
                    scope_quiescent=code is not None and telemetry['pids_current']==0
                    receipt['final_telemetry_known']=scope_quiescent
                    final_resource_admission()
                except BaseException as exc:failure(exc,'final_original_telemetry')
                # A live descendant's observation is only a lower bound. A
                # later failed read cannot upgrade it to a final measurement.
                if not scope_quiescent:
                    refusal('original process scope unresolved','scope_closure');terminate()
                    while cleanup_remaining()>0:
                        try:
                            remember_telemetry(cgroup.observe(),'cleanup')
                            cleanup.append({'operation':'scope_observe_after_failure','telemetry':telemetry})
                            validate_final_telemetry()
                            if code is not None and telemetry['pids_current']==0:
                                scope_quiescent=True;receipt['final_telemetry_known']=True
                                final_resource_admission();break
                        except BaseException as exc:failure(exc,'cleanup:scope_observe');break
                        time.sleep(min(.01,cleanup_remaining()))
            else:scope_quiescent=code is not None and self.mode=='inert-control'
        try:
            owned['phase']='attempt_begin'
            self.ledger.reserve_attempt(attempt,{'source':source,'request':request,'limits':limits,'mode':self.mode})
            execution_guard();root.mkdir(mode=0o700,exist_ok=False);out.mkdir(mode=0o700);logs.mkdir(mode=0o700)
            write_new(logs/'request.json',raw,guard=execution_guard)
            env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'}
            cmd,cgroup=self.command(source,Path(input_root),out,limits,attempt,guard=execution_guard)
            owned['cgroup']=cgroup
            if cgroup:cmd=[sys.executable,'-B','-I',str(Path(__file__).with_name('trampoline.py')),*cmd]
            receipt['argv']=cmd;execution_guard();owned['phase']='launch';owned['launch_entered']=True
            p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               cwd=out,env=env,start_new_session=True,close_fds=True)
            owned['child']=p;receipt['pid']=p.pid;owned['phase']='child_owned'
            self.ledger.append('child_launched',{'attempt_id':attempt,'pid':p.pid,'argv':cmd,'source_id':source['source_id'],'request':receipt['request'],'observed_time_ns':time.time_ns()})
            if cgroup:
                while True:
                    execution_guard();waited,status=os.waitpid(p.pid,os.WUNTRACED|os.WNOHANG)
                    if waited:break
                    time.sleep(.005)
                require(waited==p.pid and os.WIFSTOPPED(status),'trusted cgroup stop boundary')
                execution_guard();cgroup.attach(p.pid);execution_guard();os.kill(p.pid,signal.SIGCONT)
            sel=selectors.DefaultSelector();owned['selector']=sel
            for f,label in ((p.stdout,'stdout'),(p.stderr,'stderr')):
                os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,label)
            os.set_blocking(p.stdin.fileno(),False);sel.register(p.stdin,selectors.EVENT_WRITE,'stdin')
            while sel.get_map():
                if reason is None:
                    try:execution_guard()
                    except BaseException as exc:failure(exc,'actor_loop:deadline')
                if cgroup:
                    remember_telemetry(cgroup.observe(),'actor_loop')
                    if telemetry['cpu_us']>limits['cpu_ms']*1000:refusal('CPU budget','actor_loop:CPU')
                try:inventory(out,limits['output_bytes'],limits['output_files'],guard=cleanup_guard if reason else execution_guard)
                except BaseException as exc:failure(exc,'actor_loop:output_admission')
                if reason is not None:
                    terminate()
                    if cleanup_remaining()<=0:
                        stream_capture_complete=False;break
                for key,_ in sel.select(.02):
                    f=key.fileobj;label=key.data
                    if label=='stdin':
                        try:
                            n=os.write(f.fileno(),raw[sent:sent+16384]);sent+=n;receipt['stdin_bytes_delivered']=sent
                        except BrokenPipeError as exc:
                            if sent!=len(raw):failure(exc,'actor_loop:stdin')
                            sel.unregister(f);f.close();continue
                        if sent==len(raw):sel.unregister(f);f.close()
                    else:
                        capacity=limits['stream_bytes']-len(stdout)-len(stderr)
                        b=os.read(f.fileno(),min(65536,max(0,capacity)+1));stream_bytes_observed+=len(b);receipt['stream_bytes_observed']=stream_bytes_observed
                        if not b:sel.unregister(f);f.close();continue
                        target=stdout if label=='stdout' else stderr;target.extend(b[:max(0,capacity)])
                        if len(b)>capacity:
                            refusal('stream cap exceeded; suffix not retained','actor_loop:stream_cap')
                            stream_capture_complete=False;sel.unregister(f);f.close();terminate()
                code=p.poll()
                if code is not None and sent<len(raw):refusal('incomplete stdin delivery','actor_loop:stdin')
            while True:
                if reason is None:
                    execution_guard();remaining=max(0,(limits['wall_ms']*1000000-(time.monotonic_ns()-begun))/1000000000)
                else:remaining=cleanup_remaining()
                try:
                    code=p.wait(timeout=min(.02,remaining));owned['wait_observed']=True;receipt['exit_code']=code;break
                except subprocess.TimeoutExpired:
                    require(remaining>0,'original wait deadline without completion')
            if reason is None:execution_guard()
            if code!=0:refusal('nonzero process exit','original_wait')
        except BaseException as exc:
            failure(exc,owned['phase']);stream_capture_complete=False
            if p is not None:
                terminate()
                try:
                    code=p.wait(timeout=cleanup_remaining());owned['wait_observed']=True;receipt['exit_code']=code
                except BaseException as secondary:failure(secondary,'cleanup:wait');code=None
        finally:
            # Ownership and returned-code observations exist before any cleanup publication.
            try:
                if p is not None:observe_final_scope()
                else:scope_quiescent=not owned['launch_entered']
            except BaseException as exc:failure(exc,'cleanup:scope_finalization')
            close_streams()
            receipt['scope_quiescent']=scope_quiescent
            receipt['scope_proof_kind']='cgroup_observed_zero' if cgroup and scope_quiescent else ('inert_parent_only' if scope_quiescent and p is not None else ('no_process_started' if scope_quiescent else 'unresolved'))
            if scope_quiescent:self.active.pop(attempt,None)
        # Everything below may fail; the live owned record remains independently available.
        owned['phase']='finalize';census=[]
        try:
            require(scope_quiescent,'unresolved process scope outputs cannot be closed')
            if out.is_dir():census=snapshot(out,limits['output_bytes'],limits['output_files'],guard=cleanup_guard if reason else execution_guard,observations=snapshot_observations)
        except BaseException as exc:failure(exc,'final_output_snapshot')
        # Keep original terminal/output observations before any fallible final
        # clock or accounting operation. A missing final clock stays unknown.
        receipt['exit_code']=code;receipt['stream_capture_complete']=stream_capture_complete;receipt['outputs']=census
        elapsed=None
        try:
            ended=time.monotonic_ns();require(ended>=begun,'original monotonic clock moved backwards')
            elapsed=(ended-begun)//1000000
            receipt['monotonic_end_ns']=ended;receipt['wall_ms']=elapsed
        except BaseException as exc:failure(exc,'final_original_clock')
        # Known final measurements versus conservative debits are explicit.
        charges=receipt['costs']
        charges['wall_ms']=elapsed;charges['stream_bytes']=stream_bytes_observed;charges['request_bytes']=len(raw)
        lower=receipt['observed_cpu_lower_bound_us']
        try:
            cpu_known=receipt['final_telemetry_known'] and scope_quiescent and lower is not None
            observed_ms=(lower+999)//1000 if lower is not None else 0
            cpu_charge=observed_ms if cpu_known else max(limits['cpu_ms'],observed_ms)
            charges['cpu_ms']=cpu_charge
            receipt['conservative_unmeasured_CPU_charge_ms']=None if cpu_known else cpu_charge
            receipt['unavailable_measurements']=([] if cpu_known else ['aggregate_CPU','RAM','descendant_cgroup'])+([] if elapsed is not None else ['wall_end','wall_elapsed'])
            receipt['CPU_accounting']={'status':'complete_original_lifetime' if cpu_known else ('partial_lower_bound_final_unavailable' if lower is not None else 'unmeasured_final_unavailable'),
                                       'observed_lower_bound_us':lower,'debit_ms':cpu_charge,'conservative_debit_is_not_measurement':not cpu_known}
            charges['output_bytes']=sum(x['bytes'] for x in census) if census else (limits['output_bytes'] if reason else 0)
            charges['output_files']=len(census) if census else (limits['output_files'] if reason else 0)
        except BaseException as exc:failure(exc,'final_cost_observations')
        try:self.charge_original_costs(owned)
        except BaseException as exc:
            failure(exc,'final_cost_debit');receipt['resource_accounting']['status']='unresolved'
        if not accounting_complete(receipt):refusal('original resource accounting remains unresolved','final_cost_admission')
        if lower is not None and lower>limits['cpu_ms']*1000:refusal('final actor CPU budget','final_cost_admission')
        if any(self.spent[k]>self.aggregate[k] for k in self.spent):refusal('whole programme cost exceeded','final_cost_admission')
        if elapsed is not None and elapsed>=limits['wall_ms']:refusal('final wall eligibility exceeded','final_cost_admission')
        try:execution_guard()
        except BaseException as exc:failure(exc,'final_completion_deadline')
        try:
            receipt.update(signal=-code if code is not None and code<0 else None,stdout=pin(bytes(stdout),'stdout'),stderr=pin(bytes(stderr),'stderr'),original_preparation_reads=self.preparation_reads)
            receipt['natural_completion']=code==0 and reason is None and scope_quiescent
            receipt['failure_reason']=reason
            receipt['failure']=state.record()
            # Private stream buffers, original wait and debit already have custody.
            for name,body in (('stdout',stdout),('stderr',stderr)):
                write_new(logs/name,bytes(body));receipt['publication'][name]=True
            if reason is None:execution_guard()
            write_new(logs/'receipt.json',canonical(receipt));receipt['publication']['receipt']=True
            if reason is None:execution_guard()
            self.ledger.append('attempt_end',receipt);receipt['publication']['ledger']=True
            if reason is None:execution_guard()
        except BaseException as exc:
            failure(exc,'final_publication');publication_failed=True
        owned['phase']='closed' if scope_quiescent and accounting_complete(receipt) else 'unresolved'
        receipt['natural_completion']=code==0 and reason is None and scope_quiescent
        receipt['failure_reason']=reason
        if publication_failed or not accounting_complete(receipt):
            # The same exception object carries the preexisting original receipt.
            raise state.first_exception
        return receipt,out
