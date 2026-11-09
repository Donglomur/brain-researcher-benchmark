"""Original outer process/cgroup/stream observer for a separately selected authentic operation."""
import os,stat,time,selectors,subprocess,hashlib,resource
from pathlib import Path
from .common import exact,need,absolute,read,pin,canonical,Ledger,decode
from .native import _kv,_text
from .final_policy import final_outer
from .evidence import Reserve
def launch(spec):
    exact(spec,["schema","argv","source_files","request","cgroup","private_output","wall_seconds","cleanup_seconds",
                "memory_bytes","pids","cpu_max","cpu_us","io_max","stdout_bytes","stderr_bytes","read_bytes","write_bytes","provider_environment_names","interpreter","entrypoint","operation","failure_evidence"])
    need(spec["schema"]=="neural047-original-outer-lifetime-v1" and os.uname().sysname=="Linux","Selected Linux outer lifetime")
    # Original interval starts before source/request authentication or directory creation.
    started=time.monotonic();deadline=started+spec["wall_seconds"];cleanup_deadline=deadline+spec["cleanup_seconds"]
    before_cpu=resource.getrusage(resource.RUSAGE_SELF)
    L=Ledger({"wall_seconds":spec["wall_seconds"]+spec["cleanup_seconds"],"read_bytes":spec["read_bytes"],"write_bytes":spec["write_bytes"],
              "provider_requests":1,"input_tokens":1,"output_tokens":1})
    L.started=started;L.deadline=cleanup_deadline;L.work_deadline=cleanup_deadline
    need(spec["failure_evidence"]["wall_seconds"]==spec["cleanup_seconds"],"Outer evidence is within original cleanup reserve")
    E=Reserve(L,spec["failure_evidence"])
    cg=absolute(spec["cgroup"]);out=absolute(spec["private_output"])
    need(not cg.exists() and cg.parent.is_dir() and not out.exists() and out.parent.is_dir(),"Fresh owned outer roots")
    proc=None;sel=selectors.DefaultSelector();streams={};errors=[];root_waited=False;subtree_empty=False;code=None;cg_owned=False;out_owned=False
    observations={"schema":"neural047-original-outer-observation-v1","argv":spec["argv"],"process_starts":0,"outputs":{}}
    def active():
        need(time.monotonic()<deadline,"Original outer active deadline")
        own=resource.getrusage(resource.RUSAGE_SELF)
        own_us=int(1e6*((own.ru_utime-before_cpu.ru_utime)+(own.ru_stime-before_cpu.ru_stime)))
        cpu=_kv(cg/"cpu.stat")["usage_usec"] if (cg/"cpu.stat").exists() else 0
        observations["subtree_cpu_us"]=cpu;observations["outer_own_cpu_us"]=own_us
        need(cpu+own_us<=spec["cpu_us"],"Total original outer plus subtree CPU")
    def drain(timeout):
        for key,_ in sel.select(timeout):
            body=os.read(key.fd,65536)
            if not body:sel.unregister(key.fileobj);continue
            streams[key.data].append(body)
    try:
        need(type(spec["source_files"]) is list and spec["source_files"],"Complete pre-admitted outer source graph")
        for row in spec["source_files"]:
            exact(row,["path","bytes","sha256"]);read(row["path"],{k:row[k] for k in ("bytes","sha256")},L,"outer operative source",retain=False)
        need(spec["entrypoint"] in spec["source_files"],"Exact outer entrypoint must belong to admitted source graph")
        read(spec["interpreter"]["path"],{k:spec["interpreter"][k] for k in ("bytes","sha256")},L,"qualified outer interpreter",retain=False)
        request_body=read(spec["request"]["path"],{k:spec["request"][k] for k in ("bytes","sha256")},L,"selected original operation request")
        request=decode(request_body)
        if spec["operation"]=="operate":
            need(spec["stderr_bytes"]>=request["failure_evidence"]["terminal_bytes"]+16384,"Outer stderr independently covers complete programme failure fallback")
        need(spec["operation"] in ("prepare","operate"),"Only selected programme operation")
        expected_argv=[spec["interpreter"]["path"],"-I","-S","-B",spec["entrypoint"]["path"],spec["operation"],"--request",spec["request"]["path"],
                       "--request-bytes",str(spec["request"]["bytes"]),"--request-sha256",spec["request"]["sha256"]]
        need(spec["argv"]==expected_argv,"Exact admitted original entrypoint and request, no arbitrary command")
        active();cg.mkdir(mode=0o700);cg_owned=True;out.mkdir(mode=0o700);out_owned=True
        for name,value in [("memory.max",spec["memory_bytes"]),("memory.swap.max",0),("pids.max",spec["pids"]),("cpu.max",spec["cpu_max"]),("io.max",spec["io_max"])]:_text(cg/name,str(value))
        _text(cg/"cgroup.subtree_control","+cpu +memory +pids +io")
        controller=cg/"controller";jobs=cg/"jobs";controller.mkdir();jobs.mkdir()
        _text(jobs/"cgroup.subtree_control","+cpu +memory +pids +io")
        for label in ("stdout","stderr"):
            streams[label]=E.stream(out/(label+".txt"),spec[label+"_bytes"],L,"original outer "+label)
        def attach():
            os.setsid()
            _text(controller/"cgroup.procs",str(os.getpid()))
        # The independently pinned runtime profile must name cg/jobs. The caller
        # never rewrites a qualified request/profile to make a mismatched path fit.
        env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","PYTHONNOUSERSITE":"1","NEURAL047_OUTER_CGROUP":str(cg),"NEURAL047_JOBS_CGROUP":str(jobs)}
        need(type(spec["provider_environment_names"]) is list and len(set(spec["provider_environment_names"]))==len(spec["provider_environment_names"]),"Explicit credential names")
        for name in spec["provider_environment_names"]:
            need(type(name) is str and name in os.environ and name not in env,"Selected root-only provider credential environment")
            env[name]=os.environ[name]
        active();proc=subprocess.Popen(spec["argv"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,close_fds=True,preexec_fn=attach)
        observations["process_starts"]=1;observations["pid"]=proc.pid
        for label in ("stdout","stderr"):
            f=getattr(proc,label);os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,label)
        while sel.get_map() or proc.poll() is None:
            active();drain(.02)
            need(_kv(cg/"memory.events").get("oom_kill",0)==0,"Original outer OOM")
            need(_kv(cg/"pids.events").get("max",0)==0,"Original outer PID limit")
        code=proc.wait();root_waited=True;need(code==0,"Original controlled programme failed")
    except BaseException as error:errors.append({"type":type(error).__name__,"message":str(error)[:512]})
    finally:
        if cg_owned:
            try:_text(cg/"cgroup.kill","1")
            except BaseException as error:errors.append({"phase":"outer_subtree_kill","type":type(error).__name__})
        while time.monotonic()<cleanup_deadline and cg_owned:
            try:
                drain(.01)
                if proc is not None and proc.poll() is not None and not root_waited:code=proc.wait();root_waited=True
                if _kv(cg/"cgroup.events").get("populated")==0:
                    subtree_empty=True
                    if not sel.get_map():break
            except BaseException as error:errors.append({"phase":"outer_cleanup","type":type(error).__name__});break
        for label,r in streams.items():
            try:
                observations[label]=r.close(not any(k.data==label for k in sel.get_map().values()))
                need(not observations[label]["errors"],"Original outer stream persistence")
            except BaseException as error:
                observations[label]=r.summary();errors.append({"phase":"outer_"+label+"_persistence","type":type(error).__name__})
        sel.close()
        try:
            observations["subtree_cpu_us"]=_kv(cg/"cpu.stat")["usage_usec"]
            observations["memory_peak_bytes"]=int((cg/"memory.peak").read_text())
            observations["memory_events"]=_kv(cg/"memory.events")
            observations["pids_events"]=_kv(cg/"pids.events")
            observations["block_io"]=(cg/"io.stat").read_text()
        except BaseException as error:errors.append({"phase":"outer_counters","type":type(error).__name__})
        after=resource.getrusage(resource.RUSAGE_SELF)
        observations.update({"returncode":code,"root_waited":root_waited,"subtree_empty":subtree_empty,"errors":errors,"accounting":L.summary(compact=True),
            "outer_own_cpu_seconds":(after.ru_utime-before_cpu.ru_utime)+(after.ru_stime-before_cpu.ru_stime),
            "outer_process_ru_maxrss_observation":after.ru_maxrss,"elapsed_seconds":time.monotonic()-started,
            "status":"complete" if not errors and code==0 and root_waited and subtree_empty and all(observations.get(k,{}).get("EOF") for k in ("stdout","stderr")) else "failed_or_unresolved",
            "scientific_qualification":False,"outer_observer_completion":"Requires its own original external command result; not self-attested"})
        try:final_outer(observations,spec,time.monotonic(),cleanup_deadline)
        except BaseException as error:
            errors.append({"phase":"final_outer_resources","type":type(error).__name__,"message":str(error)[:256]});observations["status"]="failed_or_unresolved"
        if observations["status"]=="complete":
            try:
                need(time.monotonic()<cleanup_deadline,"Original closure interval before result recapture")
                result=decode(read(out/"stdout.txt",{"bytes":observations["stdout"]["retained_bytes"],"sha256":observations["stdout"]["sha256"]},L,"original terminal result recapture"))
                need(result["status"]==("complete" if spec["operation"]=="operate" else "prepared"),"Original programme reported complete result")
                observations["original_result_pin"]=pin(canonical(result))
            except BaseException as error:
                errors.append({"phase":"original_result_join","type":type(error).__name__});observations["status"]="failed_or_unresolved"
            observations["accounting"]=L.summary(compact=True)
        after=resource.getrusage(resource.RUSAGE_SELF)
        observations["outer_own_cpu_seconds"]=(after.ru_utime-before_cpu.ru_utime)+(after.ru_stime-before_cpu.ru_stime)
        try:final_outer(observations,spec,time.monotonic(),cleanup_deadline)
        except BaseException as error:
            errors.append({"phase":"post_result_final_resources","type":type(error).__name__,"message":str(error)[:256]});observations["status"]="failed_or_unresolved"
        observations["evidence_reservation"]=E.summary()
        E.terminal_or_fallback(out/"OBSERVATION.json" if out_owned else None,observations,
                               RuntimeError("Original outer lifetime failed") if errors else None)
        # Publication itself consumes the original observer's CPU and interval.
        # The immutable file is a pre-publication snapshot; the external original
        # command result must join this last observed acceptance as well.
        after=resource.getrusage(resource.RUSAGE_SELF)
        observations["outer_own_cpu_seconds"]=(after.ru_utime-before_cpu.ru_utime)+(after.ru_stime-before_cpu.ru_stime)
        observations["accounting"]=L.summary(compact=True)
        try:final_outer(observations,spec,time.monotonic(),cleanup_deadline)
        except BaseException as error:
            errors.append({"phase":"post_publication_final_resources","type":type(error).__name__,"message":str(error)[:256]});observations["status"]="failed_or_unresolved"
    return observations

