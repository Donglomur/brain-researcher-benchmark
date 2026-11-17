"""Bounded ownership for selected NEURAL006 runs; definitions have no side effects."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
from protocol import canonical, need

def parse(body):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'duplicate_json_key');out[key]=value
        return out
    return json.loads(body,object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_json')))

class Custody:
    def __init__(self,output,limits,start):
        self.output=Path(output);need(not self.output.exists(),'fresh_output_required')
        self.output.mkdir(parents=False)
        self.limits=limits;self.start=start
        self.end=self.start+limits['wall_seconds'];self.work_end=self.end-limits['cleanup_seconds']
        self.read_bytes=0;self.written_bytes=0;self.staged_bytes=0
        self.events=[];self.processes=[];self.fit_calls=0;self.first_error=None
        self.actor_records=[]
        self.files_reserved=0
        self.publication_reserve=min(65536,limits['retained_bytes']//8)

    def event(self,phase,error):
        if self.first_error is None:self.first_error=error
        self.events.append({'phase':phase,'class':type(error).__name__,'message':str(error)[:1024]})

    def check(self,cleanup=False):
        if not cleanup and self.first_error is not None:raise self.first_error
        need(time.monotonic()<(self.end if cleanup else self.work_end),'original_horizon_expired')

    def attempt(self,phase,operation):
        try:return operation()
        except BaseException as error:self.event(phase,error);return None

    def read(self,path,size,sha):
        self.check();path=Path(path);fd=None;primary=None;result=None
        need(type(size) is int and size>=0 and self.read_bytes+size<=self.limits['read_bytes'],'read_reservation')
        need(all(not p.is_symlink() for p in (path,*path.parents)),'no_source_symlinks')
        self.read_bytes+=size
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);a=os.fstat(fd)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==size,'source_extent')
            chunks=[];left=size
            while left:
                chunk=os.read(fd,min(left,65536));need(bool(chunk),'short_read');chunks.append(chunk);left-=len(chunk)
            need(not os.read(fd,1),'growing_source');b=os.fstat(fd)
            need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'changed_source')
            result=b''.join(chunks);need(hashlib.sha256(result).hexdigest()==sha,'source_digest')
        except BaseException as error:primary=error;self.event('read',error)
        finally:
            if fd is not None:self.attempt('read_close',lambda:os.close(fd))
            self.attempt('read_final_horizon',self.check)
        if self.first_error is not None:raise self.first_error
        return result

    def write_body(self,path,body,mode,diagnostic,phase):
        fd=None;old_count=len(self.events)
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
            os.fchmod(fd,mode)
            need(stat.S_IMODE(os.fstat(fd).st_mode)==mode,'exact_owned_file_mode')
            offset=0
            while offset<len(body):
                count=os.write(fd,body[offset:]);need(count>0,'short_write');offset+=count
            os.fsync(fd)
        except BaseException as error:self.event(phase,error)
        finally:
            if fd is not None:self.attempt(phase+'_close',lambda:os.close(fd))
            self.attempt(phase+'_final_horizon',lambda:self.check(cleanup=diagnostic))
        if len(self.events)>old_count:raise self.first_error

    def write(self,name,value,diagnostic=False):
        return self.write_bytes(name,canonical(value),diagnostic)

    def write_bytes(self,name,body,diagnostic=False):
        need(type(name) is str and name and '/' not in name and name not in ('.','..'),'output_name')
        self.check(cleanup=diagnostic);need(type(body) is bytes,'output_body_type')
        limit=self.limits['retained_bytes']-(0 if diagnostic else self.publication_reserve)
        need(len(body)<=self.limits['per_file_bytes'] and self.written_bytes+len(body)<=limit,'retention_reservation')
        need(self.files_reserved<self.limits['max_files'],'output_file_reservation');self.files_reserved+=1
        self.written_bytes+=len(body);path=self.output/name
        self.write_body(path,body,0o600,diagnostic,'write')
        return {'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

    def stage(self,path,body):
        self.check();need(type(body) is bytes and len(body)<=self.limits['per_file_bytes'],'stage_member_cap')
        self.staged_bytes+=len(body);need(self.staged_bytes<=self.limits['staged_write_bytes'],'total_stage_write_cap')
        # Private0700 parent; exact mounted files readable by a different container UID, bind read-only.
        self.write_body(path,body,0o444,False,'stage')

    def group_absent(self,p):
        try:os.killpg(p.pid,0)
        except ProcessLookupError:return True
        return False

    def close_process(self,p,selector,streams,failed,receipt):
        """Every cleanup is attempted independently, including a leader-exited residual group."""
        if p is not None:
            absent=self.attempt('process_group_probe',lambda:self.group_absent(p))
            if failed or absent is not True:
                if absent is not True:
                    def kill():
                        try:os.killpg(p.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    self.attempt('process_group_kill',kill)
                self.attempt('process_reap',lambda:p.wait(timeout=max(.001,self.end-time.monotonic())))
            receipt['returncode']=self.attempt('process_final_poll',p.poll)
            receipt['group_absent']=self.attempt('process_final_group',lambda:self.group_absent(p))
            if receipt['group_absent'] is not True:self.event('process_group_remains',RuntimeError('owned_group_not_absent'))
        if selector is not None:self.attempt('selector_close',selector.close)
        for index,stream in enumerate(streams):
            if stream is not None:self.attempt('stream_close_'+str(index),stream.close)

    def command(self,argv,seconds,stdout_cap=65536,cleanup=False):
        self.check(cleanup);end=min(self.end if cleanup else self.work_end,time.monotonic()+seconds)
        old_count=len(self.events);p=None;selector=None;buffers={};out=b''
        receipt={'argv':argv,'status':'entered'};self.processes.append(receipt);eof=[]
        try:
            p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            receipt['pid']=p.pid;selector=selectors.DefaultSelector();buffers={p.stdout:bytearray(),p.stderr:bytearray()}
            for stream in buffers:
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                need(time.monotonic()<end,'control_process_deadline')
                for key,_ in selector.select(min(.05,max(0,end-time.monotonic()))):
                    block=os.read(key.fileobj.fileno(),4096)
                    if not block:selector.unregister(key.fileobj);eof.append(key.fileobj)
                    else:
                        need(sum(map(len,buffers.values()))+len(block)<=stdout_cap,'control_stream_cap')
                        buffers[key.fileobj].extend(block)
            p.wait(timeout=max(.001,end-time.monotonic()))
            need(p.returncode==0,'control_process_failed')
            need(self.group_absent(p),'control_group_remains')
            out=bytes(buffers[p.stdout]);receipt['status']='complete'
        except BaseException as error:self.event('control_process',error);receipt['status']='failed'
        finally:
            if p is not None:
                for stream,label in ((p.stdout,'stdout'),(p.stderr,'stderr')):
                    body=bytes(buffers.get(stream,b''));receipt[label+'_bytes']=len(body)
                    receipt[label+'_sha256']=hashlib.sha256(body).hexdigest();receipt[label+'_prefix']=body[:4096].decode(errors='replace')
                    receipt[label+'_prefix_complete']=len(body)<=4096;receipt[label+'_eof']=stream in eof
            self.close_process(p,selector,[] if p is None else [p.stdout,p.stderr],len(self.events)>old_count,receipt)
            self.attempt('command_final_horizon',lambda:self.check(cleanup=cleanup))
        if len(self.events)>old_count:raise self.first_error
        return out

    def charge_fits(self,count):
        self.check();need(type(count) is int and count>=0,'fit_count')
        self.fit_calls+=count;need(self.fit_calls<=self.limits['max_fit_calls'],'fit_call_cap')

    def evidence(self):
        return {'events':list(self.events),'processes':list(self.processes),
            'actor_records':list(self.actor_records),'logical_read_bytes':self.read_bytes,
            'retained_bytes':self.written_bytes,'staged_write_bytes':self.staged_bytes,
            'reference_fit_call_announcements':self.fit_calls,
            'output_files_reserved':self.files_reserved,
            'elapsed_seconds':time.monotonic()-self.start,'original_wall_seconds':self.limits['wall_seconds']}
