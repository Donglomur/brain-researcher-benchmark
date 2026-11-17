"""Trusted container PID1: isolate candidate uid, capture processes/resources.

Source only during construction. This enforces physical boundaries; it cannot
decide whether arbitrary Python performs statistical fitting in memory.
"""
import json,os,selectors,signal,subprocess,sys,time
from pathlib import Path

def need(x,m):
    if not x:raise ValueError(m)

def capture(path):
    return Path(path).read_text()

def cgroup():
    root=Path("/sys/fs/cgroup")
    cpu=dict(line.split()for line in capture(root/"cpu.stat").splitlines())
    return {"cpu_microseconds":int(cpu["usage_usec"]),
            "memory_peak_bytes":int(capture(root/"memory.peak").strip()),
            "io_stat_literal":capture(root/"io.stat")}

def main():
    need(os.getpid()==1 and os.getuid()==0,"Trusted PID1 supervisor")
    request=json.loads(Path("/inputs/worker_request.json").read_bytes())
    limits=request["budget"]
    work=Path("/work");work.chmod(0o755)
    private=work/"control";private.mkdir(mode=0o700)
    results=work/"results";results.mkdir(mode=0o700);os.chown(results,65534,65534)
    temp=results/"tmp";temp.mkdir(mode=0o700);os.chown(temp,65534,65534)
    started=time.monotonic();initial=cgroup();proc=None;selection=None
    buffers={"stdout":bytearray(),"stderr":bytearray()}
    record={"schema":"n097-container-monitor-v1","status":"started","candidate_uid":65534,
            "semantic_no_query_fitting_enforced":False,"all_dynamic_tool_calls_observed":False,
            "model_token_accounting":"Unavailable unless separately qualified model broker is selected",
            "initial_cgroup":initial,"source_request":json.loads(os.environ["N097_SOURCE_REQUEST_ID"]),
            "original_wait_returncode":None,"remaining_descendants":[]}
    def stop(signum=None,frame=None):
        record["termination_requested"]=signum
        # PID1 may kill all remaining processes in its own private PID namespace.
        try:os.kill(-1,signal.SIGKILL)
        except ProcessLookupError:pass
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    try:
        need(limits["threads"]==1,"One native numerical thread")
        def child_identity():
            os.setgroups([]);os.setgid(65534);os.setuid(65534)
            need(os.getuid()==65534 and os.getgid()==65534,"Candidate privilege drop")
            status={line.split(":",1)[0]:line.split(":",1)[1].strip()for line in Path("/proc/self/status").read_text().splitlines()if ":"in line}
            need(all(int(status[k],16)==0 for k in("CapEff","CapPrm","CapAmb"))and status["NoNewPrivs"]=="1","Candidate has no capabilities or privilege escalation")
        env={"PATH":"/usr/local/bin:/usr/bin:/bin","TMPDIR":"/work/results/tmp","PYTHONDONTWRITEBYTECODE":"1","PYTHONHASHSEED":"0",
             "OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1"}
        argv=["python3","-I","-B","/programme/"+request["entrypoint"],"--request","/inputs/worker_request.json","--output-dir","/work/results"]
        proc=subprocess.Popen(argv,cwd="/programme",env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              start_new_session=True,preexec_fn=child_identity)
        record["candidate_pid"]=proc.pid;record["argv"]=argv
        selection=selectors.DefaultSelector()
        for name,pipe in (("stdout",proc.stdout),("stderr",proc.stderr)):
            os.set_blocking(pipe.fileno(),False);selection.register(pipe,selectors.EVENT_READ,name)
        while selection.get_map()or proc.poll()is None:
            elapsed=time.monotonic()-started;observed=cgroup()
            need(elapsed<limits["wall_seconds"],"Original worker wall limit")
            need((observed["cpu_microseconds"]-initial["cpu_microseconds"])/1e6<=limits["cpu_seconds"],"Aggregate cgroup CPU limit")
            need(observed["memory_peak_bytes"]<=limits["memory_bytes"],"Cgroup whole-tree peak memory")
            for key,_ in selection.select(.02):
                chunk=os.read(key.fileobj.fileno(),min(65536,8_000_001-len(buffers[key.data])))
                if not chunk:selection.unregister(key.fileobj);key.fileobj.close();continue
                buffers[key.data].extend(chunk);need(len(buffers[key.data])<=8_000_000,"Complete original stream cap")
        record["original_wait_returncode"]=proc.wait(timeout=max(.001,limits["wall_seconds"]-(time.monotonic()-started)))
        record["status"]="process_completed"if record["original_wait_returncode"]==0 else"process_failed"
    except BaseException as exc:
        record.update(status="failed",error_type=type(exc).__name__,reason=str(exc))
    finally:
        stop()
        cleanup_end=time.monotonic()+2
        if proc is not None:
            try:proc.wait(timeout=max(.001,cleanup_end-time.monotonic()))
            except subprocess.TimeoutExpired:record["cleanup_timeout"]=True
        # Reap original/adopted children; PID namespace teardown remains an
        # independently inspected outer-container removal barrier as well.
        while time.monotonic()<cleanup_end:
            try:
                pid,status=os.waitpid(-1,os.WNOHANG)
                if pid==0:time.sleep(.01);continue
            except ChildProcessError:break
        if selection is not None:selection.close()
        if proc is not None:
            for p in (proc.stdout,proc.stderr):
                if not p.closed:p.close()
        record["final_cgroup"]=cgroup();record["elapsed_seconds"]=time.monotonic()-started
        for name,body in buffers.items():(private/(name+".bin")).write_bytes(body)
        for item in Path("/proc").iterdir():
            if item.name.isdigit()and int(item.name)!=1:record["remaining_descendants"].append(int(item.name))
        record["all_descendants_reaped"]=not record["remaining_descendants"]
        (private/"MONITOR.json").write_text(json.dumps(record,sort_keys=True)+"\n")
    return 0 if record["status"]=="process_completed"and record["all_descendants_reaped"]else 2

if __name__=="__main__":raise SystemExit(main())
