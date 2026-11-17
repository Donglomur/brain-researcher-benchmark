"""Prospective pinned Linux OCI launcher with a persistent delegated parent cgroup.
No daemon/service changes, installations or execution occur at import. The full
backend must be independently qualified on its selected Linux host before use.
"""
import os,subprocess,time,signal
from pathlib import Path
from .io import *
class OCIBackend:
    engineering=False
    def __init__(self,profile,ledger,source,state=None,training=None):self.profile=profile;self.ledger=ledger;self.source=source;self.state=state;self.training=training;self.cg=None;self.name=None;self.started=False;self.commands=[];self.limit=None
    def command(self,argv,cap=65536,emergency_deadline=None):
        from .commands import bounded
        if emergency_deadline is None:
            self.ledger.guard(closing=True);deadline=min(time.monotonic()+self.profile["command_seconds"],self.ledger.spec["deadline_monotonic"])
        else:deadline=min(emergency_deadline,time.monotonic()+self.profile["command_seconds"])
        record,body=bounded(argv,deadline,cap,self.profile["cleanup_seconds"]);self.commands.append(record)
        need(record["failure"]is None and record["original_observed_exit"]==0 and record["original_final_wait"]==0 and not record["forced_cleanup"] and record["streams_complete"],"OCI_command_failure",record);return body
    def prepare(self,job):
        import sys
        self.limit=job["limits"];self.ledger.guard()
        need(sys.platform=="linux","qualified_Linux_required");p=self.profile
        read(p["executable"]["path"],32*1024**2,p["executable"],self.ledger.guard);need(p["image"].startswith("sha256:") and len(p["image"])==71,"immutable_OCI_image")
        root=path_guard(p["delegated_cgroup_root"],True);need((root/"cgroup.controllers").exists(),"cgroup_v2_required")
        self.name="zuco-"+digest(job["id"])[:24];self.cg=below(root,self.name);need(not self.cg.exists(),"fresh_cgroup");self.ledger.guard();self.cg.mkdir()
        # The persistent parent retains aggregate CPU/memory measurements after the OCI child exits.
        for name,value in [("memory.max",str(job["limits"]["memory_bytes"])),("pids.max",str(job["limits"]["pids"]))]:
            self.ledger.guard();(self.cg/name).write_text(value)
        args=[p["executable"]["path"],"run","--name",self.name,"--network","none","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges","--pids-limit",str(job["limits"]["pids"]),"--memory",str(job["limits"]["memory_bytes"]),"--cpus",str(job["limits"]["cores"]),"--cgroup-parent",str(self.cg),"--user",p["user"],"--tmpfs","/tmp:rw,nosuid,nodev,size="+str(job["limits"]["scratch_bytes"]),"--workdir","/output","--env","PYTHONDONTWRITEBYTECODE=1","--env","HOME=/tmp","--env","LANG=C.UTF-8"]
        mounts=[(self.source,"/candidate","ro"),(job["request_path"],"/request.json","ro"),(job["output_path"],"/output","rw"),(job["view_root"],"/view","ro")]
        if self.state:mounts.append((self.state,"/state","ro"))
        if self.training:mounts.append((self.training,"/training","ro"))
        for host,guest,mode in mounts:path_guard(host,True);args.extend(["--volume",str(Path(host).absolute())+":"+guest+":"+mode])
        args.extend([p["image"],p["python_inside"],"/candidate/"+job["entry"],"--request","/request.json","--output","/output"]);self.started=True
        return args,str(Path(job["directory"]).absolute()),{"PATH":p["trusted_PATH"],"LANG":"C.UTF-8","HOME":p["runtime_HOME"]}
    def usage(self):
        if self.cg is None:return None
        values=dict(x.split() for x in (self.cg/"cpu.stat").read_text().splitlines());return int(values["usage_usec"])/1e6
    def cleanup(self,proc,deadline):
        errors=[];inner=None;forced=False
        if self.cg is None:return {"all_descendants_dead":proc is None,"mounts_removed":proc is None,"inner_completion":None,"resources":{"cpu_seconds":0.,"memory_peak_bytes":0,"measurement_complete":proc is None}}
        populated=True
        def populated_now():
            values=dict(x.split() for x in (self.cg/"cgroup.events").read_text().splitlines());return values.get("populated")!="0"
        # Container descendants can remain after the CLI exits. Always examine the
        # retained parent, and capture the actual container completion before rm.
        populated=populated_now()
        if populated:
            forced=True
            try:(self.cg/"cgroup.kill").write_text("1")
            except BaseException as e:errors.append(failure(e))
        while populated and time.monotonic()<deadline:
            populated=populated_now()
            if populated:time.sleep(min(.01,max(0,deadline-time.monotonic())))
        try:
            body=self.command([self.profile["executable"]["path"],"inspect","--format","{{json .State}}",self.name],emergency_deadline=deadline);inner=decode(body)
            need(inner["Running"]is False and inner["ExitCode"]==0 and inner["OOMKilled"]is False and inner.get("Error","")=="" and inner.get("FinishedAt"),"original_container_failure",inner)
        except BaseException as e:errors.append(failure(e))
        values=dict(x.split() for x in (self.cg/"cpu.stat").read_text().splitlines());events=dict(x.split() for x in (self.cg/"memory.events").read_text().splitlines());peak=int((self.cg/"memory.peak").read_text())
        resources={"cpu_seconds":int(values["usage_usec"])/1e6,"memory_peak_bytes":peak,"measurement_complete":not populated,"memory_events":events,"cgroup_events":(self.cg/"cgroup.events").read_text()}
        if peak>self.limit["memory_bytes"] or int(events.get("oom_kill","0"))>0:errors.append(failure(Refusal("container_memory_failure")))
        removed=False
        try:self.command([self.profile["executable"]["path"],"rm","--force",self.name],emergency_deadline=deadline);removed=True
        except BaseException as e:errors.append(failure(e))
        try:
            if not populated:self.cg.rmdir()
        except BaseException as e:errors.append(failure(e))
        return {"all_descendants_dead":not populated,"mounts_removed":removed,"inner_completion":inner,"forced_descendant_cleanup":forced,"resources":resources,"commands":self.commands,"cleanup_failures":errors}
