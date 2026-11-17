"""Original process observation, complete streams and bounded termination.

The host launcher is only for explicitly selected inert engineering controls.
Scientific execution must enter the concrete isolated OCI/cgroup runner.
"""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from .io import need, read, identity, dump, write_new, canonical, load


def terminate(proc,events=None):
    events=[] if events is None else events
    if proc is None:return events
    for sig in (signal.SIGTERM,signal.SIGKILL):
        try:os.killpg(proc.pid,sig);events.append({"signal":int(sig),"group":proc.pid})
        except ProcessLookupError:events.append({"signal":int(sig),"group_absent":True})
        try:proc.wait(timeout=.2)
        except subprocess.TimeoutExpired:continue
    try:os.killpg(proc.pid,0);events.append({"group_absence_unconfirmed":True})
    except ProcessLookupError:events.append({"group_absent":True})
    return events


def command(argv,cwd,env,request,root,*,wall_ms,stream_bytes,observer=None,observation=None):
    from .observation import Observation
    o=Observation('command') if observation is None else observation
    try:
        return _command(argv,cwd,env,request,root,wall_ms=wall_ms,stream_bytes=stream_bytes,observer=observer,observation=o)
    except BaseException as exc:o.fail(exc,'command_terminal');o.raise_failure()


def _command(argv,cwd,env,request,root,*,wall_ms,stream_bytes,observer=None,observation=None):
    """Original carrier is caller-owned before every fallible startup effect."""
    from .observation import Observation
    o=Observation('command') if observation is None else observation
    record=o.record
    record.update(schema='cogm-original-command-v1',argv=argv,environment=env,
        cwd=None,request=None,pid=None,launch_attempted=False,returncode=None,
        natural_completion=False,failure=None,cleanup=[],wall_limit_ms=wall_ms,
        stream_cap=stream_bytes,streams={},wait_observed=False,pipe_eof={'stdout':False,'stderr':False})
    streams={'stdout':bytearray(),'stderr':bytearray()};o.streams=streams
    proc=stdin=sel=None;root=Path(root);start=time.monotonic();deadline=None
    record['command_started']=start;record['original_worker_deadline']=o.deadline
    try:
        need(type(argv)is list and argv and all(type(x)is str for x in argv),'Exact exec argv')
        need(type(wall_ms)is int and wall_ms>0 and type(stream_bytes)is int and stream_bytes>0,'Explicit command bounds')
        deadline=o.deadline if o.deadline is not None else start+wall_ms/1000;record['cwd']=str(Path(cwd).absolute())
        need(not root.exists(),'Fresh original command directory');root.mkdir(parents=True)
        input_body=canonical(request)+b'\n';record['request']=identity(input_body)
        if o.publish('stdin.json',input_body,lambda:write_new(root/'stdin.json',input_body,len(input_body))) is None:
            o.raise_failure()
        stdin=open(root/'stdin.json','rb');o.handles['stdin']=stdin
        record['launch_attempted']=True
        proc=subprocess.Popen(argv,cwd=cwd,env=env,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        o.handles['process']=proc;record['pid']=proc.pid
        sel=selectors.DefaultSelector();o.handles['selector']=sel
        for name,s in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            o.handles[name]=s;os.set_blocking(s.fileno(),False);sel.register(s,selectors.EVENT_READ,name)
        while sel.get_map() or proc.poll() is None:
            need(time.monotonic()<deadline,'Original command wall deadline')
            if observer:observer(False)
            for key,_ in sel.select(timeout=min(.02,max(0,deadline-time.monotonic()))):
                data=os.read(key.fileobj.fileno(),min(65536,stream_bytes+1-len(streams[key.data])))
                # Consume into the original carrier before any bounds/EOF close.
                streams[key.data].extend(data)
                if not data:
                    record['pipe_eof'][key.data]=True;sel.unregister(key.fileobj);key.fileobj.close();continue
                need(len(streams[key.data])<=stream_bytes,'Original stream allowance')
        remaining=deadline-time.monotonic();need(remaining>0,'Deadline includes EOF and final wait')
        record['returncode']=proc.wait(timeout=remaining);record['wait_observed']=True
        record['natural_completion']=record['returncode']==0 and time.monotonic()<=deadline
        if observer:observer(True)
    except BaseException as exc:o.fail(exc,'command_execution')
    # Each finalizer is independent. No cleanup or publication can replace the
    # first error or erase an already returned original wait/status/pipe prefix.
    if sel is not None:o.attempt('selector_close',sel.close)
    if proc is not None:
        value=o.attempt('process_cleanup',lambda:terminate(proc,record['cleanup']))
        if value is not None:record['cleanup']=value
        rc=o.attempt('final_poll',proc.poll)
        if rc is not None:record['returncode']=rc
        for name,s in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            o.attempt(name+'_close',lambda s=s:s.close() if not s.closed else None)
    if stdin is not None:o.attempt('stdin_close',stdin.close)
    record['wall_ms']=int((time.monotonic()-start)*1000)
    record['creation_outcome']='observed_process_handle' if proc is not None else 'dispatch_failed' if record['launch_attempted'] else 'not_dispatched'
    for name,b in streams.items():
        # Descriptor means consumed bytes, independently of publication status.
        record['streams'][name]=identity(b)
        o.publish(name+'.bin',b,lambda name=name,b=b:write_new(root/(name+'.bin'),bytes(b),stream_bytes+1))
    record['failure']=o.failure();record['secondary_failures']=o.secondary()
    record['publication']=o.publication_summary()
    o.completed=record
    o.publish('COMMAND.json',record,lambda:dump(root/'COMMAND.json',record))
    if o.deadline is not None:o.attempt('command_publication_complete',lambda:o.check_deadline('command_publication_complete'))
    if o.first_error is not None:o.raise_failure()
    return record


def engineering(script,selected,request,root,*,wall_ms=2000,stream_bytes=65536,observation=None):
    import sys
    from .observation import Observation
    o=Observation('engineering') if observation is None else observation
    c=Observation('command');o.children['command']=c
    try:
        need(request.get('engineering_only')is True and request.get('scientific_providers')=='inert','No scientific host execution')
        need(0<wall_ms<=10000 and 0<stream_bytes<=1000000,'Tiny engineering command')
        root=Path(root);need(not root.exists(),'Fresh engineering work');root.mkdir(parents=True)
        body=read(script,1000000,selected);write_new(root/'selected.py',body,1000000)
        argv=[sys.executable,'-I','-B',str((root/'selected.py').absolute())]
        record=command(argv,root,{'PATH':os.defpath},request,root/'command',wall_ms=wall_ms,stream_bytes=stream_bytes,observation=c)
        o.record=record;o.completed=record
        record['engineering_only']=True;record['source']=selected;record['scientifically_qualified']=False
        o.publish('ENGINEERING.json',record,lambda:dump(root/'ENGINEERING.json',record))
        if o.first_error is not None:o.raise_failure()
        return record
    except BaseException as exc:o.fail(exc,'engineering');o.raise_failure()


def validate_command(root,expected_argv,expected_request,expected_env,expected_cwd,pin=None):
    root=Path(root);r=load(root/'COMMAND.json',1000000,pin)
    need(r['argv']==expected_argv and r['environment']==expected_env and r['cwd']==str(Path(expected_cwd).absolute()),"Exact original execution command/environment/cwd")
    need(r['request']==identity(canonical(expected_request)+b'\n')and load(root/'stdin.json')==expected_request,"Exact actual stdin body")
    need(type(r['returncode'])is int and r['returncode']==0 and r['natural_completion']is True and r['failure']is None,"Original outer exit including exit-7 refusal")
    need(r['creation_outcome']=='observed_process_handle'and type(r['pid'])is int,"Actual original process creation")
    need(r['wall_ms']<=r['wall_limit_ms']and not any(x.get('group_absence_unconfirmed')for x in r['cleanup']),"Original completion/cleanup bounds")
    for name in ('stdout','stderr'):read(root/(name+'.bin'),r['stream_cap'],r['streams'][name])
    return r
