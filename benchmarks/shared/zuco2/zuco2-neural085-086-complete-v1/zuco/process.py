"""Actual process custody, bounded pipes, final resource admission and failure preservation."""
import copy,os,selectors,signal,subprocess,time,resource
from pathlib import Path
from .io import *
class LocalEngineeringBackend:
    """Only deliberately invented children. Never qualifies physical isolation."""
    engineering=True
    def __init__(self,argv,cwd):self.argv=list(argv);self.cwd=str(cwd);self.before=None
    def prepare(self,job):
        need(job["engineering"]is True,"engineering_backend_denied");self.before=resource.getrusage(resource.RUSAGE_CHILDREN)
        return self.argv,self.cwd,{"PATH":os.environ.get("PATH",""),"PYTHONDONTWRITEBYTECODE":"1","LANG":"C.UTF-8"}
    def usage(self):return None
    def cleanup(self,proc,deadline):
        killed=False
        if proc is not None:
            try:os.killpg(proc.pid,signal.SIGKILL);killed=True
            except ProcessLookupError:pass
            if proc.poll()is None:proc.wait(timeout=max(.001,deadline-time.monotonic()))
        after=resource.getrusage(resource.RUSAGE_CHILDREN);a=self.before
        return {"all_descendants_dead":False,"mounts_removed":True,"engineering_group_cleanup_attempted":True,"cleanup_signal_sent":killed,"resources":{"cpu_seconds":0. if a is None else max(0.,after.ru_utime+after.ru_stime-a.ru_utime-a.ru_stime),"memory_peak_bytes":None,"measurement_complete":a is not None,"measurement_scope":"serial invented child RUSAGE_CHILDREN delta; descendant containment unqualified"}}
class Process:
    def __init__(self,job,ledger,backend):self.job=copy.deepcopy(job);self.ledger=ledger;self.backend=backend;self.proc=None;self.error=None;self.out={"stdout":bytearray(),"stderr":bytearray()};self.counts={"stdout":0,"stderr":0};self.eof=set();self.intent=b"";self.written=0;self.output_rows=[];self.observed_exit=None;self.final_wait=None;self.forced=False;self.request_pin=None;self.launch=None;self.closed=False;self.receipt=None
    def run(self,request,stdin=b""):
        self.start=time.monotonic();self.parent_start=resource.getrusage(resource.RUSAGE_SELF);self.intent=stdin;sel=selectors.DefaultSelector();reserved=False;directory=None;cleanup={"all_descendants_dead":True,"mounts_removed":True,"resources":{"cpu_seconds":0.,"memory_peak_bytes":0,"measurement_complete":True,"not_spawned":True}}
        try:
            self.ledger.guard();self.ledger.reserve_job(self.job["id"],self.job["limits"]);reserved=True
            directory=path_guard(self.job["directory"]);need(not directory.exists(),"fresh_process_directory");self.ledger.guard();directory.mkdir(parents=True);(directory/"output").mkdir()
            need(len(encode(request))<=self.job["limits"]["receipt_bytes"],"request_extent");self.request_pin=write(directory/"request.json",request);need(len(stdin)<=self.job["limits"]["stream_bytes"],"stdin_cap");write(directory/"stdin-intended.bin",stdin)
            argv,cwd,env=self.backend.prepare({**self.job,"request_path":str(directory/"request.json"),"output_path":str(directory/"output")});self.ledger.guard()
            self.launch={"argv":list(argv),"cwd":str(cwd),"env":dict(env)}
            self.proc=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            for name in ("stdout","stderr"):
                f=getattr(self.proc,name);os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,name)
            os.set_blocking(self.proc.stdin.fileno(),False)
            if not stdin:self.proc.stdin.close()
            deadline=min(self.ledger.spec["deadline_monotonic"],self.start+self.job["limits"]["wall_seconds"])
            while len(self.eof)<2 or self.proc.poll()is None or self.written<len(stdin):
                self.ledger.guard(closing=True);need(time.monotonic()<deadline,"process_deadline")
                cpu=self.backend.usage();need(cpu is None or cpu<=self.job["limits"]["cpu_seconds"],"process_cpu")
                if self.written<len(stdin):
                    try:
                        n=os.write(self.proc.stdin.fileno(),stdin[self.written:]);need(n>0,"zero_stdin_write");self.written+=n
                        if self.written==len(stdin):self.proc.stdin.close()
                    except BlockingIOError:pass
                # Every live output remains ordinary and bounded. Final inventory is independently re-read after cleanup.
                extent(directory/"output",self.job["limits"]["files"],self.job["limits"]["output_bytes"],lambda:self.ledger.guard(closing=True))
                for key,_ in sel.select(min(.02,max(0,deadline-time.monotonic()))):
                    chunk=os.read(key.fileobj.fileno(),65536);name=key.data
                    if not chunk:self.eof.add(name);sel.unregister(key.fileobj);continue
                    self.counts[name]+=len(chunk);cap=self.job["limits"]["stream_bytes"];room=max(0,cap-len(self.out[name]));self.out[name].extend(chunk[:room]);need(len(chunk)<=room,"process_stream_cap",name)
                if self.proc.poll()is not None:self.observed_exit=self.proc.returncode
            self.observed_exit=self.proc.poll();self.final_wait=self.proc.wait(timeout=max(.001,deadline-time.monotonic()));need(self.final_wait==0,"process_exit",self.final_wait)
        except BaseException as e:self.error=e
        finally:
            if self.proc is not None and self.proc.poll()is None:
                self.forced=True
                try:os.killpg(self.proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            cleanup_start=time.monotonic();emergency_deadline=cleanup_start+self.job["limits"]["cleanup_seconds"]
            try:
                cleanup=self.backend.cleanup(self.proc,emergency_deadline)
                if self.proc is not None:self.final_wait=self.proc.wait(timeout=max(.001,emergency_deadline-time.monotonic()))
            except BaseException as e:
                self.error=self.error or e;cleanup={"all_descendants_dead":False,"mounts_removed":False,"failure":failure(e),"resources":{"cpu_seconds":None,"memory_peak_bytes":None,"measurement_complete":False}}
            # Collect still-available original pipe prefixes; no fabricated EOF or replay.
            until=min(emergency_deadline,time.monotonic()+.1)
            while self.proc is not None and len(self.eof)<2 and time.monotonic()<until:
                for key,_ in sel.select(max(0,min(.01,until-time.monotonic()))):
                    try:chunk=os.read(key.fileobj.fileno(),65536)
                    except (OSError,ValueError):continue
                    name=key.data
                    if not chunk:self.eof.add(name);sel.unregister(key.fileobj);continue
                    self.counts[name]+=len(chunk);cap=self.job["limits"]["stream_bytes"];self.out[name].extend(chunk[:max(0,cap-len(self.out[name]))])
            sel.close()
            if self.proc is not None:
                for name in ("stdin","stdout","stderr"):
                    f=getattr(self.proc,name)
                    if f is not None and not f.closed:f.close()
        capture_failures=[];streams={};end=time.monotonic()
        if directory is not None and directory.exists():
            for name,raw in [("stdout",bytes(self.out["stdout"])),("stderr",bytes(self.out["stderr"])),("stdin-written",self.intent[:self.written])]:
                try:streams[name]=write(directory/(name+".bin"),raw)
                except BaseException as e:capture_failures.append(failure(e));self.error=self.error or e
            try:self.output_rows=inventory(directory/"output",self.job["limits"]["files"],self.job["limits"]["output_bytes"])
            except BaseException as e:capture_failures.append(failure(e));self.error=self.error or e
        resources=dict(cleanup["resources"]);parent=resource.getrusage(resource.RUSAGE_SELF);resources["controller_cpu_seconds"]=max(0.,parent.ru_utime+parent.ru_stime-self.parent_start.ru_utime-self.parent_start.ru_stime);resources["wall_seconds"]=time.monotonic()-self.start
        if finite(resources.get("cpu_seconds")):resources["cpu_seconds"]+=resources["controller_cpu_seconds"]+self.job["limits"]["completion_cpu_reserve"];resources["completion_cpu_reserve"]=self.job["limits"]["completion_cpu_reserve"];resources["cpu_measurement_semantics"]="measured through collection plus prepaid bounded finalization CPU"
        if reserved:
            err=self.ledger.settle(self.job["id"],resources)
            if err:self.error=self.error or Refusal("final_resource_admission",err)
        try:
            self.ledger.guard(closing=True);need(time.monotonic()<self.start+self.job["limits"]["wall_seconds"],"final_process_wall")
            need(len(self.eof)==2 and self.written==len(self.intent),"incomplete_stream_delivery")
            need(all(self.counts[n]<=self.job["limits"]["stream_bytes"] for n in self.counts),"final_stream_cap")
            if not self.backend.engineering:need(cleanup["all_descendants_dead"] and cleanup["mounts_removed"] and not cleanup.get("cleanup_failures") and not cleanup.get("forced_descendant_cleanup",False),"cleanup_incomplete")
        except BaseException as e:self.error=self.error or e
        self.receipt={"job_id":self.job["id"],"identity":self.job["identity"],"source_pin":self.job["source_pin"],"request_pin":self.request_pin,"actual_launch":self.launch,"pid":None if self.proc is None else self.proc.pid,"original_observed_exit":self.observed_exit,"original_final_wait":self.final_wait,"forced_cleanup":self.forced,"started":self.start,"ended_after_collection":time.monotonic(),"resources":resources,"cleanup":cleanup,"streams":streams,"stream_actual_bytes":self.counts,"stream_truncated":{n:self.counts[n]>len(self.out[n]) for n in self.counts},"stdin_intended_bytes":len(self.intent),"stdin_written_bytes":self.written,"stdin_delivery_complete":self.written==len(self.intent),"streams_complete":len(self.eof)==2 and all(self.counts[n]==len(self.out[n]) for n in self.counts) and self.written==len(self.intent),"outputs":self.output_rows,"capture_failures":capture_failures,"failure":failure(self.error) if self.error else None,"engineering_only":self.backend.engineering,"outer_driver_completion":"must be supplied by independent parent after this function/process returns"}
        finalization_started=time.process_time();self.closed=True
        if directory is not None and directory.exists():
            try:
                need(len(encode(self.receipt))<=self.job["limits"]["receipt_bytes"],"completion_receipt_extent");write(directory/"COMPLETION.json",self.receipt)
            except BaseException as e:self.receipt["capture_failures"].append(failure(e));self.receipt["failure"]=self.receipt["failure"] or failure(e)
        try:
            need(time.process_time()-finalization_started<=self.job["limits"]["completion_cpu_reserve"],"completion_cpu_reserve_exceeded");self.ledger.guard(closing=True)
        except BaseException as e:self.receipt["failure"]=self.receipt["failure"] or failure(e);self.ledger.unknown=True
        return self.receipt
    def require_success(self):
        need(self.closed and self.receipt["failure"]is None and self.receipt["original_final_wait"]==0 and self.receipt["streams_complete"],"process_not_successful",self.receipt);self.ledger.guard(closing=True);return self.receipt
