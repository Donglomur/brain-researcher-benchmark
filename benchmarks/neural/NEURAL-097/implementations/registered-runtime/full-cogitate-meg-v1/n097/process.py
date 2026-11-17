"""Bounded controller-owned process custody; host execution is engineering-only.

Scientific jobs require a separately qualified sandbox lease and cannot use the
engineering launcher. A process return code alone never qualifies isolation or
scientific source/data/method semantics.
"""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from .io import need, identity, canonical, write_json, write_new, read, Refusal

def _stop(proc, grace):
    records=[]
    if proc is None:
        return records
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid,sig);records.append({"signal":int(sig),"group":proc.pid})
        except ProcessLookupError:
            records.append({"signal":int(sig),"group_absent":True})
        try:
            proc.wait(timeout=max(0.001,grace))
            # Kill the group even if its leader exited; descendants may remain.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            return records
        except subprocess.TimeoutExpired:
            pass
    return records+[{"cleanup_unconfirmed":True}]

def _execute(script, script_pin, request, output, *, wall_seconds, stream_cap, engineering):
    """Selected tiny inert metadata processes only; never an authentic candidate."""
    import sys
    root=Path(output)
    need(not root.exists(),"Fresh engineering attempt directory")
    root.mkdir(parents=True)
    start=time.monotonic();deadline=None
    proc=None; streams={"stdout":bytearray(),"stderr":bytearray()}
    record={"schema":"n097-original-process-v1","status":"prelaunch","scientifically_qualified":False,
            "request_identity":identity(canonical(request)),"source_pin":script_pin,
            "protected_job":request.get("protected_job"),"contract":request.get("contract"),
            "argv":None,"returncode":None,"cleanup":[],"stream_cap":stream_cap,
            "deadline_seconds":wall_seconds,"engineering_only":engineering,"launch_attempted":False}
    try:
        need(type(wall_seconds)in(int,float)and type(stream_cap)is int,"Typed bounded process declaration")
        if engineering:
            need(request.get("engineering_only")is True and request.get("scientific_kernels")=="stubbed","No science through engineering launcher")
            need(0<wall_seconds<=10 and 0<stream_cap<=1_000_000,"Tiny selected engineering limits")
        else:
            from .contract import require_deployment
            require_deployment()
            need(0<wall_seconds<=3600 and 0<stream_cap<=8_000_000,"Declared scientific driver bounds")
        deadline=start+wall_seconds
        body=read(script,1_000_000,script_pin)
        # Snapshot the authenticated selected source. Never import it in this controller.
        selected=root/"selected_worker.py"
        write_new(selected,body,1_000_000)
        write_json(root/"request.json",request,1_000_000)
        argv=[sys.executable,"-I","-B",str(selected.absolute()),str((root/"request.json").absolute()),str((root/"worker_output.json").absolute())]
        record["argv"]=argv
        record["interpreter"]=sys.executable
        record["cwd"]=str(root.absolute())
        record["environment"]={"PATH":os.defpath,"PYTHONHASHSEED":"0"}
        record["launch_attempted"]=True
        proc=subprocess.Popen(argv,cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              env={"PATH":os.defpath,"PYTHONHASHSEED":"0"},start_new_session=True)
        record["pid"]=proc.pid;record["status"]="running"
        selector=selectors.DefaultSelector()
        try:
            for name,stream in (("stdout",proc.stdout),("stderr",proc.stderr)):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
            while selector.get_map():
                remaining=deadline-time.monotonic()
                need(remaining>0,"Original process deadline exhausted")
                for key,_ in selector.select(timeout=min(.05,remaining)):
                    chunk=os.read(key.fileobj.fileno(),min(65536,stream_cap-len(streams[key.data])+1))
                    if not chunk:
                        selector.unregister(key.fileobj);key.fileobj.close();continue
                    streams[key.data].extend(chunk)
                    need(len(streams[key.data])<=stream_cap,"Full stream cap exceeded")
            remaining=deadline-time.monotonic()
            need(remaining>0,"Deadline expired after pipe EOF")
            record["returncode"]=proc.wait(timeout=remaining)
            record["status"]="process_completed" if record["returncode"]==0 else "process_failed"
        finally:
            selector.close()
    except BaseException as exc:
        record["status"]="failed"
        record["error_type"]=type(exc).__name__;record["reason"]=str(exc)[:2048]
    finally:
        record["cleanup"]=_stop(proc,.1)
        if proc is not None:
            record["returncode"]=proc.poll()
            for stream in (proc.stdout,proc.stderr):
                if stream is not None and not stream.closed:stream.close()
        record["process_creation_outcome"]="process_handle_observed"if proc is not None else("not_dispatched"if not record["launch_attempted"]else"dispatch_failed_no_handle")
        record["elapsed_seconds"]=time.monotonic()-start
        record["streams"]={}
        for name,body in streams.items():
            # A cap-exceeding last byte is retained as original failure evidence.
            record["streams"][name]=write_new(root/(name+".bin"),bytes(body),stream_cap+1 if type(stream_cap)is int and stream_cap>=0 else 1_000_001)
        record["descendant_resource_qualification"]=False
        record["scientific_state_isolation_qualification"]=False
        write_json(root/"PROCESS_RECORD.json",record,1_000_000)
    return record

def engineering_execute(script, script_pin, request, output, *, wall_seconds=2.0, stream_cap=65536):
    return _execute(script,script_pin,request,output,wall_seconds=wall_seconds,stream_cap=stream_cap,engineering=True)

def scientific_driver_execute(script, script_pin, request, output, *, wall_seconds, stream_cap):
    return _execute(script,script_pin,request,output,wall_seconds=wall_seconds,stream_cap=stream_cap,engineering=False)
