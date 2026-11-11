"""Source-pinned trusted Python controller process; never runs participant source."""
import os,signal,time,resource
from .io import need
class TrustedDriverBackend:
    engineering=False
    def __init__(self,argv,cwd,environment,owned_cgroup=None):self.argv=argv;self.cwd=cwd;self.environment=environment;self.owned_cgroup=owned_cgroup;self.before=None;self.cgroup_before=None
    def prepare(self,job):
        need(job.get("trusted_controller")is True,"trusted_driver_only")
        if self.owned_cgroup is not None:
            from pathlib import Path
            cg=Path(self.owned_cgroup);events=dict(x.split() for x in (cg/'cgroup.events').read_text().splitlines());need(events.get('populated')=='0','exclusive_empty_campaign_cgroup');values=dict(x.split() for x in (cg/'cpu.stat').read_text().splitlines());self.cgroup_before=int(values['usage_usec'])/1e6
        self.before=resource.getrusage(resource.RUSAGE_CHILDREN);return list(self.argv),self.cwd,dict(self.environment)
    def usage(self):return None
    def cleanup(self,proc,deadline):
        if proc is not None:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            if proc.poll()is None:proc.wait(timeout=max(.001,deadline-time.monotonic()))
        alive=False
        while proc is not None:
            try:os.killpg(proc.pid,0);alive=True
            except ProcessLookupError:alive=False;break
            if time.monotonic()>=deadline:break
            time.sleep(.005)
        # An independently delegated campaign parent can contain OCI descendants,
        # including daemon-created processes outside the Python process group.
        populated=False
        if self.owned_cgroup is not None:
            from pathlib import Path
            cg=Path(self.owned_cgroup)
            if cg.exists():
                vals=dict(x.split() for x in (cg/"cgroup.events").read_text().splitlines());populated=vals.get("populated")!="0"
                if populated:(cg/"cgroup.kill").write_text("1")
                while populated and time.monotonic()<deadline:
                    vals=dict(x.split() for x in (cg/"cgroup.events").read_text().splitlines());populated=vals.get("populated")!="0"
                    if populated:time.sleep(.005)
        a=resource.getrusage(resource.RUSAGE_CHILDREN);b=self.before;cpu=0. if b is None else max(0.,a.ru_utime+a.ru_stime-b.ru_utime-b.ru_stime)
        container_cpu=0.;measured=True
        if self.owned_cgroup is not None:
            try:
                values=dict(x.split() for x in (cg/'cpu.stat').read_text().splitlines());container_cpu=int(values['usage_usec'])/1e6-self.cgroup_before;need(container_cpu>=0,'monotone_campaign_CPU')
            except BaseException:container_cpu=0.;measured=False
        cpu+=container_cpu
        return {"mount_scope":"trusted driver introduces no mounts; each OCI worker requires its independent rm and cgroup receipt","all_descendants_dead":not alive and not populated,"mounts_removed":not populated,"resources":{"cpu_seconds":cpu,"memory_peak_bytes":a.ru_maxrss*1024,"measurement_complete":b is not None and measured,"measurement_scope":"serial trusted controller RUSAGE_CHILDREN delta plus persistent campaign cgroup CPU; deliberately conservative overlap; independent child costs retained"}}
