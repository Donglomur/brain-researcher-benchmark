"""Trusted fixed wrapper for an actual generated analysis/fit/query programme.

Runs only inside an independently admitted source/view/process realm. Ordinary
local subprocess execution is not an isolation proof. No scores are accepted
from the programme; validation and protected scoring remain operator-owned.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import time

def need(value,message):
    if not value:raise ValueError(message)

def finish_owned(operations,primary=None):
    first=primary
    for phase,operation in operations:
        try:operation()
        except BaseException as error:
            if first is None:first=error
            else:
                try:
                    records=list(getattr(first,'ach_secondary_errors',[]));records.append({'phase':phase,'type':type(error).__name__})
                    first.ach_secondary_errors=records
                except BaseException:pass
    if primary is None and first is not None:raise first

def body(path,cap):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));primary=None
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=cap,'ordinary bounded file')
        parts=[];left=cap+1
        while left:
            block=os.read(fd,min(left,65536))
            if not block:break
            parts.append(block);left-=len(block)
        raw=b''.join(parts)
        t=os.fstat(fd);need(len(raw)==s.st_size and (s.st_ino,s.st_size,s.st_mtime_ns)==
             (t.st_ino,t.st_size,t.st_mtime_ns),'immutable exact body')
        return raw
    except BaseException as error:primary=error;raise
    finally:finish_owned([('worker input close',lambda:os.close(fd))],primary)

def digest(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def decoded(raw):
    def pairs(rows):
        result={}
        for k,v in rows:need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def invalid(v):raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)

def write_json(path,value,cap):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    need(len(raw)<=cap,'preventive trusted metadata output ceiling')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o400);primary=None
    try:
        data=memoryview(raw)
        while data:
            n=os.write(fd,data);need(n>0,'complete trusted metadata write');data=data[n:]
        os.fsync(fd)
    except BaseException as error:primary=error;raise
    finally:finish_owned([('worker metadata close',lambda:os.close(fd))],primary)
    return {'path':path.name,**digest(raw)}

def run(request_path='/request/JOB.json',output_root='/output'):
    # This wrapper's finite caps and actual argv/source identities are themselves
    # part of the independently admitted fixed-mount request binding.
    request=decoded(body(request_path,1048576))
    need(set(request)=={'schema','job_id','kind','program','input','limits','origin_ns','deadline_ns'},'exact generated job request')
    need(request['schema']=='ach_generated_program_job_v1' and request['kind'] in ('analysis','fit','predict'),
         'fixed generated-programme protocol')
    need(type(request['job_id']) is str and 0<len(request['job_id'])<=128 and
         all(c.isalnum() or c in '_-.' for c in request['job_id']),'opaque non-identifying job token')
    limits=request['limits'];need(set(limits)=={'code_bytes','input_bytes','result_bytes','model_bytes','max_files','stdout_bytes','stderr_bytes'},
                                'complete preventive job limits')
    need(all(type(x) is int and x>0 for x in limits.values()),'exact positive caps')
    need(limits['max_files']>=3,'space for result and trusted execution/index metadata')
    origin,deadline=request['origin_ns'],request['deadline_ns']
    need(type(origin) is int and type(deadline) is int and origin<=time.monotonic_ns()<deadline,'original strict worker cutoff')
    program=request['program'];inputs=request['input']
    need(set(program)==set(inputs)=={'path','bytes','sha256'},'exact committed code/input bodies')
    source=body(program['path'],limits['code_bytes']);need(digest(source)=={k:program[k] for k in ('bytes','sha256')},'same generated source')
    raw_input=body(inputs['path'],limits['input_bytes']);need(digest(raw_input)=={k:inputs[k] for k in ('bytes','sha256')},'same exact minimized input')
    out=Path(output_root);candidate=out
    need(out.is_dir() and not any(out.iterdir()),'fresh empty owned output directory')
    need(origin<=time.monotonic_ns()<deadline,'original cutoff immediately before generated programme spawn')
    child=None;streams=None;primary=None
    captured={'stdout':bytearray(),'stderr':bytearray()}
    try:
        child=subprocess.Popen([sys.executable,'-I','-B',program['path'],inputs['path'],str(candidate)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
        streams=selectors.DefaultSelector()
        for stream,name in ((child.stdout,'stdout'),(child.stderr,'stderr')):
            os.set_blocking(stream.fileno(),False);streams.register(stream,selectors.EVENT_READ,name)
        while streams.get_map():
            need(time.monotonic_ns()<deadline,'generated programme/EOF original cutoff')
            for key,_ in streams.select(min(.05,max(0,(deadline-time.monotonic_ns())/1e9))):
                name=key.data;cap=limits[name+'_bytes'];remaining=cap-len(captured[name])
                chunk=os.read(key.fd,min(65536,remaining+1))
                if not chunk:streams.unregister(key.fileobj);continue
                need(len(chunk)<=remaining,'preventive generated stdout/stderr extent')
                captured[name].extend(chunk)
                # The independent outer supervisor retains the actual child
                # streams, including failures; an internal hash alone is not a log.
                destination=1 if name=='stdout' else 2
                view=memoryview(chunk)
                while view:
                    need(time.monotonic_ns()<deadline,'original cutoff while forwarding child evidence')
                    written=os.write(destination,view);need(written>0,'actual evidence stream write')
                    view=view[written:]
        code=child.wait(timeout=max(.001,(deadline-time.monotonic_ns())/1e9))
        need(type(code) is int and code>=0 and time.monotonic_ns()<deadline,
             'actual generated programme natural exit within original cutoff; signal/timeout is not a tool diagnostic')
    except BaseException as error:primary=error;raise
    finally:
        cleanup=[]
        if streams is not None:cleanup.append(('worker selector close',streams.close))
        if child is not None:
            for name in ('stderr','stdout'):
                stream=getattr(child,name)
                if stream is not None:cleanup.append(('worker '+name+' close',stream.close))
        # The outer independently owned cgroup supervisor handles a still-live
        # child/descendant on failure. No post-reap group signal or cleanup claim.
        finish_owned(cleanup,primary)
    if code==0:
        result=decoded(body(candidate/'RESULT.json',limits['result_bytes']))
        need(type(result) is dict and result.get('kind')==request['kind'],'actual typed generated result')
    outputs={};total=0
    inventory=sorted(candidate.iterdir(),key=lambda f:f.name)
    need(len(inventory)<=limits['max_files']-2,'complete generated output inventory cap including trusted metadata')
    for file in inventory:
        need(file.is_file() and not file.is_symlink(),'ordinary direct-child output files only')
        cap=limits['result_bytes'] if file.name=='RESULT.json' else limits['model_bytes']
        raw=body(file,cap);total+=len(raw);need(total<=limits['model_bytes']+limits['result_bytes'],'complete generated artifact cap')
        # The separate supervisor waits for every owned descendant and seals the
        # original outputs. Later bounded reads must match these exact hashes;
        # a descendant's late write cannot become a silently different model.
        fd=os.open(file,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));primary=None
        try:os.fsync(fd)
        except BaseException as error:primary=error;raise
        finally:finish_owned([('generated output fsync descriptor close',lambda:os.close(fd))],primary)
        outputs[file.name]={'path':file.name,**digest(raw)}
    evidence={'kind':request['kind'],'job_id':request['job_id'],'program_pin':digest(source),'input_pin':digest(raw_input),
        'actual_child_exit_code':code,'stdout_pin':digest(bytes(captured['stdout'])),'stderr_pin':digest(bytes(captured['stderr'])),
        'status':'completed' if code==0 else 'generated_program_failed',
        'stderr_excerpt':bytes(captured['stderr'])[-4096:].decode('utf-8','replace'),
        'independent_outer_closure_still_required':True}
    outputs['EXECUTION.json']=write_json(out/'EXECUTION.json',evidence,limits['result_bytes'])
    index={'schema':'ach_controller_job_index_v1','job_id':request['job_id'],'outputs':outputs}
    write_json(out/'RESULT_INDEX.json',index,limits['result_bytes'])
    fd=os.open(out,os.O_RDONLY|getattr(os,'O_DIRECTORY',0));primary=None
    try:os.fsync(fd)
    except BaseException as error:primary=error;raise
    finally:finish_owned([('worker output directory close',lambda:os.close(fd))],primary)
    return 0

if __name__=='__main__':
    raise SystemExit(run())
