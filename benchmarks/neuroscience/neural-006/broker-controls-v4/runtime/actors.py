"""Owned, finite Docker transport for the actual original-kernel and candidate routes."""
import hashlib
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
import uuid
from custody import parse
from protocol import canonical, digest, need
from model_state import CandidateSession, TrainingSession
from reference_stream import ReferenceSession

class Actors:
    def __init__(self,custody,image,docker,sources,core,programs,seeds,recipe):
        self.custody=custody;self.image=image;self.docker=docker;self.sources=sources
        self.core=core;self.programs=programs;self.cpu_reserved=0;self.records=custody.actor_records;self.reference_number=0
        self.seeds=dict(seeds);self.recipe=recipe
        need(image=='sha256:01dfc25e93283a5f7f2031628236f95b59f4a3acd9e9e9894601fdaf60dba61d','original_image')
        need(Path(docker).is_absolute(),'absolute_docker_executable')

    def container(self,case,command,mounts,session):
        c=self.custody;c.check();seconds=c.limits['candidate_seconds_per_case']
        # Prospective simultaneous-process/time envelope, including the original cleanup reserve.
        # This is not a claim of measured aggregate daemon/container CPU or qualified containment.
        self.cpu_reserved+=16*(seconds+c.limits['cleanup_seconds'])
        need(self.cpu_reserved<=c.limits['cpu_seconds'],'prospective_cpu_reservation')
        name='neural006-'+uuid.uuid4().hex;root=None;staged=[];creation_entered=False;absent=True
        record={'container':name,'case_sha256':digest(case),'phase':'stage','removed':None}
        self.records.append(record);result=None;old_count=len(c.events)
        try:
            root=Path(tempfile.mkdtemp(prefix='neural006-case-'));record['stage_path']=str(root)
            case_path=root/'case.json';staged.append(case_path);c.stage(case_path,canonical(case))
            argv=[self.docker,'create','--pull','never','--name',name,'--network','none','--read-only',
                '--cpus','1','--memory',str(c.limits['memory_bytes']),'--memory-swap',str(c.limits['memory_bytes']),
                '--pids-limit','16','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--ulimit','cpu='+str(seconds)+':'+str(seconds),'--ulimit','nofile=128:128',
                '--tmpfs','/tmp:rw,noexec,nosuid,size=16777216','--tmpfs','/output:rw,noexec,nosuid,size=16777216',
                '--env','OPENBLAS_NUM_THREADS=1','--env','OMP_NUM_THREADS=1','--env','MKL_NUM_THREADS=1',
                '--mount','type=bind,src='+str(case_path)+',dst=/input/case.json,readonly']
            for index,(source_body,destination) in enumerate(mounts):
                source=root/('source-%02d'%index);staged.append(source);c.stage(source,source_body)
                need(',' not in str(source),'mount_path_separator')
                argv+=['--mount','type=bind,src='+str(source)+',dst='+destination+',readonly']
            argv+=['-i',self.image,*command]
            record['phase']='create';creation_entered=True;absent=False
            c.command(argv,min(15,seconds));record['phase']='attached'
            result=self.attach(name,seconds,session)
            state=parse(c.command([self.docker,'inspect','--format','{{json .State}}',name],10))
            need(state.get('Running') is False and state.get('ExitCode')==0 and state.get('OOMKilled') is False,'container_terminal_state')
            record.update(phase='natural_complete',state=state)
        except BaseException as error:c.event('container_body',error);record['phase']='failed'
        finally:
            if creation_entered:
                # Removal and absence inspection are separately attempted even when one raises.
                c.attempt('container_remove',lambda:c.command([self.docker,'rm','-f',name],10,cleanup=True))
                state=c.attempt('container_absence',lambda:c.command(
                    [self.docker,'ps','-a','--filter','name=^/'+name+'$','--format','{{.ID}}'],10,cleanup=True))
                absent=type(state) is bytes and not state.strip();record['removed']=absent
                if not absent:c.event('container_still_owned',RuntimeError('container_absence_unresolved'))
            if root is not None:
                if absent:
                    for path in reversed(staged):
                        def remove(path=path):
                            try:path.unlink()
                            except FileNotFoundError:pass
                        c.attempt('stage_file_remove',remove)
                    c.attempt('stage_directory_remove',root.rmdir)
                else:record['stage_preserved_for_unresolved_container']=True
            c.attempt('container_final_horizon',lambda:c.check(cleanup=True))
        if len(c.events)>old_count:raise c.first_error
        c.check()
        return result

    def attach(self,name,seconds,session):
        c=self.custody;end=min(c.work_end,time.monotonic()+seconds);old_count=len(c.events)
        p=None;selector=None;out=bytearray();err=bytearray();pending=bytearray();input_buffer=bytearray();eof=[]
        record={'container':name,'phase':'attach_entered'};self.records.append(record)
        try:
            if hasattr(session,'bind_deadline'):session.bind_deadline(end)
            p=subprocess.Popen([self.docker,'start','-a','-i',name],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            record['pid']=p.pid;selector=selectors.DefaultSelector()
            if session.initial is not None:input_buffer.extend(canonical(session.initial))
            need(len(input_buffer)<=c.limits['per_file_bytes'],'initial_message_cap')
            os.set_blocking(p.stdin.fileno(),False)
            if input_buffer:selector.register(p.stdin,selectors.EVENT_WRITE)
            for stream in (p.stdout,p.stderr):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                active_end=min(end,session.next_deadline()) if hasattr(session,'next_deadline') else end
                need(time.monotonic()<active_end,'candidate_original_deadline')
                for key,_ in selector.select(min(.05,max(0,active_end-time.monotonic()))):
                    stream=key.fileobj
                    if stream is p.stdin:
                        if input_buffer:
                            count=os.write(stream.fileno(),input_buffer[:65536]);need(count>0,'stdin_short_write');del input_buffer[:count]
                        if not input_buffer:
                            selector.unregister(stream)
                            if session.finished:stream.close()
                        continue
                    block=os.read(stream.fileno(),4096)
                    if not block:selector.unregister(stream);eof.append(stream);continue
                    need(len(out)+len(err)+len(block)<=c.limits['per_file_bytes'],'combined_stream_cap')
                    (out if stream is p.stdout else err).extend(block)
                    if stream is p.stdout:
                        pending.extend(block)
                        default_line_cap=c.limits['per_file_bytes'] if session.native or isinstance(session,TrainingSession) else 131072
                        line_cap=min(c.limits['per_file_bytes'],getattr(session,'protocol_line_cap',default_line_cap))
                        need(len(pending)<=line_cap,'protocol_line_cap')
                        while b'\n' in pending:
                            line,_,tail=pending.partition(b'\n');pending=bytearray(tail)
                            need(not session.finished,'output_after_final_record')
                            reply=session.exchange(parse(line));input_buffer.extend(canonical(reply))
                            need(len(input_buffer)<=c.limits['per_file_bytes'],'reply_buffer_cap')
                            if p.stdin not in [k.fileobj for k in selector.get_map().values()]:
                                selector.register(p.stdin,selectors.EVENT_WRITE)
            p.wait(timeout=max(.001,end-time.monotonic()))
            need(p.returncode==0,'attached_nonzero_exit')
            need(session.finished and not pending,'missing_final_or_partial_record')
            need(c.group_absent(p),'attached_group_remains')
            record['phase']='natural_complete'
        except BaseException as error:c.event('attached_process',error);record['phase']='failed'
        finally:
            record.update(stdout_bytes=len(out),stderr_bytes=len(err),
                stdout_sha256=hashlib.sha256(out).hexdigest(),stderr_sha256=hashlib.sha256(err).hexdigest(),
                stdout_prefix=bytes(out[:4096]).decode(errors='replace'),stderr_prefix=bytes(err[:4096]).decode(errors='replace'),
                prefixes_complete=len(out)<=4096 and len(err)<=4096,
                stdout_eof=p is not None and p.stdout in eof,stderr_eof=p is not None and p.stderr in eof)
            if isinstance(session,ReferenceSession):
                record.update(durable_fit_events=session.receipts,received_fit_slots=session.completed,
                    in_flight_slot=session.pending,fit_call_announcements=session.calls,
                    unacknowledged_event=session.unacknowledged,
                    unentered_slots=session.slots[len(session.completed)+(1 if session.pending else 0):])
            c.close_process(p,selector,[] if p is None else [p.stdin,p.stdout,p.stderr],len(c.events)>old_count,record)
            c.attempt('attach_final_horizon',lambda:c.check(cleanup=True))
        if len(c.events)>old_count:raise c.first_error
        c.check()
        return session.value

    def reference(self,case):
        self.reference_number+=1;session=ReferenceSession(self.custody,self.reference_number,case)
        return self.container(case,['Rscript','--vanilla','/protocol/reference_worker.R','/protocol/core.R',
            '/input/case.json','/dev/stdout'],[(self.core,'/protocol/core.R'),
            (self.sources['reference_worker.R'],'/protocol/reference_worker.R')],session)

    def candidate(self,mode,case,reference,model=None,training_context=None,vault=None):
        mounts=[(self.programs[mode],'/candidate/program.py'),(self.core,'/protocol/core.R'),
                (self.sources['TASK.md'],'/protocol/TASK.md')]
        if model is not None:
            need(vault is not None and training_context is not None,'issued_frozen_state_required')
            record=vault.resolve(model,mode,self.recipe,self.seeds[mode],digest(training_context))
            body=record[4];model=vault.describe(model,mode)
            mounts.append((body,'/input/model.bin'))
        return self.container(case,['python3','-I','-B','/candidate/program.py'],mounts,
            CandidateSession(case,reference,self.custody.limits['tool_calls_per_case'],self.seeds[mode],model,training_context))

    def train_candidate(self,mode,training,reference_model,vault):
        return self.container(training,['python3','-I','-B','/candidate/program.py'],
            [(self.programs[mode],'/candidate/program.py'),(self.core,'/protocol/core.R'),
             (self.sources['TASK.md'],'/protocol/TASK.md')],
            TrainingSession(training,reference_model,vault,self.recipe,self.custody.limits['tool_calls_per_case'],self.seeds[mode],
                            self.custody.limits['model_artifact_bytes']))
