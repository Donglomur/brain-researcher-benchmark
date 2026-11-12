"""All-outcome arbitrary command execution through a qualified isolation monitor.

The host never imports participant/scientific code. Terminal recovery is limited
to original process streams/completion/custody; it admits no new scientific work.
"""
from __future__ import annotations
import os
import selectors
import signal
import stat
import subprocess
import time
from pathlib import Path
from .common import require,Refusal,encode,decode,digest_bytes,error_record,relative_path

COMPLETION_CAP=1024*1024
RECEIPT_CAP=64*1024
CHUNK=65536
TERMINAL_DRAIN_SECONDS=2.0
CLEANUP_CAPTURE_CAP=65536

class QualifiedMonitor:
    def __init__(self,policy,authority,store):
        self.policy,self.authority,self.store=policy,authority,store
        require(policy['qualified_capabilities']=={
            'network_denied':True,'filesystem_closed':True,'readonly_states':True,
            'all_descendant_wait':True,'cumulative_syscall_writes':True,
            'per_cgroup_cpu_rss':True,'original_stdin_and_streams':True},'INCOMPLETE_MONITOR_CAPABILITIES')
        authority.producer('isolation_monitor',policy['source_manifest_sha256'])
        store.read(policy['executable'],{'qualified_monitor_source'})

    def start(self,request_descriptor,workdir,environment):
        command=[str(self.store.root/self.policy['executable']['path']),'--request',
            str(self.store.root/request_descriptor['path']),'--completion',str(Path(workdir)/'monitor-completion.json')]
        return subprocess.Popen(command,cwd=workdir,env=environment,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)

    def terminate_tree(self,process,workdir):
        # This is a necessary supervisor operation, not a new participant job.
        command=[str(self.store.root/self.policy['executable']['path']),
            '--terminate-cgroup',str(Path(workdir)/'monitor-completion.json')]
        child=None;sel=selectors.DefaultSelector();streams={'stdout':bytearray(),'stderr':bytearray()}
        eof={'stdout':False,'stderr':False};primary=None;secondary=[];waited=False;start=time.monotonic()
        try:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,start_new_session=True,env={'PATH':'/usr/bin:/bin'})
            for name in streams:
                stream=getattr(child,name);os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,name)
            while sel.get_map():
                require(time.monotonic()-start<10,'DESCENDANT_TERMINATION_TIMEOUT')
                for key,_ in sel.select(.05):
                    b=os.read(key.fileobj.fileno(),min(CHUNK,CLEANUP_CAPTURE_CAP-len(streams[key.data])+1))
                    if not b:eof[key.data]=True;sel.unregister(key.fileobj);key.fileobj.close();continue
                    streams[key.data].extend(b);require(len(streams[key.data])<=CLEANUP_CAPTURE_CAP,'TERMINATION_STREAM_CAP_EXCEEDED')
            child.wait(timeout=max(.001,10-(time.monotonic()-start)));waited=True
            require(child.returncode==0,'DESCENDANT_TERMINATION_FAILED',child.returncode)
        except BaseException as exc:primary=exc
        finally:
            if child is not None:
                try:child.wait(timeout=2);waited=True
                except BaseException as exc:
                    if primary is None:primary=exc
                    else:secondary.append(exc)
                    try:
                        if child.poll() is None:child.kill()
                    except BaseException as exc:secondary.append(exc)
                    try:child.wait(timeout=2);waited=True
                    except BaseException as exc:secondary.append(exc)
                for stream in (child.stdout,child.stderr):
                    try:
                        if stream is not None and not stream.closed:stream.close()
                    except BaseException as exc:
                        if primary is None:primary=exc
                        else:secondary.append(exc)
            try:sel.close()
            except BaseException as exc:
                if primary is None:primary=exc
                else:secondary.append(exc)
        record={'command':command,'pid':None if child is None else child.pid,'original_wait_complete':waited,
            'returncode':None if child is None else child.returncode,'stdout':bytes(streams['stdout']),
            'stderr':bytes(streams['stderr']),'stream_eof':eof,'elapsed_seconds':time.monotonic()-start,
            'primary':error_record(primary) if primary else None,'secondary':[error_record(x) for x in secondary]}
        if primary is not None:setattr(primary,'cleanup_outcome',record);raise primary
        return record

    def completion(self,process,workdir,reader):
        body=reader(Path(workdir)/'monitor-completion.json',COMPLETION_CAP);value=decode(body)
        require(value['monitor_source_manifest_sha256']==self.policy['source_manifest_sha256'],'WRONG_MONITOR_COMPLETION_SOURCE')
        require(value['monitor_pid']==process.pid and value['returncode']==process.returncode,'WRONG_ORIGINAL_PROCESS_COMPLETION')
        require(value['completion_issuer']=='qualified_monitor','PARTICIPANT_FORGED_TELEMETRY')
        return value

class ProcessHost:
    def __init__(self,meter,journal,store,backend,*,clock=time.monotonic):
        self.meter,self.journal,self.store,self.backend=meter,journal,store,backend;self.clock=clock

    def run(self,request,*,request_id,command,source_sha256,mounts,state_seals,workdir,
            output_capacity,artifact_write_capacity,environment,context):
        self.meter.checkpoint('before_process_request');relative_path(request_id)
        require('/' not in request_id,'REQUEST_ID_MUST_BE_SINGLE_COMPONENT')
        require(command and all(type(x)is str for x in command),'INVALID_PARTICIPANT_COMMAND')
        require(context['network'] is False and context['readonly_state'] is True,'UNSAFE_PROCESS_CONTEXT')
        require(context['allowed_roles'] and len(set(m['destination'] for m in mounts))==len(mounts),'INVALID_ISOLATED_MOUNTS')
        require(type(output_capacity)is int and output_capacity>=0 and type(artifact_write_capacity)is int and artifact_write_capacity>=0,'INVALID_PROCESS_CAPACITY')
        require(len(request_id)<=128 and len(source_sha256)<=256,'UNBOUNDED_PROCESS_IDENTITY')
        require(self.journal.meter.limits.closure_bytes-self.journal.emergency_offset>=
                2*RECEIPT_CAP+32768,'INSUFFICIENT_PRE_RESERVED_PROCESS_FAILURE_CLOSURE')
        self.meter.reserve('write_bytes',RECEIPT_CAP,'bounded_original_process_receipt_capacity')
        body=encode(request);capture_cap=output_capacity+2*CHUNK
        # Reserve both original/final completion attempts and terminal stream drain
        # before spawning. No after-deadline fresh reservation is invented.
        self.meter.reserve('jobs',1,'job_admission')
        self.meter.reserve('read_bytes',2*capture_cap+2*(COMPLETION_CAP+1)+2*(CLEANUP_CAPTURE_CAP+1),'all_original_stream_completion_reads')
        self.meter.reserve('write_bytes',len(body)+2*capture_cap+2*(COMPLETION_CAP+1)+2*(CLEANUP_CAPTURE_CAP+1)+artifact_write_capacity,'original_stdin_pipe_capture_and_child_writes')
        intent=self.journal.append('PROCESS_INTENT',{'request_id':request_id,'request_sha256':digest_bytes(body),
            'command':command,'source_sha256':source_sha256,'mounts':mounts,'states':state_seals,'context':context,
            'original_deadline':self.meter.deadline,'max_stdout':output_capacity,'max_stderr':output_capacity,
            'terminal_stream_capacity_each':capture_cap,'completion_attempts_capacity':2,'max_cumulative_child_writes':artifact_write_capacity})
        intended=self.store.write(f'jobs/{request_id}/original-stdin-intended.bin',body,
            role='original_process_stream',producer=intent['sha256'],media_type='application/octet-stream')
        monitor_request={'schema':'finite_isolated_job_v1','request_id':request_id,'command':command,
            'request_sha256':digest_bytes(body),'source_manifest_sha256':source_sha256,'mounts':mounts,
            'state_seals':state_seals,'context':context,'original_deadline':self.meter.deadline,
            'job_wall_seconds':self.meter.limits.job_wall_seconds,'job_cpu_seconds':self.meter.limits.job_cpu_seconds,
            'job_rss_bytes':self.meter.limits.job_rss_bytes,'max_cumulative_child_writes':artifact_write_capacity,'environment':environment}
        manifest=self.store.write_json(f'jobs/{request_id}/monitor-request.json',monitor_request,role='monitor_request',producer=intent['sha256'])
        fds={};sizes={};hashes={};paths={};durable={};process=None;selector=selectors.DefaultSelector()
        captured={'stdout':bytearray(),'stderr':bytearray()};eof={'stdout':False,'stderr':False};sent=0
        primary=None;secondary=[];waited=False;completion=None;completion_capture_index=None;attempts=[];cleanup=None;receipt=None;started=None
        def remember(exc):
            nonlocal primary
            if primary is None:primary=exc
            else:secondary.append(exc)
        def persist(name,data):
            # Already reserved descriptor-only custody, legal during terminal close.
            offset=0
            while offset<len(data):
                n=os.write(fds[name],data[offset:]);require(n>0,'ZERO_CUSTODY_WRITE');offset+=n
                sizes[name]+=n;hashes[name].update(data[offset-n:offset]);self.meter.observe('write_bytes',n)
        def read_completion(path,cap):
            require(len(attempts)<2 and cap<=COMPLETION_CAP,'UNRESERVED_COMPLETION_READ')
            name='completion-'+str(len(attempts));attempt={'index':len(attempts),'path':str(path),'terminal':primary is not None,'captured':False};attempts.append(attempt)
            fd=None
            try:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);require(stat.S_ISREG(os.fstat(fd).st_mode),'NONORDINARY_MONITOR_COMPLETION')
                chunks=[];total=0
                while total<=cap:
                    chunk=os.read(fd,min(CHUNK,cap+1-total))
                    if not chunk:break
                    chunks.append(chunk);total+=len(chunk)
                    attempt['bytes']=total;attempt['sha256']=digest_bytes(b''.join(chunks))
                    # Preserve every original read prefix even if a later read
                    # or final decode fails; charge the observed crossing chunk.
                    observation=None
                    try:self.meter.observe('read_bytes',len(chunk))
                    except BaseException as exc:observation=exc
                    persist(name,chunk);attempt['captured']=True
                    if observation:raise observation
                data=b''.join(chunks)
                require(len(data)<=cap,'MONITOR_COMPLETION_TOO_LARGE');return data
            except BaseException as exc:attempt['error']=error_record(exc);raise
            finally:
                if fd is not None:os.close(fd)
        def admit_completion(value,terminal):
            require(value['request_id']==request_id and value['request_sha256']==digest_bytes(body),'MONITOR_REQUEST_SUBSTITUTION')
            require(value['stdin_bytes']==sent and value['stdin_sha256']==digest_bytes(body[:sent]),'DELIVERED_STDIN_MISMATCH')
            require(value['source_manifest_sha256']==source_sha256,'MONITOR_SOURCE_SUBSTITUTION')
            require(value['state_seals_before']==state_seals and value['state_seals_after']==state_seals,'STATE_MUTATED_DURING_INFERENCE')
            self.meter.child_complete(value['telemetry'],job_id=intent['sha256'],write_capacity=artifact_write_capacity,terminal=terminal)
        def read_stream(key,terminal=False):
            name=key.data;stream=key.fileobj;room=capture_cap-len(captured[name])
            require(room>0,'TERMINAL_STREAM_CAPTURE_EXHAUSTED',name)
            try:data=os.read(stream.fileno(),min(CHUNK,room))
            except BlockingIOError:return
            if not data:eof[name]=True;selector.unregister(stream);stream.close();return
            captured[name].extend(data);observation=None
            try:self.meter.observe('read_bytes',len(data))
            except BaseException as exc:observation=exc
            persist(name,data)
            if observation:raise observation
            if not terminal:require(len(captured[name])<=output_capacity,'PROCESS_STREAM_CAP_EXCEEDED',name)
        try:
            import hashlib
            for name in ('stdout','stderr','completion-0','completion-1','cleanup-stdout','cleanup-stderr'):
                path=f'jobs/{request_id}/original-{name}.bin'
                paths[name]=path;sizes[name]=0;hashes[name]=hashlib.sha256();durable[name]=False
                parent,leaf=self.store._parent(path,create=True)
                try:
                    self.meter.checkpoint('before_original_custody_file_create')
                    fds[name]=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
                finally:os.close(parent)
            self.meter.checkpoint('immediately_before_process_launch');started=self.clock()
            process=self.backend.start(manifest,workdir,environment);self.meter.observe('jobs',1)
            # Register pipes before fallible publication so a start-record error
            # still has original pipe handles for complete terminal recovery.
            for name,stream in [('stdin',process.stdin),('stdout',process.stdout),('stderr',process.stderr)]:
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_WRITE if name=='stdin' else selectors.EVENT_READ,name)
            self.journal.append('PROCESS_STARTED',{'request_id':request_id,'pid':process.pid,'intent':intent['sha256']})
            while selector.get_map():
                self.meter.checkpoint('process_poll');require(self.clock()-started<self.meter.limits.job_wall_seconds,'JOB_WALL_EXCEEDED')
                for key,_ in selector.select(.05):
                    self.meter.checkpoint('before_original_pipe_effect')
                    if key.data=='stdin':
                        try:n=os.write(key.fileobj.fileno(),body[sent:sent+CHUNK])
                        except BlockingIOError:continue
                        require(n>0,'ZERO_STDIN_WRITE');sent+=n;self.meter.observe('write_bytes',n)
                        if sent==len(body):selector.unregister(key.fileobj);key.fileobj.close()
                    else:read_stream(key)
                if process.poll() is not None and any(x.data=='stdin' for x in selector.get_map().values()):raise Refusal('CHILD_EXIT_BEFORE_COMPLETE_STDIN')
            process.wait(timeout=max(.001,min(10,self.meter.deadline-self.clock())));waited=True
            self.meter.checkpoint('after_original_process_wait')
            completion=self.backend.completion(process,workdir,read_completion)
            completion_capture_index=len(attempts)-1
            admit_completion(completion,False)
            require(process.returncode==0,'PROCESS_FAILED',process.returncode)
        except BaseException as exc:remember(exc)
        finally:
            if process is not None:
                # Close original stdin, terminate descendants even if leader has
                # exited, then wait that exact leader and drain original pipes.
                try:
                    if process.stdin is not None and not process.stdin.closed:
                        try:selector.unregister(process.stdin)
                        except KeyError:pass
                        process.stdin.close()
                except BaseException as exc:remember(exc)
                try:cleanup=self.backend.terminate_tree(process,workdir)
                except BaseException as exc:cleanup=getattr(exc,'cleanup_outcome',None);remember(exc)
                if cleanup is not None:
                    original_cleanup=cleanup
                    cleanup={k:v for k,v in cleanup.items() if k not in ('stdout','stderr')}
                    for name in ('stdout','stderr'):
                        try:
                            raw=original_cleanup[name];require(type(raw)is bytes,'INVALID_CLEANUP_STREAM')
                            cleanup[name+'_observed']={'bytes':len(raw),'sha256':digest_bytes(raw)}
                            self.meter.observe('read_bytes',len(raw));persist('cleanup-'+name,raw)
                            require(len(raw)<=CLEANUP_CAPTURE_CAP+1,'CLEANUP_STREAM_CAPTURE_EXHAUSTED')
                        except BaseException as exc:remember(exc)
                # A cleanup/kill error must never skip the original wait. The
                # successful supervisor stop normally makes this wait immediate.
                try:process.wait(timeout=2);waited=True
                except BaseException as exc:
                    remember(exc)
                    try:
                        if process.poll() is None:process.kill()
                    except BaseException as kill_error:remember(kill_error)
                    try:process.wait(timeout=10);waited=True
                    except BaseException as wait_error:remember(wait_error)
                end=time.monotonic()+TERMINAL_DRAIN_SECONDS
                while selector.get_map() and time.monotonic()<end:
                    try:
                        for key,_ in selector.select(.02):read_stream(key,True)
                    except BaseException as exc:remember(exc);break
                for name in captured:
                    if not eof[name]:remember(Refusal('ORIGINAL_STREAM_EOF_UNOBSERVED',name))
                try:
                    completion=self.backend.completion(process,workdir,read_completion)
                    completion_capture_index=len(attempts)-1
                    admit_completion(completion,True)
                except BaseException as exc:self.meter.unknown('terminal_original_monitor_completion',exc);remember(exc)
                for stream in (process.stdin,process.stdout,process.stderr):
                    try:
                        if stream is not None and not stream.closed:stream.close()
                    except BaseException as exc:remember(exc)
            try:selector.close()
            except BaseException as exc:remember(exc)
            for name,fd in fds.items():
                try:os.fsync(fd);durable[name]=True
                except BaseException as exc:remember(exc)
                try:os.close(fd)
                except BaseException as exc:remember(exc)
        counter_closure=None
        if process is not None:
            try:counter_closure=self.meter.finish_child(intent['sha256'])
            except BaseException as exc:remember(exc)
        if primary is None:
            try:
                require(waited and all(eof.values()) and sent==len(body),'INCOMPLETE_ORIGINAL_PROCESS_CUSTODY')
                require(completion is not None,'MISSING_FINAL_MONITOR_COMPLETION')
                require(self.clock()-started<self.meter.limits.job_wall_seconds,'FINAL_JOB_WALL_EXCEEDED')
                self.meter.checkpoint('after_final_telemetry_stream_inventory_before_receipt')
            except BaseException as exc:remember(exc)
        # Full original JSON is already preserved in the exact final captured
        # completion file. Only its bounded, closed validated projection enters
        # ordinary/terminal receipts and downstream capsule serialization.
        projection=completion_projection(completion,completion_capture_index,paths,sizes,hashes,durable)
        record={'request_id':request_id,'intent':intent,'source_sha256':source_sha256,
            'intended_stdin':intended,'intended_stdin_bytes':len(body),'delivered_stdin_bytes':sent,
            'delivered_stdin_sha256':digest_bytes(body[:sent]),'unsent_suffix_bytes':len(body)-sent,
            'stdin_representation':'exact first delivered_stdin_bytes of immutable intended_stdin body',
            'stdout_bytes':len(captured['stdout']),'stderr_bytes':len(captured['stderr']),
            'stdout_sha256':digest_bytes(captured['stdout']),'stderr_sha256':digest_bytes(captured['stderr']),
            'streams_complete':all(eof.values()),'stream_eof':eof,'original_wait_complete':waited,
            'returncode':None if process is None else process.returncode,'completion':projection,
            'completion_attempts':attempts,'cleanup':cleanup,'counter_closure':counter_closure,'original_streams':{
                name:{'path':paths[name],'bytes':sizes[name],'sha256':hashes[name].hexdigest(),'fsync_complete':durable[name]}
                for name in fds},'primary':error_record(primary) if primary else None,
            'secondary':[error_record(x) for x in secondary],'durable_receipt_complete':False}
        # Strong original carrier exists before any fallible receipt encoding or signing.
        if primary is not None:setattr(primary,'process_outcome',record)
        try:
            encode(record,RECEIPT_CAP)
            receipt=self.journal.append('PROCESS_FAILURE' if primary else 'PROCESS_COMPLETE',record,terminal=primary is not None)
            record['durable_receipt_complete']=True
            if primary is None:self.meter.checkpoint('after_process_receipt_before_return')
        except BaseException as exc:
            remember(exc);record['original_publication_receipt']=receipt;record['durable_receipt_complete']=False
            record['primary']=error_record(primary);record['secondary']=[error_record(x) for x in secondary]
            setattr(primary,'process_outcome',record)
            try:
                receipt=self.journal.append('PROCESS_PUBLICATION_FAILURE',record,terminal=True);record['durable_receipt_complete']=True
            except BaseException as fallback:
                secondary.append(fallback);record['secondary']=[error_record(x) for x in secondary]
                self.meter.unknown('process_failure_receipt_fallback',fallback)
        if primary is not None:setattr(primary,'process_outcome',record);raise primary
        return {'receipt':receipt,'stdout':bytes(captured['stdout']),'stderr':bytes(captured['stderr']),
            'completion':projection,'outcome':record}


def completion_projection(value,index,paths,sizes,hashes,durable):
    """Bounded metadata projection; exact original JSON is never discarded."""
    if value is None:return None
    import math
    from .common import identity
    invalid=[];out={'schema':'finite_original_completion_projection_v1'}
    if type(value) is not dict:value={};invalid.append('nonobject_completion')
    raw_telemetry=value.get('telemetry',{})
    if type(raw_telemetry) is not dict:raw_telemetry={};invalid.append('nonobject_telemetry')
    for key in ('request_id','request_sha256','stdin_sha256','source_manifest_sha256',
                'monitor_source_manifest_sha256','completion_issuer'):
        item=value.get(key)
        if item is None:out[key]=None
        elif type(item) is str and len(item)<=256:out[key]=item
        else:out[key]=None;invalid.append(key)
    for key in ('monitor_pid','returncode','stdin_bytes'):
        item=value.get(key)
        if item is None:out[key]=None
        elif type(item) is int and -(2**63)<=item<2**63:out[key]=item
        else:out[key]=None;invalid.append(key)
    telemetry={}
    for key in ('cpu_seconds','peak_rss_bytes','cumulative_write_bytes'):
        item=raw_telemetry.get(key)
        if type(item) in (int,float) and math.isfinite(item) and 0<=item<2**63:telemetry[key]=item
        else:telemetry[key]=None;invalid.append('telemetry.'+key)
    for key in ('descendants_closed','original_wait_complete','observation_complete'):
        item=raw_telemetry.get(key)
        if type(item) is bool:telemetry[key]=item
        else:telemetry[key]=False;invalid.append('telemetry.'+key)
    out['telemetry']=telemetry
    for key in ('state_seals_before','state_seals_after'):
        item=value.get(key)
        out[key+'_sha256']=identity(item);out[key+'_count']=len(item) if type(item) is dict else None
    if index is not None:
        name='completion-'+str(index)
        out['exact_original_completion']={'path':paths[name],'bytes':sizes[name],
            'sha256':hashes[name].hexdigest(),'attempt_index':index,'fsync_complete':durable[name]}
    else:out['exact_original_completion']=None
    out['unrepresentable_fields']=invalid
    # Bad/missing monitor fields remain failures in original admission; they are
    # recorded here without creating an unbounded secondary closure failure.
    return out
