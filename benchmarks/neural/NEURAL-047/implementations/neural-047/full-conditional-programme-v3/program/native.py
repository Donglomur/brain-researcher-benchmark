"""Concrete Linux namespace/cgroup runner, never qualified by source checks."""
import os,stat,subprocess,selectors,time,hashlib,json,ctypes
from pathlib import Path
from .common import need,exact,absolute,read,canonical,pin,decode,observed_write
from .final_policy import final_native
class NativeFailure(RuntimeError):
    def __init__(self,message,receipt):
        super().__init__(message);self.receipt=receipt
def _text(path,body):
    with open(path,"w") as f:f.write(body)
def _kv(path):
    result={}
    for line in Path(path).read_text().splitlines():
        k,v=line.split();result[k]=int(v)
    return result
def private_mount_namespace():
    """Run once in the qualified dedicated outer process, never the shared host."""
    libc=ctypes.CDLL(None,use_errno=True)
    need(libc.unshare(0x00020000)==0,"Dedicated outer mount namespace required")
    need(libc.mount(None,b"/",None,ctypes.c_ulong(16384|262144),None)==0,"Make mount propagation recursively private")
def tmpfs(path,size):
    libc=ctypes.CDLL(None,use_errno=True)
    need(libc.mount(b"neural047",os.fsencode(path),b"tmpfs",ctypes.c_ulong(2|4|8),
                    ("size="+str(size)+",nr_inodes=4096,mode=0700").encode())==0,"Bounded private output filesystem")
def unmount(path):
    libc=ctypes.CDLL(None,use_errno=True);need(libc.umount2(os.fsencode(path),0)==0,"Owned output unmount")
def output_bytes(path,cap,ledger):
    data=b"";opened=False
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);opened=True
        with os.fdopen(fd,"rb") as f:
            before=os.fstat(f.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,"Closed bounded ordinary output")
            ledger.charge("read_bytes",before.st_size+1,"original producer output")
            data=f.read(before.st_size+1);ledger.observe("read_bytes",len(data),"original producer output")
            after=os.fstat(f.fileno());ledger.live()
            need(len(data)==before.st_size and all(getattr(before,k)==getattr(after,k) for k in ("st_dev","st_ino","st_size","st_nlink","st_mtime_ns","st_ctime_ns")),"Complete stable output")
            return data
    except BaseException as error:
        observation={"path":str(path),"opened":opened,"seen_bytes":len(data),"seen_sha256":hashlib.sha256(data).hexdigest(),"failure_type":type(error).__name__}
        ledger.record_read_failure(observation);error.original_capture_observation=observation;raise
class LinuxExecutor:
    """Caller owns immutable mounts, trusted profile and private capture root."""
    def __init__(self,profile,ledger,evidence):
        exact(profile,["schema","bwrap","runtime_root","cgroup_parent","kernel_identity","qualification_pin","limits","bridge"])
        need(profile["schema"]=="neural047-linux-runtime-v1" and os.uname().sysname=="Linux","Qualified Linux required")
        self.p=profile;self.ledger=ledger;self.evidence=evidence
        self.cgroot=absolute(profile["cgroup_parent"]);self.runtime=absolute(profile["runtime_root"])
        need(self.cgroot.is_dir() and self.runtime.is_dir(),"Selected native runtime/cgroup roots")
        self.bwrap=absolute(profile["bwrap"]["path"])
        read(self.bwrap,{k:profile["bwrap"][k] for k in ("bytes","sha256")},ledger,"qualified namespace executable",retain=False)
        need(Path("/proc/sys/kernel/osrelease").read_text().strip()==profile["kernel_identity"],"Exact qualified kernel")
        exact(profile["limits"],["memory_bytes","pids","cpu_us","cpu_max","threads","stdout_bytes","stderr_bytes","output_bytes","job_wall_seconds","cleanup_seconds","io_max"])
        for k,v in profile["limits"].items():
            if k not in ("io_max","cpu_max"):need(type(v) is int and v>0,"Positive native limits")
        need(type(profile["limits"]["io_max"]) is str and profile["limits"]["io_max"],"Qualified block I/O mapping required")
    def execute(self,job,source,input_dir,output_dir,log_dir,argv,provider=None):
        L=self.ledger;limits=self.p["limits"];L.live()
        source,input_dir,output_dir,log_dir=map(absolute,(source,input_dir,output_dir,log_dir))
        need(self.runtime!=Path("/") and not any(p.is_relative_to(self.runtime) for p in (source,input_dir,output_dir,log_dir)),"Dedicated runtime image cannot contain task/operator directories")
        need(all(p.is_dir() for p in (source,input_dir,output_dir,log_dir)),"Owned pre-staged directories")
        need(not any(output_dir.iterdir()),"Fresh empty output")
        need(type(argv) is list and argv and all(type(s) is str and "\0" not in s for s in argv),"Exact selected command")
        cg=self.cgroot/job["job_id"];need(not cg.exists(),"No adoption of prior process group")
        cg.mkdir(mode=0o700)
        receipt={"schema":"neural047-native-attempt-v1","job":job,"argv":argv,"starts":0,"stdout":None,"stderr":None,"returncode":None,"root_waited":False,"subtree_empty":False,"status":"started","cpu_us":0,"memory_peak":0,"errors":[],"provider":[]}
        streams={};proc=None;sel=selectors.DefaultSelector();pending=bytearray();busy=False;mounted=False;outputs={}
        started=time.monotonic();deadline=min(L.work_deadline,started+limits["job_wall_seconds"])
        cleanup_deadline=min(L.deadline,deadline+limits["cleanup_seconds"])
        def clock():
            L.live();need(time.monotonic()<deadline,"Original job deadline")
        def monitor():
            clock()
            cpu=_kv(cg/"cpu.stat")["usage_usec"];receipt["cpu_us"]=cpu
            receipt["last_polled_cpu_us"]=cpu
            need(cpu<=limits["cpu_us"],"Cumulative subtree CPU exhausted")
            receipt["memory_peak"]=int((cg/"memory.peak").read_text())
            need(receipt["memory_peak"]<=limits["memory_bytes"],"Subtree memory exhausted")
            need(_kv(cg/"memory.events").get("oom_kill",0)==0,"Subtree OOM")
            need(_kv(cg/"pids.events").get("max",0)==0,"Subtree PID budget exhausted")
        def capture(stream,label,data):
            streams[label].append(data)
            if label=="stdout" and provider is not None:
                pending.extend(data);need(len(pending)<=1048576,"I protocol frame cap")
        def drain(timeout):
            for key,_ in sel.select(timeout):
                data=os.read(key.fd,65536)
                if not data:sel.unregister(key.fileobj);continue
                capture(key.fileobj,key.data,data)
        def service():
            nonlocal busy
            while b"\n" in pending:
                line,_,rest=pending.partition(b"\n");pending[:]=rest
                msg=decode(line);exact(msg,["type","request_id","payload"])
                need(msg["type"]=="provider" and not busy,"One ordered provider request")
                busy=True
                def tick():
                    monitor();drain(0)
                    need(b"\n" not in pending,"No overlapping provider request")
                try:
                    response,original=provider.request(msg,tick,deadline)
                finally:
                    receipt["provider"]=provider.snapshot()
                    busy=False
                body=canonical({"type":"provider_response","request_id":msg["request_id"],"payload":response})
                L.charge("write_bytes",len(body),"provider-to-worker transport")
                sent=0
                while sent<len(body):
                    monitor();drain(0)
                    try:
                        n=observed_write(lambda data:os.write(proc.stdin.fileno(),data),body[sent:],L,"provider-to-worker transport")
                        sent+=n;need(n>0,"Original provider response write progress")
                    except BlockingIOError as error:
                        # The helper already credited any reported partial write.
                        # Advance before retry so accepted bytes are never resent.
                        sent+=getattr(error,"characters_written",0);time.sleep(.005)
        try:
            for name,value in [("memory.max",limits["memory_bytes"]),("memory.swap.max",0),("pids.max",limits["pids"]),("cpu.max",limits["cpu_max"]),("io.max",limits["io_max"])]:_text(cg/name,str(value))
            need(int((cg/"memory.max").read_text())==limits["memory_bytes"] and int((cg/"pids.max").read_text())==limits["pids"],"Native controls effective")
            clock();tmpfs(output_dir,limits["output_bytes"]);mounted=True
            if provider:provider.bind_cgroup(cg)
            command=[str(self.bwrap),"--die-with-parent","--new-session","--unshare-all",
                     "--ro-bind",str(self.runtime),"/","--ro-bind",str(source),"/method",
                     "--ro-bind",str(input_dir),"/input","--bind",str(output_dir),"/output",
                     "--tmpfs","/tmp","--dir","/work","--proc","/proc","--dev","/dev","--chdir","/work",*argv]
            for label in ("stdout","stderr"):
                streams[label]=self.evidence.stream(log_dir/(label+".txt"),limits[label+"_bytes"],L,"private original "+label)
            def attach():
                os.setsid()
                _text(cg/"cgroup.procs",str(os.getpid()))
            env={"PATH":"/usr/bin:/bin","HOME":"/tmp","LANG":"C.UTF-8","PYTHONNOUSERSITE":"1","OMP_NUM_THREADS":str(limits["threads"]),"OPENBLAS_NUM_THREADS":str(limits["threads"]),"MKL_NUM_THREADS":str(limits["threads"])}
            clock();proc=subprocess.Popen(command,stdin=subprocess.PIPE if provider else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,close_fds=True,preexec_fn=attach)
            receipt["starts"]=1;receipt["pid"]=proc.pid
            for label in ("stdout","stderr"):
                stream=getattr(proc,label);os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,label)
            if provider:os.set_blocking(proc.stdin.fileno(),False)
            while sel.get_map() or proc.poll() is None:
                monitor();drain(.02)
                if provider:service()
            receipt["returncode"]=proc.wait();receipt["root_waited"]=True
            need(not pending,"Incomplete I protocol frame")
            need(receipt["returncode"]==0,"Original producer failed")
            receipt["status"]="producer_closed"
        except BaseException as error:
            receipt["errors"].append({"type":type(error).__name__,"message":str(error)[:512]});receipt["status"]="failed"
        finally:
            if provider is not None:receipt["provider"]=provider.snapshot()
            # A waited root does not imply descendants are gone. Always kill the owned subtree.
            try:_text(cg/"cgroup.kill","1")
            except BaseException as error:receipt["errors"].append({"phase":"subtree_kill","type":type(error).__name__})
            while time.monotonic()<cleanup_deadline:
                try:
                    drain(.01)
                    if proc is not None and proc.poll() is not None and not receipt["root_waited"]:
                        receipt["returncode"]=proc.wait();receipt["root_waited"]=True
                    if _kv(cg/"cgroup.events").get("populated")==0:
                        receipt["subtree_empty"]=True
                        if not sel.get_map():break
                except BaseException as error:
                    receipt["errors"].append({"phase":"cleanup","type":type(error).__name__});break
            for label,record in streams.items():
                try:
                    receipt[label]=record.close(not any(k.data==label for k in sel.get_map().values()))
                    need(not receipt[label]["errors"],"Original stream persistence incomplete")
                except BaseException as error:
                    receipt[label]=record.summary();receipt["errors"].append({"phase":label+"_persistence","type":type(error).__name__})
            sel.close()
            receipt["final_counters_complete"]=False
            receipt["cpu_us"]=None;receipt["memory_peak"]=None
            try:
                receipt["cpu_us"]=_kv(cg/"cpu.stat")["usage_usec"]
                receipt["memory_peak"]=int((cg/"memory.peak").read_text())
                receipt["memory_events"]=_kv(cg/"memory.events")
                receipt["pids_events"]=_kv(cg/"pids.events")
                receipt["io_stat"]=(cg/"io.stat").read_text()
                receipt["final_counters_complete"]=True
                final_native(receipt,limits,time.monotonic(),cleanup_deadline)
            except BaseException as error:receipt["errors"].append({"phase":"final_counters","type":type(error).__name__})
            receipt["elapsed_seconds"]=time.monotonic()-started
            receipt["subtree_and_streams_closed"]=receipt["subtree_empty"] and receipt["root_waited"] and all(receipt[k] and receipt[k]["EOF"] for k in ("stdout","stderr"))
            if mounted:
                try:
                    need(receipt["subtree_and_streams_closed"] and not receipt["errors"],"No output adoption after failed producer/capture")
                    need(time.monotonic()<cleanup_deadline,"Original cleanup interval before output capture")
                    expected={"prediction.json","reference.json"} if job["mode"].startswith("R") else ({"fields.json"} if job["mode"]=="PREP" else {"prediction.json"})
                    need({p.name for p in output_dir.iterdir()}==expected,"Exact final output names")
                    for name in sorted(expected):
                        need(time.monotonic()<cleanup_deadline,"Original output capture cutoff")
                        outputs[name]=output_bytes(output_dir/name,limits["output_bytes"],L)
                    receipt["outputs"]={k:pin(v) for k,v in outputs.items()}
                except BaseException as error:receipt["errors"].append({"phase":"output_capture","type":type(error).__name__,"message":str(error)[:256],"known":getattr(error,"original_capture_observation",None)})
                try:
                    need(time.monotonic()<cleanup_deadline,"Original cleanup cutoff before unmount")
                    unmount(output_dir);receipt["output_mount_removed"]=True
                except BaseException as error:receipt["errors"].append({"phase":"output_unmount","type":type(error).__name__})
        try:final_native(receipt,limits,time.monotonic(),cleanup_deadline)
        except BaseException as error:receipt["errors"].append({"phase":"final_acceptance","type":type(error).__name__,"message":str(error)[:256]})
        if receipt["errors"] or receipt["status"]!="producer_closed" or not receipt["subtree_and_streams_closed"]:
            raise NativeFailure("Original producer or cleanup failed",receipt)
        receipt["status"]="closed";return outputs,receipt

